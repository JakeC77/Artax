"""
models.py - Data models for Trident team builder
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Mission(BaseModel):
    """The core mission definition"""
    objective: str = Field(
        description="What the user wants to accomplish"
    )
    why: str = Field(
        description="The deeper motivation - why this matters (3 layers down)"
    )
    success_looks_like: str = Field(
        description="How we'll know we've succeeded"
    )


class TeamBuildingGuidance(BaseModel):
    """
    Hidden metadata for team builder - captured silently during intent discovery.

    These fields are inferred from the conversation and NOT shown to the user.
    They guide team building architecture decisions.
    """
    # Expertise domains (what fields need to be understood)
    expertise_needed: List[str] = Field(
        default_factory=list,
        description="Domains that need to be understood (e.g., finance, operations, market analysis, technical systems)"
    )

    # Operational modes (what the team needs to DO)
    capabilities_needed: List[str] = Field(
        default_factory=list,
        description="What the team needs to DO (e.g., analyze data, synthesize insights, generate recommendations)"
    )

    # Complexity assessment
    complexity_level: str = Field(
        default="Moderate",
        description="Simple | Moderate | Complex - based on domain breadth and uncertainty"
    )
    complexity_notes: str = Field(
        default="",
        description="Notes about what makes this complex or straightforward"
    )

    # Collaboration pattern (how agents should work together)
    collaboration_pattern: str = Field(
        default="Coordinated",
        description="Solo | Coordinated | Orchestrated - based on task structure"
    )

    # Human-AI handshake points (where human judgment is critical)
    human_ai_handshake_points: List[str] = Field(
        default_factory=list,
        description="Where human judgment is critical vs AI can operate autonomously"
    )

    # Workflow pattern (for architectural decisions)
    workflow_pattern: str = Field(
        default="OneTime",
        description="OneTime | Recurring | Exploratory - affects tool and state design"
    )


class IterationRecord(BaseModel):
    """A record of changes made during intent refinement"""
    version: int = Field(description="Version number")
    timestamp: datetime = Field(default_factory=datetime.now)
    change_description: str = Field(description="What changed and why")
    user_feedback: str = Field(default="", description="User's specific feedback that prompted the change")


class IntentPackage(BaseModel):
    """
    The complete Intent Information Package that Theo assembles
    through conversation with the user.

    This package is handed off to the team builder to create
    the actual agent team.
    """

    # Schema versioning for future migrations
    schema_version: int = Field(
        default=1,
        description="Schema version for future migrations. Increment on breaking changes."
    )

    # User-facing summary
    title: str = Field(description="Short, clear title for the mission")
    description: str = Field(
        default="",
        description="Short description (100-200 chars) of the workspace's purpose and objectives for UI card display"
    )
    summary: str = Field(
        description="2-4 sentences describing what we're doing, why it matters, and what success looks like"
    )

    # Detailed mission breakdown
    mission: Mission

    # Guidance for team building
    team_guidance: TeamBuildingGuidance

    # Conversation context
    conversation_transcript: Optional[str] = Field(
        default=None,
        description="Full conversation transcript from intent discovery for team building context"
    )

    # Iteration tracking
    iteration_history: List[IterationRecord] = Field(default_factory=list)
    current_version: int = Field(default=1)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    confirmed: bool = Field(
        default=False,
        description="Has the user confirmed this intent package?"
    )

    @model_validator(mode='before')
    @classmethod
    def migrate_schema(cls, values):
        """
        Handle schema migrations for older IntentPackage versions.

        This validator runs before Pydantic creates the model instance,
        allowing us to transform old data formats to the current schema.
        """
        if isinstance(values, dict):
            version = values.get('schema_version', 1)

            # Ensure schema_version is always set
            if 'schema_version' not in values:
                values['schema_version'] = 1

            # Future migrations go here
            # Example for future v2 migration:
            # if version < 2:
            #     values = cls._migrate_v1_to_v2(values)
            #     values['schema_version'] = 2

            # Log migrations for debugging
            if version != values.get('schema_version', 1):
                logger.info(f"Migrated IntentPackage from v{version} to v{values['schema_version']}")

        return values

    def get_user_facing_summary(self) -> str:
        """Get the formatted summary to show the user"""
        return f"""
┌─────────────────────────────────────────────────┐
│ {self.title:^47} │
│                                                 │
│ {self.summary:47} │
└─────────────────────────────────────────────────┘
        """.strip()

    def get_formatted_intent_text(self) -> str:
        """
        Get the formatted intent text in the markdown format that Theo uses
        when presenting the intent for confirmation.
        
        This matches the format shown in theo_intent_instructions.md:
        - Title as header
        - Objective section
        - Strategic Context section (why)
        - Success Criteria section
        """
        lines = [
            f"# {self.title}",
            "",
            "## Objective",
            self.mission.objective,
            "",
            "## Strategic Context",
            self.mission.why,
            "",
            "## Success Criteria",
            self.mission.success_looks_like,
        ]
        return "\n".join(lines)

    def add_iteration(self, change_description: str, user_feedback: str = ""):
        """Record an iteration/change to the intent"""
        self.current_version += 1
        self.iteration_history.append(
            IterationRecord(
                version=self.current_version,
                change_description=change_description,
                user_feedback=user_feedback
            )
        )

    def to_handoff_dict(self) -> dict:
        """Convert to dict for handoff to team builder"""
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "description": self.description,
            "summary": self.summary,
            "mission": {
                "objective": self.mission.objective,
                "why": self.mission.why,
                "success_looks_like": self.mission.success_looks_like
            },
            "team_guidance": {
                "expertise_needed": self.team_guidance.expertise_needed,
                "capabilities_needed": self.team_guidance.capabilities_needed,
                "complexity_level": self.team_guidance.complexity_level,
                "complexity_notes": self.team_guidance.complexity_notes,
                "collaboration_pattern": self.team_guidance.collaboration_pattern,
                "human_ai_handshake_points": self.team_guidance.human_ai_handshake_points,
                "workflow_pattern": self.team_guidance.workflow_pattern
            },
            "conversation_transcript": self.conversation_transcript,
            "iteration_history": [
                {
                    "version": record.version,
                    "timestamp": record.timestamp.isoformat(),
                    "change_description": record.change_description,
                    "user_feedback": record.user_feedback
                }
                for record in self.iteration_history
            ],
            "current_version": self.current_version,
            "created_at": self.created_at.isoformat(),
            "confirmed": self.confirmed
        }

    def to_dict(self) -> dict:
        """Convert to dict for serialization (alias for to_handoff_dict)"""
        return self.to_handoff_dict()
