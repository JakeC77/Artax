"""
tools.py - Custom tools for Theo intent guide agent
"""

from pydantic_ai import RunContext
from typing import List, Optional
from .models import IntentPackage, Mission, TeamBuildingGuidance

# Import TheoState from theo_agent (unified state class)
from .theo_agent import TheoState

# Keep IntentBuilderState for backward compatibility (deprecated)
class IntentBuilderState:
    """State for tracking the intent package being built (DEPRECATED - use TheoState)"""
    def __init__(self):
        self.intent_package: Optional[IntentPackage] = None
        self.finalized: bool = False


# Tool registry for Theo-specific tools
THEO_TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""
    def decorator(func):
        THEO_TOOLS[name] = func
        return func
    return decorator


@register_tool("update_intent_package")
async def update_intent_package(
    ctx: RunContext[TheoState],
    title: Optional[str] = None,
    description: Optional[str] = None,
    summary: Optional[str] = None,
    objective: Optional[str] = None,
    why: Optional[str] = None,
    success_looks_like: Optional[str] = None,
    # HIDDEN METADATA - Captured silently, NOT shown to user
    expertise_needed: Optional[List[str]] = None,
    capabilities_needed: Optional[List[str]] = None,
    complexity_level: Optional[str] = None,
    complexity_notes: Optional[str] = None,
    collaboration_pattern: Optional[str] = None,
    human_ai_handshake_points: Optional[List[str]] = None,
    workflow_pattern: Optional[str] = None,
    # Iteration tracking
    iteration_note: Optional[str] = None,
    user_feedback: Optional[str] = None
) -> dict:
    """
    Update the intent package being built through the conversation.

    Use this tool throughout the conversation as you learn more about
    what the user wants to accomplish. You can update any field as you
    gather information.

    IMPORTANT: The team_guidance fields (expertise_needed, capabilities_needed, etc.)
    are HIDDEN METADATA. Capture them silently based on the conversation. DO NOT
    show these to the user or mention them in your responses.

    Args:
        ctx: Pydantic AI context containing the IntentBuilderState
        title: Short, clear title for the mission
        description: Short description (100-200 chars) of the workspace's purpose for UI card display
        summary: 2-4 sentence summary of the mission
        objective: What the user wants to accomplish
        why: The deeper motivation (3 layers down)
        success_looks_like: How we'll know we've succeeded

        # HIDDEN METADATA (capture silently, don't show to user):
        expertise_needed: Domains needed (e.g., ["sales", "finance", "operations"])
        capabilities_needed: What team needs to DO (e.g., ["analyze data", "create strategy"])
        complexity_level: "Simple" | "Moderate" | "Complex"
        complexity_notes: Notes about what makes this complex
        collaboration_pattern: "Solo" | "Coordinated" | "Orchestrated"
        human_ai_handshake_points: Where human judgment is critical
        workflow_pattern: "OneTime" | "Recurring" | "Exploratory"

        iteration_note: Description of what changed (if this is an iteration)
        user_feedback: User's feedback that prompted this update

    Returns:
        Status message indicating what was updated (user-facing fields only)
    """
    state = ctx.deps

    # DEBUG: Log what parameters were passed (set DEBUG=True to enable)
    DEBUG = True
    if DEBUG:
        passed_params = {k: v for k, v in locals().items() if k not in ['ctx', 'state'] and v is not None}
        if passed_params:
            print(f"[DEBUG] update_intent_package called with: {list(passed_params.keys())}")

    # Initialize intent package if it doesn't exist
    if state.intent_package is None:
        state.intent_package = IntentPackage(
            # NOTE: Title should ALWAYS be provided by the LLM - see theo_intent_instructions.md
            title=title or "",
            description=description or "",
            summary=summary or "",
            mission=Mission(
                objective=objective or "",
                why=why or "",
                success_looks_like=success_looks_like or ""
            ),
            team_guidance=TeamBuildingGuidance(
                expertise_needed=expertise_needed or [],
                capabilities_needed=capabilities_needed or [],
                complexity_level=complexity_level or "Moderate",
                complexity_notes=complexity_notes or "",
                collaboration_pattern=collaboration_pattern or "Coordinated",
                human_ai_handshake_points=human_ai_handshake_points or [],
                workflow_pattern=workflow_pattern or "OneTime"
            )
        )
        # Signal intent_builder to emit intent_updated event
        state.intent_needs_broadcast = True
        state.last_update_summary = "Intent package initialized"

        # Return only user-facing fields (hide team guidance)
        return {
            "status": "created",
            "message": "Intent package initialized. Continue gathering information.",
            "version": state.intent_package.current_version
        }

    # Update existing package
    # Track ONLY user-facing fields for return message
    user_facing_updates = []

    if title is not None:
        state.intent_package.title = title
        user_facing_updates.append("title")

    if description is not None:
        state.intent_package.description = description
        user_facing_updates.append("description")

    if summary is not None:
        state.intent_package.summary = summary
        user_facing_updates.append("summary")

    if objective is not None:
        state.intent_package.mission.objective = objective
        user_facing_updates.append("objective")

    if why is not None:
        state.intent_package.mission.why = why
        user_facing_updates.append("why")

    if success_looks_like is not None:
        state.intent_package.mission.success_looks_like = success_looks_like
        user_facing_updates.append("success_looks_like")

    # Update hidden metadata silently (don't add to user-facing updates)
    if expertise_needed is not None:
        state.intent_package.team_guidance.expertise_needed = expertise_needed

    if capabilities_needed is not None:
        state.intent_package.team_guidance.capabilities_needed = capabilities_needed

    if complexity_level is not None:
        state.intent_package.team_guidance.complexity_level = complexity_level

    if complexity_notes is not None:
        state.intent_package.team_guidance.complexity_notes = complexity_notes

    if collaboration_pattern is not None:
        state.intent_package.team_guidance.collaboration_pattern = collaboration_pattern

    if human_ai_handshake_points is not None:
        state.intent_package.team_guidance.human_ai_handshake_points = human_ai_handshake_points

    if workflow_pattern is not None:
        state.intent_package.team_guidance.workflow_pattern = workflow_pattern

    # Record iteration if specified
    if iteration_note:
        state.intent_package.add_iteration(
            change_description=iteration_note,
            user_feedback=user_feedback or ""
        )

    # Return only user-facing fields (hide team guidance updates)
    if user_facing_updates:
        # Signal intent_builder to emit intent_updated event
        state.intent_needs_broadcast = True
        state.last_update_summary = f"Updated: {', '.join(user_facing_updates)}"

        # Clear user_edited_fields since AI just made an update
        # Frontend will track new edits from this point forward
        state.clear_user_edited_fields()

        # Build a record of what values were set so Theo can detect user edits later
        # When Theo sees CURRENT INTENT STATE differ from these values, user edited it
        values_set = {}
        if title is not None:
            values_set["title"] = title
        if description is not None:
            values_set["description"] = description
        if summary is not None:
            values_set["summary"] = summary
        if objective is not None:
            values_set["objective"] = objective
        if why is not None:
            values_set["why"] = why
        if success_looks_like is not None:
            values_set["success_looks_like"] = success_looks_like

        return {
            "status": "updated",
            "message": f"Updated: {', '.join(user_facing_updates)}",
            "version": state.intent_package.current_version,
            "values_set": values_set  # Echo back values so Theo can detect user edits
        }
    else:
        # Only metadata was updated (hidden from user) - no broadcast needed
        return {
            "status": "updated",
            "message": "Background metadata captured. Continue the conversation.",
            "version": state.intent_package.current_version
        }


