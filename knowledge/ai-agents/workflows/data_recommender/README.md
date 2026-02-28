# Data Scope Recommendation Workflow

This workflow translates user intent into precise data scope recommendations using Pydantic AI's structured output feature.

## Overview

The Data Scope Recommendation agent helps users identify exactly which data from their workspace graph is relevant to their objectives. It receives a high-level intent and produces a structured recommendation specifying:

- Which entities to include
- What filters to apply
- Which relationships to traverse
- What fields are most relevant

## Architecture

### Core Components

1. **models.py** - Pydantic models for structured output
   - `FilterOperator` - Enum of all supported operators
   - `EntityFilter` - Filter specification with operator and value
   - `EntityScope` - Entity with filters and field prioritization
   - `ScopeRecommendation` - Complete agent output
   - `ScopeExecutionResult` - Execution results with matching node IDs

2. **agent.py** - Pydantic AI agent with structured output
   - `create_scope_agent()` - Agent factory with Theo's persona
   - `recommend_scope()` - Main entry point for recommendations
   - Uses `output_type=ScopeRecommendation` for structured output
   - Dynamic prompt injection via `@agent.instructions`

3. **prompts.py** - System prompts and instructions
   - Reuses Theo's persona for consistency
   - Detailed scope recommendation instructions
   - Decision flow and clarification guidelines
   - Examples of good recommendations

## Key Features

### Structured Output
The agent uses Pydantic AI's `output_type` parameter to enforce valid `ScopeRecommendation` objects:

```python
result = await agent.run(
    prompt,
    deps=state,
    output_type=ScopeRecommendation  # Enforces structure
)
```

This eliminates validation errors and ensures consistent output format.

### Theo's Persona Integration
The agent embodies Theo's core principles:
- **Parsimony**: Minimal scope that satisfies intent
- **Pattern Recognition**: Matches intents to schema intelligently
- **Signal Extraction**: Focuses on what matters most
- **Trust Source Material**: Works with what's given, clarifies ambiguities

### Ideal Filter Recommendations
The agent is **unaware of API limitations** and recommends filters using the full operator set:
- Equality: `eq`, `neq`
- Comparison: `gt`, `gte`, `lt`, `lte`, `between`
- String: `contains`
- List: `in`
- Null checks: `is_null`, `is_not_null`

The executor (Task 5) handles translating these to API constraints.

### Clarification Flow
When intent is ambiguous, the agent sets `requires_clarification=True` and provides specific questions:

```python
ScopeRecommendation(
    requires_clarification=True,
    clarification_questions=[
        "What time period do you mean by 'recent'? (a) last 30 days, (b) this quarter, or (c) this year?"
    ],
    confidence_level="medium"
)
```

## Usage

### Basic Example

```python
from app.workflows.theo.models import IntentPackage
from app.workflows.data_recommender.agent import recommend_scope, GraphSchema, EntityType, PropertyInfo

# User's intent
intent = IntentPackage(
    title="Analyze Employee Compensation",
    summary="Review salary distribution across departments",
    mission=Mission(
        objective="Understand compensation patterns",
        why="Ensure competitive and equitable pay",
        success_looks_like="Clear view of salary ranges by department"
    )
)

# Workspace schema
schema = GraphSchema(
    entities=[
        EntityType(
            name="Employee",
            properties=[
                PropertyInfo(name="salary", type="number"),
                PropertyInfo(name="department", type="string"),
                PropertyInfo(name="hireDate", type="date"),
            ]
        )
    ]
)

# Get recommendation
recommendation = await recommend_scope(intent, schema)

print(recommendation.summary)
# "Employees with salary and department data for compensation analysis"

print(recommendation.entities[0].filters)
# May include filters based on intent interpretation
```

### With Clarification

```python
# Vague intent
intent = IntentPackage(
    title="Recent Claims Analysis",
    summary="Show me recent claims",
    ...
)

recommendation = await recommend_scope(intent, schema)

if recommendation.requires_clarification:
    for question in recommendation.clarification_questions:
        print(f"❓ {question}")
    # "What time period do you mean by 'recent'? (a) last 30 days, (b) this quarter, or (c) this year?"
```

## Decision Flow

The agent follows this decision flow:

1. **Identify Primary Entities** - What entities are mentioned/implied?
2. **Determine Filters** - What constraints are specified?
3. **Identify Relationships** - Are connections between entities needed?
4. **Prioritize Fields** - Which properties are most relevant?
5. **Assess Clarity** - Is clarification needed?

## Prompts Structure

The agent receives layered context via `@agent.instructions`:

1. **Theo's Persona** (base character)
   - Conversational, efficient, pattern-recognizing
   - Parsimonious, trusts source material

2. **Scope Instructions** (task-specific)
   - How to translate intent to scope
   - Decision flow and guidelines
   - Examples of good recommendations

3. **Schema Context** (dynamic, per request)
   - Available entities and properties
   - Relationship types

4. **Intent Context** (dynamic, per request)
   - User's objective and why
   - Success criteria
   - Full intent summary

## Testing

Run tests to verify agent structure:

```bash
cd app/workflows/data_recommender
python3 test_agent.py
```

Tests verify:
- Agent creation and configuration
- State management with intent and schema
- Schema summary generation
- ScopeRecommendation model structure
- Clarification flow support

## Integration with Theo Workflow

This agent is designed to be called after Theo completes intent discovery:

1. **Theo** (intent_builder) - Extracts user intent → `IntentPackage`
2. **Data Scope Agent** - Translates intent to scope → `ScopeRecommendation`
3. **Filter Executor** (Task 5) - Executes scope against graph → `ScopeExecutionResult`

## Next Steps

- **Task 3**: System prompt (prompts/scope_instructions.md) - Already completed inline
- **Task 4**: Schema matcher utilities for deterministic entity/property matching
- **Task 5**: Filter executor to execute recommendations against GraphQL API
- **Task 6**: GraphQL client wrapper
- **Task 7**: Integration tests with real workflows

## Design Decisions

### Why Pydantic AI's Structured Output?
- **Eliminates validation errors**: Output is guaranteed to be valid `ScopeRecommendation`
- **Self-documenting**: Schema tells LLM exactly what to return
- **Type-safe**: No manual parsing or field extraction
- **Retry-friendly**: Agent can self-correct on validation failures

### Why Separate Agent from Executor?
- **Agent recommends ideal filters** (full operator set)
- **Executor handles API limitations** (translates to GraphQL constraints)
- **Clean separation of concerns**: Intelligence vs implementation

### Why Low Temperature (0.3)?
- Scope recommendation needs consistency, not creativity
- Same intent + schema should produce similar recommendations
- Reduces hallucination and ensures reliability

### Why Minimal Dependencies?
- Only depends on Theo's IntentPackage (natural handoff)
- GraphSchema is self-contained (no external schema service)
- Can be tested independently of full workflow

## Files

```
app/workflows/data_recommender/
├── __init__.py                 # Package marker
├── README.md                   # This file
├── models.py                   # Pydantic models (Task 1) ✓
├── agent.py                    # Scope agent with structured output (Task 2) ✓
├── prompts.py                  # System prompts and instructions (Task 3) ✓
├── schema_matcher.py           # Schema matching utilities (Task 4) ✓
├── executor.py                 # Two-phase filter executor (Task 5) ✓
├── graphql_client.py           # GraphQL client wrapper (Task 6) ✓
├── test_agent.py              # Basic agent tests
├── test_models.py             # Model validation tests
├── test_schema_matcher.py     # Schema matcher unit tests (Task 4) ✓
├── test_executor.py           # Filter executor unit tests (Task 5) ✓
├── test_graphql_client.py     # GraphQL client unit tests (Task 6) ✓
└── tests/                     # Integration tests directory (Task 7) ✓
    ├── __init__.py
    ├── README.md
    ├── test_integration.py
    └── fixtures/
        ├── sample_schema.json
        ├── sample_intent_simple.json
        ├── sample_intent_complex.json
        ├── sample_intent_ambiguous.json
        └── mock_graphql_responses.json
```

## Status

**Tasks Completed:**
- ✅ Task 1: Define Output Models
- ✅ Task 2: Create Agent with Structured Output
- ✅ Task 3: Write System Prompt (inline in prompts.py)
- ✅ Task 4: Build Schema Matcher Utilities
- ✅ Task 5: Build Filter Executor
- ✅ Task 6: Build GraphQL Client
- ✅ Task 7: Integration Tests (complete end-to-end testing)

**All Tasks Complete!** The Data Scope Recommendation workflow is ready for production use.
