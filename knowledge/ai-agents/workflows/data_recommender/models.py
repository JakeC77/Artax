"""
Pydantic models for Data Scope Recommendation workflow.

This module defines the data structures for:
1. Agent output (ScopeRecommendation)
2. Filter execution (ScopeExecutionResult)
3. Execution statistics (ExecutionStats)
4. Streaming interview models (ClarificationOption, ClarificationQuestion, ScopePreview)
"""

import uuid
from enum import Enum
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class FilterOperator(str, Enum):
    """
    Filter operators supported by the data scope recommendation system.

    Operators are classified as:
    - API-executable: eq, contains (with string values)
    - Python-side: gt, gte, lt, lte, between, in, is_null, is_not_null, and non-string eq

    Examples:
        >>> FilterOperator.EQ
        'eq'
        >>> FilterOperator.BETWEEN
        'between'
    """
    # Equality operators
    EQ = "eq"
    NEQ = "neq"

    # Comparison operators (numeric/date)
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"

    # String operators
    CONTAINS = "contains"

    # List operators
    IN = "in"

    # Null check operators
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class FieldOfInterest(BaseModel):
    """
    A field/property of interest with justification for why it's relevant.

    This provides transparency to the user about why specific fields
    were selected for their data scope.

    Example:
        >>> FieldOfInterest(
        ...     field="averageWholesalePrice",
        ...     justification="Key pricing metric for identifying high-cost medications"
        ... )
    """
    field: str = Field(
        description="The property/field name (e.g., 'averageWholesalePrice', 'patientId')"
    )
    justification: str = Field(
        description="Why this field is relevant to the user's intent"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "field": "averageWholesalePrice",
                    "justification": "Key pricing metric for identifying high-cost medications"
                },
                {
                    "field": "patientOutcome",
                    "justification": "Required to analyze effectiveness of treatments"
                },
                {
                    "field": "prescriptionDate",
                    "justification": "Needed for time-based filtering of recent prescriptions"
                }
            ]
        }


class EntityFilter(BaseModel):
    """
    A filter to apply to an entity's property.

    The value field is polymorphic to support different data types.

    Examples:
        String filter:
        >>> EntityFilter(
        ...     property="status",
        ...     operator=FilterOperator.EQ,
        ...     value="active"
        ... )

        Numeric filter:
        >>> EntityFilter(
        ...     property="salary",
        ...     operator=FilterOperator.GT,
        ...     value=100000
        ... )

        Date range filter:
        >>> EntityFilter(
        ...     property="hireDate",
        ...     operator=FilterOperator.BETWEEN,
        ...     value=["2020-01-01", "2023-12-31"]
        ... )

        List membership:
        >>> EntityFilter(
        ...     property="department",
        ...     operator=FilterOperator.IN,
        ...     value=["Engineering", "Product"]
        ... )
    """
    property: str = Field(
        description="The entity property name to filter on (e.g., 'status', 'hireDate', 'salary')"
    )
    operator: FilterOperator = Field(
        description="The comparison operator to apply"
    )
    value: Union[str, int, float, bool, List[Union[str, int, float]], None] = Field(
        description="The value to compare against. Type depends on property and operator. "
                    "List for 'in' and 'between' operators, None for is_null/is_not_null."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent's explanation for why this filter is needed"
    )
    # Frontend SSE integration fields
    id: str = Field(
        default="",
        description="Stable content-based identifier for frontend tracking"
    )
    display_text: str = Field(
        default="",
        description="Human-readable filter description (e.g., 'status = active')"
    )

    def model_post_init(self, __context) -> None:
        """Generate id and display_text if not provided."""
        if not self.id:
            object.__setattr__(self, 'id', self._generate_id())
        if not self.display_text:
            object.__setattr__(self, 'display_text', self._generate_display_text())

    def _generate_id(self) -> str:
        """Generate a stable content-based identifier for this filter."""
        import hashlib
        content = f"{self.property}:{self.operator.value}:{self.value}"
        return f"filter-{self.property}-{hashlib.md5(content.encode()).hexdigest()[:8]}"

    def _generate_display_text(self) -> str:
        """Generate human-readable filter description."""
        op_map = {
            "eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
            "contains": "contains", "in": "in", "between": "between",
            "is_null": "is null", "is_not_null": "is not null"
        }
        op = op_map.get(self.operator.value, self.operator.value)
        if self.operator.value in ("is_null", "is_not_null"):
            return f"{self.property} {op}"
        elif self.operator.value == "between" and isinstance(self.value, list):
            return f"{self.property} {op} {self.value[0]} and {self.value[1]}"
        elif self.operator.value == "in" and isinstance(self.value, list):
            vals = ", ".join(str(v) for v in self.value[:3])
            suffix = "..." if len(self.value) > 3 else ""
            return f"{self.property} {op} [{vals}{suffix}]"
        return f"{self.property} {op} {self.value}"

    def with_entity_context(self, entity_type: str) -> "EntityFilter":
        """Return filter with entity-prefixed ID for cross-entity uniqueness."""
        import hashlib
        content = f"{entity_type}:{self.property}:{self.operator.value}:{self.value}"
        new_id = f"filter-{entity_type.lower()}-{self.property}-{hashlib.md5(content.encode()).hexdigest()[:8]}"
        return self.model_copy(update={"id": new_id})

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "property": "status",
                    "operator": "eq",
                    "value": "active",
                    "reasoning": "User wants only active employees",
                    "id": "filter-status-a1b2c3d4",
                    "display_text": "status = active"
                },
                {
                    "property": "salary",
                    "operator": "gte",
                    "value": 100000,
                    "reasoning": "Filter for senior-level compensation",
                    "id": "filter-salary-e5f6g7h8",
                    "display_text": "salary >= 100000"
                }
            ]
        }


