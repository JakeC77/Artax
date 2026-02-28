"""
translator.py - Translate Theo team definitions to Geodesic YAML format

Why: Two-stage translation pattern - Theo works in conversational format,
Geodesic requires structured YAML. This translator bridges the gap.

Tradeoff: Additional translation layer adds complexity, but enables natural
team building UX while maintaining Geodesic's structured agent definitions.

Alternative considered: Single format for both (but either too conversational
for agents or too structured for conversation).
"""

from pathlib import Path
from typing import Dict, Any, List, Tuple
import yaml
import re

from .team_models import (
    TheoTeamDefinition,
    TheoConductor,
    TheoSpecialist,
    TeamBundle
)


class TeamTranslator:
    """
    Translates Theo team definitions to Geodesic agent YAML format.

    Why: Separates translation logic from conversation logic.
    Tradeoff: Separate class (more structure) vs functions (simpler).
    Choice: Class wins because translation has state (template patterns, etc).

    Design decisions:
    - Conductor gets template-based delegation instructions
    - Specialists get focused, minimal configs
    - Both use Geodesic v3.0 agent format
    """

    def __init__(self):
        """
        Initialize translator with format templates.

        Why: Templates ensure consistent structure across translated agents.
        """
        # Geodesic agent format version
        self.agent_version = "3.0"

    def translate(
        self,
        team_bundle: TeamBundle,
        output_dir: Path
    ) -> Dict[str, Path]:
        """
        Translate complete team bundle to Geodesic format and save to disk.

        Why: One-stop translation - takes Theo format, outputs Geodesic YAML.
        Tradeoff: All-in-one method vs separate translate/save steps.
        Choice: All-in-one is simpler for team builder workflow.

        Args:
            team_bundle: Complete team bundle from Theo
            output_dir: Directory to save team files (e.g., teams/{team_name}/)

        Returns:
            Dictionary mapping agent_id -> file_path for all created agents

        File structure created:
            teams/{team_name}/
                agents/
                    {conductor_id}.yaml
                    {specialist_1_id}.yaml
                    ...
                composition.yaml
                manifest.yaml
                theo_definition.json
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        team = team_bundle.team_definition
        agent_paths = {}

        # Create agents directory
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(exist_ok=True)

        # Translate conductor
        conductor_id = self._make_agent_id(team.conductor.identity.role)
        conductor_yaml = self._translate_conductor(
            team.conductor,
            team.specialists,
            conductor_id
        )
        conductor_path = agents_dir / f"{conductor_id}.yaml"
        self._save_yaml(conductor_yaml, conductor_path)
        agent_paths[conductor_id] = conductor_path

        # Translate specialists
        specialist_ids = []
        for specialist in team.specialists:
            specialist_id = self._make_agent_id(specialist.identity.name)
            specialist_ids.append(specialist_id)

            specialist_yaml = self._translate_specialist(specialist, specialist_id)
            specialist_path = agents_dir / f"{specialist_id}.yaml"
            self._save_yaml(specialist_yaml, specialist_path)
            agent_paths[specialist_id] = specialist_path

        # Create composition.yaml
        # Why: TeamComposition format for Geodesic orchestration engine
        composition = self._create_composition(
            team_bundle.team_name,
            conductor_id,
            specialist_ids,
            team_bundle.intent_package
        )
        composition_path = output_dir / "composition.yaml"
        self._save_yaml(composition, composition_path)

        # Create manifest.yaml
        # Why: Quick metadata for team discovery without parsing full team
        manifest = team_bundle.to_manifest()
        manifest_path = output_dir / "manifest.yaml"
        self._save_yaml(manifest, manifest_path)

        # Create theo_definition.json (already saved by team_builder but kept for consistency)
        # Why: Preserve original Theo format for re-editing and context
        theo_def = team_bundle.team_definition.model_dump()
        theo_def_path = output_dir / "theo_definition.json"
        self._save_json(theo_def, theo_def_path)

        return agent_paths

    def _translate_conductor(
        self,
        conductor: TheoConductor,
        specialists: List[TheoSpecialist],
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Translate Theo conductor to Geodesic agent YAML structure.

        Why: Conductors are complex - they orchestrate, delegate, and work solo.
        Key feature: Template-based delegation instructions built into system_prompt.

        Args:
            conductor: Theo conductor definition
            specialists: List of specialists (needed for delegation instructions)
            agent_id: Unique agent identifier

        Returns:
            Dictionary ready for YAML serialization
        """
        # Build delegation instructions
        # Why: Conductor needs to know HOW to delegate - this is critical
        delegation_instructions = self._build_delegation_instructions(
            conductor,
            specialists
        )

        # Build system prompt with delegation logic
        # Why: System prompt is where agent behavior is defined
        system_prompt = self._build_conductor_system_prompt(
            conductor,
            delegation_instructions
        )

        # Extract domain expertise from role
        domain_expertise = [conductor.identity.role.lower().replace(" ", "_")]

        return {
            "id": agent_id,
            "version": self.agent_version,
            "metadata": {
                "role": "conductor",
                "name": conductor.identity.name,
                "description": f"{conductor.identity.role} - {conductor.persona.background[:100]}...",
                "tags": domain_expertise
            },
            "identity": {
                "role": conductor.identity.role,
                "domain_expertise": domain_expertise,
                "purpose": conductor.service_delivery.core_responsibility,
                "communication_style": conductor.persona.communication_style
            },
            "cognition": {
                "system_prompt": system_prompt,
                "reasoning_mode": "react",
                "max_reasoning_steps": 5,
                "reflection_enabled": False
            },
            "capability": {
                "tools": conductor.tools.available,
                "max_tool_calls_per_task": 10
            },
            "behavior": {
                "task_types": conductor.service_delivery.capabilities,
                "quality_checks": ["relevance", "completeness"]
            },
            "context": {
                "memory": {
                    "short_term": True,
                    "long_term": True
                }
            }
        }

    def _translate_specialist(
        self,
        specialist: TheoSpecialist,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Translate Theo specialist to Geodesic agent YAML structure.

        Why: Specialists are simpler - focused on narrow expertise.
        Tradeoff: Less configuration than conductor, but still full agent definition.

        Args:
            specialist: Theo specialist definition
            agent_id: Unique agent identifier

        Returns:
            Dictionary ready for YAML serialization
        """
        # Build focused system prompt
        # Why: Specialist should know their narrow focus and when they're called
        system_prompt = self._build_specialist_system_prompt(specialist)

        # Extract domain expertise from focus area
        domain_expertise = [specialist.identity.focus.lower().replace(" ", "_")]

        return {
            "id": agent_id,
            "version": self.agent_version,
            "metadata": {
                "role": "worker",
                "name": specialist.identity.name,
                "description": specialist.identity.focus,
                "tags": domain_expertise
            },
            "identity": {
                "role": specialist.identity.name,
                "domain_expertise": domain_expertise,
                "purpose": specialist.service_delivery.core_responsibility,
                "communication_style": specialist.identity.focus
            },
            "cognition": {
                "system_prompt": system_prompt,
                "reasoning_mode": "react",
                "max_reasoning_steps": 3,
                "reflection_enabled": False
            },
            "capability": {
                "tools": specialist.tools.available,
                "max_tool_calls_per_task": 5
            },
            "behavior": {
                "task_types": specialist.service_delivery.capabilities,
                "quality_checks": ["relevance", "accuracy"]
            },
            "context": {
                "memory": {
                    "short_term": True,
                    "long_term": False  # Specialists typically don't need long-term memory
                }
            }
        }

    def _build_conductor_system_prompt(
        self,
        conductor: TheoConductor,
        delegation_instructions: str
    ) -> str:
        """
        Build comprehensive system prompt for conductor matching conductor_template.txt.

        CRITICAL: Translates ENTIRE JSON to system prompt with dynamic + static sections.

        Structure:
        - Header
        - DYNAMIC SECTIONS (from JSON)
        - STATIC SECTIONS (injected for all conductors)

        Args:
            conductor: Theo conductor definition
            delegation_instructions: Pre-built delegation instructions

        Returns:
            Complete system prompt string matching template
        """
        lines = []

        # Header
        lines.append("The Conductor is the user-facing lead agent. They converse directly with users, understand the full intent, work independently or delegate to specialists, and synthesize work into actionable responses.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## DYNAMIC SECTIONS")
        lines.append("[Intent-specific configuration]")
        lines.append("")
        lines.append("---")

        # Meta
        lines.append("")
        lines.append("### Meta")
        lines.append(f"├── Name: {conductor.identity.name}")
        lines.append(f"└── Role: {conductor.identity.role}")

        # Mission
        lines.append("")
        lines.append("### Mission")
        lines.append("")
        lines.append("Problem:")
        lines.append(conductor.mission.problem)
        lines.append("")
        lines.append("Stakes:")
        lines.append(conductor.mission.stakes)
        lines.append("")
        lines.append("Success Looks Like:")
        for criterion in conductor.mission.success_criteria:
            lines.append(f"- {criterion}")

        # Persona
        lines.append("")
        lines.append("### Persona")
        lines.append("")
        lines.append("Background:")
        lines.append(conductor.persona.background)
        lines.append("")
        lines.append("Communication Style:")
        lines.append(conductor.persona.communication_style)
        lines.append("")
        lines.append("Personality:")
        lines.append(conductor.persona.personality)

        # Service Delivery
        lines.append("")
        lines.append("### Service Delivery")
        lines.append("")
        lines.append("Core Responsibility:")
        lines.append(conductor.service_delivery.core_responsibility)
        lines.append("")
        lines.append("Service Areas:")
        for area in conductor.service_delivery.service_areas:
            lines.append(f"- {area}")
        lines.append("")
        lines.append("Deliverables:")
        for deliverable in conductor.service_delivery.deliverables:
            lines.append(f"- {deliverable}")
        lines.append("")
        lines.append("Capabilities:")
        for capability in conductor.service_delivery.capabilities:
            lines.append(f"- {capability}")

        # Working Agreement
        lines.append("")
        lines.append("### Working Agreement")
        lines.append("")
        lines.append("User Can Expect:")
        for expectation in conductor.working_agreement.user_can_expect:
            lines.append(f"- {expectation}")
        lines.append("")
        lines.append("User Should Provide:")
        for need in conductor.working_agreement.user_should_provide:
            lines.append(f"- {need}")
        lines.append("")
        lines.append("Boundaries:")
        for boundary in conductor.working_agreement.boundaries:
            lines.append(f"- {boundary}")

        # Philosophy
        lines.append("")
        lines.append("### Philosophy")
        lines.append("")
        lines.append("Problem-Solving Approach:")
        lines.append(conductor.philosophy.problem_solving_approach)
        lines.append("")
        lines.append("Decision-Making Style:")
        lines.append(conductor.philosophy.decision_making_style)
        lines.append("")
        lines.append("Guiding Principles:")
        for i, principle in enumerate(conductor.philosophy.guiding_principles, 1):
            lines.append(f"{i}. {principle}")
        lines.append("")
        lines.append("Definition of Done:")
        for item in conductor.philosophy.definition_of_done:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Quality Metrics:")
        for metric in conductor.philosophy.quality_metrics:
            lines.append(f"- {metric}")

        # Operations
        lines.append("")
        lines.append("### Operations")
        lines.append("")
        lines.append("Solo Handling:")
        for item in conductor.operations.solo_handling:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Delegation Triggers:")
        for item in conductor.operations.delegation_triggers:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Synthesis Considerations:")
        lines.append(conductor.operations.synthesis_considerations)
        lines.append("")
        lines.append("Task Constraints:")
        for constraint in conductor.operations.task_constraints:
            lines.append(f"- {constraint}")

        # Edge Cases
        if conductor.edge_cases:
            lines.append("")
            lines.append("### Edge Cases")
            lines.append("")
            for edge_case in conductor.edge_cases:
                lines.append(f"- {edge_case}")

        # Specialist Communication
        if delegation_instructions:
            lines.append("")
            lines.append("### Specialist Communication")
            lines.append("")
            lines.append(delegation_instructions)

        # Tools
        if conductor.tools.available or conductor.tools.usage_guidance:
            lines.append("")
            lines.append("### Tools")
            lines.append("")
            if conductor.tools.available:
                lines.append("Available:")
                for tool in conductor.tools.available:
                    lines.append(f"- {tool}")
                lines.append("")
            if conductor.tools.usage_guidance:
                lines.append("Usage Guidance:")
                for guidance in conductor.tools.usage_guidance:
                    lines.append(f"- {guidance}")

        # Examples
        if conductor.examples:
            lines.append("")
            lines.append("### Examples")
            lines.append("")
            for i, example in enumerate(conductor.examples, 1):
                lines.append(f"**Example {i}: {example.task_type}**")
                lines.append("")
                lines.append("Input:")
                lines.append(example.input)
                lines.append("")
                lines.append("Output:")
                lines.append(example.output)
                if i < len(conductor.examples):
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        # STATIC SECTIONS - Injected for all conductors
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## STATIC SECTIONS")
        lines.append("[Same for all Conductors]")
        lines.append("")
        lines.append("---")

        # 1. Synthesis Approach
        lines.append("")
        lines.append("### Synthesis Approach")
        lines.append("")
        lines.append("When combining specialist outputs:")
        lines.append("")
        lines.append("1. **Alignment Check**")
        lines.append("   - Where do findings agree? (high confidence)")
        lines.append("   - Where do they conflict? (investigate)")
        lines.append("   - Where are gaps? (follow up)")
        lines.append("")
        lines.append("2. **Conflict Resolution**")
        lines.append("   - Identify the specific claim in conflict")
        lines.append("   - Compare evidence: data-backed > pattern-based > inference")
        lines.append("   - If unresolvable: present both with your assessment")
        lines.append("")
        lines.append("3. **Confidence Calibration**")
        lines.append("   - High: Multiple sources converge")
        lines.append("   - Medium: Single source or inferential")
        lines.append("   - Low: Limited data, significant assumptions")
        lines.append("   - State confidence explicitly")
        lines.append("")
        lines.append("4. **Gap Acknowledgment**")
        lines.append("   - What couldn't we determine?")
        lines.append("   - What would we need?")
        lines.append("   - Risk of proceeding without it?")
        lines.append("")
        lines.append("5. **Narrative Integration**")
        lines.append("   - Lead with \"so what\"")
        lines.append("   - Structure for audience")
        lines.append("   - Note confident vs. provisional")

        # 2. State Management
        lines.append("")
        lines.append("### State Management")
        lines.append("")
        lines.append("Track across turns:")
        lines.append("- **Established Facts:** Confirmed, with source")
        lines.append("- **Open Questions:** Still to determine")
        lines.append("- **Delegated Work:** Sent to specialists, status")
        lines.append("- **User Preferences:** Format, depth, focus")
        lines.append("")
        lines.append("For complex analyses, checkpoint:")
        lines.append("\"Here's what I understand: [confirmed], [investigating], [next]. Correct?\"")

        # 3. Actionability Standards
        lines.append("")
        lines.append("### Actionability Standards")
        lines.append("")
        lines.append("Insights are not deliverables. Recommendations are.")
        lines.append("")
        lines.append("Every recommendation includes (where applicable):")
        lines.append("- **What:** Specific action")
        lines.append("- **Who:** Owner responsible")
        lines.append("- **When:** Timeline or trigger")
        lines.append("- **Measure:** How we know it worked")
        lines.append("")
        lines.append("The test: Could an executive delegate this tomorrow with no clarification?")
        lines.append("")
        lines.append("BAD: \"Improve forecast accuracy\"")
        lines.append("GOOD: \"Implement weekly pipeline review owned by Sales Ops, starting Jan 15, targeting 80% accuracy\"")

        # 4. Scope Handling
        lines.append("")
        lines.append("### Scope Handling")
        lines.append("")
        lines.append("Workspace intent defines core competency, not hard boundaries.")
        lines.append("")
        lines.append("- **Within Intent:** Full capability, proactive depth")
        lines.append("- **Adjacent:** Helpful engagement, acknowledge limits")
        lines.append("- **Outside:** Offer what value you can, be honest about limits")
        lines.append("")
        lines.append("Never refuse to engage. Always offer value.")

        # 5. Quality References
        lines.append("")
        lines.append("### Quality References")
        lines.append("")
        lines.append("Before finalizing: verify Definition of Done is met. Assess against Quality Metrics—aim for excellent. On judgment calls, return to Guiding Principles.")

        #6. Standard Quality Requirements
        lines.append("")
        lines.append("### Standard Quality Requirements")
        lines.append("")
        lines.append("**Accuracy:**")
        lines.append("- All factual claims must be supportable")
        lines.append("- Numbers must be traceable to their source")
        lines.append("- Do not fabricate or assume data")
        lines.append("- If you're not sure, say so")
        lines.append("")
        lines.append("**Clarity:**")
        lines.append("- Outputs should be understandable to the intended audience")
        lines.append("- Define jargon or technical terms when first used")
        lines.append("- Structure information logically")
        lines.append("- Prefer simple explanations over complex ones when both work")
        lines.append("")
        lines.append("**Actionability:**")
        lines.append("- Recommendations should specify what to do")
        lines.append("- Avoid vague advice (\"consider improving\")")
        lines.append("- Prefer concrete next steps with clear ownership")
        lines.append("- If action isn't possible, explain why")
        lines.append("")
        lines.append("**Honesty:**")
        lines.append("- State limitations and caveats upfront")
        lines.append("- Don't hide uncertainty behind hedge words")
        lines.append("- Distinguish facts from interpretations")
        lines.append("- Acknowledge when you don't know something")
        lines.append("")
        lines.append("**Completeness:**")
        lines.append("- Address all parts of the request")
        lines.append("- Flag if something was intentionally omitted and why")
        lines.append("- Don't trail off or leave threads hanging")
        lines.append("- Ensure the recipient has what they need to move forward")

        #7. Standard Edge Case Handling
        lines.append("")
        lines.append("### Standard Edge Case Handling")
        lines.append("")
        lines.append("**When facing incomplete information:**")
        lines.append("- State explicitly what's missing")
        lines.append("- Assess impact on your ability to deliver")
        lines.append("- Either proceed with clearly stated assumptions, or request the specific information needed")
        lines.append("- Never silently guess or fill gaps without disclosure")
        lines.append("")
        lines.append("**When facing ambiguous requests:**")
        lines.append("- Ask a single clarifying question if critical to proceeding")
        lines.append("- Otherwise, state your interpretation explicitly before proceeding")
        lines.append("- Offer to adjust if your interpretation was wrong")
        lines.append("")
        lines.append("**When facing conflicting inputs:**")
        lines.append("- Surface the conflict explicitly—do not silently pick one")
        lines.append("- Assess which source is more reliable and why")
        lines.append("- If unresolvable, present both perspectives with your assessment")
        lines.append("- Let the appropriate party make the final call")
        lines.append("")
        lines.append("**When facing out-of-scope requests:**")
        lines.append("- Acknowledge the request")
        lines.append("- Explain briefly why it's outside your focus")
        lines.append("- Suggest what or who could help if known")
        lines.append("- Do not attempt work you're not equipped for")
        lines.append("")
        lines.append("**When uncertain:**")
        lines.append("- State your confidence level explicitly")
        lines.append("- Distinguish between \"I don't know\" and \"I'm not certain\"")
        lines.append("- Never present uncertainty as certainty")
        lines.append("- It's better to flag uncertainty than to deliver confident mistakes")


        return "\n".join(lines)

    def _build_specialist_system_prompt(
        self,
        specialist: TheoSpecialist
    ) -> str:
        """
        Build focused system prompt for specialist matching specialist_template.txt.

        CRITICAL: Translates ENTIRE JSON to system prompt with dynamic + static sections.

        Args:
            specialist: Theo specialist definition

        Returns:
            Complete system prompt string matching template
        """
        lines = []

        # Mission Context
        lines.append("### Mission Context")
        lines.append("")
        lines.append("Problem We're Solving:")
        lines.append(specialist.mission.problem_context)
        lines.append("")
        lines.append("Your Contribution:")
        lines.append(specialist.mission.contribution)
        lines.append("")
        lines.append("Stakes:")
        lines.append(specialist.mission.stakes)
        lines.append("")
        lines.append("Downstream Consumer:")
        lines.append(specialist.mission.downstream_consumer)

        # Identity
        lines.append("")
        lines.append("### Identity")
        lines.append("")
        lines.append(f"You are a {specialist.identity.name}.")
        lines.append(f"**Specialized Focus:** {specialist.identity.focus}")

        # Service Delivery
        lines.append("")
        lines.append("### Service Delivery")
        lines.append("")
        lines.append("Core Responsibility:")
        lines.append(specialist.service_delivery.core_responsibility)
        lines.append("")
        lines.append("Deliverables:")
        for deliverable in specialist.service_delivery.deliverables:
            lines.append(f"- {deliverable}")
        lines.append("")
        lines.append("Capabilities:")
        for capability in specialist.service_delivery.capabilities:
            lines.append(f"- {capability}")
        lines.append("")
        lines.append(f"**Output Format:** {specialist.service_delivery.output_format}")
        lines.append(f"**Output Purpose:** {specialist.service_delivery.output_purpose}")

        # Boundaries
        lines.append("")
        lines.append("### Boundaries")
        lines.append("")
        lines.append(f"**Primary Focus:** {specialist.boundaries.primary_focus}")
        lines.append(f"**Flag for Conductor:** {specialist.boundaries.flag_for_conductor}")
        if specialist.boundaries.hard_limits:
            lines.append("**Hard Limits:**")
            for limit in specialist.boundaries.hard_limits:
                lines.append(f"- {limit}")

        # Philosophy
        lines.append("")
        lines.append("### Philosophy")
        lines.append("")
        lines.append("Problem-Solving Approach:")
        lines.append(specialist.philosophy.problem_solving_approach)
        lines.append("")
        lines.append("Guiding Principles:")
        for i, principle in enumerate(specialist.philosophy.guiding_principles, 1):
            lines.append(f"{i}. {principle}")
        lines.append("")
        lines.append("Definition of Done:")
        for item in specialist.philosophy.definition_of_done:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Quality Metrics:")
        for metric in specialist.philosophy.quality_metrics:
            lines.append(f"- {metric}")

        # Operations
        lines.append("")
        lines.append("### Operations")
        lines.append("")
        lines.append("Called When:")
        for trigger in specialist.operations.called_when:
            lines.append(f"- {trigger}")
        lines.append("")
        lines.append("Task Constraints:")
        for constraint in specialist.operations.task_constraints:
            lines.append(f"- {constraint}")

        # Edge Cases
        if specialist.edge_cases:
            lines.append("")
            lines.append("### Edge Cases")
            lines.append("")
            for edge_case in specialist.edge_cases:
                lines.append(f"- {edge_case}")

        # Tools
        if specialist.tools.available or specialist.tools.usage_guidance:
            lines.append("")
            lines.append("### Tools")
            lines.append("")
            if specialist.tools.available:
                lines.append("Available:")
                for tool in specialist.tools.available:
                    lines.append(f"- {tool}")
                lines.append("")
            if specialist.tools.usage_guidance:
                lines.append("Usage Guidance:")
                for guidance in specialist.tools.usage_guidance:
                    lines.append(f"- {guidance}")

        # Examples
        if specialist.examples:
            lines.append("")
            lines.append("### Examples")
            lines.append("")
            for i, example in enumerate(specialist.examples, 1):
                lines.append(f"**Example {i}: {example.task_type}**")
                lines.append("")
                lines.append("Input:")
                lines.append(example.input)
                lines.append("")
                lines.append("Output:")
                lines.append(example.output)
                if i < len(specialist.examples):
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        # STATIC SECTION - Injected for all specialists
        lines.append("")
        lines.append("### Quality References")
        lines.append("")
        lines.append("Before returning results: verify Definition of Done. Assess against Quality Metrics. If uncertain whether work meets standards, note uncertainty for Conductor.")

        #6. Standard Quality Requirements
        lines.append("")
        lines.append("### Standard Quality Requirements")
        lines.append("")
        lines.append("**Accuracy:**")
        lines.append("- All factual claims must be supportable")
        lines.append("- Numbers must be traceable to their source")
        lines.append("- Do not fabricate or assume data")
        lines.append("- If you're not sure, say so")
        lines.append("")
        lines.append("**Clarity:**")
        lines.append("- Outputs should be understandable to the intended audience")
        lines.append("- Define jargon or technical terms when first used")
        lines.append("- Structure information logically")
        lines.append("- Prefer simple explanations over complex ones when both work")
        lines.append("")
        lines.append("**Actionability:**")
        lines.append("- Recommendations should specify what to do")
        lines.append("- Avoid vague advice (\"consider improving\")")
        lines.append("- Prefer concrete next steps with clear ownership")
        lines.append("- If action isn't possible, explain why")
        lines.append("")
        lines.append("**Honesty:**")
        lines.append("- State limitations and caveats upfront")
        lines.append("- Don't hide uncertainty behind hedge words")
        lines.append("- Distinguish facts from interpretations")
        lines.append("- Acknowledge when you don't know something")
        lines.append("")
        lines.append("**Completeness:**")
        lines.append("- Address all parts of the request")
        lines.append("- Flag if something was intentionally omitted and why")
        lines.append("- Don't trail off or leave threads hanging")
        lines.append("- Ensure the recipient has what they need to move forward")

        # Standard Edge Case Handling
        lines.append("")
        lines.append("### Standard Edge Case Handling")
        lines.append("")
        lines.append("**When facing incomplete information:**")
        lines.append("- State explicitly what's missing")
        lines.append("- Assess impact on your ability to deliver")
        lines.append("- Either proceed with clearly stated assumptions, or request the specific information needed")
        lines.append("- Never silently guess or fill gaps without disclosure")
        lines.append("")
        lines.append("**When facing ambiguous requests:**")
        lines.append("- Ask a single clarifying question if critical to proceeding")
        lines.append("- Otherwise, state your interpretation explicitly before proceeding")
        lines.append("- Offer to adjust if your interpretation was wrong")
        lines.append("")
        lines.append("**When facing conflicting inputs:**")
        lines.append("- Surface the conflict explicitly—do not silently pick one")
        lines.append("- Assess which source is more reliable and why")
        lines.append("- If unresolvable, present both perspectives with your assessment")
        lines.append("- Let the Conductor make the final call")
        lines.append("")
        lines.append("**When facing out-of-scope requests:**")
        lines.append("- Acknowledge the request")
        lines.append("- Explain briefly why it's outside your focus")
        lines.append("- Return to Conductor for routing")
        lines.append("- Do not attempt work you're not equipped for")
        lines.append("")
        lines.append("**When uncertain:**")
        lines.append("- State your confidence level explicitly")
        lines.append("- Distinguish between \"I don't know\" and \"I'm not certain\"")
        lines.append("- Never present uncertainty as certainty")
        lines.append("- It's better to flag uncertainty than to deliver confident mistakes")


        return "\n".join(lines)

    def _build_delegation_instructions(
        self,
        conductor: TheoConductor,
        specialists: List[TheoSpecialist]
    ) -> str:
        """
        Build template-based delegation instructions for conductor.

        Why: This is THE KEY feature - conductor needs explicit instructions
        on how to delegate to each specialist.

        Tradeoff: Detailed instructions (verbose) vs minimal (conductor figures it out).
        Choice: Detailed wins - explicit is better than implicit for agent behavior.

        Args:
            conductor: Theo conductor definition
            specialists: List of specialists

        Returns:
            Formatted delegation instructions section
        """
        lines = []

        lines.append("## Team Structure")

        if not specialists:
            lines.append("You work independently. No specialists available for delegation.")
            return "\n".join(lines)

        lines.append("You lead a team of specialists. Use them strategically.")

        # Build specialist list with focus areas from conductor's perspective
        if conductor.specialists.available:
            for spec_desc in conductor.specialists.available:
                lines.append("")
                lines.append(f"### {spec_desc.name}")
                lines.append(f"Focus: {spec_desc.focus}")
                lines.append(f"Capabilities: {', '.join(spec_desc.capabilities)}")
                lines.append(f"Called when: {spec_desc.called_when}")

        # Build delegation process instructions
        protocol = conductor.specialists.delegation_protocol

        lines.append("")
        lines.append("## How to Delegate")
        lines.append("When delegating work to a specialist:")
        lines.append(f"**Provide:** {protocol.provide}")
        lines.append(f"**Be Specific About:** {protocol.be_specific_about}")
        lines.append(f"**Expect Back:** {protocol.expect_back}")

        return "\n".join(lines)

    def _create_composition(
        self,
        team_name: str,
        conductor_id: str,
        specialist_ids: List[str],
        intent_package: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create Geodesic TeamComposition YAML.

        Why: TeamComposition is how Geodesic orchestration engine understands teams.
        This connects our translated agents into a functional team.

        Args:
            team_name: Unique team identifier
            conductor_id: Conductor agent ID
            specialist_ids: List of specialist agent IDs
            intent_package: Original intent (for domain/tags inference)

        Returns:
            TeamComposition dictionary ready for YAML
        """
        # Infer domain from intent
        # Why: Best guess based on expertise - helps with team discovery
        domain = "general"
        expertise_needed = intent_package.get("team_guidance", {}).get("expertise_needed", [])
        if expertise_needed:
            domain = expertise_needed[0].lower().replace(" ", "_")

        # Infer tags from capabilities
        tags = intent_package.get("team_guidance", {}).get("capabilities_needed", [])
        tags = [tag.lower().replace(" ", "_") for tag in tags]

        return {
            "id": team_name,
            "name": team_name.replace("_", " ").title(),
            "description": intent_package.get("summary", "AI team for task execution"),
            "conductor_id": conductor_id,
            "worker_ids": specialist_ids,
            "domain": domain,
            "tags": tags,
            "version": "1.0"
        }

    def _make_agent_id(self, role: str) -> str:
        """
        Convert role name to filesystem-safe agent ID.

        Why: Agent IDs become filenames - must be filesystem-safe.
        Tradeoff: Loss of special characters vs safety.

        Args:
            role: Human-readable role name

        Returns:
            Filesystem-safe agent ID (lowercase, underscores)

        Examples:
            "Business Strategy Lead" -> "business_strategy_lead"
            "Data Analyst (SQL Expert)" -> "data_analyst_sql_expert"
        """
        # Remove special characters, convert to lowercase
        agent_id = re.sub(r'[^\w\s-]', '', role)
        # Replace spaces and hyphens with underscores
        agent_id = re.sub(r'[-\s]+', '_', agent_id)
        # Remove leading/trailing underscores
        agent_id = agent_id.strip('_').lower()
        return agent_id

    def _save_yaml(self, data: Dict[str, Any], path: Path):
        """
        Save dictionary to YAML file with proper formatting.

        Why: Consistent YAML formatting across all team files.
        Tradeoff: Custom formatting (readable) vs default dump (works but ugly).

        Args:
            data: Dictionary to save
            path: File path to write to
        """
        # Custom representer for multiline strings to use literal block scalar style (|)
        def str_representer(dumper, data):
            if '\n' in data:
                # Use literal block scalar for multiline strings
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)

        yaml.add_representer(str, str_representer)

        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=80
            )

    def _save_json(self, data: Dict[str, Any], path: Path):
        """
        Save dictionary to JSON file with proper formatting.

        Why: JSON for mason_definition preserves exact structure for re-editing.

        Args:
            data: Dictionary to save
            path: File path to write to
        """
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
