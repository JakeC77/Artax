"""
theo_tools.py - Custom tools for Theo's team building mode

Why: Theo needs tools to research existing teams, explore available tools,
and build/finalize team definitions during team building mode.

Tradeoff: Custom tools vs generic ones - these are purpose-built for team
building workflow, making Theo's team building clearer and more natural.
"""

from pydantic_ai import RunContext
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import Field
import yaml

from .team_models import TheoTeamDefinition, TeamBundle
from geodesic.tools import list_available_tools, get_tool_function


class TeamBuilderState:
    """
    State for tracking team building conversation.

    Why: Similar to IntentBuilderState pattern - tracks work in progress.
    Tradeoff: Mutable state (simpler) vs immutable (more functional).
    """
    def __init__(self):
        self.team_draft: Optional[TheoTeamDefinition] = None
        self.intent_package: Optional[Dict[str, Any]] = None
        self.finalized: bool = False
        self.team_bundle: Optional[TeamBundle] = None
        self.mode: str = "intent"  # "intent" or "team"


# Tool registry for Theo's team building tools
THEO_TEAM_TOOLS = {}


def register_tool(name: str):
    """Decorator to register a Theo team building tool"""
    def decorator(func):
        THEO_TEAM_TOOLS[name] = func
        return func
    return decorator


