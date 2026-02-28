"""Configuration for Analysis Workflow.

This module provides per-workflow configuration for the analysis workflow,
supporting multi-provider model selection via YAML config files.

Usage:
    from app.workflows.analysis.config import load_config

    config = load_config()
    model_instance = config.planner_model.create()
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.workflow_config import ModelSpec


class AnalysisWorkflowConfig(BaseModel):
    """Configuration for analysis workflow."""

    # Model selection - using ModelSpec for multi-provider support
    planner_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for analysis planning",
    )
    executor_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for analysis execution",
    )
    scenario_planner_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for scenario planning",
    )
    scenario_executor_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for scenario execution",
    )

    # Tool configuration
    planning_tools: List[str] = Field(
        default=["calculator", "cypher_query"],
        description="Tools available during planning",
    )
    analysis_tools: List[str] = Field(
        default=["calculator", "web_search", "date_time_utilities", "cypher_query"],
        description="Tools available during analysis",
    )
    scenario_planning_tools: List[str] = Field(
        default=["calculator", "web_search", "cypher_query"],
        description="Tools available during scenario planning",
    )
    scenario_execution_tools: List[str] = Field(
        default=["calculator", "web_search", "cypher_query", "date_time_utilities"],
        description="Tools available during scenario execution",
    )

    # Workflow limits
    max_analyses: int = Field(default=3, ge=1, description="Maximum number of analyses")
    max_scenarios_per_analysis: int = Field(
        default=3, ge=0, description="Maximum scenarios per analysis"
    )
    max_scenarios_total: int = Field(
        default=9, ge=0, description="Maximum total scenarios across all analyses"
    )

    # Execution timeouts (seconds)
    planning_timeout_seconds: int = Field(
        default=180, ge=1, description="Timeout for planning phase"
    )
    analysis_timeout_seconds: int = Field(
        default=300, ge=1, description="Timeout for analysis execution"
    )
    scenario_planning_timeout_seconds: int = Field(
        default=120, ge=1, description="Timeout for scenario planning"
    )
    scenario_timeout_seconds: int = Field(
        default=180, ge=1, description="Timeout for scenario execution"
    )
    graphql_timeout_seconds: int = Field(
        default=60, ge=1, description="Timeout for GraphQL/Cypher queries"
    )

    # Concurrency
    max_parallel_workstreams: int = Field(
        default=3, ge=1, description="Maximum parallel analysis workstreams"
    )
    max_parallel_scenarios_per_analysis: int = Field(
        default=3, ge=1, description="Maximum parallel scenarios per analysis"
    )

    # Feature flags
    enable_web_search: bool = Field(
        default=True, description="Enable web search tool"
    )
    enable_validation: bool = Field(
        default=True, description="Enable result validation"
    )

    # Cypher query configuration
    cypher_query_timeout_seconds: int = Field(
        default=30, ge=1, description="Timeout for individual Cypher queries"
    )
    max_cypher_results: int = Field(
        default=500, ge=1, le=1000, description="Maximum results per Cypher query"
    )
    context_package_timeout_seconds: int = Field(
        default=60, ge=1, description="Timeout for building context package"
    )

    # Cypher result compression (reduces token usage in agent conversation history)
    compress_cypher_results: bool = Field(
        default=False,
        description=(
            "When True, cypher_query returns compressed results (summary + sample rows + aggregates) "
            "instead of full data. Dramatically reduces token usage for multi-query agents."
        ),
    )
    compress_sample_rows: int = Field(
        default=10, ge=1, le=50,
        description="Number of sample rows to include when compress_cypher_results is True",
    )

    # History compaction (post-turn context reduction)
    enable_history_compaction: bool = Field(
        default=True,
        description=(
            "When True, uses a history_processor to compact cypher_query results in message history "
            "after the agent has reasoned about them. Agent sees full data during reasoning, but "
            "history is compacted before next turn to reduce token usage."
        ),
    )
    compaction_sample_rows: int = Field(
        default=10, ge=1, le=50,
        description="Number of sample rows to keep when compacting cypher results in history",
    )
    compaction_min_rows: int = Field(
        default=20, ge=1,
        description="Minimum result size to trigger history compaction (smaller results kept as-is)",
    )

    # Query budget: max cypher_query calls per agent phase
    planner_max_cypher_calls: int = Field(
        default=8, ge=1, le=30,
        description="Maximum cypher_query tool calls for the planner agent",
    )
    executor_max_cypher_calls: int = Field(
        default=10, ge=1, le=30,
        description="Maximum cypher_query tool calls per analysis executor agent",
    )
    scenario_planner_max_cypher_calls: int = Field(
        default=6, ge=1, le=20,
        description="Maximum cypher_query tool calls for scenario planner agent",
    )
    scenario_executor_max_cypher_calls: int = Field(
        default=8, ge=1, le=20,
        description="Maximum cypher_query tool calls per scenario executor agent",
    )
    planner_max_web_search_calls: int = Field(
        default=2, ge=0, le=5,
        description="Maximum web_search tool calls per analysis planner agent",
    )
    executor_max_web_search_calls: int = Field(
        default=2, ge=0, le=5,
        description="Maximum web_search tool calls per analysis executor agent",
    )
    scenario_planner_max_web_search_calls: int = Field(
        default=2, ge=0, le=5,
        description="Maximum web_search tool calls for scenario planner agent",
    )
    scenario_executor_max_web_search_calls: int = Field(
        default=2, ge=0, le=5,
        description="Maximum web_search tool calls per scenario executor agent",
    )


# Module-level cached config
_config: Optional[AnalysisWorkflowConfig] = None


def load_config(config_path: Optional[str] = None) -> AnalysisWorkflowConfig:
    """Load config from YAML file or use defaults.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.

    Returns:
        AnalysisWorkflowConfig instance with validated settings.
    """
    global _config

    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config

    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = AnalysisWorkflowConfig()
            return _config
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = AnalysisWorkflowConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result

    result = AnalysisWorkflowConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> AnalysisWorkflowConfig:
    """Force reload of configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()


__all__ = ["AnalysisWorkflowConfig", "load_config", "reload_config"]
