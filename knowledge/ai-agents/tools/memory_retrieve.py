"""Memory retrieval tool for accessing past context (stub implementation).

Why: Agents need to remember past interactions to build on previous work.
Tradeoff: Adds complexity (vector DB, embeddings) but enables continuity.
Alternative considered: Stateless agents (simpler but can't learn or maintain context).
"""

from typing import List, Dict, Any
from pydantic_ai import RunContext
from app.tools import register_tool


@register_tool("memory_retrieve")
async def memory_retrieve(
    ctx: RunContext[dict],
    query: str,
    memory_type: str = "episodes",
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Retrieve past task history and learned patterns from the agent's memory.

    Use this tool FIRST when:
    - The task mentions "past findings", "previous research", "what we learned before"
    - You need to build on previous work or avoid repeating research
    - You want to see what tools worked well for similar tasks
    - The user asks about past analysis or recommendations

    Tool Selection Workflow:
    1. Check memory_retrieve for past context (if task relates to previous work)
    2. If nothing found or need current data, use web_search for new research
    3. Use workspace tools (workspace_items_lookup, etc.) for workspace-specific data
    4. Use calculator for any mathematical operations

    When to use:
    - "What did we find before about X?" → memory_retrieve("X")
    - "Use past findings about pricing" → memory_retrieve("pricing analysis")
    - "What tools worked for similar tasks?" → memory_retrieve("task type", memory_type="patterns")
    - Building on previous research or analysis

    When NOT to use:
    - For current market data (use web_search instead)
    - For workspace data (use workspace_items_lookup instead)
    - For calculations (use calculator instead)
    - For brand new topics with no prior work

    Args:
        ctx: Pydantic AI context (accesses memory system via ctx.deps)
        query: What you're looking for (e.g., "pricing analysis", "research tasks", "competitor data")
        memory_type: Type of memory to search:
            - 'episodes' (default): Past completed tasks and their outcomes
            - 'patterns': Learned workflows and tool sequences that worked well
        limit: Maximum number of items to retrieve (default: 3)

    Returns:
        List of memory items with:
            - task: Original task description
            - tools_used: Tools that worked well for this task
            - outcome/success: Whether task succeeded and what was learned
            - created_at: When it happened
            - agent: Which agent completed it

    Examples:
        - memory_retrieve("pricing analysis") → Finds past pricing research episodes
        - memory_retrieve("market research", memory_type="patterns") → Finds learned workflows for market research
        - memory_retrieve("ROI calculations") → Finds past calculation tasks and methods used
    """
    print(f"  🧠 Memory Retrieve: '{query}' (type={memory_type})")

    # Access memory system from context
    memory_context = ctx.deps.get("memory_context", {})

    if not memory_context:
        return [{
            "task": "No memory available yet",
            "tools_used": [],
            "success": False,
            "note": "Memory builds as you complete tasks"
        }]

    # Return past successful episodes
    if memory_type == "episodes":
        episodes = memory_context.get("past_successes", [])
        if not episodes:
            return [{
                "task": "No past successful tasks yet",
                "tools_used": [],
                "success": True,
                "note": "Complete a few tasks to build memory"
            }]

        # Return most recent episodes (up to limit)
        results = []
        for ep in episodes[:limit]:
            # Episode is a Pydantic model, access attributes directly
            results.append({
                "task": ep.task_description,
                "tools_used": ep.tools_used,
                "outcome": ep.outcome,
                "agent": ep.agent_id,
                "created_at": ep.created_at.isoformat() if hasattr(ep.created_at, 'isoformat') else str(ep.created_at)
            })
        return results

    # Return learned patterns
    elif memory_type == "patterns":
        patterns = memory_context.get("patterns", [])
        if not patterns:
            return [{
                "pattern": "No patterns learned yet",
                "note": "Patterns form after completing similar tasks 3+ times"
            }]

        results = []
        for pattern in patterns[:limit]:
            # Pattern is a Pydantic model, access attributes directly
            results.append({
                "pattern": pattern.description,
                "tool_sequence": list(pattern.tool_sequence),
                "confidence": pattern.confidence,
                "evidence_count": pattern.evidence_count
            })
        return results

    return [{"error": f"Unknown memory_type: {memory_type}"}]


