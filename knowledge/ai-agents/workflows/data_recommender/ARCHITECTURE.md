# Data Recommender: Cypher-First Architecture

## Overview

The Data Recommender workflow converts user intent into executable graph queries. It uses a conversational agent to build a `ScopeRecommendation`, then generates and executes Cypher queries against the graph database.

```
User Intent → Agent Interview → ScopeRecommendation → Cypher Query → Graph Results
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CALLER (workflows, API)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SCOPE BUILDING (Conversational)                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │   agent.py      │    │   prompts.py    │    │  schema_discovery.py    │  │
│  │  ScopeBuilder   │◄───│  Theo persona   │    │  fetch_workspace_schema │  │
│  │  (pydantic-ai)  │    │  Instructions   │    │  (semanticFields API)   │  │
│  └────────┬────────┘    └─────────────────┘    └─────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     ScopeRecommendation                              │    │
│  │  - entities: [{entity_type, filters, fields_of_interest}]           │    │
│  │  - relationships: [{from_entity, to_entity, relationship_type}]     │    │
│  │  - summary, confidence_level                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCOPE EXECUTION (Cypher-First)                      │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │   executor.py    │  Thin facade for backward compatibility               │
│  │   ScopeExecutor  │────────────────────────────────────────┐              │
│  └──────────────────┘                                        │              │
│                                                              ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    cypher_executor.py                                 │   │
│  │                      CypherExecutor                                   │   │
│  │  - Orchestrates query generation and execution                        │   │
│  │  - Handles retries with LLM correction                                │   │
│  │  - Emits streaming events for UI                                      │   │
│  └───────────────┬──────────────────────────────────┬───────────────────┘   │
│                  │                                  │                       │
│                  ▼                                  ▼                       │
│  ┌───────────────────────────┐      ┌───────────────────────────────────┐   │
│  │   cypher_generator.py     │      │      graphql_client.py            │   │
│  │     CypherGenerator       │      │        GraphQLClient              │   │
│  │                           │      │                                   │   │
│  │  Pattern Classification:  │      │  nodes_by_cypher(query)           │   │
│  │  - SINGLE_ENTITY         │      │  → graphNodesByCypher API          │   │
│  │  - SINGLE_HOP            │      │                                   │   │
│  │  - MULTI_HOP             │      │  (deprecated: nodes_search,       │   │
│  │  - COMPLEX → LLM         │      │   fetch_neighbors)                │   │
│  └───────────┬───────────────┘      └───────────────────────────────────┘   │
│              │                                                              │
│              ▼                                                              │
│  ┌───────────────────────────┐                                              │
│  │    cypher_prompts.py      │                                              │
│  │  - CYPHER_CHEAT_SHEET     │                                              │
│  │  - CYPHER_GENERATION_PROMPT│                                              │
│  │  - CYPHER_CORRECTION_PROMPT│                                              │
│  └───────────────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ScopeExecutionResult                               │
│  - matching_node_ids: {entity_type → [node_ids]}                           │
│  - sample_nodes: {entity_type → [properties]}                              │
│  - stats: {total_candidates, total_matches, execution_time}                │
│  - cypher_query: "MATCH (n:Entity) WHERE ... RETURN n"                     │
│  - generation_method: "deterministic" | "llm" | "llm_corrected"            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Files

### Core Execution

| File | Purpose |
|------|---------|
| `executor.py` | Thin facade - delegates to CypherExecutor |
| `cypher_executor.py` | Main execution engine - generates query, executes, retries |
| `cypher_generator.py` | Builds Cypher queries from ScopeRecommendation |
| `cypher_prompts.py` | LLM prompts for complex query generation |
| `graphql_client.py` | GraphQL API client with `nodes_by_cypher()` |

### Agent & Schema

| File | Purpose |
|------|---------|
| `agent.py` | Conversational scope builder using pydantic-ai |
| `prompts.py` | Theo persona and interview instructions |
| `schema_discovery.py` | Fetches schema via semanticEntities/semanticFields |
| `schema_matcher.py` | Fuzzy matching for entities/properties |

### Models

| File | Purpose |
|------|---------|
| `models.py` | All Pydantic models (ScopeRecommendation, filters, results) |

### Deprecated

| File | Status |
|------|--------|
| `execution_planner.py` | DEPRECATED - was used for two-phase traversal planning |

## Data Flow

### 1. Schema Discovery

```python
# Optimized: 2 queries instead of 2N+1
schema = await fetch_workspace_schema(workspace_id, tenant_id)