class EntityScope(BaseModel):
    """
    Defines the scope for a single entity type with filters and field prioritization.

    Example:
        >>> EntityScope(
        ...     entity_type="Employee",
        ...     filters=[
        ...         EntityFilter(property="status", operator=FilterOperator.EQ, value="active"),
        ...         EntityFilter(property="salary", operator=FilterOperator.GTE, value=100000)
        ...     ],
        ...     relevance_level="primary",
        ...     fields_of_interest=[
        ...         FieldOfInterest(field="employeeId", justification="Unique identifier for tracking"),
        ...         FieldOfInterest(field="name", justification="Display name for reporting"),
        ...         FieldOfInterest(field="salary", justification="Key metric for compensation analysis"),
        ...     ],
        ...     reasoning="Focusing on high-earning active employees for compensation analysis"
        ... )
    """
    entity_type: str = Field(
        description="The graph entity type (e.g., 'Employee', 'Patient', 'Claim')"
    )
    filters: List[EntityFilter] = Field(
        default_factory=list,
        description="Filters to apply to this entity type"
    )
    relevance_level: str = Field(
        default="primary",
        description="How relevant this entity is to the query: 'primary', 'related', or 'contextual'"
    )
    fields_of_interest: List[FieldOfInterest] = Field(
        default_factory=list,
        description="Which properties of this entity are most relevant to the user's intent, "
                    "with justifications for why each field was selected."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent's explanation for why this entity is included and how it relates to intent"
    )
    # Frontend SSE integration fields
    enabled: bool = Field(
        default=True,
        description="Whether this entity is included in the current scope"
    )
    estimated_count: Optional[int] = Field(
        default=None,
        description="Estimated count of matching records (populated after query validation)"
    )
    query: Optional[str] = Field(
        default=None,
        description="Generated Cypher query for this entity (populated after query generation)"
    )

    def model_post_init(self, __context) -> None:
        """Ensure filters have entity-scoped IDs for cross-entity uniqueness."""
        if self.filters:
            updated_filters = [f.with_entity_context(self.entity_type) for f in self.filters]
            object.__setattr__(self, 'filters', updated_filters)

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "entity_type": "Employee",
                    "filters": [
                        {"property": "status", "operator": "eq", "value": "active"}
                    ],
                    "relevance_level": "primary",
                    "fields_of_interest": [
                        {"field": "employeeId", "justification": "Unique identifier for tracking"},
                        {"field": "name", "justification": "Display name for reporting"},
                        {"field": "department", "justification": "Organizational context for analysis"}
                    ],
                    "reasoning": "Primary entity for workforce analysis",
                    "enabled": True,
                    "estimated_count": 342,
                    "query": "MATCH (e:Employee) WHERE e.status = 'active' RETURN DISTINCT e"
                }
            ]
        }


class RelationshipPath(BaseModel):
    """
    Defines a relationship traversal between entities.

    Example:
        >>> RelationshipPath(
        ...     from_entity="Employee",
        ...     to_entity="Department",
        ...     relationship_type="WORKS_IN",
        ...     reasoning="Connect employees to their departments for org structure context"
        ... )
    """
    from_entity: str = Field(
        description="Source entity type"
    )
    to_entity: str = Field(
        description="Target entity type"
    )
    relationship_type: str = Field(
        description="The relationship type/label in the graph (e.g., 'WORKS_IN', 'MANAGES')"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Why this relationship is relevant to the query"
    )
    # Frontend SSE integration field
    display_label: str = Field(
        default="",
        description="Human-readable label (e.g., 'works in' for WORKS_IN)"
    )

    def model_post_init(self, __context) -> None:
        """Generate display_label if not provided."""
        if not self.display_label:
            # Convert WORKS_IN to "works in"
            readable = self.relationship_type.lower().replace("_", " ")
            object.__setattr__(self, 'display_label', readable)

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "from_entity": "Employee",
                    "to_entity": "Department",
                    "relationship_type": "WORKS_IN",
                    "reasoning": "Provides organizational context",
                    "display_label": "works in"
                }
            ]
        }


