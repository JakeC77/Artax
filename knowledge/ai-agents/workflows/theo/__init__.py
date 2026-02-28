"""
Trident - Team Building Workflow for Geodesic AI

This package provides conversational intent discovery and team building
capabilities using the Geodesic AI framework.
"""

from .models import IntentPackage, Mission, IterationRecord
from .intent_builder import IntentBuilder
from .tools import IntentBuilderState
from .team_builder import TeamBuilder, TeamBuildResult

__all__ = [
    "IntentPackage",
    "Mission",
    "IterationRecord",
    "IntentBuilder",
    "IntentBuilderState",
    "TeamBuilder",
    "TeamBuildResult",
]
