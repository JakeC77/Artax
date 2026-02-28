"""
Unified Workspace Setup Workflow.

This workflow orchestrates the entire workspace setup process through a single
ScenarioRun with persistent Theo context. It handles:

1. Intent Discovery (Stage 1) - Conversational intent building with IntentBuilder
2. Data Scoping (Stage 2) - Conversational data scope building with ScopeBuilder
   - Includes Build Query / Preview Data UI with real-time scope updates
   - Preview data can be fetched without finalizing scope
3. Data Execution & Staging (Stage 3) - Executes scope queries and stages data
   to workspace via confirmDataReviewAndBuildTeam mutation
4. Team Building (Stage 4) - Generates AI team configuration

Stages run: Intent → Scoping → (Execute & Stage || Team Building) in parallel

Control Events (from frontend via Service Bus):
- user_message: Process message in current stage
- end_intent: Stage 1 → 2 transition
- end_data_scoping: Stage 2 → 3 transition (triggers execution + staging)
- cancel_workflow: User cancels the workflow

All events include metadata.stage for frontend filtering.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config
from app.core.authenticated_graphql_client import run_graphql

# Stage 1: Intent Discovery
from app.workflows.theo.intent_builder import IntentBuilder
from app.workflows.theo.models import IntentPackage

# Stage 2: Data Scoping
from app.workflows.data_recommender.agent import ScopeBuilder, GraphSchema
from app.workflows.data_recommender.config import load_config as load_dr_config
from app.workflows.data_recommender.schema_discovery import (
    fetch_workspace_schema,
    fetch_sample_data
)

# Stage 3: Data Execution
from app.workflows.data_recommender.executor import ScopeExecutor
from app.workflows.data_recommender.graphql_client import create_client
from app.workflows.data_recommender.models import (
    ScopeRecommendation,
    EntityScope,
    RelationshipPath,
    EntityFilter
)

# Stage 4: Team Building
from app.workflows.theo.team_builder import TeamBuilder

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


# Stage constants
STAGE_INTENT_DISCOVERY = "intent_discovery"
STAGE_DATA_SCOPING = "data_scoping"
STAGE_DATA_REVIEW = "data_review"
STAGE_TEAM_BUILDING = "team_building"

# GraphQL mutation for staging data to workspace
CONFIRM_DATA_REVIEW_MUTATION = """
mutation ConfirmDataReviewAndBuildTeam(
    $workspaceId: UUID!,
    $executionResults: String!
) {
    confirmDataReviewAndBuildTeam(
        workspaceId: $workspaceId,
        executionResults: $executionResults
    ) {
        runId
        stage
        message
    }
}
""".strip()


class WorkspaceSetupWorkflow(BaseWorkflow):
    """
    Unified workspace setup workflow.

    Single entry point for the entire workspace setup process.
    Maintains Theo's context across all stages through a single run.
    """

    def __init__(self):
        """Initialize Workspace Setup workflow."""
        super().__init__(
            workflow_id="workspace_setup",
            name="Workspace Setup Workflow"
        )

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the unified workspace setup workflow.

        Args:
            event: WorkflowEvent containing:
                - run_id: Single run ID for entire setup
                - tenant_id: Tenant for authentication
                - workspace_id: Workspace being configured
                - inputs_dict: May contain initial_context

        Returns:
            WorkflowResult with setup completion status
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id
        workspace_id = event.workspace_id

        # Create Logfire span for entire workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'workspace_setup_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting Workspace Setup workflow for run_id={run_id}, "
            f"workspace_id={workspace_id}"
        )

        if logfire:
            logfire.info(
                'workspace_setup_workflow_started',
                run_id=run_id,
                workspace_id=workspace_id,
            )

        # Initialize GraphQL logger (single logger for entire workflow)
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

        # Initialize event stream reader (single reader for entire workflow)
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

        # State that persists across stages
        intent_package: Optional[IntentPackage] = None
        data_scope: Optional[ScopeRecommendation] = None
        execution_results: Optional[Dict[str, Any]] = None
        team_config: Optional[Dict[str, Any]] = None
        current_stage = STAGE_INTENT_DISCOVERY

        try:
            # Log workflow start
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Workspace Setup Started",
                    metadata={
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "stage": current_stage
                    },
                    agent_id="theo"
                )

            # Extract initial context from event
            initial_context = None
            if event.inputs_dict:
                initial_context = event.inputs_dict.get("initial_context")
            if not initial_context and event.prompt:
                initial_context = event.prompt
            workspace_id = event.inputs_dict.get("workspaceId")
            # ============================================================
            # STAGE 1: Intent Discovery
            # ============================================================
            logger.info("Starting Stage 1: Intent Discovery")
            current_stage = STAGE_INTENT_DISCOVERY

            if logfire:
                logfire.info('stage_started', stage=current_stage)

            intent_package = await self._run_intent_discovery(
                initial_context=initial_context,
                event_reader=event_reader,
                workspace_id=workspace_id,
                log_streamer=log_streamer,
                stage=current_stage
            )

            if intent_package is None:
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Intent discovery was cancelled or failed"
                logger.warning(error_msg)

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="workflow_error",
                        message=error_msg,
                        agent_id="theo",
                        metadata={"stage": current_stage}
                    )

                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )

            logger.info(f"Intent discovery complete: {intent_package.title}")

            # Emit intent_ready event (slim metadata - no conversation_transcript)
            if log_streamer:
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
                        "ready": True,
                        "stage": current_stage
                    },
                    agent_id="theo"
                )

            # ============================================================
            # STAGE 2: Data Scoping
            # ============================================================
            logger.info("Starting Stage 2: Data Scoping")
            current_stage = STAGE_DATA_SCOPING

            if logfire:
                logfire.info('stage_started', stage=current_stage)

            data_scope = await self._run_data_scoping(
                intent_package=intent_package,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                event_reader=event_reader,
                log_streamer=log_streamer,
                stage=current_stage
            )

            if data_scope is None:
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Data scoping was cancelled or failed"
                logger.warning(error_msg)

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="workflow_error",
                        message=error_msg,
                        agent_id="theo",
                        metadata={"stage": current_stage}
                    )

                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )

            logger.info(f"Data scoping complete: {len(data_scope.entities)} entities")

            # Emit scope_ready event
            if log_streamer:
                await log_streamer.log_event(
                    event_type="scope_ready",
                    message=f"Data scope ready: {data_scope.summary}",
                    metadata={
                        "data_scope": self._scope_to_dict(data_scope),
                        "ready": True,
                        "stage": current_stage
                    },
                    agent_id="theo"
                )

            # ============================================================
            # STAGE 3 & 4: Data Execution/Staging + Team Building (PARALLEL)
            # These are independent operations — run them concurrently
            # ============================================================
            logger.info("Starting Stage 3 & 4 in parallel: Data Execution/Staging + Team Building")

            if log_streamer:
                await log_streamer.log_event(
                    event_type="setup_phase",
                    message="Staging data and building your AI team...",
                    agent_id="theo",
                    metadata={
                        "phase_name": "parallel_setup",
                        "phases": ["staging_data", "building_team"],
                        "status": "started",
                        "stage": STAGE_DATA_REVIEW,
                    }
                )

            # Run execution/staging and team building concurrently
            execution_task = self._run_execution_and_staging(
                data_scope=data_scope,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                log_streamer=log_streamer,
            )

            team_task = self._run_team_building(
                intent_package=intent_package,
                data_scope=data_scope,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                log_streamer=log_streamer,
                stage=STAGE_TEAM_BUILDING
            )

            # Wait for both to complete
            execution_results, team_config = await asyncio.gather(
                execution_task,
                team_task,
                return_exceptions=False
            )

            # Handle data execution failure (fatal)
            if not execution_results or not execution_results.get("success"):
                error_msg = "Data execution/staging failed"
                logger.error(f"Data execution failed: {execution_results}")

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="setup_error",
                        message=error_msg,
                        agent_id="theo",
                        metadata={
                            "phase_name": "staging_data",
                            "recoverable": False,
                            "stage": STAGE_DATA_REVIEW,
                        }
                    )

                duration = (datetime.utcnow() - start_time).total_seconds()
                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )

            # Handle team building failure (non-fatal)
            if not team_config:
                logger.warning("Team building failed - workflow will continue without team config")
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="setup_error",
                        message="Team building failed, but data staging was successful",
                        agent_id="theo",
                        metadata={
                            "phase_name": "building_team",
                            "recoverable": False,
                            "stage": STAGE_TEAM_BUILDING,
                        }
                    )

            # ============================================================
            # All stages complete - workflow is done
            # ============================================================
            # Flow: Intent → Scoping → (Execute & Stage || Team Building)

            # Track completion status
            execution_success = execution_results is not None and isinstance(execution_results, dict) and execution_results.get("success", False)
            team_success = team_config is not None and isinstance(team_config, dict)

            logger.info(f"Parallel stages complete: execution_success={execution_success}, team_success={team_success}")

            # Extract node IDs from execution results if available
            # results is a list of dicts: [{"entity_type": "...", "node_ids": [...], ...}, ...]
            selected_node_ids = []
            if execution_results and isinstance(execution_results, dict):
                results = execution_results.get("results", [])
                for result_item in results:
                    if isinstance(result_item, dict):
                        node_ids = result_item.get("node_ids", [])
                        if isinstance(node_ids, list):
                            selected_node_ids.extend(node_ids)

            # ============================================================
            # COMPLETION
            # ============================================================
            logger.info("Workspace setup complete!")

            # Emit setup_complete event with slim metadata
            # Note: Full data is stored in result_data for actual use - this is just for UI display
            if log_streamer:
                await log_streamer.log_event(
                    event_type="setup_complete",
                    message="Workspace setup completed successfully",
                    metadata={
                        # Intent summary (exclude conversation_transcript)
                        "intent_title": intent_package.title if intent_package else None,
                        "intent_summary": intent_package.summary if intent_package else None,
                        # Scope summary (exclude full entity details)
                        "scope_summary": data_scope.summary if data_scope else None,
                        "entity_count": len(data_scope.entities) if data_scope else 0,
                        # Execution summary (exclude full results)
                        "execution_success": execution_results.get("success", False) if execution_results else False,
                        "total_matches": execution_results.get("total_matches", 0) if execution_results else 0,
                        # Team summary (exclude full config)
                        "team_name": team_config.get("team_name") if team_config else None,
                        "team_size": len(team_config.get("agents", [])) if team_config else 0,
                        # Node count (not full list)
                        "selected_node_count": len(selected_node_ids),
                        "stage": "completed"
                    },
                    agent_id="theo"
                )

                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message="Workspace setup workflow completed",
                    agent_id="theo",
                    metadata={"stage": "completed"}
                )

            # Build result
            result_data = {
                "intent_package": intent_package.to_dict() if intent_package else None,
                "data_scope": self._scope_to_dict(data_scope) if data_scope else None,
                "execution_results": execution_results,
                "team_config": team_config,
                "selected_node_ids": selected_node_ids,
                "success": True
            }

            result_text = json.dumps(result_data, indent=2, default=str)
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Workspace Setup workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'workspace_setup_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Workspace Setup workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'workspace_setup_workflow_failed',
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
                    metadata={"stage": current_stage}
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

    # ========================================================================
    # Stage Implementation Methods
    # ========================================================================

    async def _run_intent_discovery(
        self,
        initial_context: Optional[str],
        workspace_id: Optional[str],
        event_reader: EventStreamReader,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[IntentPackage]:
        """Run Stage 1: Intent Discovery using IntentBuilder.

        Args:
            initial_context: Optional initial user message
            event_reader: Event stream reader for user messages
            log_streamer: GraphQL logger for events
            stage: Current stage name for event tagging

        Returns:
            IntentPackage or None if cancelled
        """
        if logfire:
            with logfire.span('intent_discovery_stage'):
                intent_builder = IntentBuilder(workspace_id=workspace_id)

                # Create a wrapper log_streamer that adds stage to all events
                stage_streamer = _StageAwareLogger(log_streamer, stage) if log_streamer else None

                return await intent_builder.start_conversation(
                    initial_context=initial_context,
                    message_source=event_reader,
                    log_streamer=stage_streamer
                )
        else:
            intent_builder = IntentBuilder(workspace_id=workspace_id)
            stage_streamer = _StageAwareLogger(log_streamer, stage) if log_streamer else None

            return await intent_builder.start_conversation(
                initial_context=initial_context,
                message_source=event_reader,
                log_streamer=stage_streamer
            )

    async def _run_data_scoping(
        self,
        intent_package: IntentPackage,
        workspace_id: str,
        tenant_id: str,
        event_reader: EventStreamReader,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[ScopeRecommendation]:
        """Run Stage 2: Data Scoping using ScopeBuilder.

        Args:
            intent_package: Intent from Stage 1
            workspace_id: Workspace to analyze
            tenant_id: Tenant for authentication
            event_reader: Event stream reader for user messages
            log_streamer: GraphQL logger for events
            stage: Current stage name for event tagging

        Returns:
            ScopeRecommendation or None if cancelled
        """
        if logfire:
            with logfire.span('data_scoping_stage'):
                return await self._do_data_scoping(
                    intent_package, workspace_id, tenant_id,
                    event_reader, log_streamer, stage
                )
        else:
            return await self._do_data_scoping(
                intent_package, workspace_id, tenant_id,
                event_reader, log_streamer, stage
            )

    async def _do_data_scoping(
        self,
        intent_package: IntentPackage,
        workspace_id: str,
        tenant_id: str,
        event_reader: EventStreamReader,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[ScopeRecommendation]:
        """Internal implementation of data scoping."""
        # Fetch workspace schema
        dr_config = load_dr_config()
        schema = await fetch_workspace_schema(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            excluded_entities=dr_config.excluded_entities,
        )

        # Fetch sample data
        entity_types = [e.name for e in schema.entities]
        sample_data = await fetch_sample_data(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            entity_types=entity_types,
            samples_per_entity=3
        )

        # Create stage-aware logger
        stage_streamer = _StageAwareLogger(log_streamer, stage) if log_streamer else None

        # Run scope building — schema is already a GraphSchema from fetch_workspace_schema
        scope_builder = ScopeBuilder()
        return await scope_builder.start_conversation(
            intent_package=intent_package,
            graph_schema=schema,
            sample_data=sample_data,
            message_source=event_reader,
            log_streamer=stage_streamer,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )

    async def _run_data_execution(
        self,
        data_scope: ScopeRecommendation,
        workspace_id: str,
        tenant_id: str,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[Dict[str, Any]]:
        """Run Stage 3: Data Execution using ScopeExecutor.

        Args:
            data_scope: Scope from Stage 2
            workspace_id: Workspace to query
            tenant_id: Tenant for authentication
            log_streamer: GraphQL logger for events
            stage: Current stage name for event tagging

        Returns:
            Execution results dict or None if failed
        """
        if logfire:
            with logfire.span('data_execution_stage'):
                return await self._do_data_execution(
                    data_scope, workspace_id, tenant_id, log_streamer, stage
                )
        else:
            return await self._do_data_execution(
                data_scope, workspace_id, tenant_id, log_streamer, stage
            )

    async def _do_data_execution(
        self,
        data_scope: ScopeRecommendation,
        workspace_id: str,
        tenant_id: str,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[Dict[str, Any]]:
        """Internal implementation of data execution."""
        stage_streamer = _StageAwareLogger(log_streamer, stage) if log_streamer else None

        entity_total = len(data_scope.entities)

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
            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_error",
                    message=f"Failed to create GraphQL client: {e}",
                    agent_id="theo",
                    metadata={"phase_name": "staging_data", "recoverable": False}
                )
            return None

        # Create executor (test_mode=True for faster testing - limits traversal)
        executor = ScopeExecutor(
            tenant_id=tenant_id,
            log_streamer=stage_streamer,
            graphql_client=graphql_client,
            debug=False,
            test_mode=True,  # TODO: Make this configurable via env var or workflow input
            max_nodes_to_traverse=50,
            max_neighbors_per_node=3
        )

        # Execute the scope
        execution_result = await executor.execute(data_scope, schema)

        if not execution_result or not execution_result.success:
            error_msg = execution_result.error_message if execution_result else "Execution failed"
            logger.error(f"Scope execution failed: {error_msg}")

            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_error",
                    message=error_msg,
                    agent_id="theo",
                    metadata={"phase_name": "staging_data", "recoverable": False}
                )
            return None

        # Build results and emit per-entity setup_task events
        results = []
        entity_stats = execution_result.stats.entity_stats
        for task_index, entity_stat in enumerate(entity_stats):
            entity_type = entity_stat.entity_type
            node_ids = execution_result.matching_node_ids.get(entity_type, [])
            sample_data = execution_result.sample_nodes.get(entity_type, [])
            count = entity_stat.matches_after_filtering
            task_id = f"entity_{entity_type.lower()}"

            # Emit running
            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_task",
                    message=f"Fetching {entity_type} records...",
                    metadata={
                        "task_id": task_id,
                        "task_type": "entity",
                        "title": entity_type,
                        "task_index": task_index,
                        "task_total": entity_total,
                        "status": "running",
                    }
                )

            results.append({
                "entity_type": entity_type,
                "node_ids": node_ids,
                "sample_data": sample_data,
                "total_count": count,
            })

            # Emit completed
            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_task",
                    message=f"Fetched {count:,} {entity_type} records",
                    metadata={
                        "task_id": task_id,
                        "task_type": "entity",
                        "title": entity_type,
                        "task_index": task_index,
                        "task_total": entity_total,
                        "status": "completed",
                        "progress": {"current": count, "total": count},
                    }
                )

        return {
            "results": results,
            "total_matches": execution_result.stats.total_matches,
            "execution_time_seconds": execution_result.stats.execution_time_seconds,
            "success": True
        }

    async def _stage_to_workspace(
        self,
        execution_results: Dict[str, Any],
        workspace_id: str,
        tenant_id: str,
    ) -> bool:
        """Stage execution results to workspace via confirmDataReviewAndBuildTeam mutation.

        Transforms execution results into the format expected by the C# mutation
        and calls it to create WorkspaceItems and transition to team_building stage.

        Args:
            execution_results: Dict from _run_data_execution with "results" list
            workspace_id: Workspace to stage into
            tenant_id: Tenant for authentication

        Returns:
            True if staging succeeded, False otherwise
        """
        # Pass through as-is — C# ExecutionResultItem uses snake_case JsonPropertyName
        results_list = execution_results.get("results", [])
        execution_items = [
            {"entity_type": r["entity_type"], "node_ids": r["node_ids"]}
            for r in results_list
            if r.get("node_ids")
        ]

        if not execution_items:
            logger.warning("No node IDs to stage")
            return False

        execution_json = json.dumps(execution_items)
        total_nodes = sum(len(item["node_ids"]) for item in execution_items)
        logger.info(f"Staging {len(execution_items)} entity types, {total_nodes} total nodes")

        try:
            result = await run_graphql(
                CONFIRM_DATA_REVIEW_MUTATION,
                {"workspaceId": workspace_id, "executionResults": execution_json},
                tenant_id=tenant_id,
                timeout=60.0,
            )

            response = result.get("confirmDataReviewAndBuildTeam", {})
            logger.info(f"Staging complete: {response.get('message')}")
            return True

        except Exception as e:
            logger.error(f"Failed to stage data to workspace: {e}")
            return False

    async def _run_execution_and_staging(
        self,
        data_scope: ScopeRecommendation,
        workspace_id: str,
        tenant_id: str,
        log_streamer: Optional[ScenarioRunLogger],
    ) -> Optional[Dict[str, Any]]:
        """Run data execution and staging as a single operation.

        Combines _run_data_execution and _stage_to_workspace into one
        coroutine for parallel execution with team building.

        Args:
            data_scope: Scope from Stage 2
            workspace_id: Workspace to query and stage into
            tenant_id: Tenant for authentication
            log_streamer: GraphQL logger for events

        Returns:
            Execution results dict with success=True, or dict with success=False on failure
        """
        # Run data execution
        execution_results = await self._run_data_execution(
            data_scope=data_scope,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            log_streamer=log_streamer,
            stage=STAGE_DATA_REVIEW
        )

        if not execution_results or not execution_results.get("success"):
            return {"success": False, "error": "Data execution failed"}

        # Stage to workspace
        staging_success = await self._stage_to_workspace(
            execution_results=execution_results,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
        )

        if not staging_success:
            return {"success": False, "error": "Staging to workspace failed"}

        return execution_results

    async def _run_team_building(
        self,
        intent_package: IntentPackage,
        data_scope: ScopeRecommendation,
        workspace_id: str,
        tenant_id: str,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[Dict[str, Any]]:
        """Run Stage 4: Team Building using TeamBuilder.

        Args:
            intent_package: Intent from Stage 1
            data_scope: Scope from Stage 2
            workspace_id: Workspace to configure
            tenant_id: Tenant for authentication
            log_streamer: GraphQL logger for events
            stage: Current stage name for event tagging

        Returns:
            Team config dict or None if failed
        """
        if logfire:
            with logfire.span('team_building_stage'):
                return await self._do_team_building(
                    intent_package, data_scope, workspace_id, tenant_id,
                    log_streamer, stage
                )
        else:
            return await self._do_team_building(
                intent_package, data_scope, workspace_id, tenant_id,
                log_streamer, stage
            )

    async def _do_team_building(
        self,
        intent_package: IntentPackage,
        data_scope: ScopeRecommendation,
        workspace_id: str,
        tenant_id: str,
        log_streamer: Optional[ScenarioRunLogger],
        stage: str
    ) -> Optional[Dict[str, Any]]:
        """Internal implementation of team building."""
        stage_streamer = _StageAwareLogger(log_streamer, stage) if log_streamer else None

        # Create team builder
        team_builder = TeamBuilder(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            graphql_endpoint=Config.GRAPHQL_ENDPOINT
        )

        # Build the team - returns TeamBuildResult with error details
        result = await team_builder.start_conversation(intent_package)

        if not result.success:
            error_msg = result.error_message or "Team building failed"
            if result.validation_errors:
                error_msg = f"Validation errors: {'; '.join(result.validation_errors)}"

            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_error",
                    message=error_msg,
                    agent_id="theo",
                    metadata={
                        "phase_name": "building_team",
                        "recoverable": False,
                        "error_code": result.error_type,
                    }
                )
            return None

        team_bundle = result.team_bundle
        conductor = team_bundle.team_definition.conductor
        specialists = team_bundle.team_definition.specialists
        all_agents = [conductor] + list(specialists)
        agent_total = len(all_agents)

        team_config = {
            "team_id": team_bundle.team_name,
            "team_name": team_bundle.team_name,
            "conductor": {
                "agent_id": self._make_agent_id(conductor.identity.role),
                "name": conductor.identity.name,
                "role": conductor.identity.role,
                "capabilities": conductor.tools.available if conductor.tools.available else []
            },
            "agents": []
        }

        # Add conductor + emit setup_task
        conductor_id = self._make_agent_id(conductor.identity.role)
        if stage_streamer:
            await stage_streamer.log_event(
                event_type="setup_task",
                message=f"Configuring {conductor.identity.name}...",
                metadata={
                    "task_id": f"agent_{conductor_id}",
                    "task_type": "agent",
                    "title": conductor.identity.name,
                    "task_index": 0,
                    "task_total": agent_total,
                    "status": "running",
                }
            )

        team_config["agents"].append({
            "agent_id": conductor_id,
            "name": conductor.identity.name,
            "role": conductor.identity.role,
            "type": "conductor",
            "capabilities": conductor.tools.available if conductor.tools.available else []
        })

        if stage_streamer:
            await stage_streamer.log_event(
                event_type="setup_task",
                message=f"{conductor.identity.name} ready",
                metadata={
                    "task_id": f"agent_{conductor_id}",
                    "task_type": "agent",
                    "title": conductor.identity.name,
                    "task_index": 0,
                    "task_total": agent_total,
                    "status": "completed",
                }
            )

        # Add specialists + emit setup_task for each
        for idx, specialist in enumerate(specialists):
            agent_id = self._make_agent_id(specialist.identity.name)
            task_index = idx + 1  # conductor is 0

            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_task",
                    message=f"Configuring {specialist.identity.name}...",
                    metadata={
                        "task_id": f"agent_{agent_id}",
                        "task_type": "agent",
                        "title": specialist.identity.name,
                        "task_index": task_index,
                        "task_total": agent_total,
                        "status": "running",
                    }
                )

            team_config["agents"].append({
                "agent_id": agent_id,
                "name": specialist.identity.name,
                "role": specialist.identity.focus,
                "type": "specialist",
                "capabilities": specialist.tools.available if specialist.tools.available else []
            })

            if stage_streamer:
                await stage_streamer.log_event(
                    event_type="setup_task",
                    message=f"{specialist.identity.name} ready",
                    metadata={
                        "task_id": f"agent_{agent_id}",
                        "task_type": "agent",
                        "title": specialist.identity.name,
                        "task_index": task_index,
                        "task_total": agent_total,
                        "status": "completed",
                    }
                )

        return team_config

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _scope_to_dict(self, scope: ScopeRecommendation) -> Dict[str, Any]:
        """Convert ScopeRecommendation to dict for JSON serialization."""
        return {
            "scopes": [
                {
                    "entity_type": e.entity_type,
                    "rationale": e.reasoning if hasattr(e, 'reasoning') else e.rationale if hasattr(e, 'rationale') else "",
                    "filters": [f.model_dump() if hasattr(f, 'model_dump') else dict(f) for f in e.filters],
                    "estimated_count": 0,
                    "relevance_level": e.relevance_level,
                    "fields_of_interest": e.fields_of_interest,
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

    def _make_agent_id(self, name: str) -> str:
        """Generate agent ID from name."""
        import re
        agent_id = name.lower()
        agent_id = re.sub(r'[^a-z0-9_-]+', '_', agent_id)
        agent_id = re.sub(r'_+', '_', agent_id).strip('_')
        return agent_id


class _StageAwareLogger:
    """Wrapper that adds stage to all log_event calls."""

    def __init__(self, logger: ScenarioRunLogger, stage: str):
        self._logger = logger
        self._stage = stage

    async def flush(self) -> None:
        """Proxy flush to underlying logger."""
        if hasattr(self._logger, 'flush'):
            await self._logger.flush()

    async def log_event(self, event_type: str, message: str = None, metadata: Optional[dict] = None, agent_id: Optional[str] = None, **kwargs):
        """Log event with stage automatically added to metadata."""
        # Create a copy of metadata to avoid mutation of caller's dict
        metadata = {**metadata} if metadata else {}
        metadata["stage"] = self._stage

        await self._logger.log_event(
            event_type=event_type,
            message=message,
            metadata=metadata,
            agent_id=agent_id,
            **kwargs
        )