class ScopeRecommendation(BaseModel):
    """
    The complete scope recommendation output from the agent.

    This is the primary output model returned by the data scope recommendation agent.

    Example:
        >>> ScopeRecommendation(
        ...     entities=[
        ...         EntityScope(
        ...             entity_type="Employee",
        ...             filters=[
        ...                 EntityFilter(property="status", operator=FilterOperator.EQ, value="active"),
        ...                 EntityFilter(property="salary", operator=FilterOperator.GTE, value=100000)
        ...             ],
        ...             relevance_level="primary",
        ...             fields_of_interest=[
        ...                 FieldOfInterest(field="name", justification="Employee identifier for reporting"),
        ...                 FieldOfInterest(field="salary", justification="Key metric for compensation analysis"),
        ...                 FieldOfInterest(field="hireDate", justification="Tenure context for seniority")
        ...             ]
        ...         )
        ...     ],
        ...     relationships=[],
        ...     summary="Scope includes active employees earning $100k+ for compensation analysis",
        ...     requires_clarification=False
        ... )
    """
    entities: List[EntityScope] = Field(
        description="The entities to include in the scope, with their filters"
    )
    relationships: List[RelationshipPath] = Field(
        default_factory=list,
        description="Relationships to traverse between entities"
    )
    summary: str = Field(
        description="Natural language summary of what this scope includes and why"
    )
    requires_clarification: bool = Field(
        default=False,
        description="True if the agent needs more information from the user"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Questions to ask the user if clarification is needed"
    )
    confidence_level: str = Field(
        default="high",
        description="Agent's confidence in this recommendation: 'high', 'medium', 'low'"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "entities": [
                        {
                            "entity_type": "Employee",
                            "filters": [
                                {"property": "status", "operator": "eq", "value": "active"}
                            ],
                            "relevance_level": "primary",
                            "fields_of_interest": [
                                {"field": "name", "justification": "Employee identifier for display"},
                                {"field": "department", "justification": "Organizational grouping for analysis"}
                            ]
                        }
                    ],
                    "relationships": [],
                    "summary": "Active employees for workforce analysis",
                    "requires_clarification": False,
                    "clarification_questions": [],
                    "confidence_level": "high"
                }
            ]
        }


class EntityExecutionStats(BaseModel):
    """
    Execution statistics for a single entity type.

    Example:
        >>> EntityExecutionStats(
        ...     entity_type="Employee",
        ...     candidates_fetched=1500,
        ...     matches_after_filtering=342,
        ...     api_filters_applied=1,
        ...     python_filters_applied=2
        ... )
    """
    entity_type: str = Field(
        description="The entity type these stats apply to"
    )
    candidates_fetched: int = Field(
        description="Number of nodes fetched from API (after API-side filters)"
    )
    matches_after_filtering: int = Field(
        description="Number of nodes that passed all filters (including Python-side)"
    )
    api_filters_applied: int = Field(
        description="Count of filters executed on API side"
    )
    python_filters_applied: int = Field(
        description="Count of filters executed in Python"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "entity_type": "Employee",
                    "candidates_fetched": 1500,
                    "matches_after_filtering": 342,
                    "api_filters_applied": 1,
                    "python_filters_applied": 2
                }
            ]
        }


class ExecutionStats(BaseModel):
    """
    Overall execution statistics for scope execution.

    Example:
        >>> ExecutionStats(
        ...     total_candidates=1500,
        ...     total_matches=342,
        ...     execution_time_seconds=1.23,
        ...     entity_stats=[
        ...         EntityExecutionStats(
        ...             entity_type="Employee",
        ...             candidates_fetched=1500,
        ...             matches_after_filtering=342,
        ...             api_filters_applied=1,
        ...             python_filters_applied=2
        ...         )
        ...     ]
        ... )
    """
    total_candidates: int = Field(
        description="Total nodes fetched across all entities"
    )
    total_matches: int = Field(
        description="Total nodes that passed filtering across all entities"
    )
    execution_time_seconds: float = Field(
        description="Total time taken to execute the scope"
    )
    entity_stats: List[EntityExecutionStats] = Field(
        default_factory=list,
        description="Per-entity execution statistics"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "total_candidates": 1500,
                    "total_matches": 342,
                    "execution_time_seconds": 1.23,
                    "entity_stats": [
                        {
                            "entity_type": "Employee",
                            "candidates_fetched": 1500,
                            "matches_after_filtering": 342,
                            "api_filters_applied": 1,
                            "python_filters_applied": 2
                        }
                    ]
                }
            ]
        }


