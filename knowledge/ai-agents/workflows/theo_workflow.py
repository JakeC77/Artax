"""Theo workflow for conversational intent discovery."""

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

# Import Theo modules from app/workflows/theo/
from app.workflows.theo.intent_builder import IntentBuilder

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class TheoWorkflow(BaseWorkflow):
    """Theo workflow for conversational intent discovery.

    This workflow:
    1. Uses EventStreamReader to read user messages during intent discovery
    2. Runs IntentBuilder in conversational mode with event stream support
    3. Emits intent_ready event when intent is finalized
    4. Returns WorkflowResult with intent package

    Note: Team building has been extracted to a separate TeamBuilderWorkflow
    """
    
    def __init__(self):
        """Initialize Theo workflow."""
        super().__init__(
            workflow_id="theo",
            name="Theo Workflow"
        )
    
    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the Theo workflow.

        Args:
            event: WorkflowEvent containing all event data

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id

        # Create Logfire span for entire Theo workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'theo_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting Theo workflow for run_id={run_id}, "
            f"workspace_id={event.workspace_id}"
        )

        if logfire:
            logfire.info(
                'theo_workflow_started',
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

            # Close span before early return
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
                    message="Theo Workflow Started",
                    metadata={
                        "workspace_id": str(event.workspace_id),
                        "run_id": str(run_id),
                        "stage": "intent_discovery"
                    },
                    agent_id="theo"
                )
            
            # Extract initial context from event
            initial_context = None
            workspace_id_from_context = None
            if event.inputs_dict:
                initial_context = event.inputs_dict.get("initial_context")
                # Check if initial_context is a dict/JSON that contains workspace_id
                if initial_context:
                    if isinstance(initial_context, dict):
                        workspace_id_from_context = initial_context.get("workspace_id") or initial_context.get("workspaceId")
                    elif isinstance(initial_context, str):
                        # Try to parse as JSON
                        try:
                            import json
                            context_dict = json.loads(initial_context)
                            if isinstance(context_dict, dict):
                                workspace_id_from_context = context_dict.get("workspace_id") or context_dict.get("workspaceId")
                        except (json.JSONDecodeError, ValueError):
                            # Not JSON, treat as plain string
                            pass
            if not initial_context and event.prompt:
                initial_context = event.prompt
            
            # Use workspace_id from initial_context if available, otherwise fall back to event.workspace_id
            workspace_id = workspace_id_from_context or event.workspace_id
            
            # Stage 1: Intent Discovery with conversational Theo
            logger.info("Starting intent discovery phase")

            intent_start_time = datetime.utcnow()

            # Create span for intent discovery stage
            intent_span = None
            if logfire:
                intent_span = logfire.span(
                    'theo_workflow.intent_discovery',
                    run_id=run_id,
                    has_initial_context=initial_context is not None,
                ).__enter__()

            try:
                intent_builder = IntentBuilder(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id
                )

                # Run intent discovery with event stream support
                intent_package = await intent_builder.start_conversation(
                    initial_context=initial_context,
                    message_source=event_reader,
                    log_streamer=log_streamer
                )

                intent_duration = (datetime.utcnow() - intent_start_time).total_seconds()

                # Set intent discovery span attributes
                if intent_span:
                    intent_span.set_attribute('intent_complete', intent_package is not None)
                    if intent_package:
                        intent_span.set_attribute('intent_title', intent_package.title)
                    intent_span.set_attribute('duration_seconds', intent_duration)
            finally:
                # Close intent discovery span
                if intent_span:
                    intent_span.__exit__(None, None, None)
            
            if intent_package is None:
                # User quit or error during intent discovery
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Intent discovery was cancelled or failed"
                logger.warning(error_msg)
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="workflow_error",
                        message=error_msg,
                        agent_id="theo",
                    )
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )
            
            logger.info(f"Intent discovery complete: {intent_package.title}")
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_stage_complete",
                    message="Intent Discovery Complete",
                    metadata={
                        "title": intent_package.title,
                        "summary": intent_package.summary[:200]
                    },
                    agent_id="theo"
                )
                # Emit intent_ready event (for workspace setup flow) - slim metadata
                await log_streamer.log_event(
                    event_type="intent_ready",
                    message=f"Intent package ready: {intent_package.title}",
                    metadata={
                        "title": intent_package.title,
                        "description": intent_package.description,
                        "summary": intent_package.summary,
                        "objective": intent_package.mission.objective,
                        "why": intent_package.mission.why,
                        "success_looks_like": intent_package.mission.success_looks_like,
                        "ready": True
                    },
                    agent_id="theo"
                )
                # Also emit intent_finalized for backward compatibility
                intent_text = intent_package.get_formatted_intent_text()
                try:
                    await log_streamer.log_event(
                        event_type="intent_finalized",
                        message=f"Intent finalized: {intent_package.title}",
                        metadata={
                            "intent_text": intent_text,
                            "title": intent_package.title,
                            "summary": intent_package.summary,
                            "objective": intent_package.mission.objective,
                            "why": intent_package.mission.why,
                            "success_criteria": intent_package.mission.success_looks_like
                        },
                        agent_id="theo",
                    )
                except Exception as e:
                    # Don't fail workflow if event emission fails
                    logger.warning(f"Failed to emit intent_finalized event: {e}")

            # Build result with intent package
            result_data = {
                "intent_package": intent_package.to_dict(),
                "intent_title": intent_package.title,
                "intent_summary": intent_package.summary,
                "ready_for_next_stage": True
            }

            result_text = json.dumps(result_data, indent=2)
            duration = (datetime.utcnow() - start_time).total_seconds()

            if log_streamer:
                # Send final completion message to user
                completion_message = (
                    f"Intent discovery complete!\n\n"
                    f"**Intent:** {intent_package.title}\n"
                    f"**Summary:** {intent_package.summary}\n\n"
                    f"Your intent is ready for the next stage of the workflow."
                )

                await log_streamer.log_event(
                    event_type="agent_message",
                    message=completion_message,
                    agent_id="theo",
                )

                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message=f"Intent '{intent_package.title}' finalized successfully",
                    agent_id="theo",
                )

            logger.info(f"Theo workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'theo_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    intent_title=intent_package.title,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('intent_title', intent_package.title)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Theo workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'theo_workflow_failed',
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
                    agent_id="theo",
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


