from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, Union
from enum import Enum

# ============================================
# Analysis Plan Models (Stage 1 Output)
# ============================================

class SuggestedQuery(BaseModel):
    """A Cypher query suggested by the planner for the executor.

    The planner analyzes the workspace context and suggests queries that
    will help the executor gather the data needed for analysis. The executor
    can use these as-is, modify them, or write additional queries.
    """
    query_id: str = Field(description="Unique identifier for this query")
    description: str = Field(description="What this query retrieves and why it's useful")
    cypher: str = Field(description="The Cypher query to execute")
    expected_columns: List[str] = Field(
        default_factory=list,
        description="Expected columns/fields in the result"
    )


class AnalysisEntry(BaseModel):
    """Single analysis definition from planner.

    Agents use cypher_query tool for on-demand data access instead of
    receiving pre-filtered data.
    """
    id: str
    type: str  # e.g., "utilization_concentration", "cost_driver_analysis"
    title: str
    strategic_rationale: str = Field(
        description="Why this analysis is critical to the intent and what decisions it informs"
    )
    key_patterns_observed: List[str] = Field(
        description="Patterns the planner identified that justify this analysis"
    )
    analysis_approach: str = Field(
        description="How the executor should approach this analysis"
    )
    expected_insights: List[str] = Field(
        description="What findings this analysis should surface"
    )

    # Suggested Cypher queries for the executor
    suggested_queries: List[SuggestedQuery] = Field(
        description="Cypher queries the executor should run to gather data"
    )

    # Key metrics to calculate
    key_metrics: List[str] = Field(
        default_factory=list,
        description="Specific metrics the executor should calculate"
    )


class AnalysisPlanSummary(BaseModel):
    """Summary of analysis plan."""
    total_analyses: int
    execution_approach: str = Field(
        default="All analyses execute in parallel using cypher_query tool for data access"
    )


class AnalysisPlan(BaseModel):
    """Output from Analysis Planner agent."""
    plan_summary: AnalysisPlanSummary
    analyses: List[AnalysisEntry]  # 1-3 analyses

# ============================================
# Analysis Execution Models (Stage 3 Output)
# ============================================

class BlockType(str, Enum):
    RICH_TEXT = "rich_text"
    SINGLE_METRIC = "single_metric"
    MULTI_METRIC = "multi_metric"
    INSIGHT_CARD = "insight_card"
    DATA_GRID = "data_grid"
    COMPARISON_TABLE = "comparison_table"

class RichTextContent(BaseModel):
    """Content for rich_text block."""
    markdown: str

class SingleMetricContent(BaseModel):
    """Content for single_metric block."""
    label: str
    value: str
    unit: Optional[str] = None
    trend: Optional[str] = None  # "up", "down", "flat"

class MetricItem(BaseModel):
    """Single metric in a multi-metric block."""
    label: str
    value: str
    unit: Optional[str] = None
    trend: Optional[str] = None
    baseline: Optional[str] = None
    delta: Optional[str] = None

class MultiMetricContent(BaseModel):
    """Content for multi_metric block."""
    title: Optional[str] = None
    metrics: List[MetricItem]

class InsightCardContent(BaseModel):
    """Content for insight_card block."""
    badge: Optional[str] = None  # "Critical", "Warning", "Info", "Opportunity"
    title: str
    body: str
    severity: Optional[str] = None  # "critical", "warning", "info"

class ColumnDef(BaseModel):
    """Column definition for data grids/tables.

    Accepts both verbose format {"key": "metric", "label": "Metric"}
    and simple format {"label": "Metric"} (key auto-generated from label).
    """
    key: str = Field(default="", description="Column key/identifier (auto-generated from label if empty)")
    label: str = Field(description="Display label for the column")

    @model_validator(mode="after")
    def auto_generate_key(self) -> "ColumnDef":
        if not self.key:
            # Convert label to snake_case key: "Paid Amount" -> "paid_amount"
            self.key = self.label.lower().replace(" ", "_").replace("-", "_")
        return self


class RowValue(BaseModel):
    """Single value in a table row."""
    column_key: str = Field(description="Column key this value belongs to")
    value: str = Field(description="The cell value as string")


class TableRow(BaseModel):
    """Row in a data grid or comparison table.

    Accepts both verbose format {"values": [{"column_key": "x", "value": "y"}]}
    and flat dict format {"Metric": "Total", "Baseline": "$4,950"}.
    """
    values: List[RowValue] = Field(description="List of column values for this row")

    @model_validator(mode="before")
    @classmethod
    def accept_flat_dict(cls, data: Any) -> Any:
        """Convert flat dict rows to the structured RowValue format.

        If the input is a dict without a 'values' key, treat each key-value
        pair as a column_key -> value mapping.
        """
        if isinstance(data, dict) and "values" not in data:
            # Flat dict like {"Metric": "Total", "Baseline": "$4,950"}
            values = [
                {"column_key": str(k), "value": str(v)}
                for k, v in data.items()
            ]
            return {"values": values}
        return data