@register_tool("propose_intent")
async def propose_intent(
    ctx: RunContext[TheoState]
) -> dict:
    """
    Propose the intent summary to the user for review.

    Use this tool when you've gathered enough information (objective, why, success criteria)
    and are ready to present the intent back to the user for confirmation.

    This tool ONLY proposes - it does NOT finalize. After calling this, you should:
    1. Show the user the intent summary in a clean format
    2. Ask "Does that capture what we're after?"
    3. Wait for their response
    4. If they confirm, the system will automatically finalize

    Args:
        ctx: Pydantic AI context containing the TheoState

    Returns:
        Status message with the intent summary to present
    """
    state = ctx.deps

    if state.intent_package is None:
        return {
            "status": "error",
            "message": "No intent package to propose. Build it first using update_intent_package."
        }

    # Validate that the package has minimum required fields before proposing
    pkg = state.intent_package
    missing_fields = []
    if not pkg.title or not pkg.title.strip():
        missing_fields.append("title")
    if not pkg.mission.objective or not pkg.mission.objective.strip():
        missing_fields.append("objective")
    if not pkg.mission.why or not pkg.mission.why.strip():
        missing_fields.append("why (strategic context)")
    if not pkg.mission.success_looks_like or not pkg.mission.success_looks_like.strip():
        missing_fields.append("success_looks_like (success criteria)")

    if missing_fields:
        return {
            "status": "error",
            "message": f"Intent package is incomplete. Missing required fields: {', '.join(missing_fields)}. "
                      f"Use update_intent_package to fill these in before proposing."
        }

    # Mark as proposed (but NOT finalized yet)
    state.intent_proposed = True

    # Return minimal status - Theo's instructions already tell it what to say
    # Avoid giving Theo text to parrot, which causes duplicate output
    return {
        "status": "proposed",
        "message": "Intent proposal recorded. Respond naturally to the user.",
        "next_step": "data_scoping"
    }

