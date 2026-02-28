"""Data Recommender workflow for conversational scope building."""

import json
import logging
from datetime import datetime
from typing import Optional, Any

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config

# Import from data_recommender module
from app.workflows.data_recommender.agent import ScopeBuilder
from app.workflows.data_recommender.config import load_config as load_dr_config
from app.workflows.data_recommender.schema_discovery import (
    fetch_workspace_schema,
    fetch_sample_data
)
from app.workflows.theo.models import IntentPackage

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class DataRecommenderWorkflow(BaseWorkflow):
    """
    Data Recommender workflow for conversational scope building.

    This workflow:
    1. Uses EventStreamReader to read user messages during scope building
    2. Runs ScopeBuilder in conversational mode with streaming
    3. Emits scope_ready event when scope is finalized
    4. Returns WorkflowResult with finalized data_scope

    The workflow receives an intent_package from the Theo workflow and
    interactively helps the user define the data scope for their analysis.

    Note: Execution has been extracted to a separate DataRecommenderExecutionWorkflow
    """

    def __init__(self):
        """Initialize Data Recommender workflow."""
        super().__init__(
            workflow_id="data_recommender",
            name="Data Recommender Workflow"
        )

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the Data Recommender workflow.

        Args:
            event: WorkflowEvent containing:
                - run_id: Unique run identifier
                - tenant_id: Tenant for authentication
                - workspace_id: Workspace to analyze
                - inputs_dict: Should contain 'intent_package' from Theo workflow

        Returns:
            WorkflowResult with scope recommendation or error
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id
        workspace_id = event.workspace_id

        # Create Logfire span for workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'data_recommender_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting Data Recommender workflow for run_id={run_id}, "
            f"workspace_id={workspace_id}"
        )

        if logfire:
            logfire.info(
                'data_recommender_workflow_started',
                run_id=run_id,
                workspace_id=workspace_id,
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

        # Initialize event stream reader
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
                    message="Data Recommender Workflow Started",
                    metadata={
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "stage": "schema_discovery"
                    },
                    agent_id="theo"
                )

            # Extract intent package from event inputs and hydrate to model
            intent_package = None
            if event.inputs_dict:
                intent_dict = event.inputs_dict.get("intent_package")
                if intent_dict:
                    intent_package = IntentPackage(**intent_dict)

            if not intent_package:
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "No intent_package provided in workflow inputs"
                logger.error(error_msg)

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

            # Stage 1: Schema Discovery
            logger.info("Starting schema discovery phase")
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_stage",
                    message="Discovering workspace schema...",
                    agent_id="theo",
                )

            schema_span = None
            if logfire:
                schema_span = logfire.span(
                    'data_recommender_workflow.schema_discovery',
                    run_id=run_id,
                    workspace_id=workspace_id,
                ).__enter__()

            try:
                # Fetch workspace schema
                dr_config = load_dr_config()
                schema = await fetch_workspace_schema(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    excluded_entities=dr_config.excluded_entities,
                )

                # Fetch sample data for all entities
                entity_types = [e.name for e in schema.entities]
                sample_data = await fetch_sample_data(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    entity_types=entity_types,
                    samples_per_entity=3
                )

                if schema_span:
                    schema_span.set_attribute('entity_count', len(schema.entities))
                    schema_span.set_attribute('relationship_count', len(schema.relationships))
                    schema_span.set_attribute('sample_data_count', sum(len(s) for s in sample_data.values()))

            finally:
                if schema_span:
                    schema_span.__exit__(None, None, None)

            logger.info(f"Schema discovery complete: {len(schema.entities)} entities")

            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_stage_complete",
                    message="Schema Discovery Complete",
                    metadata={
                        "entity_count": len(schema.entities),
                        "relationship_count": len(schema.relationships),
                        "sample_data_count": sum(len(s) for s in sample_data.values())
                    },
                    agent_id="theo"
                )

            # Stage 2: Scope Building Interview
            logger.info("Starting scope building interview")
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_stage",
                    message="Starting scope interview with Theo...",
                    agent_id="theo",
                )

            scope_span = None
            if logfire:
                scope_span = logfire.span(
                    'data_recommender_workflow.scope_interview',
                    run_id=run_id,
                    intent_title=intent_package.title,
                ).__enter__()

            scope_start_time = datetime.utcnow()

            try:
                # Run scope building conversation
                scope_builder = ScopeBuilder()
                scope = await scope_builder.start_conversation(
                    intent_package=intent_package,
                    graph_schema=schema,
                    sample_data=sample_data,
                    message_source=event_reader,
                    log_streamer=log_streamer,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )

                scope_duration = (datetime.utcnow() - scope_start_time).total_seconds()

                if scope_span:
                    scope_span.set_attribute('scope_complete', scope is not None)
                    if scope:
                        scope_span.set_attribute('entity_count', len(scope.entities))
                        scope_span.set_attribute('confidence', scope.confidence_level)
                    scope_span.set_attribute('duration_seconds', scope_duration)

            finally:
                if scope_span:
                    scope_span.__exit__(None, None, None)

            if scope is None:
                # User cancelled or error
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Scope building was cancelled or failed"
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

            logger.info(f"Scope building complete: {len(scope.entities)} entities, {scope.confidence_level} confidence")

            # Build data_scope structure
            data_scope = {
                "scopes": [
                    {
                        "entity_type": e.entity_type,
                        "rationale": e.reasoning,
                        "filters": [f.model_dump() for f in e.filters],
                        "estimated_count": 0,  # Will be filled during execution
                        "relevance_level": e.relevance_level,
                        "fields_of_interest": [foi.model_dump() for foi in e.fields_of_interest],
                    }
                    for e in scope.entities
                ],
                "summary": scope.summary,
                "confidence_level": scope.confidence_level,
                "relationships": [
                    {
                        "from_entity": r.from_entity,
                        "to_entity": r.to_entity,
                        "relationship_type": r.relationship_type,
                    }
                    for r in scope.relationships
                ]
            }

            # Emit scope_ready event (for workspace setup flow)
            if log_streamer:
                await log_streamer.log_event(
                    event_type="scope_ready",
                    message=f"Data scope ready: {scope.summary}",
                    metadata={
                        "data_scope": data_scope,
                        "ready": True
                    },
                    agent_id="theo"
                )

                # Send completion message to user
                entity_list = ", ".join(e.entity_type for e in scope.entities)
                completion_message = (
                    f"Data scope complete!\n\n"
                    f"**Summary:** {scope.summary}\n"
                    f"**Entities:** {entity_list}\n"
                    f"**Confidence:** {scope.confidence_level}\n\n"
                    f"Your data scope is ready for the next stage."
                )

                await log_streamer.log_event(
                    event_type="agent_message",
                    message=completion_message,
                    agent_id="theo",
                )

                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message=f"Data scope finalized: {len(scope.entities)} entities",
                    agent_id="theo",
                )

            # Build result data
            result_data = {
                "data_scope": data_scope,
                "intent_title": intent_package.title,
                "scope_summary": scope.summary,
                "confidence_level": scope.confidence_level,
                "ready_for_next_stage": True
            }

            result_text = json.dumps(result_data, indent=2)
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Data Recommender workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'data_recommender_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    entity_count=len(scope.entities),
                    confidence_level=scope.confidence_level,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('entity_count', len(scope.entities))

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Data Recommender workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'data_recommender_workflow_failed',
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
