"""
team_models.py - Data models for Theo team builder

Why: Theo uses a structured format aligned with conductor/specialist templates.
These models match the JSON structure defined in theo_team_instructions.md.

Design: Two-stage translation - conversational format (Theo) to structured YAML (Geodesic).
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# CONDUCTOR MODELS
# ============================================================================

class ConductorMission(BaseModel):
    """Mission context for conductor - injected from workspace intent"""
    problem: str = Field(description="Specific problem this workspace solves")
    stakes: str = Field(description="Urgency, consequences, what depends on this")
    success_criteria: List[str] = Field(default_factory=list, description="What 'done well' looks like")
    audience: str = Field(description="Who consumes output and for what decision")


class ConductorIdentity(BaseModel):
    """Identity for conductor agent"""
    name: str = Field(description="Human name (friendly, approachable)")
    role: str = Field(description="Role title")


class ConductorPersona(BaseModel):
    """Character sketch defining who the conductor is"""
    background: str = Field(description="2-3 sentences on their story and experiences")
    communication_style: str = Field(description="How they talk and communicate")
    personality: str = Field(description="Key traits that shape their work")


class ServiceDelivery(BaseModel):
    """What the conductor provides - framed as professional service"""
    core_responsibility: str = Field(description="Primary function in one clear sentence")
    service_areas: List[str] = Field(default_factory=list, description="Categories of help they provide")
    deliverables: List[str] = Field(default_factory=list, description="Tangible outputs they produce")
    capabilities: List[str] = Field(default_factory=list, description="What this agent can DO")


class WorkingAgreement(BaseModel):
    """Mutual expectations for the relationship"""
    user_can_expect: List[str] = Field(default_factory=list, description="What the agent commits to")
    user_should_provide: List[str] = Field(default_factory=list, description="What the agent needs to be effective")
    boundaries: List[str] = Field(default_factory=list, description="What they won't do, where they draw lines")


class Philosophy(BaseModel):
    """How they think - methodology and judgment"""
    problem_solving_approach: str = Field(description="Step-by-step methodology")
    decision_making_style: str = Field(description="How they weigh options and make choices")
    guiding_principles: List[str] = Field(default_factory=list, description="3-5 actionable rules")
    definition_of_done: List[str] = Field(default_factory=list, description="Checkable criteria")
    quality_metrics: List[str] = Field(default_factory=list, description="What distinguishes excellent from adequate")


class ConductorOperations(BaseModel):
    """Dynamic operational guidance for conductor"""
    solo_handling: List[str] = Field(default_factory=list, description="Tasks to handle without delegation")
    delegation_triggers: List[str] = Field(default_factory=list, description="When to call specialists")
    synthesis_considerations: str = Field(description="Intent-specific notes on combining specialist work")
    task_constraints: List[str] = Field(default_factory=list, description="What NOT to do or attempt")


class AvailableSpecialist(BaseModel):
    """Description of a specialist available for delegation"""
    name: str = Field(description="Specialist name")
    focus: str = Field(description="Their narrow expertise")
    capabilities: List[str] = Field(default_factory=list, description="What they can do")
    called_when: str = Field(description="Trigger for delegation")


class DelegationProtocol(BaseModel):
    """Instructions for delegating work to specialists"""
    provide: str = Field(description="What context to give specialist")
    be_specific_about: str = Field(description="What to clarify in delegation")
    expect_back: str = Field(description="What specialist will return")


class ConductorSpecialists(BaseModel):
    """How to work with the team"""
    available: List[AvailableSpecialist] = Field(default_factory=list, description="Available specialists")
    delegation_protocol: DelegationProtocol


class ToolConfiguration(BaseModel):
    """Tool assignment and usage guidance"""
    available: List[str] = Field(default_factory=list, description="Tools assigned to this agent")
    usage_guidance: List[str] = Field(default_factory=list, description="Tool-specific guidance strings")


class Example(BaseModel):
    """Example demonstrating quality and voice"""
    task_type: str = Field(description="Type of task (e.g., 'Core Task', 'Judgment Call')")
    input: str = Field(description="Realistic user request")
    output: str = Field(description="Quality response demonstrating agent capabilities")


class TheoConductor(BaseModel):
    """
    Conductor definition in Theo's format - UPDATED STRUCTURE.

    Why: This is the "main character" - primary point of contact with users.
    Uses service-oriented framing with working agreements and philosophy.
    """
    mission: ConductorMission
    identity: ConductorIdentity
    persona: ConductorPersona
    service_delivery: ServiceDelivery
    working_agreement: WorkingAgreement
    philosophy: Philosophy
    operations: ConductorOperations
    specialists: ConductorSpecialists
    tools: ToolConfiguration
    edge_cases: List[str] = Field(default_factory=list, description="Domain-specific edge cases")
    examples: List[Example] = Field(default_factory=list, description="2 examples for calibration")


# ============================================================================
# SPECIALIST MODELS
# ============================================================================

class SpecialistMission(BaseModel):
    """Mission context for specialist - injected from workspace intent"""
    problem_context: str = Field(description="2-3 sentences: specific problem this workspace solves")
    contribution: str = Field(description="How this specialist's work contributes to success")
    stakes: str = Field(description="What happens if analysis is wrong/incomplete")
    downstream_consumer: str = Field(description="Who uses output and for what decision")


class SpecialistIdentity(BaseModel):
    """Identity for specialist agent"""
    name: str = Field(description="Function-based name (clear and descriptive)")
    focus: str = Field(description="Narrow area of expertise in one line")


class SpecialistServiceDelivery(BaseModel):
    """What the specialist provides"""
    core_responsibility: str = Field(description="What they do in one sentence")
    deliverables: List[str] = Field(default_factory=list, description="What they produce")
    capabilities: List[str] = Field(default_factory=list, description="What they can DO")
    output_format: str = Field(description="How outputs should be structured")
    output_purpose: str = Field(description="What decision/action this output enables")


class SpecialistBoundaries(BaseModel):
    """Scope and boundaries for specialist"""
    primary_focus: str = Field(description="What they own and go deep on")
    flag_for_conductor: str = Field(description="What adjacent observations to flag")
    hard_limits: List[str] = Field(default_factory=list, description="What should go back to Conductor")


class SpecialistPhilosophy(BaseModel):
    """How the specialist thinks and works"""
    problem_solving_approach: str = Field(description="Their methodology")
    guiding_principles: List[str] = Field(default_factory=list, description="Core beliefs guiding their work")
    definition_of_done: List[str] = Field(default_factory=list, description="When task is complete")
    quality_metrics: List[str] = Field(default_factory=list, description="What distinguishes excellent from adequate")


class SpecialistOperations(BaseModel):
    """Operational guidance for specialist"""
    called_when: List[str] = Field(default_factory=list, description="Triggers for conductor to delegate")
    task_constraints: List[str] = Field(default_factory=list, description="What NOT to do")


class TheoSpecialist(BaseModel):
    """
    Specialist definition in Theo's format - UPDATED STRUCTURE.

    Why: Focused experts with narrow, deep expertise.
    Uses service-oriented framing with explicit boundaries and philosophy.
    """
    mission: SpecialistMission
    identity: SpecialistIdentity
    service_delivery: SpecialistServiceDelivery
    boundaries: SpecialistBoundaries
    philosophy: SpecialistPhilosophy
    operations: SpecialistOperations
    tools: ToolConfiguration
    edge_cases: List[str] = Field(default_factory=list, description="Domain-specific edge cases")
    examples: List[Example] = Field(default_factory=list, description="1-2 examples")


# ============================================================================
# REPORT MODELS
# ============================================================================

class DesignRationale(BaseModel):
    """Explanation of team design choices"""
    structure_choice: str = Field(description="Why this team structure (Conductor only vs Conductor + N specialists)")
    conductor: str = Field(description="Why this conductor design was chosen")
    specialists: str = Field(description="Why these specialists (or why none)")
    tool_assignments: str = Field(description="Why certain tools to certain agents")


class TradeOffsMade(BaseModel):
    """Trade-offs made in team design"""
    depth_vs_breadth: str = Field(description="Specialists for depth vs generalist for breadth")
    speed_vs_thoroughness: str = Field(description="Fewer agents (faster) vs more agents (thorough)")
    autonomy_vs_control: str = Field(description="Human-in-loop vs autonomous execution")


class TeamBuildingReport(BaseModel):
    """
    Final report explaining team design.

    Why: Documents design decisions for users and future refinement.
    """
    intent_summary: str = Field(description="What we're trying to accomplish")
    team_overview: str = Field(description="High-level description of the team composition")
    design_rationale: DesignRationale
    trade_offs_made: TradeOffsMade
    failure_modes_addressed: List[str] = Field(default_factory=list, description="What failure modes were designed around")
    human_in_loop_points: List[str] = Field(default_factory=list, description="Where human judgment is critical")
    success_criteria_coverage: str = Field(description="How this team addresses success criteria")


# ============================================================================
# TEAM DEFINITION
# ============================================================================

class TheoTeamDefinition(BaseModel):
    """
    Complete team definition in Theo's format.

    Why: This is what Theo builds - structured format matching conductor/specialist templates.
    Will be translated to Geodesic YAML format by translator.

    Design: Conductor is required, 0-3 specialists (simple to complex intents).
    """
    conductor: TheoConductor
    specialists: List[TheoSpecialist] = Field(
        default_factory=list,
        description="0-3 specialists depending on complexity"
    )
    report: TeamBuildingReport

    def get_all_tool_names(self) -> List[str]:
        """
        Get all unique tools used across the team.

        Why: Useful for validation and displaying team capabilities.
        Returns sorted list for deterministic output.
        """
        tools = set(self.conductor.tools.available)
        for specialist in self.specialists:
            tools.update(specialist.tools.available)
        return sorted(tools)

    def get_specialist_count(self) -> int:
        """Get number of specialists (0-3)"""
        return len(self.specialists)

    def validate_team_size(self) -> List[str]:
        """
        Validate team composition constraints.

        Why: Theo has constraints (0-3 specialists). Validate before translation.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if len(self.specialists) > 3:
            errors.append(
                f"Team has {len(self.specialists)} specialists, maximum is 3. "
                "Keep teams focused - more specialists = more coordination overhead."
            )

        # Check for duplicate specialist roles
        roles = [s.identity.name for s in self.specialists]
        if len(roles) != len(set(roles)):
            duplicates = [r for r in roles if roles.count(r) > 1]
            errors.append(
                f"Duplicate specialist roles: {duplicates}. "
                "Each specialist should have a unique focus area."
            )

        return errors


