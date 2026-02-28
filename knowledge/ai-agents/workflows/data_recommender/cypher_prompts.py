"""
Prompts for LLM-assisted Cypher generation.

This module contains the cheat sheet and prompt templates used when
deterministic Cypher generation fails and we need LLM assistance.
"""

# =============================================================================
# Cypher Quick Reference (included in LLM prompts)
# =============================================================================

CYPHER_CHEAT_SHEET = """
## Cypher Quick Reference

### Basic Patterns
```cypher
MATCH (n:Label)                           # Single node by label
MATCH (a:Label1)-[r:REL]->(b:Label2)      # Directed relationship
MATCH (a:Label1)-[r:REL]-(b:Label2)       # Undirected relationship
MATCH (a)-[*1..3]->(b)                    # Variable length path (1-3 hops)
```

### WHERE Clauses
```cypher
WHERE n.prop = 'value'                    # Equality (strings in single quotes)
WHERE n.prop <> 'value'                   # Not equal
WHERE n.prop > 100                        # Greater than
WHERE n.prop >= 100                       # Greater than or equal
WHERE n.prop < 100                        # Less than
WHERE n.prop <= 100                       # Less than or equal
WHERE toLower(n.prop) CONTAINS toLower('text')  # Case-insensitive contains
WHERE n.prop IN ['a', 'b', 'c']          # List membership
WHERE 100 <= n.prop <= 500               # Range (inclusive)
WHERE n.prop IS NULL                      # Null check
WHERE n.prop IS NOT NULL                  # Not null check
WHERE n.prop =~ '.*pattern.*'            # Regex match
```

### Combining Conditions
```cypher
WHERE condition1 AND condition2           # Both must be true
WHERE condition1 OR condition2            # Either can be true
WHERE NOT condition                       # Negation
WHERE (a OR b) AND c                      # Grouping with parentheses
```

### Return Patterns
```cypher
RETURN n                                  # Return full node
RETURN n.prop1, n.prop2                   # Return specific properties
RETURN DISTINCT n                         # Deduplicate results
RETURN n, m, r                            # Return multiple items
```

### Important Notes
1. **String booleans**: Many systems store booleans as strings.
   Use `n.isActive = 'True'` NOT `n.isActive = true`

2. **Single quotes for strings**: `'value'` not `"value"`

3. **Property names are case-sensitive**: `n.Status` ≠ `n.status`

4. **Escape single quotes**: Use `\\'` inside strings: `'it\\'s working'`
""".strip()


# =============================================================================
# LLM Generation Prompt
# =============================================================================

CYPHER_GENERATION_PROMPT = """
Generate a Neo4j Cypher query for the following data scope.

{cheat_sheet}

## Graph Schema

{schema_summary}

## Scope Recommendation (JSON)

```json
{scope_json}
```

## Requirements

1. Return ALL requested entity types in the RETURN clause
2. Apply ALL specified filters exactly as described
3. Use exact entity/property names from the schema (case-sensitive)
5. Use single quotes for string values
6. Handle boolean-as-string values (e.g., 'True' not true)

## Output Format

Output ONLY the Cypher query, no explanation or markdown code blocks.
The query should be ready to execute directly.
""".strip()


# =============================================================================
# Cypher Correction Prompt (for retry after failure)
# =============================================================================

CYPHER_CORRECTION_PROMPT = """
The following Cypher query failed to execute. Please fix it.

## Original Query

```cypher
{original_query}
```

## Error Message

{error_message}

## Graph Schema

{schema_summary}

## Original Scope (JSON)

```json
{scope_json}
```

{cheat_sheet}

## Instructions

1. Analyze the error and identify the issue
2. Fix the query while preserving the original intent
3. Ensure all entity/property names match the schema exactly
Output ONLY the corrected Cypher query, no explanation.
""".strip()


# =============================================================================
# Schema Summary Template (for prompts)
# =============================================================================

def format_schema_for_prompt(schema) -> str:
    """
    Format a GraphSchema for inclusion in LLM prompts.

    Args:
        schema: GraphSchema object with entities and relationships

    Returns:
        Markdown-formatted schema summary
    """
    lines = ["### Entities and Properties\n"]

    for entity in schema.entities:
        header = f"**{entity.name}**"
        entity_count = getattr(entity, 'count', None)
        if entity_count is not None:
            header += f" ({entity_count:,} nodes)"
        lines.append(header)

        entity_desc = getattr(entity, 'description', None)
        if entity_desc:
            lines.append(f"  {entity_desc}")

        if entity.properties:
            for prop in entity.properties:
                parts = [f"  - `{prop.name}` ({prop.type})"]

                # Add range info if available
                if prop.min_value is not None or prop.max_value is not None:
                    range_parts = []
                    if prop.min_value is not None:
                        range_parts.append(f"min: {prop.min_value}")
                    if prop.max_value is not None:
                        range_parts.append(f"max: {prop.max_value}")
                    parts.append(', '.join(range_parts))

                # Add description if available
                prop_desc = getattr(prop, 'description', None)
                if prop_desc:
                    parts.append(prop_desc)

                lines.append(" — ".join(parts))
        else:
            lines.append("  - (no properties)")

        lines.append("")

    if schema.relationships:
        lines.append("### Relationships\n")
        for rel in schema.relationships:
            lines.append(f"- `(:{rel.from_entity})-[:{rel.name}]->(:{rel.to_entity})`")

    suggested_patterns = getattr(schema, 'suggested_patterns', [])
    if suggested_patterns:
        lines.append("")
        lines.append("### Suggested Query Patterns\n")
        for pattern in suggested_patterns:
            lines.append(f"**{pattern.name}**")
            if pattern.description:
                lines.append(f"  {pattern.description}")
            if pattern.example_query:
                lines.append(f"  ```cypher")
                lines.append(f"  {pattern.example_query}")
                lines.append(f"  ```")
            lines.append("")

    return "\n".join(lines)
