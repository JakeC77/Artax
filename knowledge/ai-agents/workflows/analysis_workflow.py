"""
Analysis Workflow - Multi-stage parallel analysis and scenario execution.

Architecture (Schema + Tools):
  Stage 0: Build Context Package (schema, stats, ranges)
  Stage 1: Build Analysis Plan (with schema + cypher_query tool)
  Stage 2-4: Execute Analysis/Scenarios (with cypher_query tool)
  Stage 5: Persist All Reports
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional

from pydantic_ai import Agent

from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.graphql_logger import ScenarioRunLogger
from app.core.authenticated_graphql_client import run_graphql
from app.tools import TOOL_REGISTRY

from app.workflows.analysis.models import (
    AnalysisPlan, AnalysisEntry, AnalysisResult,
    ScenarioPlanForAnalysis, ScenarioEntry, ScenarioResult,
    UsedQuery,
)
from app.workflows.analysis.prompts import (
    ANALYSIS_PLANNER_PROMPT,
    ANALYSIS_EXECUTOR_PROMPT,
    SCENARIO_PLANNER_PROMPT,
    SCENARIO_EXECUTOR_PROMPT,
)
from app.workflows.analysis.progress import AnalysisProgressTracker
from app.workflows.analysis.report_persistence import ReportPersistence
from app.workflows.analysis.config import AnalysisWorkflowConfig, load_config

from app.workflows.analysis.context_package import (
    WorkspaceContextPackage,
    build_context_package,
    build_cypher_guide,
)
from app.tools.cypher_result_compactor import create_cypher_compactor

logger = logging.getLogger(__name__)


def _make_budget_deps(
    base_deps: dict,
    max_cypher_calls: int,
    max_web_search_calls: int = 2
) -> dict:
    """Create a deps copy with fresh budget state for an agent phase.

    Each agent phase gets its own budget so parallel executors have independent limits.
    The cypher_query and web_search tools read these keys to enforce call limits.
    """
    phase_deps = {**base_deps}
    # Cypher budget
    phase_deps["cypher_budget_max_calls"] = max_cypher_calls
    phase_deps["cypher_budget_state"] = {
        "calls_made": 0,
        "total_results_returned": 0,
        "queries": [],
    }
    # Web search budget
    phase_deps["web_search_budget_max_calls"] = max_web_search_calls
    phase_deps["web_search_budget_state"] = {
        "calls_made": 0,
        "queries": [],
    }
    return phase_deps


class AnalysisWorkflow(BaseWorkflow):
    """
    Multi-stage workflow for workspace analysis and scenario modeling.

    Flow:
      Event → Build Context Package → Plan (with schema + tools) →
      [Analysis 1: Execute with cypher_query] (parallel)
      [Analysis 2: Execute with cypher_query] (parallel)
      [Analysis 3: Execute with cypher_query] (parallel)
      → Plan Scenarios → Execute Scenarios → Persist All Reports
    """

    workflow_id = "ai:workspace-analyzer"
    engine_pattern = "ai:workspace-analyzer"

    def __init__(self, config: AnalysisWorkflowConfig = None):
        super().__init__(workflow_id=self.workflow_id, name="Workspace Analyzer")
        self.config = config or load_config()
        self.analysis_planner: Optional[Agent] = None

    def _get_history_processors(self) -> list:
        """Get history processors based on config.

        Returns list of history processor functions for agent initialization.
        Currently includes cypher result compaction if enabled.
        """
        processors = []
        if self.config.enable_history_compaction:
            processors.append(
                create_cypher_compactor(
                    sample_rows=self.config.compaction_sample_rows,
                    min_rows_to_compact=self.config.compaction_min_rows,
                )
            )
        return processors

    async def execute(self, event) -> WorkflowResult:
        """Execute the analysis workflow."""
        import time
        from app.models.workflow_event import WorkflowEvent
        start_time = time.time()

        # Extract event data - handle both WorkflowEvent object and dict
        if isinstance(event, WorkflowEvent):
            run_id = event.run_id
            workspace_id = event.workspace_id
            tenant_id = event.tenant_id
            scenario_id = event.scenario_id
            inputs = event.inputs_dict
        else:
            # Dict-style access for backwards compatibility
            run_id = str(event.get("RunId", event.get("run_id", "")))
            workspace_id = str(event.get("WorkspaceId", event.get("workspace_id", "")))
            tenant_id = str(event.get("TenantId", event.get("tenant_id", "")))
            scenario_id = event.get("ScenarioId", event.get("scenario_id"))
            if scenario_id:
                scenario_id = str(scenario_id)
            inputs_raw = event.get("Inputs", event.get("inputs", "{}"))
            try:
                inputs = json.loads(inputs_raw) if isinstance(inputs_raw, str) else inputs_raw
            except json.JSONDecodeError:
                inputs = {}

        intent_package = inputs.get("intent_package", {})

        # Initialize components
        sse_logger = ScenarioRunLogger(run_id=run_id, tenant_id=tenant_id)
        progress = AnalysisProgressTracker(logger=sse_logger)
        persistence = ReportPersistence(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            config=self.config
        )

        # Agent dependencies
        deps = {
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
            "run_id": run_id,
            # Compression settings for cypher_query tool
            "compress_cypher_results": self.config.compress_cypher_results,
            "compress_sample_rows": self.config.compress_sample_rows,
        }

        try:
            # ==========================================
            # PHASE 1: Planning Analysis
            # Build context package + create plan with tools
            # ==========================================
            await progress.phase_started("planning_analysis")

            await sse_logger.log_event(
                event_type="status",
                message="Analysis workflow started",
                metadata={"run_id": run_id, "workspace_id": workspace_id}
            )

            await sse_logger.log_event(
                event_type="message",
                message="Building workspace context (Schema + Tools mode)",
            )

            # Build compact context package
            context_package = await build_context_package(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                timeout_seconds=self.config.context_package_timeout_seconds
            )

            # Store workspace node IDs in deps for cypher_query tool scoping
            deps["workspace_node_ids"] = context_package.workspace_node_ids

            total_nodes = context_package.total_nodes
            total_relationships = context_package.total_relationships

            await sse_logger.log_event(
                event_type="message",
                message=f"Context package built: {total_nodes} nodes, {len(context_package.entity_schemas)} entity types",
                metadata={
                    "entity_counts": context_package.entity_counts,
                    "relationship_count": total_relationships
                }
            )

            # Build analysis plan using schema + tools
            analysis_plan = await self._build_analysis_plan(
                intent_package=intent_package,
                context_package=context_package,
                deps=deps
            )

            await sse_logger.log_event(
                event_type="message",
                message=f"Analysis plan created: {analysis_plan.plan_summary.total_analyses} analyses",
                metadata={"analyses": [a.title for a in analysis_plan.analyses]}
            )

            await progress.phase_complete("planning_analysis")

            # ==========================================
            # PHASE 2: Executing Analysis
            # (Run all analyses in parallel)
            # ==========================================
            await progress.phase_started("executing_analysis")

            total_analyses = len(analysis_plan.analyses)

            async def run_analysis(entry: AnalysisEntry, index: int):
                await progress.task_started(
                    task_type="analysis",
                    task_id=entry.id,
                    task_index=index + 1,
                    task_total=total_analyses,
                    title=entry.title
                )

                analysis_result = await self._execute_analysis(
                    entry=entry,
                    context_package=context_package,
                    intent_package=intent_package,
                    deps=deps
                )

                await progress.task_complete(
                    task_type="analysis",
                    task_id=entry.id,
                    task_index=index + 1,
                    task_total=total_analyses,
                    title=entry.title,
                    success=True
                )

                return {
                    "entry": entry,
                    "analysis_result": analysis_result,
                }

            analysis_tasks = [
                run_analysis(entry, i)
                for i, entry in enumerate(analysis_plan.analyses)
            ]

            analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # Filter successful analyses
            successful_analyses = [
                r for r in analysis_results if not isinstance(r, Exception)
            ]

            if len(successful_analyses) < len(analysis_plan.analyses):
                failed_count = len(analysis_plan.analyses) - len(successful_analyses)
                await sse_logger.log_event(
                    event_type="warning",
                    message=f"{failed_count} analysis(es) failed",
                    metadata={"successful": len(successful_analyses), "total": len(analysis_plan.analyses)}
                )

            await progress.phase_complete("executing_analysis", metadata={
                "completed": len(successful_analyses),
                "total": len(analysis_plan.analyses)
            })

            # ==========================================
            # PHASE 3: Planning Scenarios
            # (Plan scenarios for each completed analysis)
            # ==========================================
            await progress.phase_started("planning_scenarios")

            await sse_logger.log_event(
                event_type="message",
                message=f"Modeling Scenarios for {len(successful_analyses)} Analyses",
            )

            async def plan_scenarios(analysis_data: dict):
                scenario_plan = await self._plan_scenarios(
                    analysis_result=analysis_data["analysis_result"],
                    context_package=context_package,
                    intent_package=intent_package,
                    deps=deps
                )
                return {
                    **analysis_data,
                    "scenario_plan": scenario_plan
                }

            logger.info(f"Starting scenario planning for {len(successful_analyses)} successful analyses")
            scenario_planning_tasks = [plan_scenarios(a) for a in successful_analyses if isinstance(a, dict)]

            planned_results = await asyncio.gather(*scenario_planning_tasks, return_exceptions=True)

            # Log any failures
            for i, result in enumerate(planned_results):
                if isinstance(result, Exception):
                    logger.error(f"Scenario planning failed for analysis {i}: {result}")
                    import traceback
                    logger.error(traceback.format_exception(type(result), result, result.__traceback__))

            # Filter successful scenario plans
            successful_plans: List[dict] = [
                r for r in planned_results if isinstance(r, dict)
            ]
            logger.info(f"Scenario planning complete: {len(successful_plans)} successful, {len(planned_results) - len(successful_plans)} failed")

            # Collect all scenarios from all analyses
            all_scenarios = []
            for plan_data in successful_plans:
                scenario_plan = plan_data["scenario_plan"]
                logger.info(f"Analysis {plan_data['analysis_result'].analysis_id} has {len(scenario_plan.scenarios)} scenarios in plan")
                for scenario in scenario_plan.scenarios:
                    scenario_data = {
                        "scenario": scenario,
                        "parent_analysis": plan_data["analysis_result"],
                    }
                    all_scenarios.append(scenario_data)

            logger.info(f"Total scenarios to execute: {len(all_scenarios)}")
            await progress.phase_complete("planning_scenarios", metadata={
                "scenarios_planned": len(all_scenarios)
            })

            # ==========================================
            # PHASE 4: Executing Scenarios
            # (Execute all scenarios in parallel)
            # ==========================================
            await progress.phase_started("executing_scenarios")

            total_scenarios_to_run = len(all_scenarios)
            scenario_results_all: List[ScenarioResult] = []

            if all_scenarios:
                async def run_scenario(scenario_data: dict, index: int):
                    scenario = scenario_data["scenario"]

                    await progress.task_started(
                        task_type="scenario",
                        task_id=scenario.scenario_id,
                        task_index=index + 1,
                        task_total=total_scenarios_to_run,
                        title=scenario.title
                    )

                    try:
                        result = await self._execute_scenario(
                            scenario=scenario,
                            parent_analysis=scenario_data["parent_analysis"],
                            context_package=context_package,
                            intent_package=intent_package,
                            deps=deps
                        )

                        await progress.task_complete(
                            task_type="scenario",
                            task_id=scenario.scenario_id,
                            task_index=index + 1,
                            task_total=total_scenarios_to_run,
                            title=scenario.title,
                            success=True
                        )
                        return result
                    except Exception as e:
                        await progress.task_complete(
                            task_type="scenario",
                            task_id=scenario.scenario_id,
                            task_index=index + 1,
                            task_total=total_scenarios_to_run,
                            title=scenario.title,
                            success=False,
                            error=str(e)
                        )
                        raise

                scenario_tasks = [
                    run_scenario(s, i)
                    for i, s in enumerate(all_scenarios)
                ]

                scenario_results = await asyncio.gather(*scenario_tasks, return_exceptions=True)

                # Collect successful results (filter out exceptions)
                scenario_results_all = []
                for i, r in enumerate(scenario_results):
                    if isinstance(r, ScenarioResult):
                        scenario_results_all.append(r)
                    elif isinstance(r, Exception):
                        logger.error(f"Scenario {i} execution failed with exception: {type(r).__name__}: {r}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exception(type(r), r, r.__traceback__)}")

            await progress.phase_complete("executing_scenarios", metadata={
                "completed": len(scenario_results_all),
                "total": total_scenarios_to_run
            })

            # ==========================================
            # Persist All Reports (after all phases complete)
            # With graceful degradation - partial failures don't block workflow completion
            # ==========================================
            analysis_report_ids = {}
            persistence_errors = []
            persisted_scenario_count = 0

            # Persist each analysis report (each gets its own WorkspaceAnalysis)
            for plan_data in successful_plans:
                analysis_result = plan_data["analysis_result"]
                try:
                    # Create WorkspaceAnalysis using actual analysis title/description
                    workspace_analysis_id = await persistence.create_workspace_analysis(
                        title=analysis_result.title,
                        description=analysis_result.executive_summary
                    )
                    logger.info(f"Created WorkspaceAnalysis {workspace_analysis_id} for: {analysis_result.title}")

                    # Persist the analysis report
                    report_id = await persistence.persist_analysis_report(
                        analysis_result,
                        workspace_analysis_id=workspace_analysis_id
                    )
                    analysis_report_ids[analysis_result.analysis_id] = report_id
                    logger.info(f"Persisted analysis report {report_id} for: {analysis_result.title}")
                except Exception as e:
                    error_msg = f"Failed to persist analysis '{analysis_result.title}': {e}"
                    logger.error(error_msg)
                    persistence_errors.append(error_msg)

            # Persist scenario reports (each creates its own Scenario object)
            for scenario_result in scenario_results_all:
                parent_report_id = analysis_report_ids.get(scenario_result.parent_analysis)
                if parent_report_id:
                    try:
                        # Pass scenario_id=None to force creation of new Scenario for each
                        await persistence.persist_scenario_report(
                            scenario_result,
                            parent_report_id,
                            scenario_id=None
                        )
                        persisted_scenario_count += 1
                        logger.info(f"Persisted scenario report for: {scenario_result.title}")
                    except Exception as e:
                        error_msg = f"Failed to persist scenario '{scenario_result.title}': {e}"
                        logger.error(error_msg)
                        persistence_errors.append(error_msg)

            # Log persistence summary
            if persistence_errors:
                logger.warning(
                    f"Report persistence completed with {len(persistence_errors)} error(s). "
                    f"Successfully persisted: {len(analysis_report_ids)} analyses, {persisted_scenario_count} scenarios"
                )
                await sse_logger.log_event(
                    event_type="warning",
                    message=f"Some reports failed to persist ({len(persistence_errors)} errors)",
                    metadata={"errors": persistence_errors[:5]}  # Limit to first 5 errors
                )

            # ==========================================
            # Workflow Complete
            # ==========================================
            workflow_outputs = {
                "analysis_count": len(successful_analyses),
                "scenario_count": len(scenario_results_all),
                "report_ids": list(analysis_report_ids.values()),
                "persisted_analyses": len(analysis_report_ids),
                "persisted_scenarios": persisted_scenario_count,
            }
            if persistence_errors:
                workflow_outputs["persistence_errors"] = len(persistence_errors)

            try:
                await self._update_run_status(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    status="completed",
                    outputs=workflow_outputs
                )
            except Exception as e:
                # Log but don't fail the workflow if status update fails
                logger.error(f"Failed to update run status to 'completed': {e}")

            await sse_logger.log_event(
                event_type="complete",
                message="Analysis workflow completed successfully",
                metadata={
                    "analyses_completed": len(successful_analyses),
                    "scenarios_completed": len(scenario_results_all),
                    "reports_created": len(analysis_report_ids) + persisted_scenario_count,
                    "persistence_errors": len(persistence_errors) if persistence_errors else 0
                }
            )

            duration = time.time() - start_time
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=f"Completed {len(successful_analyses)} analyses and {len(scenario_results_all)} scenarios",
                duration_seconds=duration
            )

        except Exception as e:
            logger.exception(f"Analysis workflow failed: {e}")

            await sse_logger.log_event(
                event_type="error",
                message=f"Workflow failed: {str(e)}",
                metadata={"error": str(e)}
            )

            try:
                await self._update_run_status(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    status="failed",
                    outputs={"error": str(e)}
                )
            except Exception as status_error:
                # Log but don't mask the original error
                logger.error(f"Failed to update run status to 'failed': {status_error}")

            duration = time.time() - start_time
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=str(e),
                duration_seconds=duration
            )

    # ==========================================
    # Stage Implementations
    # ==========================================

    async def _build_analysis_plan(
        self,
        intent_package: Dict[str, Any],
        context_package: WorkspaceContextPackage,
        deps: Dict[str, Any]
    ) -> AnalysisPlan:
        """Build analysis plan using schema + cypher_query tool.

        Agents receive compact schema context (entity types, properties, ranges)
        and use cypher_query tool for on-demand data access.
        """
        import time
        planner_start = time.time()

        logger.info(f"Creating planner agent with model: {self.config.planner_model}")

        # Build context and guide strings
        context_str = context_package.to_prompt_string()
        cypher_guide = build_cypher_guide(context_package, labels_exist=context_package.labels_exist_in_graph)

        system_prompt = ANALYSIS_PLANNER_PROMPT.format(
            intent_package=json.dumps(intent_package, indent=2),
            context_package=context_str,
            cypher_guide=cypher_guide
        )
        logger.info(f"System prompt length: {len(system_prompt):,} chars")

        # Tools come from config (cypher_query should be in planning_tools)
        tools = list(self.config.planning_tools)
        resolved_tools = [t for t in tools if t in TOOL_REGISTRY]

        # Get history processors for context compaction
        history_processors = self._get_history_processors()

        planner = Agent(
            model=self.config.planner_model.create(),
            system_prompt=system_prompt,
            output_type=AnalysisPlan,
            tools=[TOOL_REGISTRY[t] for t in resolved_tools],
            deps_type=dict,
            history_processors=history_processors if history_processors else None,
        )
        planner.model_settings = self.config.planner_model.get_model_settings()

        logger.info(f"Starting planner.run() with {len(resolved_tools)} tools...")

        planner_deps = _make_budget_deps(
            deps,
            max_cypher_calls=self.config.planner_max_cypher_calls,
            max_web_search_calls=self.config.planner_max_web_search_calls
        )

        result = await planner.run(
            "Explore the workspace data using cypher_query, then create an analysis plan.",
            deps=planner_deps
        )
        plan = result.output

        planner_elapsed = time.time() - planner_start
        budget = planner_deps.get("cypher_budget_state", {})

        # Debug: Log what the planner actually returned
        logger.info(f"Planner returned {len(plan.analyses)} analyses")
        for i, analysis in enumerate(plan.analyses):
            logger.info(f"  Analysis {i+1}: {analysis.id} - {analysis.title}")
        logger.info(
            f"Planner completed in {planner_elapsed:.1f}s — "
            f"budget: {budget.get('calls_made', 0)}/{self.config.planner_max_cypher_calls} calls, "
            f"{budget.get('total_results_returned', 0)} total results"
        )

        # Enforce config limits
        if len(plan.analyses) > self.config.max_analyses:
            logger.warning(f"Limiting analyses from {len(plan.analyses)} to {self.config.max_analyses} (config limit)")
            plan.analyses = plan.analyses[:self.config.max_analyses]
            plan.plan_summary.total_analyses = len(plan.analyses)

        return plan

    async def _execute_analysis(
        self,
        entry: AnalysisEntry,
        context_package: WorkspaceContextPackage,
        intent_package: Dict[str, Any],
        deps: Dict[str, Any]
    ) -> AnalysisResult:
        """Execute a single analysis using schema + cypher_query tool."""
        import time
        exec_start = time.time()

        # Build context strings
        context_str = context_package.to_prompt_string()
        cypher_guide = build_cypher_guide(context_package, labels_exist=context_package.labels_exist_in_graph)

        logger.info(f"Creating analysis executor with model: {self.config.executor_model}")

        # Tools come from config (cypher_query should be in analysis_tools)
        tools = list(self.config.analysis_tools)
        resolved_tools = [t for t in tools if t in TOOL_REGISTRY]

        # Get history processors for context compaction
        history_processors = self._get_history_processors()

        executor = Agent(
            model=self.config.executor_model.create(),
            output_type=AnalysisResult,
            tools=[TOOL_REGISTRY[t] for t in resolved_tools],
            deps_type=dict,
            history_processors=history_processors if history_processors else None,
        )
        executor.model_settings = self.config.executor_model.get_model_settings()

        prompt = ANALYSIS_EXECUTOR_PROMPT.format(
            analysis_spec=json.dumps(entry.model_dump(), indent=2),
            context_package=context_str,
            cypher_guide=cypher_guide,
            intent_package=json.dumps(intent_package, indent=2)
        )

        logger.info(f"Starting analysis executor for {entry.id}")
        logger.info(f"  Prompt length: {len(prompt):,} chars")

        executor_deps = _make_budget_deps(
            deps,
            max_cypher_calls=self.config.executor_max_cypher_calls,
            max_web_search_calls=self.config.executor_max_web_search_calls
        )

        result = await executor.run(prompt, deps=executor_deps)

        exec_elapsed = time.time() - exec_start
        budget = executor_deps.get("cypher_budget_state", {})
        logger.info(
            f"Analysis {entry.id} completed in {exec_elapsed:.1f}s — "
            f"budget: {budget.get('calls_made', 0)}/{self.config.executor_max_cypher_calls} calls, "
            f"{budget.get('total_results_returned', 0)} total results"
        )

        # Extract used queries from budget state and attach to result
        analysis_result = result.output
        if budget and "queries" in budget:
            analysis_result.used_queries = [
                UsedQuery(
                    query=q["query"],
                    result_count=q["result_count"],
                    truncated=q.get("truncated", False)
                )
                for q in budget["queries"]
            ]
            logger.info(f"Captured {len(analysis_result.used_queries)} queries for analysis {entry.id}")

        return analysis_result

    async def _plan_scenarios(
        self,
        analysis_result: AnalysisResult,
        context_package: WorkspaceContextPackage,
        intent_package: Dict[str, Any],
        deps: Dict[str, Any]
    ) -> ScenarioPlanForAnalysis:
        """Plan scenarios for analysis using schema + cypher_query tool."""
        import time
        plan_start = time.time()

        context_str = context_package.to_prompt_string()
        cypher_guide = build_cypher_guide(context_package, labels_exist=context_package.labels_exist_in_graph)

        logger.info(f"Creating scenario planner with model: {self.config.scenario_planner_model}")

        # Tools come from config (cypher_query should be in scenario_planning_tools)
        tools = list(self.config.scenario_planning_tools)
        resolved_tools = [t for t in tools if t in TOOL_REGISTRY]

        # Get history processors for context compaction
        history_processors = self._get_history_processors()

        planner = Agent(
            model=self.config.scenario_planner_model.create(),
            output_type=ScenarioPlanForAnalysis,
            tools=[TOOL_REGISTRY[t] for t in resolved_tools],
            deps_type=dict,
            history_processors=history_processors if history_processors else None,
        )
        planner.model_settings = self.config.scenario_planner_model.get_model_settings()

        # Format used queries for prompt
        used_queries_str = "\n".join(
            f"- Query: `{q.query}`\n  Results: {q.result_count}{' (truncated)' if q.truncated else ''}"
            for q in analysis_result.used_queries
        ) if analysis_result.used_queries else "No queries were executed during the parent analysis."

        prompt = SCENARIO_PLANNER_PROMPT.format(
            intent_package=json.dumps(intent_package, indent=2),
            analysis_result=json.dumps(analysis_result.model_dump(), indent=2),
            context_package=context_str,
            cypher_guide=cypher_guide,
            used_queries=used_queries_str
        )

        logger.info(f"Starting scenario planner for analysis {analysis_result.analysis_id}")

        planner_deps = _make_budget_deps(
            deps,
            max_cypher_calls=self.config.scenario_planner_max_cypher_calls,
            max_web_search_calls=self.config.scenario_planner_max_web_search_calls
        )

        result = await planner.run(prompt, deps=planner_deps)
        plan = result.output

        plan_elapsed = time.time() - plan_start
        budget = planner_deps.get("cypher_budget_state", {})
        logger.info(
            f"Scenario planning completed in {plan_elapsed:.1f}s - {len(plan.scenarios)} scenarios — "
            f"budget: {budget.get('calls_made', 0)}/{self.config.scenario_planner_max_cypher_calls} calls, "
            f"{budget.get('total_results_returned', 0)} total results"
        )

        # Enforce limits
        if len(plan.scenarios) > self.config.max_scenarios_per_analysis:
            plan.scenarios = plan.scenarios[:self.config.max_scenarios_per_analysis]

        return plan

    async def _execute_scenario(
        self,
        scenario: ScenarioEntry,
        parent_analysis: AnalysisResult,
        context_package: WorkspaceContextPackage,
        intent_package: Dict[str, Any],
        deps: Dict[str, Any]
    ) -> ScenarioResult:
        """Execute a single scenario using schema + cypher_query tool."""
        import time
        exec_start = time.time()

        context_str = context_package.to_prompt_string()
        cypher_guide = build_cypher_guide(context_package, labels_exist=context_package.labels_exist_in_graph)

        logger.info(f"Creating scenario executor with model: {self.config.scenario_executor_model}")

        # Tools come from config (cypher_query should be in scenario_execution_tools)
        tools = list(self.config.scenario_execution_tools)
        resolved_tools = [t for t in tools if t in TOOL_REGISTRY]

        # Get history processors for context compaction
        history_processors = self._get_history_processors()

        executor = Agent(
            model=self.config.scenario_executor_model.create(),
            output_type=ScenarioResult,
            tools=[TOOL_REGISTRY[t] for t in resolved_tools],
            deps_type=dict,
            history_processors=history_processors if history_processors else None,
        )
        executor.model_settings = self.config.scenario_executor_model.get_model_settings()

        # Format used queries from parent analysis for prompt
        used_queries_str = "\n".join(
            f"- Query: `{q.query}`\n  Results: {q.result_count}{' (truncated)' if q.truncated else ''}"
            for q in parent_analysis.used_queries
        ) if parent_analysis.used_queries else "No queries were executed during the parent analysis."

        prompt = SCENARIO_EXECUTOR_PROMPT.format(
            scenario_spec=json.dumps(scenario.model_dump(), indent=2),
            parent_analysis=json.dumps(parent_analysis.model_dump(), indent=2),
            context_package=context_str,
            cypher_guide=cypher_guide,
            intent_package=json.dumps(intent_package, indent=2),
            used_queries=used_queries_str
        )

        logger.info(f"Starting scenario executor for {scenario.scenario_id}")

        executor_deps = _make_budget_deps(
            deps,
            max_cypher_calls=self.config.scenario_executor_max_cypher_calls,
            max_web_search_calls=self.config.scenario_executor_max_web_search_calls
        )

        result = await executor.run(prompt, deps=executor_deps)

        exec_elapsed = time.time() - exec_start
        budget = executor_deps.get("cypher_budget_state", {})
        logger.info(
            f"Scenario {scenario.scenario_id} completed in {exec_elapsed:.1f}s — "
            f"budget: {budget.get('calls_made', 0)}/{self.config.scenario_executor_max_cypher_calls} calls, "
            f"{budget.get('total_results_returned', 0)} total results"
        )
        return result.output

    async def _update_run_status(
        self,
        run_id: str,
        tenant_id: str,
        status: str,
        outputs: Dict[str, Any]
    ):
        """Update the scenario run status via GraphQL."""
        mutation = """
        mutation UpdateScenarioRun($runId: UUID!, $status: String!, $outputs: String) {
            updateScenarioRun(runId: $runId, status: $status, outputs: $outputs)
        }
        """
        await run_graphql(
            mutation,
            {
                "runId": run_id,
                "status": status,
                "outputs": json.dumps(outputs)
            },
            tenant_id=tenant_id
        )