class ScopeExecutionResult(BaseModel):
    """
    Result of executing a scope recommendation against the graph.

    This model contains the matching node IDs and execution statistics.

    Example:
        >>> ScopeExecutionResult(
        ...     scope_recommendation=ScopeRecommendation(...),
        ...     matching_node_ids={
        ...         "Employee": ["emp_001", "emp_002", "emp_003"]
        ...     },
        ...     stats=ExecutionStats(
        ...         total_candidates=1500,
        ...         total_matches=3,
        ...         execution_time_seconds=1.23
        ...     ),
        ...     success=True
        ... )
    """
    scope_recommendation: ScopeRecommendation = Field(
        description="The original scope recommendation that was executed"
    )
    matching_node_ids: Dict[str, List[str]] = Field(
        description="Node IDs grouped by entity type. Key is entity type, value is list of node IDs."
    )
    sample_nodes: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Sample nodes with properties for each entity type (first 10 per type for preview)"
    )
    stats: ExecutionStats = Field(
        description="Execution statistics and performance metrics"
    )
    success: bool = Field(
        description="Whether execution completed successfully"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings during execution (e.g., 'Date parsing failed for property X')"
    )
    executed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this scope was executed"
    )
    # Cypher execution fields
    cypher_query: Optional[str] = Field(
        default=None,
        description="The Cypher query that was executed (for debugging and transparency)"
    )
    generation_method: Optional[str] = Field(
        default=None,
        description="How the query was generated: 'deterministic', 'llm', 'llm_corrected', or 'legacy' for old executor"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "scope_recommendation": {
                        "entities": [
                            {
                                "entity_type": "Employee",
                                "filters": [
                                    {"property": "status", "operator": "eq", "value": "active"}
                                ],
                                "relevance_level": "primary"
                            }
                        ],
                        "relationships": [],
                        "summary": "Active employees",
                        "requires_clarification": False,
                        "confidence_level": "high"
                    },
                    "matching_node_ids": {
                        "Employee": ["emp_001", "emp_002", "emp_003"]
                    },
                    "stats": {
                        "total_candidates": 1500,
                        "total_matches": 3,
                        "execution_time_seconds": 1.23,
                        "entity_stats": []
                    },
                    "success": True,
                    "error_message": None,
                    "warnings": []
                }
            ]
        }


# Helper models for GraphQL integration