class DataGridContent(BaseModel):
    """Content for data_grid block (table).

    Gemini-compatible: Uses explicit models for columns and rows.
    """
    title: Optional[str] = None
    columns: List[ColumnDef]
    rows: List[TableRow]
    summary: Optional[str] = None


class ComparisonTableContent(BaseModel):
    """Content for comparison_table block.

    Gemini-compatible: Uses explicit models for columns and rows.
    """
    title: Optional[str] = None
    columns: List[ColumnDef]
    rows: List[TableRow]


class LayoutHints(BaseModel):
    """Layout hints for report blocks.

    Gemini-compatible: Uses explicit fields instead of Dict[str, Any].
    """
    width: Optional[str] = Field(default=None, description="Width hint: '1/3', '1/2', 'full'")
    order: Optional[int] = Field(default=None, description="Display order within section")


class ReportBlockOutput(BaseModel):
    """Block output from agent - will be converted to ReportBlock."""
    block_type: BlockType
    order: int
    layout_hints: Optional[LayoutHints] = None
    source_refs: List[str] = Field(default_factory=list)  # References to source_ids

    # Content - one of these based on block_type
    content: Union[
        RichTextContent,
        SingleMetricContent,
        MultiMetricContent,
        InsightCardContent,
        DataGridContent,
        ComparisonTableContent
    ]

class SectionType(str, Enum):
    """Section types for Analysis Reports."""
    EXECUTIVE_SUMMARY = "executive_summary"
    CORE_ANALYSIS = "core_analysis"
    DETAILED_FINDINGS = "detailed_findings"
    RECOMMENDATIONS = "recommendations"
    AUDIT_TRAIL = "audit_trail"
    # Note: SOURCES section removed - sources are tracked via the sources list + source_refs in blocks


class ScenarioSectionType(str, Enum):
    """Section types for Scenario Reports.

    Scenarios are projections ("what happens if?") not discoveries,
    so they use different section semantics than analysis reports.
    """
    SCENARIO_OVERVIEW = "scenario_overview"  # What is being modeled and why
    SCENARIO_OUTCOMES = "scenario_outcomes"  # What the model produces (comparisons, projections)
    DRIVERS_SENSITIVITIES = "drivers_sensitivities"  # Which assumptions matter most
    RECOMMENDATIONS = "recommendations"  # Decision implications
    METHODOLOGY = "methodology"  # Calculation logic, assumptions, verification
    # Note: SOURCES section removed - sources are tracked via the sources list + source_refs in blocks


class ReportSectionOutput(BaseModel):
    """Section output from Analysis agent - will be converted to ReportSection."""
    section_type: SectionType
    header: str
    order: int
    blocks: List[ReportBlockOutput]


class ScenarioSectionOutput(BaseModel):
    """Section output from Scenario agent - uses scenario-specific section types."""
    section_type: ScenarioSectionType
    header: str
    order: int
    blocks: List[ReportBlockOutput]

class SourceType(str, Enum):
    EXTERNAL_WEB = "external_web"  # ONLY use if web_search tool was actually called
    UPLOADED_FILE = "uploaded_file"
    WORKSPACE_GRAPH = "workspace_graph"
    PARENT_ANALYSIS = "parent_analysis"

class SourceMetadata(BaseModel):
    """Metadata for a source/citation.

    Gemini-compatible: Uses explicit fields instead of Dict[str, Any].
    """
    author: Optional[str] = None
    date: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    node_type: Optional[str] = Field(default=None, description="For workspace_graph sources")
    node_id: Optional[str] = Field(default=None, description="For workspace_graph sources")
    query: Optional[str] = Field(default=None, description="Query used to retrieve this source")


class UsedQuery(BaseModel):
    """Record of a Cypher query executed during analysis.

    Stored in AnalysisResult so that downstream phases (scenario planning/execution)
    can reference the same queries to ensure data consistency.
    """
    query: str = Field(description="The Cypher query that was executed")
    result_count: int = Field(description="Number of results returned by this query")
    truncated: bool = Field(default=False, description="Whether results were truncated due to limits")


class SourceOutput(BaseModel):
    """Source/citation output from agent - will be converted to Source.

    Gemini-compatible: Uses SourceMetadata instead of Dict[str, Any].
    """
    source_id: str  # Temporary ID for cross-referencing in blocks
    source_type: SourceType
    uri: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[SourceMetadata] = None