# DISABLED: No teams directory yet, causes 40s+ timeout
# @register_tool("search_existing_teams")
async def search_existing_teams(
    ctx: RunContext[TeamBuilderState],
    domain: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> dict:
    """
    Search for existing teams that might be similar or useful as reference.

    Why: Don't reinvent the wheel - find similar teams to use as starting points.
    Tradeoff: File-based search (simple) vs database (more powerful but complex).

    Args:
        ctx: Pydantic AI context containing TeamBuilderState
        domain: Domain to filter by (e.g., "business", "engineering")
        tags: Tags to filter by (e.g., ["finance", "strategy"])

    Returns:
        Dictionary with matching teams and their metadata
    """
    # Look for teams in standard location
    # Why: Convention over configuration - teams stored in teams/ directory
    teams_dir = Path("teams")

    if not teams_dir.exists():
        return {
            "status": "no_teams_found",
            "message": "No existing teams directory found. You'll be building from scratch.",
            "teams": []
        }

    matching_teams = []

    # Scan for team bundles
    # Why: Each team is a directory with manifest.yaml for quick overview
    for team_path in teams_dir.iterdir():
        if not team_path.is_dir():
            continue

        manifest_path = team_path / "manifest.yaml"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = yaml.safe_load(f)

            # Filter by domain if specified
            if domain:
                team_domain = manifest.get("intent", {}).get("domain", "").lower()
                if domain.lower() not in team_domain:
                    continue

            # Filter by tags if specified
            if tags:
                team_tags = manifest.get("team", {}).get("tags", [])
                if not any(tag.lower() in [t.lower() for t in team_tags] for tag in tags):
                    continue

            matching_teams.append({
                "team_name": manifest.get("team_name", team_path.name),
                "conductor": manifest.get("team", {}).get("conductor", ""),
                "specialists": manifest.get("team", {}).get("specialists", []),
                "specialist_count": manifest.get("team", {}).get("specialist_count", 0),
                "tools": manifest.get("team", {}).get("tools", []),
                "complexity": manifest.get("complexity", ""),
                "intent_summary": manifest.get("intent", {}).get("summary", "")
            })

        except Exception as e:
            # Log error but continue
            # Why: One corrupted manifest shouldn't break team search
            continue

    if not matching_teams:
        return {
            "status": "no_matches",
            "message": f"No teams found matching criteria (domain={domain}, tags={tags})",
            "teams": []
        }

    return {
        "status": "success",
        "message": f"Found {len(matching_teams)} matching team(s)",
        "teams": matching_teams
    }


def get_available_tools() -> list[dict]:
    """
    Get list of available tools from the Geodesic tool registry.

    Why: Theo needs to know what tools exist to assign them appropriately.
    This function returns the current tool registry state.

    Returns:
        List of dicts with 'name' and 'description' for each tool.
        Returns empty list if no tools registered or registry unavailable.

    Note: Non-async utility function for use in prompt building.
    """
    try:
        from geodesic.tools import list_available_tools, get_tool_function

        tool_names = list_available_tools()

        # Get tool details
        tools_info = []
        for name in tool_names:
            tool_func = get_tool_function(name)
            if tool_func:
                # Extract docstring for description
                doc = tool_func.__doc__ or "No description available"
                # Get first line of docstring as summary
                summary = doc.strip().split('\n')[0] if doc else "No description"

                tools_info.append({
                    "name": name,
                    "description": summary
                })

        return tools_info

    except Exception:
        # If tool registry not available, return empty list
        # Why: Allows team building to work without tools
        return []


@register_tool("finalize_team")
async def finalize_team(
    ctx: RunContext[TeamBuilderState],
    team_name: str,
    team: dict,  # Contains "conductor" and "specialists" (0-3)
    report: dict  # Team building report (separate from team definition)
) -> dict:
    """
    [DEPRECATED] Finalize and save complete team definition.

    NOTE: This tool is deprecated in favor of structured output (result_type).
    The team builder now uses Pydantic AI's result_type parameter to enforce
    correct team structure automatically. This tool is kept for backward
    compatibility but should not be called in normal operation.

    Args:
        team_name: Unique identifier for this team (filesystem-safe, lowercase, underscores)
        team: Team definition dict with keys "conductor" and "specialists" (0-3)
        report: Team building report dict with design rationale, trade-offs, etc.

    Returns:
        Confirmation with team bundle information
    """
    state = ctx.deps

    if state.intent_package is None:
        return {
            "status": "error",
            "message": "No intent package available. Intent context is required for team storage."
        }

    try:
        # Validate team name is filesystem-safe
        # Why: Team name becomes directory name - must be safe
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', team_name):
            return {
                "status": "error",
                "message": f"Team name '{team_name}' is not filesystem-safe. Use only letters, numbers, hyphens, and underscores."
            }

        # Validate team structure has required keys
        if not isinstance(team, dict):
            return {
                "status": "error",
                "message": "Team must be a dictionary with 'conductor' and 'specialists' keys."
            }

        if "conductor" not in team:
            return {
                "status": "error",
                "message": "Team must have 'conductor' key. 'specialists' is optional (0-3)."
            }

        if not isinstance(report, dict):
            return {
                "status": "error",
                "message": "Report must be a dictionary with design documentation."
            }

        # Convert dicts to Pydantic models
        # Why: Validates structure and enables type-safe operations
        from .team_models import (
            TheoConductor,
            TheoSpecialist,
            TheoTeamDefinition,
            TeamBuildingReport
        )

        # Parse conductor
        conductor_model = TheoConductor(**team["conductor"])

        # Parse specialists (0-3)
        specialists_data = team.get("specialists", [])
        specialist_models = [TheoSpecialist(**s) for s in specialists_data]

        # Parse report (separate parameter now)
        report_model = TeamBuildingReport(**report)

        # Build team definition
        team_def = TheoTeamDefinition(
            conductor=conductor_model,
            specialists=specialist_models,
            report=report_model
        )

        # Validate team constraints (0-3 specialists, no duplicates)
        # Why: Catch architectural errors before saving
        validation_errors = team_def.validate_team_size()
        if validation_errors:
            return {
                "status": "validation_error",
                "message": "Team definition has validation errors",
                "errors": validation_errors
            }

        # Create team bundle
        from datetime import datetime
        bundle = TeamBundle(
            team_name=team_name,
            intent_package=state.intent_package,
            team_definition=team_def,
            created_at=datetime.now()
        )

        # Save to state
        # Why: TeamBuilder needs bundle for file I/O operations
        state.team_bundle = bundle
        state.team_draft = team_def  # Keep for compatibility
        state.team_finalized = True

        conductor_display = f"{conductor_model.meta.name} - {conductor_model.meta.role}"
        specialist_display = [s.meta.name for s in specialist_models]

        return {
            "status": "finalized",
            "message": f"Team '{team_name}' built and ready for deployment!",
            "team_name": team_name,
            "bundle_info": {
                "conductor": conductor_display,
                "specialists": specialist_display,
                "specialist_count": len(specialist_models),
                "tools": team_def.get_all_tool_names()
            }
        }

    except Exception as e:
        # Log full error for debugging
        # Why: Pydantic validation errors can be detailed - preserve context
        import traceback
        error_detail = traceback.format_exc()
        error_str = str(e)

        # Extract helpful info from validation errors
        if "validation error" in error_str.lower():
            # Make validation errors more actionable
            helpful_msg = f"""Failed to finalize team due to validation error.

ERROR: {error_str}

SOLUTION: Review the Conductor and Specialist templates in your instructions. Ensure EVERY field in the templates is included in your team definition dict. Common missing fields:
- instructions.quality_references (both Conductor and Specialists)
- philosophy.quality_metrics (list of dicts with 'metric' and 'description')
- edge_case_handling (list of dicts with 'case' and 'guidance')

Do not call finalize_team again - the agent will retry automatically."""

            return {
                "status": "error",
                "message": helpful_msg,
                "detail": error_detail
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to finalize team: {error_str}",
                "detail": error_detail
            }