# ============================================================================
# TEAM BUNDLE
# ============================================================================

class TeamBundle(BaseModel):
    """
    Complete team bundle for storage.

    Why: Bundles team definition with metadata for storage and discovery.
    This is what gets saved to teams/{team_name}/ directory.

    Contains:
    - Original intent package (context for why team was built)
    - Theo team definition (structured format)
    - Creation metadata
    """
    team_name: str = Field(
        description="Unique team identifier (filesystem-safe)"
    )
    intent_package: Dict[str, Any] = Field(
        description="Original intent from Theo (for context)"
    )
    team_definition: TheoTeamDefinition
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this team was built"
    )
    version: str = Field(
        default="1.0",
        description="Team version"
    )

    def to_manifest(self) -> Dict[str, Any]:
        """
        Generate manifest.yaml content.

        Why: Manifest provides quick overview without parsing full team definition.
        Used for team discovery and listing.
        """
        return {
            "team_name": self.team_name,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "intent": {
                "title": self.intent_package.get("title", ""),
                "summary": self.intent_package.get("summary", "")
            },
            "team": {
                "conductor": self.team_definition.conductor.identity.name + " - " + self.team_definition.conductor.identity.role,
                "specialists": [s.identity.name for s in self.team_definition.specialists],
                "specialist_count": self.team_definition.get_specialist_count(),
                "tools": self.team_definition.get_all_tool_names()
            }
        }


# ============================================================================
# BACKWARD COMPATIBILITY ALIASES (for migration)
# ============================================================================

# Alias old names to new names for backward compatibility during transition
MasonConductor = TheoConductor
MasonSpecialist = TheoSpecialist
MasonTeamDefinition = TheoTeamDefinition