class GraphNode(BaseModel):
    """
    Represents a graph node from the GraphQL API.

    Example:
        >>> GraphNode(
        ...     id="emp_001",
        ...     labels=["Employee"],
        ...     properties={"name": "John Doe", "status": "active", "salary": 120000}
        ... )
    """
    id: str = Field(
        description="Unique node identifier"
    )
    labels: List[str] = Field(
        description="Node labels/types"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Node properties as key-value pairs"
    )

    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get a property value with fallback to default.

        Args:
            key: Property name
            default: Default value if property doesn't exist

        Returns:
            Property value or default
        """
        return self.properties.get(key, default)

    def has_label(self, label: str) -> bool:
        """
        Check if node has a specific label.

        Args:
            label: Label to check for

        Returns:
            True if node has the label
        """
        return label in self.labels


class GraphPropertyMatchInput(BaseModel):
    """
    GraphQL input type for property matching.

    This is used to construct GraphQL queries with property filters.

    Example:
        >>> GraphPropertyMatchInput(
        ...     key="status",
        ...     value="active",
        ...     match_type="EXACT"
        ... )
    """
    key: str = Field(
        description="Property key to match"
    )
    value: str = Field(
        description="Value to match against (always string for GraphQL API)"
    )
    match_type: str = Field(
        default="EXACT",
        description="Match type: EXACT or CONTAINS"
    )


# =============================================================================
# Streaming Interview Models
# =============================================================================


class ClarificationOption(BaseModel):
    """
    Single option in a clarification question.

    Used by the agent's ask_clarification tool to present structured options
    to the user during the scope interview.

    Example:
        >>> ClarificationOption(
        ...     label="Absolute threshold (> $1,000)",
        ...     description="Fixed dollar amount per prescription",
        ...     recommended=True
        ... )
    """
    label: str = Field(
        description="Short label for the option (e.g., 'Absolute threshold (> $1,000)')"
    )
    description: str = Field(
        description="Explanation of what this option means (e.g., 'Fixed dollar amount per prescription')"
    )
    recommended: bool = Field(
        default=False,
        description="Whether this option is recommended by the agent"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "label": "Absolute threshold (> $1,000)",
                    "description": "Fixed dollar amount per prescription",
                    "recommended": False
                },
                {
                    "label": "Relative threshold (top 10%)",
                    "description": "Percentile-based within your data",
                    "recommended": True
                }
            ]
        }


class ClarificationQuestion(BaseModel):
    """
    Structured clarification question with multiple-choice options.

    The agent uses ask_clarification tool to emit these questions during
    the scope interview. The UI renders them as a card with clickable options.

    Example:
        >>> ClarificationQuestion(
        ...     question_id="high_cost_definition",
        ...     question="How do you want to define 'high-cost' medications?",
        ...     context="This affects which pricing filters I apply.",
        ...     options=[
        ...         ClarificationOption(label="Absolute threshold (> $1,000)", ...),
        ...         ClarificationOption(label="Relative threshold (top 10%)", ...),
        ...     ],
        ...     allows_other=True,
        ...     affects_entities=["Medication", "PricingData"]
        ... )
    """
    question_id: str = Field(
        description="Unique identifier for tracking (e.g., 'high_cost_definition')"
    )
    question: str = Field(
        description="The question text to display to the user"
    )
    context: Optional[str] = Field(
        default=None,
        description="Why we're asking this question (helps user understand importance)"
    )
    options: List[ClarificationOption] = Field(
        description="Available options (2-5 options). UI will add 'Other' automatically."
    )
    allows_other: bool = Field(
        default=True,
        description="Whether to show a free-text 'Other' option"
    )
    affects_entities: List[str] = Field(
        default_factory=list,
        description="Which entities this question impacts (for UI highlighting)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "question_id": "high_cost_definition",
                    "question": "How do you want to define 'high-cost' medications?",
                    "context": "This affects which pricing filters I apply.",
                    "options": [
                        {"label": "Absolute threshold (> $1,000)", "description": "Fixed dollar amount", "recommended": False},
                        {"label": "Relative threshold (top 10%)", "description": "Percentile-based", "recommended": True}
                    ],
                    "allows_other": True,
                    "affects_entities": ["Medication", "PricingData"]
                }
            ]
        }


class ScopePreview(BaseModel):
    """
    Partial scope for visual preview during the interview (not final).

    The agent calls update_scope tool to emit these previews, showing the
    user how the scope is evolving as the conversation progresses.

    Example:
        >>> ScopePreview(
        ...     entities=[EntityScope(entity_type="Employee", ...)],
        ...     relationships=[],
        ...     summary="Active employees with salary > $100k",
        ...     confidence="medium"
        ... )
    """
    entities: List[EntityScope] = Field(
        description="Current entity recommendations"
    )
    relationships: List[RelationshipPath] = Field(
        default_factory=list,
        description="Current relationship recommendations"
    )
    summary: str = Field(
        description="Current understanding in natural language"
    )
    confidence: str = Field(
        default="medium",
        description="Agent's confidence in current scope: 'high', 'medium', 'low'"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "entities": [
                        {
                            "entity_type": "Employee",
                            "filters": [{"property": "status", "operator": "eq", "value": "active"}],
                            "relevance_level": "primary",
                            "fields_of_interest": [
                                {"field": "name", "justification": "Employee identifier for display"},
                                {"field": "salary", "justification": "Key metric for compensation analysis"}
                            ]
                        }
                    ],
                    "relationships": [],
                    "summary": "Active employees with salary filters (pending threshold clarification)",
                    "confidence": "medium"
                }
            ]
        }


# =============================================================================
# Unified Scope State Models (for Build Query / Preview Data UI)
# =============================================================================


class QueryStructure(BaseModel):
    """
    The query definition built by the AI during scoping.

    This represents the logical structure of what data will be retrieved,
    including entities, filters, and relationships.
    """
    primary_entity: Optional[str] = Field(
        default=None,
        description="The main entity type being queried (e.g., 'Employee', 'Plan')"
    )
    entities: List[EntityScope] = Field(
        default_factory=list,
        description="All entities in the query with their filters and fields of interest"
    )
    relationships: List[RelationshipPath] = Field(
        default_factory=list,
        description="Relationships to traverse between entities"
    )

    def get_all_filters(self) -> List[EntityFilter]:
        """Get all filters from all entities (denormalized for easy access)."""
        return [f for e in self.entities for f in e.filters]

    def get_all_fields_of_interest(self) -> List[FieldOfInterest]:
        """Get all fields of interest from all entities."""
        return [foi for e in self.entities for foi in e.fields_of_interest]

    def get_entity(self, entity_type: str) -> Optional[EntityScope]:
        """Get entity scope by type name."""
        return next((e for e in self.entities if e.entity_type == entity_type), None)


class EntityPreviewData(BaseModel):
    """
    Preview data for a single entity type.

    Contains count and sample records for display in the Preview Data tab.
    """
    entity_type: str = Field(
        description="The entity type this preview is for"
    )
    count: int = Field(
        default=0,
        description="Total number of matching records"
    )
    sample_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sample records for preview (first N rows)"
    )
    cypher_query: Optional[str] = Field(
        default=None,
        description="The Cypher query used to fetch this entity (for debugging)"
    )


class ScopeExecutionResults(BaseModel):
    """
    Results from executing the scope query.

    Contains counts, samples, and optionally full node IDs after staging.
    """
    cypher_queries: Dict[str, str] = Field(
        default_factory=dict,
        description="Cypher queries by entity type"
    )
    counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Match counts by entity type"
    )
    samples: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Sample data by entity type (for preview)"
    )
    full_data: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Full node IDs by entity type (only populated after staging)"
    )
    total_matches: int = Field(
        default=0,
        description="Total matching records across all entities"
    )
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Time taken to execute the queries"
    )
    last_executed: Optional[datetime] = Field(
        default=None,
        description="When the scope was last executed for preview"
    )

    def invalidate(self) -> "ScopeExecutionResults":
        """Return a new instance with cleared preview data (for cache invalidation)."""
        return ScopeExecutionResults(
            cypher_queries={},
            counts={},
            samples={},
            full_data=None,
            total_matches=0,
            execution_time_seconds=None,
            last_executed=None
        )


class ScopeMetadata(BaseModel):
    """
    Metadata about the current scope state.

    Includes natural language summary, confidence level, and versioning.
    """
    natural_language_summary: str = Field(
        default="",
        description="Human-readable summary of what the scope includes"
    )
    confidence: str = Field(
        default="medium",
        description="AI confidence level: 'high', 'medium', 'low'"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the scope was last modified"
    )
    version: int = Field(
        default=1,
        description="Increments on each scope update (for optimistic locking)"
    )
    last_update_summary: Optional[str] = Field(
        default=None,
        description="Brief description of the last change (e.g., 'Added Zoloft to medication filter')"
    )


class ScopeUIState(BaseModel):
    """
    UI state hints from the backend.

    These help the frontend render the appropriate UI state.
    """
    active_tab: str = Field(
        default="build_query",
        description="Suggested active tab: 'build_query' or 'preview_data'"
    )
    preview_loading: bool = Field(
        default=False,
        description="Whether preview data is currently being fetched"
    )
    selected_preview_entity: Optional[str] = Field(
        default=None,
        description="Currently selected entity in the preview tab"
    )
    can_stage: bool = Field(
        default=False,
        description="Whether the scope is ready to be staged (high confidence, no pending questions)"
    )
    has_pending_clarification: bool = Field(
        default=False,
        description="Whether there's a pending clarification question"
    )


def compute_scope_diff(old_state: Optional["ScopeState"], new_state: "ScopeState") -> dict:
    """
    Compute changes between scope states for UI highlighting.

    Args:
        old_state: Previous scope state (None if this is the first update)
        new_state: New scope state

    Returns:
        Dict with:
        - changed_entities: List of entity types that changed
        - is_new_entity: True if any entity is completely new
        - added_filter_ids: List of newly added filter IDs
        - added_field_names: List of newly added field names
    """
    result = {
        "changed_entities": [],
        "is_new_entity": False,
        "added_filter_ids": [],
        "added_field_names": []
    }

    # If no old state, everything is new
    if old_state is None:
        result["changed_entities"] = [e.entity_type for e in new_state.query.entities]
        result["is_new_entity"] = len(new_state.query.entities) > 0
        for entity in new_state.query.entities:
            result["added_filter_ids"].extend([f.id for f in entity.filters])
            result["added_field_names"].extend([foi.field for foi in entity.fields_of_interest])
        return result

    # Build lookups for old state
    old_entities = {e.entity_type: e for e in old_state.query.entities}
    old_filter_ids = {f.id for e in old_state.query.entities for f in e.filters}
    old_fields = {
        f"{e.entity_type}:{foi.field}"
        for e in old_state.query.entities
        for foi in e.fields_of_interest
    }

    # Compare new state against old
    for entity in new_state.query.entities:
        if entity.entity_type not in old_entities:
            # Completely new entity
            result["changed_entities"].append(entity.entity_type)
            result["is_new_entity"] = True
            result["added_filter_ids"].extend([f.id for f in entity.filters])
            result["added_field_names"].extend([foi.field for foi in entity.fields_of_interest])
        else:
            # Entity exists - check for changes
            changed = False
            for f in entity.filters:
                if f.id not in old_filter_ids:
                    result["added_filter_ids"].append(f.id)
                    changed = True
            for foi in entity.fields_of_interest:
                key = f"{entity.entity_type}:{foi.field}"
                if key not in old_fields:
                    result["added_field_names"].append(foi.field)
                    changed = True
            if changed:
                result["changed_entities"].append(entity.entity_type)

    return result


class ScopeState(BaseModel):
    """
    Complete scope state for the unified Build Query / Preview Data interface.

    This is the main model sent to the frontend via events. It provides:
    - The current query structure (what filters/entities are selected)
    - Preview execution results (counts and samples)
    - Metadata (summaries, confidence, timestamps)
    - UI state hints

    Example:
        >>> ScopeState(
        ...     query=QueryStructure(
        ...         primary_entity="Employee",
        ...         entities=[EntityScope(entity_type="Employee", ...)]
        ...     ),
        ...     results=ScopeExecutionResults(counts={"Employee": 342}),
        ...     metadata=ScopeMetadata(natural_language_summary="Active employees in Engineering"),
        ...     ui_state=ScopeUIState(can_stage=True)
        ... )
    """
    query: QueryStructure = Field(
        default_factory=QueryStructure,
        description="The query definition (entities, filters, relationships)"
    )
    results: ScopeExecutionResults = Field(
        default_factory=ScopeExecutionResults,
        description="Execution results (counts, samples, node IDs)"
    )
    metadata: ScopeMetadata = Field(
        default_factory=ScopeMetadata,
        description="Metadata (summary, confidence, version)"
    )
    ui_state: ScopeUIState = Field(
        default_factory=ScopeUIState,
        description="UI state hints for the frontend"
    )
    state_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this state version"
    )

    def with_updated_query(
        self,
        entities: Optional[List[EntityScope]] = None,
        relationships: Optional[List[RelationshipPath]] = None,
        primary_entity: Optional[str] = None,
        summary: Optional[str] = None,
        confidence: Optional[str] = None,
        update_summary: Optional[str] = None,
    ) -> "ScopeState":
        """
        Return a new ScopeState with updated query (immutable pattern).

        Invalidates cached preview results since scope changed.
        """
        new_query = QueryStructure(
            primary_entity=primary_entity or self.query.primary_entity,
            entities=entities if entities is not None else self.query.entities,
            relationships=relationships if relationships is not None else self.query.relationships,
        )

        new_metadata = ScopeMetadata(
            natural_language_summary=summary or self.metadata.natural_language_summary,
            confidence=confidence or self.metadata.confidence,
            last_updated=datetime.utcnow(),
            version=self.metadata.version + 1,
            last_update_summary=update_summary,
        )

        return ScopeState(
            query=new_query,
            results=self.results.invalidate(),  # Clear cached preview data
            metadata=new_metadata,
            ui_state=ScopeUIState(
                active_tab="build_query",
                can_stage=confidence == "high" if confidence else self.ui_state.can_stage,
                preview_loading=False,
                has_pending_clarification=False,
            ),
            state_id=str(uuid.uuid4()),
        )

    def with_preview_results(
        self,
        entity_type: str,
        count: int,
        samples: List[Dict[str, Any]],
        cypher_query: Optional[str] = None,
    ) -> "ScopeState":
        """
        Return a new ScopeState with updated preview results (immutable pattern).
        """
        new_counts = {**self.results.counts, entity_type: count}
        new_samples = {**self.results.samples, entity_type: samples}
        new_cypher = {**self.results.cypher_queries}
        if cypher_query:
            new_cypher[entity_type] = cypher_query

        new_results = ScopeExecutionResults(
            cypher_queries=new_cypher,
            counts=new_counts,
            samples=new_samples,
            full_data=self.results.full_data,
            total_matches=sum(new_counts.values()),
            execution_time_seconds=self.results.execution_time_seconds,
            last_executed=datetime.utcnow(),
        )

        return ScopeState(
            query=self.query,
            results=new_results,
            metadata=self.metadata,
            ui_state=ScopeUIState(
                active_tab="preview_data",
                selected_preview_entity=entity_type,
                can_stage=self.ui_state.can_stage,
                preview_loading=False,
                has_pending_clarification=False,
            ),
            state_id=str(uuid.uuid4()),
        )

    def to_frontend_format(self) -> dict:
        """
        Convert nested ScopeState to flat frontend format.

        Returns a dict structured for the frontend SSE contract with:
        - primary_entity: The main entity being queried
        - entities: Flat list with filters and fields inline
        - relationships: List with display_label
        - counts: Match counts by entity type
        - confidence: Current confidence level
        """
        frontend_entities = []
        for entity in self.query.entities:
            frontend_entities.append({
                "entity_type": entity.entity_type,
                "enabled": entity.enabled,
                "relevance_level": entity.relevance_level,
                "reasoning": entity.reasoning,
                "estimated_count": entity.estimated_count or self.results.counts.get(entity.entity_type),
                "query": entity.query or self.results.cypher_queries.get(entity.entity_type),
                "filters": [
                    {
                        "id": f.id,
                        "property": f.property,
                        "operator": f.operator.value,
                        "value": f.value,
                        "display_text": f.display_text
                    }
                    for f in entity.filters
                ],
                "fields_of_interest": [
                    {
                        "field": foi.field,
                        "justification": foi.justification
                    }
                    for foi in entity.fields_of_interest
                ],
            })

        frontend_relationships = [
            {
                "from_entity": r.from_entity,
                "to_entity": r.to_entity,
                "relationship_type": r.relationship_type,
                "display_label": r.display_label
            }
            for r in self.query.relationships
        ]

        return {
            "primary_entity": self.query.primary_entity,
            "entities": frontend_entities,
            "relationships": frontend_relationships,
            "counts": self.results.counts,
            "confidence": self.metadata.confidence,
        }


# =============================================================================
# Preview Request/Response Models
# =============================================================================


class PreviewRequest(BaseModel):
    """
    Request for paginated preview data.

    Sent from frontend when user navigates Preview Data tab.
    """
    entity_type: str = Field(
        description="Which entity to preview"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Records per page"
    )


class PreviewResponse(BaseModel):
    """
    Paginated preview data response.

    Returned when fetching preview data for an entity.
    """
    entity_type: str = Field(
        description="Which entity this preview is for"
    )
    data: List[Dict[str, Any]] = Field(
        description="The preview records"
    )
    total_count: int = Field(
        description="Total matching records (not just this page)"
    )
    page: int = Field(
        description="Current page number"
    )
    page_size: int = Field(
        description="Records per page"
    )
    total_pages: int = Field(
        description="Total number of pages"
    )
    has_next: bool = Field(
        description="Whether there are more pages"
    )
    has_previous: bool = Field(
        description="Whether there are previous pages"
    )


# =============================================================================
# Event Payload Models
# =============================================================================


class ScopeReadyEvent(BaseModel):
    """
    Event payload for scope_ready.

    Emitted after initial scope is generated from intent.
    """
    event_type: str = Field(default="scope_ready")
    scope_state: ScopeState
    message: str


class ScopeUpdatedEvent(BaseModel):
    """
    Event payload for scope_updated.

    Emitted after any scope modification (filter add/remove, entity toggle, etc.).
    """
    event_type: str = Field(default="scope_updated")
    scope_state: ScopeState
    version: int = Field(description="State version for optimistic locking")
    update_summary: str = Field(description="Brief description of what changed")
    changed_entities: List[str] = Field(
        default_factory=list,
        description="Which entities were affected by this change"
    )


class PreviewDataEvent(BaseModel):
    """
    Event payload for preview_data.

    Emitted when preview data is fetched for an entity.
    """
    event_type: str = Field(default="preview_data")
    entity_type: str
    data: List[Dict[str, Any]]
    count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class StagingStartedEvent(BaseModel):
    """
    Event payload for staging_started.

    Emitted when user confirms "Stage Data" button.
    """
    event_type: str = Field(default="staging_started")
    entities: List[str] = Field(description="Entities being staged")
    message: str


class StagingCompleteEvent(BaseModel):
    """
    Event payload for staging_complete.

    Emitted when all data has been successfully staged.
    """
    event_type: str = Field(default="staging_complete")
    total_records: int
    entities: List[str]
    entity_counts: Dict[str, int] = Field(default_factory=dict)
    execution_time_seconds: float
    message: str


class StagingErrorEvent(BaseModel):
    """
    Event payload for staging_error.

    Emitted when staging fails. Per design decision, all partial
    staging is rolled back.
    """
    event_type: str = Field(default="staging_error")
    error: str = Field(description="Error message")
    failed_entity: Optional[str] = Field(
        default=None,
        description="Which entity failed (if applicable)"
    )
    rolled_back: bool = Field(
        default=True,
        description="Whether partial staging was rolled back"
    )