class AnalysisResult(BaseModel):
    """Complete output from Analysis Executor agent."""
    analysis_id: str
    analysis_type: str
    title: str
    description: str = Field(
        description="Short 1-2 sentence description suitable for card/list view (100-200 chars)"
    )

    # Report structure
    sections: List[ReportSectionOutput]
    sources: List[SourceOutput]

    # Quick reference
    executive_summary: str = Field(
        description="Longer 2-3 sentence summary of key findings for report header"
    )
    key_findings: List[str]

    # Query tracking for downstream phases (scenario planning/execution)
    # This field is populated AFTER agent execution, not by the agent itself
    used_queries: List[UsedQuery] = Field(
        default_factory=list,
        description="Cypher queries executed during this analysis. Populated post-execution for scenario phases."
    )

    @field_validator('sections')
    @classmethod
    def validate_all_sections_present(cls, sections: List[ReportSectionOutput]) -> List[ReportSectionOutput]:
        """Ensure all 5 required sections are present."""
        required = {
            SectionType.EXECUTIVE_SUMMARY,
            SectionType.CORE_ANALYSIS,
            SectionType.DETAILED_FINDINGS,
            SectionType.RECOMMENDATIONS,
            SectionType.AUDIT_TRAIL,
            # SOURCES section removed - sources tracked via sources list + source_refs
        }
        present = {s.section_type for s in sections}
        missing = required - present
        if missing:
            raise ValueError(f"Missing required sections: {[m.value for m in missing]}")
        return sections

# ============================================
# Scenario Plan Models (Stage 4 Output)
# ============================================

class ScenarioVariable(BaseModel):
    """Variable being modified in scenario."""
    variable: str
    description: str
    scenario_value: Any
    type: str  # "assumption", "data_from_analysis", "configuration_choice", etc.
    rationale: str
    source_refs: List[str] = Field(default_factory=list)

class FixedAssumption(BaseModel):
    """Assumption held constant in scenario."""
    assumption: str
    source_refs: List[str]

class ExpectedOutcome(BaseModel):
    """Expected outcome to calculate in scenario."""
    outcome: str
    description: str
    calculation_approach: str
    calculation_source_refs: List[str]
    comparison_to_baseline: str

class BaselineComparison(BaseModel):
    """Baseline state for comparison."""
    baseline_description: str
    baseline_annual_cost: Optional[str] = None
    baseline_calculation: Optional[str] = None
    source_refs: List[str]
    key_differences: List[str]

class ScenarioApproach(BaseModel):
    """What this scenario models."""
    what_varies: str
    specific_configuration: str
    rationale: str

class ScenarioEntry(BaseModel):
    """Single scenario definition from planner."""
    scenario_id: str
    parent_analysis: str
    scenario_type: str  # "policy_simulation", "configuration_comparison", etc.
    title: str
    purpose: str
    scenario_approach: ScenarioApproach
    key_variables: List[ScenarioVariable]
    fixed_assumptions: List[FixedAssumption]
    expected_outcomes: List[ExpectedOutcome]
    baseline_comparison: BaselineComparison

class AnalysisScenarioCount(BaseModel):
    """Count of scenarios for a specific analysis.

    Gemini-compatible: Uses explicit fields instead of Dict[str, int].
    """
    analysis_id: str = Field(description="ID of the parent analysis")
    scenario_count: int = Field(description="Number of scenarios for this analysis")


class ScenarioPlanSummary(BaseModel):
    """Summary of scenario plan.

    Gemini-compatible: Uses List[AnalysisScenarioCount] instead of Dict[str, int].
    """
    total_scenarios: int
    scenarios_by_analysis: List[AnalysisScenarioCount]
    execution_approach: str

class ScenarioPlan(BaseModel):
    """Output from Scenario Planner agent."""
    plan_summary: ScenarioPlanSummary
    scenarios: List[ScenarioEntry]  # 0-9 scenarios
    sources: List[SourceOutput]

# ============================================
# Scenario Execution Models (Stage 5 Output)
# ============================================

class ScenarioResult(BaseModel):
    """Complete output from Scenario Executor agent."""
    scenario_id: str
    parent_analysis: str
    scenario_type: str
    title: str
    description: str = Field(
        description="Short 1-2 sentence description suitable for card/list view (100-200 chars)"
    )

    # Report structure (scenario-specific sections)
    sections: List[ScenarioSectionOutput]
    sources: List[SourceOutput]

    # Quick reference
    scenario_summary: str = Field(
        description="2-3 sentence summary of the scenario and its key outcomes"
    )
    key_outcomes: List[str]
    recommendations: List[str]

    @field_validator('sections')
    @classmethod
    def validate_all_sections_present(cls, sections: List[ScenarioSectionOutput]) -> List[ScenarioSectionOutput]:
        """Ensure all 5 required scenario sections are present."""
        required = {
            ScenarioSectionType.SCENARIO_OVERVIEW,
            ScenarioSectionType.SCENARIO_OUTCOMES,
            ScenarioSectionType.DRIVERS_SENSITIVITIES,
            ScenarioSectionType.RECOMMENDATIONS,
            ScenarioSectionType.METHODOLOGY,
            # SOURCES section removed - sources tracked via sources list + source_refs
        }
        present = {s.section_type for s in sections}
        missing = required - present
        if missing:
            raise ValueError(f"Missing required scenario sections: {[m.value for m in missing]}")
        return sections

# ============================================
# Scenario Plan for Single Analysis
# ============================================

class ScenarioPlanForAnalysis(BaseModel):
    """Scenario plan for a single analysis (0-3 scenarios)."""
    parent_analysis_id: str
    plan_summary: ScenarioPlanSummary
    scenarios: List[ScenarioEntry]  # 0-3 scenarios
    sources: List[SourceOutput]