# Uses:
# - semanticEntities → entity id → name mapping
# - semanticFields → ALL properties + rangeInfo in one query
# - graphNodeRelationshipTypes → relationships (still N queries)
```

**Key insight**: `semanticFields` includes `rangeInfo` with min/max values, enabling the agent to validate filter values against actual data ranges.

### 2. Scope Building (Agent)

```python
builder = ScopeBuilder()
result = await builder.start_conversation(
    intent_package=intent,
    graph_schema=schema,
    sample_data=samples
)
recommendation = result.scope  # ScopeRecommendation
```

The agent uses tools:
- `update_scope()` - Emit partial scope for UI preview
- `ask_clarification()` - Ask structured questions with options
- `finalize_scope()` - Complete the recommendation

### 3. Cypher Generation

```python
generator = CypherGenerator(schema)
result = generator.generate(recommendation)
# result.query = "MATCH (e:Employee) WHERE e.status = 'active' RETURN e LIMIT 1000"
# result.method = "deterministic" | "llm"
# result.pattern = QueryPattern.SINGLE_ENTITY
```

**Pattern Classification:**

| Pattern | Criteria | Example |
|---------|----------|---------|
| SINGLE_ENTITY | 1 entity, 0 relationships | `MATCH (e:Employee) WHERE ... RETURN e` |
| SINGLE_HOP | 2 entities, 1 relationship | `MATCH (a)-[r:REL]->(b) WHERE ... RETURN a, b` |
| MULTI_HOP | 3+ entities, chain | `MATCH (a)-[:R1]->(b)-[:R2]->(c) WHERE ... RETURN a, b, c` |
| COMPLEX | Doesn't fit templates | Falls back to LLM generation |

**Filter to Cypher Mapping:**

| FilterOperator | Cypher Template |
|----------------|-----------------|
| EQ | `n.prop = 'value'` |
| NEQ | `n.prop <> 'value'` |
| GT/GTE/LT/LTE | `n.prop > value` |
| CONTAINS | `toLower(n.prop) CONTAINS toLower('value')` |
| IN | `n.prop IN ['a', 'b']` |
| BETWEEN | `min <= n.prop <= max` |
| IS_NULL | `n.prop IS NULL` |

### 4. Query Execution

```python
executor = ScopeExecutor(tenant_id=tenant_id, graphql_client=client)
result = await executor.execute(recommendation, schema)
```

**Execution flow:**
1. Generate Cypher query (deterministic or LLM)
2. Execute via `graphNodesByCypher` API
3. On failure: attempt LLM correction, retry
4. Return `ScopeExecutionResult` with nodes and stats

**Retry strategy:**
- Max 2 attempts by default
- On error, call `generator.correct_with_llm()` to fix query
- Mark `generation_method="llm_corrected"` if fixed

## Models Reference

### ScopeRecommendation (Input to Executor)

```python
class ScopeRecommendation(BaseModel):
    entities: List[EntityScope]        # Entities with filters
    relationships: List[RelationshipPath]  # How entities connect
    summary: str                       # Natural language description
    requires_clarification: bool       # Agent needs more info
    clarification_questions: List[str] # Questions to ask
    confidence_level: str              # "high" | "medium" | "low"
```

### EntityScope

```python
class EntityScope(BaseModel):
    entity_type: str                   # e.g., "Employee"
    filters: List[EntityFilter]        # Filters to apply
    relevance_level: str               # "primary" | "related" | "contextual"
    fields_of_interest: List[FieldOfInterest]  # Important properties
    reasoning: str                     # Why this entity is included
```

### EntityFilter

```python
class EntityFilter(BaseModel):
    property: str                      # e.g., "status"
    operator: FilterOperator           # e.g., FilterOperator.EQ
    value: Union[str, int, float, bool, List, None]
    reasoning: Optional[str]           # Why this filter
