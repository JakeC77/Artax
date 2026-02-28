"""Ontology creation workflow for conversational ontology design."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config

# Import ontology creation modules
from app.workflows.ontology_creation.ontology_builder import OntologyBuilder

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class OntologyCreationWorkflow(BaseWorkflow):
    """Ontology creation workflow for conversational ontology design.

    This workflow:
    1. Uses EventStreamReader to read user messages during ontology creation
    2. Runs OntologyBuilder in conversational mode with event stream support
    3. Emits ontology_ready event when ontology is finalized
    4. Returns WorkflowResult with ontology package
    """
    
    def __init__(self):
        """Initialize ontology creation workflow."""
        super().__init__(
            workflow_id="ontology-creation",
            name="Ontology Creation Workflow"
        )
    
    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the ontology creation workflow.

        Args:
            event: WorkflowEvent containing all event data

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id

        # Create Logfire span for entire workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'ontology_creation_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting ontology creation workflow for run_id={run_id}, "
            f"workspace_id={event.workspace_id}"
        )

        if logfire:
            logfire.info(
                'ontology_creation_workflow_started',
                run_id=run_id,
                workspace_id=event.workspace_id,
            )
        
        # Initialize GraphQL logger
        log_streamer = None
        if Config.GRAPHQL_LOGGING_ENABLED:
            try:
                log_streamer = ScenarioRunLogger(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    enabled=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize GraphQL logger: {e}")
        
        # Initialize event stream reader (required for conversational workflow)
        event_reader = None
        try:
            event_reader = EventStreamReader(
                run_id=run_id,
                tenant_id=tenant_id,
                graphql_endpoint=Config.GRAPHQL_ENDPOINT,
            )
            await event_reader.start()
            logger.info("Event stream reader started")
        except Exception as e:
            logger.error(f"Failed to start event stream reader: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            if span_ctx:
                span_ctx.set_attribute('success', False)
                span_ctx.set_attribute('error', f"Failed to start event stream: {str(e)}")
                span_ctx.__exit__(None, None, None)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=f"Failed to start event stream: {str(e)}",
                duration_seconds=duration,
            )
        
        try:
            # Log workflow start
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Ontology Creation Workflow Started",
                    metadata={
                        "workspace_id": str(event.workspace_id),
                        "run_id": str(run_id),
                        "stage": "ontology_creation"
                    },
                    agent_id="ontology_agent"
                )
            
            # Extract inputs from event
            ontology_id = None
            initial_context = None
            if event.inputs_dict:
                ontology_id = event.inputs_dict.get("ontology_id")
                initial_context = event.inputs_dict.get("initial_context")
            if not initial_context and event.prompt:
                initial_context = event.prompt
            
            # Require ontology_id from event - never generate a new one
            if not ontology_id:
                error_msg = "ontology_id is required in the incoming event. Cannot create a new ontology without an ontology_id."
                logger.error(error_msg)
                
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="workflow_error",
                        message=error_msg,
                        agent_id="ontology_agent"
                    )
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                if span_ctx:
                    span_ctx.set_attribute('success', False)
                    span_ctx.set_attribute('error', error_msg)
                    span_ctx.__exit__(None, None, None)
                
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )
            
            # Create ontology builder
            logger.info("Starting ontology creation phase")
            ontology_start_time = datetime.utcnow()

            ontology_span = None
            if logfire:
                ontology_span = logfire.span(
                    'ontology_creation_workflow.ontology_creation',
                    run_id=run_id,
                    has_initial_context=initial_context is not None,
                    ontology_id=ontology_id,
                ).__enter__()

            try:
                ontology_builder = OntologyBuilder(
                    tenant_id=tenant_id,
                    ontology_id=ontology_id
                )

                # Run ontology creation with event stream support
                ontology_package = await ontology_builder.start_conversation(
                    initial_context=initial_context,
                    message_source=event_reader,
                    log_streamer=log_streamer
                )

                ontology_duration = (datetime.utcnow() - ontology_start_time).total_seconds()

                if ontology_span:
                    ontology_span.set_attribute('ontology_complete', ontology_package is not None)
                    if ontology_package:
                        ontology_span.set_attribute('ontology_title', ontology_package.title)
                        ontology_span.set_attribute('semantic_version', ontology_package.semantic_version)
                    ontology_span.set_attribute('duration_seconds', ontology_duration)
            finally:
                if ontology_span:
                    ontology_span.__exit__(None, None, None)
            
            if ontology_package is None:
                # User quit or error during ontology creation
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Ontology creation was cancelled or failed"
                logger.warning(error_msg)
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="workflow_error",
                        message=error_msg,
                        agent_id="ontology_agent",
                    )
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )
            
            logger.info(f"Ontology creation complete: {ontology_package.title}")
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_stage_complete",
                    message="Ontology Creation Complete",
                    metadata={
                        "title": ontology_package.title,
                        "semantic_version": ontology_package.semantic_version,
                        "entity_count": len(ontology_package.entities),
                        "relationship_count": len(ontology_package.relationships)
                    },
                    agent_id="ontology_agent"
                )
                # Emit ontology_ready event
                await log_streamer.log_event(
                    event_type="ontology_ready",
                    message=f"Ontology package ready: {ontology_package.title}",
                    metadata={
                        "ontology_id": ontology_package.ontology_id,
                        "title": ontology_package.title,
                        "description": ontology_package.description,
                        "semantic_version": ontology_package.semantic_version,
                        "entity_count": len(ontology_package.entities),
                        "relationship_count": len(ontology_package.relationships),
                        "ready": True
                    },
                    agent_id="ontology_agent"
                )
                # Also emit ontology_finalized for backward compatibility
                ontology_text = ontology_package.get_formatted_ontology_text()
                try:
                    await log_streamer.log_event(
                        event_type="ontology_finalized",
                        message=f"Ontology finalized: {ontology_package.title}",
                        metadata={
                            "ontology_text": ontology_text,
                            "title": ontology_package.title,
                            "semantic_version": ontology_package.semantic_version,
                        },
                        agent_id="ontology_agent",
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit ontology_finalized event: {e}")

            # Build result with ontology package
            result_data = {
                "ontology_package": ontology_package.to_dict(),
                "ontology_id": ontology_package.ontology_id,
                "ontology_title": ontology_package.title,
                "semantic_version": ontology_package.semantic_version,
                "ready_for_next_stage": True
            }

            result_text = json.dumps(result_data, indent=2)
            duration = (datetime.utcnow() - start_time).total_seconds()

            if log_streamer:
                # Send final completion message to user
                completion_message = (
                    f"Ontology creation complete!\n\n"
                    f"**Ontology:** {ontology_package.title}\n"
                    f"**Version:** {ontology_package.semantic_version}\n"
                    f"**Entities:** {len(ontology_package.entities)}\n"
                    f"**Relationships:** {len(ontology_package.relationships)}\n\n"
                    f"Your ontology is ready for use."
                )

                await log_streamer.log_event(
                    event_type="agent_message",
                    message=completion_message,
                    agent_id="ontology_agent",
                )

                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message=f"Ontology '{ontology_package.title}' finalized successfully",
                    agent_id="ontology_agent",
                )

            logger.info(f"Ontology creation workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'ontology_creation_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    ontology_title=ontology_package.title,
                    semantic_version=ontology_package.semantic_version,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('ontology_title', ontology_package.title)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Ontology creation workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'ontology_creation_workflow_failed',
                    run_id=run_id,
                    error=error_msg,
                    error_type=type(e).__name__,
                    duration_seconds=duration,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', False)
                    span_ctx.set_attribute('error', error_msg)
                    span_ctx.record_exception(e)

            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_error",
                    message=error_msg,
                    agent_id="ontology_agent",
                )

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )

        finally:
            # Close Logfire span
            if span_ctx:
                span_ctx.__exit__(None, None, None)

            # Clean up event stream reader
            if event_reader:
                try:
                    await event_reader.stop()
                    logger.info("Event stream reader stopped")
                except Exception as e:
                    logger.warning(f"Error stopping event stream reader: {e}")
