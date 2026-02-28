"""Interactive user prompting tool (stub implementation).

Why: Agents need to ask clarifying questions when requirements are ambiguous.
Tradeoff: Adds latency to task execution, but prevents wrong assumptions.
Alternative considered: Always proceeding with best guess (leads to poor results).
"""

from pydantic_ai import RunContext
from app.tools import register_tool


@register_tool("ask_user")
async def ask_user(
    ctx: RunContext[dict],
    question: str,
    context: str = ""
) -> str:
    """Ask the user a question and wait for their response.

    Use this when you need clarification or additional information from the user
    to complete a task accurately.

    Why: Better to ask than guess - reduces rework and improves accuracy.
    Tradeoff: Adds latency (user response time), but worth it for quality.

    Args:
        ctx: Pydantic AI context (unused but required by signature)
        question: Question to ask the user
        context: Optional context explaining why this question is being asked

    Returns:
        User's response (currently stubbed - returns placeholder message)

    Examples:
        - "What is your target market segment?" → Gets market focus
        - "What budget range are you considering?" → Gets financial constraints

    Note:
        This is a Phase 1 stub. Real implementation in Phase 3 will:
        - Prompt user via CLI/web interface
        - Wait for response with timeout
        - Handle timeout gracefully
    """
    # Console logging for CLI observability
    # Why: Shows when agents would ask questions (helps identify UX needs)
    print(f"  ❓ Ask User: {question}")
    if context:
        print(f"     Context: {context}")

    # Stub implementation - return placeholder
    # Why: Phase 1 focuses on tool structure, not full functionality
    return "[User response placeholder - interactive prompting coming in Phase 3]"