```

### ScopeExecutionResult (Output)

```python
class ScopeExecutionResult(BaseModel):
    scope_recommendation: ScopeRecommendation
    matching_node_ids: Dict[str, List[str]]  # entity_type → [ids]
    sample_nodes: Dict[str, List[Dict]]      # entity_type → [properties]
    stats: ExecutionStats
    success: bool
    error_message: Optional[str]
    warnings: List[str]
    executed_at: datetime
    cypher_query: Optional[str]              # The executed query
    generation_method: Optional[str]         # How query was generated
```

## API Usage

### Basic Execution

```python
from app.workflows.data_recommender.executor import ScopeExecutor
from app.workflows.data_recommender.graphql_client import create_client

# Create client
client = create_client(workspace_id=workspace_id, tenant_id=tenant_id)

# Execute scope
executor = ScopeExecutor(
    tenant_id=tenant_id,
    graphql_client=client,
    debug=True  # Enable detailed logging
)

result = await executor.execute(recommendation, schema)

if result.success:
    print(f"Found {result.stats.total_matches} matches")
    print(f"Query: {result.cypher_query}")
    print(f"Method: {result.generation_method}")
else:
    print(f"Failed: {result.error_message}")
```

### Direct Cypher Generation (Testing)

```python
from app.workflows.data_recommender.cypher_generator import CypherGenerator

generator = CypherGenerator(schema, use_llm_fallback=False)
result = generator.generate(recommendation)

print(f"Pattern: {result.pattern}")
print(f"Query:\n{result.query}")
print(f"Warnings: {result.warnings}")
```

### Schema Discovery

```python
from app.workflows.data_recommender.schema_discovery import fetch_workspace_schema

schema = await fetch_workspace_schema(
    workspace_id=workspace_id,
    tenant_id=tenant_id,
    debug=True  # Show property ranges
)

# Schema includes rangeInfo from semanticFields
for entity in schema.entities:
    for prop in entity.properties:
        if prop.min_value or prop.max_value:
            print(f"{entity.name}.{prop.name}: {prop.min_value} to {prop.max_value}")
```

## Migration from Legacy Executor

The old two-phase executor (API-side + Python-side filtering) has been replaced. Key changes:

| Before | After |
|--------|-------|
| `graphNodesSearch` + Python filters | `graphNodesByCypher` single query |
| `graphNodePropertyMetadata` (N calls) | `semanticFields` (1 call) |
| `ExecutionPlanner` for traversal | Cypher handles traversal natively |
| Feature flag `USE_CYPHER_EXECUTOR` | Always Cypher (flag removed) |

**Backward compatibility:**
- `ScopeExecutor` API unchanged
- `executor.py` is now a thin facade
- Old constructor params kept but deprecated

## Debugging

### Enable Debug Logging

```python
executor = ScopeExecutor(debug=True)  # Logs query details
```

### Check Generation Method

```python
result = await executor.execute(recommendation, schema)
print(f"Method: {result.generation_method}")
# "deterministic" = template-based (fast, predictable)
# "llm" = LLM-generated (complex patterns)
# "llm_corrected" = LLM fixed a failed query
```

### Inspect Generated Query

```python
result = await executor.execute(recommendation, schema)
print(result.cypher_query)
# MATCH (e:Employee)
# WHERE e.status = 'active' AND e.salary > 100000
# RETURN e
# LIMIT 1000
```

## Performance Characteristics

| Metric | Two-Phase (Legacy) | Cypher-First |
|--------|-------------------|--------------|
| API calls per execution | O(N) entities + traversal | O(1) |
| Schema discovery calls | 2N+1 | N+2 |
| Relationship handling | Python traversal loop | Native Cypher |
| Filter execution | Split API/Python | All in Cypher |

## Future Considerations

1. **Query caching** - Cache generated queries for repeated scopes
2. **Pagination** - Handle large result sets via SKIP/LIMIT
3. **Validation extraction** - Move `CypherGenerator.validate()` to separate module if it grows
4. **Connection pooling** - Optimize GraphQL client connections
