"""Data Recommender Execution workflow for executing finalized scopes."""

import json
import logging
from datetime import datetime
from typing import Optional

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config

# Import from data_recommender module
from app.workflows.data_recommender.executor import ScopeExecutor
from app.workflows.data_recommender.graphql_client import create_client
from app.workflows.data_recommender.models import (
    ScopeRecommendation,
    EntityScope,
    RelationshipScope,
    FilterCriterion
)
from app.workflows.data_recommender.config import load_config as load_dr_config
from app.workflows.data_recommender.schema_discovery import fetch_workspace_schema

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class DataRecommenderExecutionWorkflow(BaseWorkflow):
    """
    Data Recommender Execution workflow for executing finalized data scopes.

    This workflow:
    1. Accepts data_scope from the frontend/API
    2. Executes the scope against the graph database
    3. Streams progress events during execution
    4. Returns execution results with matching node IDs

    Triggered after user confirms the data scope in the setup flow.
    """

    def __init__(self):
        """Initialize Data Recommender Execution workflow."""
        super().__init__(
            workflow_id="data_recommender_execution",
            name="Data Recommender Execution Workflow"
        )

    def _parse_data_scope(self, data_scope_dict: dict) -> ScopeRecommendation:
        """Parse data_scope dictionary into ScopeRecommendation object.

        Args:
            data_scope_dict: Dictionary containing data scope

        Returns:
            ScopeRecommendation object
        """
        scopes = data_scope_dict.get("scopes", [])

        # Parse entity scopes
        entities = []
        for scope in scopes:
            # Parse filters
            filters = []
            for filter_dict in scope.get("filters", []):
                filters.append(FilterCriterion(
                    field_path=filter_dict.get("field_path", ""),
                    operator=filter_dict.get("operator", "equals"),
                    value=filter_dict.get("value"),
                    description=filter_dict.get("description", "")
                ))

            entities.append(EntityScope(
                entity_type=scope.get("entity_type"),
                rationale=scope.get("rationale", ""),
                relevance_level=scope.get("relevance_level", "core"),
                filters=filters,
                fields_of_interest=scope.get("fields_of_interest", []),
                estimated_count=scope.get("estimated_count", 0)
            ))

        # Parse relationships
        relationships = []
        for rel_dict in data_scope_dict.get("relationships", []):
            relationships.append(RelationshipScope(
                from_entity=rel_dict.get("from_entity"),
                to_entity=rel_dict.get("to_entity"),
                relationship_type=rel_dict.get("relationship_type"),
                rationale=rel_dict.get("rationale", "")
            ))

        return ScopeRecommendation(
            entities=entities,
            relationships=relationships,
            summary=data_scope_dict.get("summary", "Data scope"),
            confidence_level=data_scope_dict.get("confidence_level", "medium"),
            clarifying_questions=[],  # Not needed for execution
            needs_clarification=False
        )

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the Data Recommender Execution workflow.

        Args:
            event: WorkflowEvent containing:
                - data_scope: Finalized data scope from frontend

        Returns:
            WorkflowResult with execution results
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id
        workspace_id = event.workspace_id

        # Create Logfire span for workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'data_recommender_execution_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting Data Recommender Execution workflow for run_id={run_id}, "
            f"workspace_id={workspace_id}"
        )

        if logfire:
            logfire.info(
                'data_recommender_execution_workflow_started',
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

        try:
            # Log workflow start
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Data Scope Execution Started",
                    metadata={
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id)
                    },
                    agent_id="theo"
                )

            # Extract data scope from event inputs
            if not event.inputs_dict or "data_scope" not in event.inputs_dict:
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "No data_scope provided in workflow inputs"
                logger.error(error_msg)

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="execution_error",
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

            data_scope_dict = event.inputs_dict["data_scope"]

            # Parse data_scope into ScopeRecommendation
            scope = self._parse_data_scope(data_scope_dict)

            logger.info(f"Executing scope with {len(scope.entities)} entities")

            # Emit execution progress
            if log_streamer:
                await log_streamer.log_event(
                    event_type="execution_progress",
                    entity_type="all",
                    status=f"Starting execution for {len(scope.entities)} entity types",
                    metadata={
                        "entity_count": len(scope.entities),
                        "entities": [e.entity_type for e in scope.entities]
                    }
                )

            # Fetch schema for execution
            dr_config = load_dr_config()
            schema = await fetch_workspace_schema(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                excluded_entities=dr_config.excluded_entities,
            )

            # Create GraphQL client
            try:
                graphql_client = create_client(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id
                )
            except Exception as e:
                logger.error(f"Failed to create GraphQL client: {e}")
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="execution_error",
                        message=f"Failed to create GraphQL client: {e}",
                        agent_id="theo",
                    )

                duration = (datetime.utcnow() - start_time).total_seconds()
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=f"Failed to create GraphQL client: {e}",
                    duration_seconds=duration,
                )

            # Create executor
            executor = ScopeExecutor(
                tenant_id=tenant_id,
                log_streamer=log_streamer,
                graphql_client=graphql_client,
                debug=False
            )

            # Execute the scope
            logger.info("Starting scope execution")
            execution_result = await executor.execute(scope, schema)

            if not execution_result or not execution_result.success:
                error_msg = execution_result.error_message if execution_result else "Execution failed"
                logger.error(f"Scope execution failed: {error_msg}")

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="execution_error",
                        message=error_msg,
                        agent_id="theo",
                    )

                duration = (datetime.utcnow() - start_time).total_seconds()
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )

            # Build execution results
            results = []
            for entity_stat in execution_result.stats.entity_stats:
                entity_type = entity_stat.entity_type
                node_ids = execution_result.matching_node_ids.get(entity_type, [])

                results.append({
                    "entity_type": entity_type,
                    "node_ids": node_ids,
                    "sample_data": [],  # Could fetch sample data here if needed
                    "total_count": entity_stat.matches_after_filtering
                })

                # Emit per-entity completion event
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="entity_complete",
                        entity_type=entity_type,
                        node_ids=node_ids,
                        sample_data=[],
                        metadata={
                            "total_count": entity_stat.matches_after_filtering,
                            "candidates_fetched": entity_stat.candidates_fetched,
                            "filters_applied": entity_stat.api_filters_applied + entity_stat.python_filters_applied
                        }
                    )

            # Emit execution_complete event
            if log_streamer:
                total_matches = execution_result.stats.total_matches

                await log_streamer.log_event(
                    event_type="execution_complete",
                    results=results,
                    metadata={
                        "total_matches": total_matches,
                        "execution_time_seconds": execution_result.stats.execution_time_seconds
                    }
                )

                completion_message = (
                    f"Data execution complete!\n\n"
                    f"**Total Matches:** {total_matches}\n"
                    f"**Entities:** {len(results)}"
                )

                await log_streamer.log_event(
                    event_type="agent_message",
                    message=completion_message,
                    agent_id="theo",
                )

                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message=f"Data execution complete: {total_matches} total matches",
                    agent_id="theo",
                )

            # Build result data
            result_data = {
                "execution_results": results,
                "total_matches": execution_result.stats.total_matches,
                "execution_time_seconds": execution_result.stats.execution_time_seconds,
                "success": True
            }

            result_text = json.dumps(result_data, indent=2)
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Data Recommender Execution workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'data_recommender_execution_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    total_matches=execution_result.stats.total_matches,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('total_matches', execution_result.stats.total_matches)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Data Recommender Execution workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'data_recommender_execution_workflow_failed',
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
                    event_type="execution_error",
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