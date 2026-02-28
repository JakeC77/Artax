"""Azure Service Bus message handler for workflow events."""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta
import urllib.parse

try:
    from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
    from azure.servicebus import ServiceBusReceivedMessage
    from azure.servicebus.exceptions import MessageLockLostError
    SERVICE_BUS_AVAILABLE = True
except ImportError:
    SERVICE_BUS_AVAILABLE = False
    # Create mock types for type hints
    ServiceBusReceivedMessage = None
    ServiceBusClient = None
    ServiceBusReceiver = None
    MessageLockLostError = Exception

from app.models.workflow_event import WorkflowEvent
from app.core.workflow_router import WorkflowRouter
from app.config import Config

logger = logging.getLogger(__name__)


class ServiceBusHandler:
    """Handles Service Bus queue messages and routes to workflow router."""
    
    def __init__(
        self,
        connection_string: str,
        queue_name: str,
        workflow_router: WorkflowRouter,
        max_concurrent: int = 5,
    ):
        """Initialize Service Bus handler.
        
        Args:
            connection_string: Azure Service Bus connection string
            queue_name: Queue name to listen to
            workflow_router: Router for processing workflow events
            max_concurrent: Maximum concurrent message processing
        """
        if not SERVICE_BUS_AVAILABLE:
            raise ImportError(
                "azure-servicebus package not installed. "
                "Install with: pip install azure-servicebus"
            )
        
        self.connection_string = connection_string
        self.queue_name = queue_name
        self.workflow_router = workflow_router
        self.max_concurrent = max_concurrent
        self.client: Optional[ServiceBusClient] = None
        self.receiver: Optional[ServiceBusReceiver] = None
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    def _extract_namespace_from_connection_string(self) -> Optional[str]:
        """Extract Service Bus namespace from connection string for logging.
        
        Returns:
            Namespace name if found, None otherwise
        """
        if not self.connection_string:
            return None
        
        try:
            # Parse connection string format: Endpoint=sb://namespace.servicebus.windows.net/;...
            parts = self.connection_string.split(';')
            for part in parts:
                if part.startswith('Endpoint='):
                    endpoint = part.split('=', 1)[1]
                    # Remove sb:// prefix and trailing /
                    if endpoint.startswith('sb://'):
                        endpoint = endpoint[5:]
                    if endpoint.endswith('/'):
                        endpoint = endpoint[:-1]
                    # Extract namespace (everything before .servicebus.windows.net)
                    if '.servicebus.windows.net' in endpoint:
                        namespace = endpoint.split('.servicebus.windows.net')[0]
                        return namespace
                    return endpoint
        except Exception as e:
            logger.debug(f"Failed to extract namespace from connection string: {e}")
        
        return None
    
    async def start(self):
        """Start listening to Service Bus queue."""
        if self._running:
            logger.warning("Handler already running")
            return
        
        # Log connection details for troubleshooting
        logger.info("=" * 70)
        logger.info("SERVICE BUS CONNECTION DETAILS")
        logger.info("=" * 70)
        logger.info(f"Queue Name: {self.queue_name}")
        logger.info(f"Connection String Configured: {'Yes' if self.connection_string else 'No'}")
        
        namespace = self._extract_namespace_from_connection_string()
        if namespace:
            logger.info(f"Service Bus Namespace: {namespace}")
        else:
            logger.warning("Could not extract namespace from connection string")
        
        logger.info(f"Max Concurrent Messages: {self.max_concurrent}")
        logger.info(f"Max Lock Duration: {Config.SERVICE_BUS_MAX_LOCK_DURATION_SECONDS}s")
        logger.info(f"Lock Renewal Interval: {Config.SERVICE_BUS_LOCK_RENEWAL_INTERVAL_SECONDS}s")
        logger.info("=" * 70)
        
        logger.info(f"Connecting to Service Bus queue: {self.queue_name}")
        
        try:
            self.client = ServiceBusClient.from_connection_string(
                conn_str=self.connection_string
            )
            # Configure receiver with lock duration settings
            max_lock_duration = timedelta(seconds=Config.SERVICE_BUS_MAX_LOCK_DURATION_SECONDS)
            
            self.receiver = self.client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=5,  # Wait up to 5 seconds for messages
                max_lock_duration=max_lock_duration,
            )
            
            logger.info(
                f"Service Bus receiver configured with max_lock_duration={Config.SERVICE_BUS_MAX_LOCK_DURATION_SECONDS}s"
            )
            
            self._running = True
            
            logger.info("Service Bus handler started successfully")
        except Exception as e:
            logger.error(
                f"Failed to start Service Bus handler: {e}. "
                f"Queue: {self.queue_name}, Namespace: {namespace or 'unknown'}"
            )
            raise
    
    async def stop(self):
        """Stop listening and close connections."""
        if not self._running:
            return
        
        logger.info("Stopping Service Bus handler...")
        self._running = False
        
        if self.receiver:
            await self.receiver.close()
        
        if self.client:
            await self.client.close()
        
        logger.info("Service Bus handler stopped")
    
    async def _renew_message_lock_periodically(
        self,
        message: ServiceBusReceivedMessage,
        renewal_interval: int,
        stop_event: asyncio.Event
    ):
        """Renew message lock periodically to prevent expiration during long workflows.
        
        Args:
            message: Message to renew lock for
            renewal_interval: Seconds between renewals
            stop_event: Event to signal when to stop renewing
        """
        while not stop_event.is_set():
            try:
                # Wait for renewal interval or until stop event
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=renewal_interval
                    )
                    # Stop event was set, exit loop
                    break
                except asyncio.TimeoutError:
                    # Timeout means we should renew the lock
                    pass
                
                # Renew the lock
                try:
                    await self.receiver.renew_message_lock(message)
                    logger.debug(f"Renewed message lock for message {message.message_id}")
                except MessageLockLostError:
                    logger.warning(f"Message lock already lost for message {message.message_id}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to renew message lock: {e}")
                    # Continue trying - don't break on transient errors
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in lock renewal loop: {e}")
                # Continue trying
    
    async def process_message(self, message: ServiceBusReceivedMessage):
        """Process a single Service Bus message.
        
        Args:
            message: Received Service Bus message
            
        Note: Message is completed immediately after validation to prevent duplicate processing.
              Workflow execution runs as a background task to allow concurrent processing.
        """
        event = None
        
        # Use semaphore only for message validation/completion (quick operation)
        async with self._semaphore:
            try:
                # Deserialize message
                message_body = str(message)
                logger.debug(f"Received message: {message_body[:200]}...")
                
                try:
                    event = WorkflowEvent.from_json(message_body)
                except ValueError as e:
                    logger.error(f"Invalid event data: {e}. Message body: {message_body[:500]}")
                    # Abandon invalid message
                    try:
                        await self.receiver.abandon_message(message)
                    except MessageLockLostError:
                        logger.warning("Message lock lost while abandoning invalid message")
                    return
                
                # Validate run_id and workflow_id are present
                if not event.run_id:
                    logger.error(f"Event missing run_id. Event data: {event.to_dict()}")
                    try:
                        await self.receiver.abandon_message(message)
                    except MessageLockLostError:
                        logger.warning("Message lock lost while abandoning message without run_id")
                    return
                
                if not event.workflow_id:
                    logger.error(f"Event missing workflow_id. Event data: {event.to_dict()}")
                    try:
                        await self.receiver.abandon_message(message)
                    except MessageLockLostError:
                        logger.warning("Message lock lost while abandoning message without workflow_id")
                    return
                
                logger.info(
                    f"Processing event: run_id={event.run_id}, "
                    f"workflow_id={event.workflow_id}, scenario_id={event.scenario_id}"
                )
                
                # Complete message immediately to prevent duplicate processing
                # TODO: Make this more robust - if processing fails, we'll lose the message
                # For now, this prevents duplicate processing which is the main concern
                try:
                    await self.receiver.complete_message(message)
                    logger.debug(f"Message completed for run_id={event.run_id}")
                except MessageLockLostError:
                    logger.warning(f"Message lock lost for run_id={event.run_id}, message may have been redelivered")
                    # If lock is lost, don't process - message will be redelivered
                    return
                except Exception as complete_error:
                    logger.error(f"Failed to complete message for run_id={event.run_id}: {complete_error}")
                    # If we can't complete, don't process - message will be redelivered
                    return
                
                # Semaphore is released here - workflow execution runs as background task
                # This allows multiple workflows to run concurrently
                
            except Exception as e:
                logger.exception(f"Error processing message: {e}")
                return
        
        # Start workflow execution as background task (semaphore already released)
        # This allows the message handler to continue processing other messages
        if event is None:
            logger.error("Event is None, cannot start workflow")
            return
        
        async def run_workflow():
            """Run workflow in background task."""
            try:
                result = await self.workflow_router.route(event)
                
                # Handle result (message already completed, so just log)
                if result.success:
                    logger.info(
                        f"Workflow {result.workflow_id} succeeded for run_id={result.run_id} "
                        f"in {result.duration_seconds:.2f}s"
                    )
                else:
                    logger.error(
                        f"Workflow {result.workflow_id} failed for run_id={result.run_id}: {result.error}"
                    )
                    # Note: Message already completed, so it won't be retried
                    # TODO: Implement dead-letter queue or retry mechanism for failed workflows
            except Exception as e:
                logger.exception(f"Error executing workflow for run_id={event.run_id}: {e}")
        
        # Start workflow as background task (don't await - allows concurrent execution)
        asyncio.create_task(run_workflow())
    
    async def listen(self):
        """Main loop: continuously receive and process messages."""
        if not self._running:
            raise RuntimeError("Handler not started. Call start() first.")
        
        logger.info("Starting message listener loop...")
        
        try:
            while self._running:
                try:
                    # Receive messages (non-blocking with max_wait_time)
                    messages = await self.receiver.receive_messages(
                        max_message_count=10,  # Batch size
                        max_wait_time=5,
                    )
                    
                    if messages:
                        logger.debug(f"Received {len(messages)} message(s)")
                        
                        # Process messages concurrently
                        tasks = [
                            self.process_message(msg) for msg in messages
                        ]
                        await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Small sleep to prevent tight loop
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.exception(f"Error in listener loop: {e}")
                    # Continue listening despite errors
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("Listener loop cancelled")
            raise
        except Exception as e:
            logger.exception(f"Fatal error in listener loop: {e}")
            raise


async def create_handler(workflow_router: WorkflowRouter) -> ServiceBusHandler:
    """Factory function to create and configure Service Bus handler."""
    handler = ServiceBusHandler(
        connection_string=Config.SERVICE_BUS_CONNECTION_STRING,
        queue_name=Config.SERVICE_BUS_QUEUE_NAME,
        workflow_router=workflow_router,
        max_concurrent=Config.MAX_CONCURRENT_MESSAGES,
    )
    return handler


