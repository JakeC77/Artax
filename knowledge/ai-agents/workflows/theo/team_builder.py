"""
team_builder.py - Orchestrates team building with Theo in team mode

Why: Similar to IntentBuilder pattern - manages state and team bundle persistence.
Theo focuses on team design, TeamBuilder handles orchestration and file I/O.

Design: Uses Theo agent in team building mode with dynamic system prompt injection.
Workflow switches Theo from intent mode to team mode deterministically.

Tradeoff: Separate builder class (more structure) vs inline (simpler).
Choice: Separate wins for testability and reusability.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic_ai.models import KnownModelName
import json
import re
import logging

from app.workflows.theo.config import load_config
from .models import IntentPackage
from .team_models import TeamBundle
from .theo_tools import THEO_TEAM_TOOLS
from .theo_agent import TheoState, create_team_agent
from .translator import TeamTranslator
from .graphql_client import _run_graphql

logger = logging.getLogger(__name__)


@dataclass
class TeamBuildResult:
    """Result of team building operation with error details."""
    success: bool
    team_bundle: Optional[TeamBundle] = None
    error_type: Optional[str] = None  # "validation", "llm_error", "save_error"
    error_message: Optional[str] = None
    validation_errors: Optional[List[str]] = None


class TeamBuilder:
    """
    Orchestrates team building with Theo from an Intent Package.

    Why: Separates orchestration from team design logic.
    Theo (agent) focuses on team design, TeamBuilder handles workflow and I/O.

    Design pattern: Similar to IntentBuilder
    - Theo agent in team mode with custom tools
    - TeamBuilderState tracks team bundle
    - Single-call build (team generated in one LLM call)
    - Save team bundle on finalization
    - Translate to Geodesic format

    Design: Theo operates in team building mode with dynamically injected prompts:
    - Persona (who Theo is)
    - Team instructions (how to build teams)
    - Conductor template (what to generate for conductor)
    - Specialist template (what to generate for specialists)
    """

    def __init__(
        self,
        model: KnownModelName = None,
        teams_output_dir: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        graphql_endpoint: Optional[str] = None
    ):
        """
        Initialize the Team Builder.

        Args:
            model: Optional model name override. If not provided, uses workflow config.
                   The model factory will automatically use Azure OpenAI if configured.
            teams_output_dir: Directory to save team bundles (defaults to ./teams)
            workspace_id: Optional workspace ID for saving teams to GraphQL API
            tenant_id: Optional tenant ID for GraphQL API authentication
            graphql_endpoint: Optional GraphQL endpoint URL (defaults to env var or standard endpoint)
        """
        # Get configuration from workflow config
        config = load_config()
        self.state = TheoState(mode="team")  # Start in team mode
        self.translator = TeamTranslator()

        # Set output directory for teams
        if teams_output_dir is None:
            self.teams_output_dir = Path("teams")
        else:
            self.teams_output_dir = Path(teams_output_dir)

        # GraphQL API configuration
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.graphql_endpoint = graphql_endpoint

        # Create the Theo agent with dynamic prompts
        # Use provided model or workflow config's team_builder_model
        if model is not None:
            self.model = model
            self.agent = create_team_agent(model=self.model)
        else:
            self.model = str(config.team_builder_model)
            model_instance = config.team_builder_model.create()
            self.agent = create_team_agent(model=model_instance)
        # Agent has retries=2, giving 3 total attempts for self-correction

        # Note: No tools registered when using structured output (result_type)
        # Why: result_type mode generates structured data directly without tool calls
        # The finalize_team tool is deprecated - kept in theo_tools.py for backward compatibility only

    async def start_conversation(
        self,
        intent_package: IntentPackage
        ) -> TeamBuildResult:
        """
        Build team using Theo in team building mode with structured output.

        Why: Uses Pydantic AI's result_type to enforce correct team structure.
        Tradeoff: Structured output (guaranteed format) vs free-form (more flexible).
        Choice: Structured wins - eliminates validation errors and manual checks.

        Args:
            intent_package: Intent package from Theo (intent mode)

        Returns:
            TeamBuildResult with success status, team_bundle (if successful),
            and error details (if failed)

        Workflow:
            1. Theo receives intent package in team mode
            2. Theo architects complete team matching conductor/specialist templates
            3. Pydantic AI enforces TheoTeamDefinition structure automatically
            4. TeamBuilder validates and creates bundle
            5. TeamBuilder translates to Geodesic format and saves
        """
        print("\n" + "=" * 60)
        print("TEAM BUILDING WITH THEO")
        print("=" * 60)
        print("\nTheo is analyzing your intent and architecting the optimal team...")
        print("This will take a moment as Theo designs your team.")
        print("-" * 60 + "\n")

        # Store intent package in state
        self.state.intent_package = intent_package.to_handoff_dict()

        # Build prompt with intent package
        # Why: Give Theo full context for team building
        prompt = self._build_team_prompt(intent_package)

        try:
            # Call Theo to build team with structured output enforcement
            # Why: result_type forces LLM to return TheoTeamDefinition structure
            # No manual validation needed - Pydantic AI handles schema generation and validation
            from .team_models import TheoTeamDefinition

            result = await self.agent.run(
                prompt,
                deps=self.state,
                output_type=TheoTeamDefinition  # Force structured output
            )

            # result.data is already a validated TheoTeamDefinition!
            team_def = result.output

            print("\n" + "=" * 60)
            print("TEAM STRUCTURE VALIDATED!")
            print("=" * 60)
            print(f"\nConductor: {team_def.conductor.identity.name} - {team_def.conductor.identity.role}")
            print(f"Specialists: {len(team_def.specialists)}")
            for spec in team_def.specialists:
                print(f"  - {spec.identity.name}: {spec.identity.focus}")
            print(f"Tools: {', '.join(team_def.get_all_tool_names())}")

            # Validate team size constraints
            validation_errors = team_def.validate_team_size()
            if validation_errors:
                print("\n" + "=" * 60)
                print("VALIDATION ERRORS")
                print("=" * 60)
                for error in validation_errors:
                    print(f"- {error}")
                return TeamBuildResult(
                    success=False,
                    error_type="validation",
                    error_message="Team validation failed",
                    validation_errors=validation_errors
                )

            # Generate team name from intent
            # Why: Use intent title as filesystem-safe team name
            import re
            team_name = intent_package.title.lower()
            team_name = re.sub(r'[^a-z0-9_-]+', '_', team_name)
            team_name = re.sub(r'_+', '_', team_name).strip('_')

            # Create team bundle
            from datetime import datetime
            bundle = TeamBundle(
                team_name=team_name,
                intent_package=self.state.intent_package,
                team_definition=team_def,
                created_at=datetime.now()
            )

            # Save team bundle
            print("\n" + "=" * 60)
            print("TEAM FINALIZED!")
            print("=" * 60)
            print("\nTranslating team to Geodesic format and saving...")

            team_location = await self._save_team_bundle(bundle)
            print(f"\nTeam saved successfully!")
            print(f"Location: {team_location}")
            print("\nYour team is ready to deploy.")
            return TeamBuildResult(success=True, team_bundle=bundle)

        except Exception as e:
            # Fatal error (validation or other)
            import traceback
            error_msg = str(e)
            print(f"\nFatal error building team: {error_msg}")
            print("\nFull traceback:")
            print(traceback.format_exc())
            return TeamBuildResult(
                success=False,
                error_type="llm_error",
                error_message=error_msg
            )

    async def quick_build(
        self,
        intent_package: IntentPackage,
        team_name: str
    ) -> TeamBuildResult:
        """
        Quick build mode - create team silently (same as start_conversation).

        Why: Single-call mode makes quick_build and start_conversation identical.
        Kept for API compatibility - both now do the same thing.

        Args:
            intent_package: Intent package from Theo
            team_name: Name for the team (currently ignored - Theo chooses name)

        Returns:
            TeamBuildResult with success status, team_bundle (if successful),
            and error details (if failed)
        """
        # In single-call mode, quick_build is the same as start_conversation
        return await self.start_conversation(intent_package)
    
    def _format_transcript_for_llm(self, raw_transcript: str) -> str:
        """
        Parse raw pydantic-ai style transcript into clean conversational format.
        Removes system prompts and instructions, keeps user/assistant turns and tool activity.
        """
        lines = []
        
        # Patterns to extract content
        patterns = {
            'user_prompt': r"UserPromptPart\(content='(.*?)', timestamp=",
            'text_response': r"TextPart\(content='(.*?)'\)",
            'tool_call': r"ToolCallPart\(tool_name='(\w+)', args='({.*?})'",
            'tool_return': r"ToolReturnPart\(tool_name='(\w+)', content=({.*?}), tool_call_id",
        }
        
        # Split into logical chunks (each UNKNOWN: block)
        chunks = raw_transcript.split('UNKNOWN: ')
        
        for chunk in chunks:
            if not chunk.strip():
                continue
                
            # Skip if it's primarily system prompt / instructions
            if 'SystemPromptPart' in chunk and 'UserPromptPart' not in chunk:
                continue
            
            # Extract user messages
            user_match = re.search(patterns['user_prompt'], chunk, re.DOTALL)
            if user_match:
                content = user_match.group(1)
                content = content.encode().decode('unicode_escape')  # Handle escapes
                lines.append(f"**User:** {content.strip()}")
            
            # Extract assistant text responses
            text_match = re.search(patterns['text_response'], chunk, re.DOTALL)
            if text_match:
                content = text_match.group(1)
                content = content.encode().decode('unicode_escape')
                lines.append(f"**Assistant:** {content.strip()}")
            
            # Extract tool calls (summarized)
            tool_call_match = re.search(patterns['tool_call'], chunk, re.DOTALL)
            if tool_call_match and not text_match:  # Only if no text response
                tool_name = tool_call_match.group(1)
                try:
                    args = json.loads(tool_call_match.group(2))
                    # Summarize key fields
                    summary = _summarize_tool_args(tool_name, args)
                    lines.append(f"**Assistant:** [Called `{tool_name}`: {summary}]")
                except:
                    lines.append(f"**Assistant:** [Called `{tool_name}`]")
        
        return "\n\n".join(lines)


    def _summarize_tool_args(self, tool_name: str, args: dict) -> str:
        """Summarize tool arguments to key information."""
        if tool_name == 'update_intent_package':
            updated = [k for k in args.keys() if k not in ('iteration_note', 'user_feedback')]
            return f"updated {', '.join(updated)}"
        elif tool_name == 'send_intent_package':
            return "finalized intent"
        else:
            return str(list(args.keys()))


    def _build_transcript_section(self, conversation_transcript: Optional[str]) -> str:
        """Build the transcript section for the Team Builder prompt."""
        if not conversation_transcript:
            return ""
        
        formatted = self._format_transcript_for_llm(conversation_transcript)
        
        return f"""
        <conversation_transcript>
        The discovery conversation that produced this intent. Contains nuance, context, 
        and user language that may not be fully captured in the one-pager.

        {formatted}
        </conversation_transcript>"""

    def _build_team_prompt(self, intent_package: IntentPackage) -> str:
        """
        Build prompt for Theo in team mode with intent package context.

        Why: Give Theo all context needed to build complete team based on templates.
        Tradeoff: Large prompt (more tokens) vs complete context (better results).

        Args:
            intent_package: Intent package from Theo (intent mode)

        Returns:
            Formatted prompt string for team building
        """
        mission = intent_package.mission
        guidance = intent_package.team_guidance

        # Get available tools from registry
        # Why: Theo should only assign tools that actually exist
        from .theo_tools import get_available_tools
        available_tools = get_available_tools()

        # Build the intent one-pager as specified in theo_team_instructions.md
        intent_onepager = f"""# {intent_package.title}

## Objective
{mission.objective}

## Strategic Context
{mission.why}

## Success Criteria
{mission.success_looks_like}
"""

        # Build hidden metadata for team building
        metadata = f"""**Expertise Domains**: {', '.join(guidance.expertise_needed)}
**Operational Modes**: {', '.join(guidance.capabilities_needed)}
**Complexity Level**: {guidance.complexity_notes}
"""

        # Build tool registry section
        if available_tools:
            tools_section = "\n\n<Available Tools>\n"
            tools_section += "These tools are available in the deployment environment. Only assign tools from this list:\n\n"
            for tool in available_tools:
                tools_section += f"- **{tool['name']}**: {tool['description']}\n"
            tools_section += "</Available Tools>"
        else:
            tools_section = "\n\n<Available Tools>\nNo tools currently registered. Set tools.available to empty array [] for all agents.\n</Available Tools>"

        # Build conversation transcript section if available
        transcript_section = ""
        if intent_package.conversation_transcript:
            transcript_section = self._format_transcript_for_llm(raw_transcript=f"{intent_package.conversation_transcript}")


        prompt = f"""You have received a confirmed workspace intent. Your job is to design the AI team composition that will execute on this intent.

This is a background job—you have complete inputs and will output a complete team specification in structured format. There's no user interaction in this phase.

<Intent>
{intent_onepager}
{metadata}
</Intent>\n
<Past_Transcript>
{transcript_section}
</Past_Transcript>\n
{tools_section}

Your job:
1. Apply the Team Building Guidelines from your instructions:
   - Determine team structure (Conductor only vs Conductor + 1-3 Specialists)
   - Design agents following the Conductor and Specialist templates
   - Make explicit trade-offs (depth vs breadth, speed vs thoroughness, autonomy vs control)
   - Address potential failure modes

2. Generate the complete team definition matching the required structure:
   - Full Conductor specification (meta, persona, philosophy, instructions, edge cases, specialist communication, tools, examples)
   - 0-3 Specialist specifications (meta, persona, philosophy, instructions, edge cases, tools, examples)
   - Complete Report (intent summary, team overview, design rationale, trade-offs, failure modes, human-in-loop points, complexity assessment, success criteria coverage, considerations)

Your output will be automatically validated against the TheoTeamDefinition structure with these top-level fields:
- conductor: TheoConductor (required)
- specialists: List[TheoSpecialist] (0-3 items)
- report: TeamBuildingReport (required)

Remember:
- Output the complete team structure directly - no tool calls needed
- Follow the Conductor and Specialist templates precisely
- Conductor gets HUMAN NAME
- Specialists get FUNCTION NAMES (Data Analyst, Report Generator, etc.)
- Provide complete examples for each agent (2 for Conductor, 1-2 for Specialists)
- Include comprehensive philosophy, edge case handling, and tool guidance
- Ensure ALL required fields are populated (quality_references, quality_metrics, etc.)
- **CRITICAL**: Only assign tools from the <Available Tools> list above. Do not invent tool names.

Generate the complete team definition now."""

        return prompt

    async def _create_ai_team(
        self,
        workspace_id: str,
        name: str,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Create an AI team in the GraphQL API.

        Args:
            workspace_id: Workspace UUID
            name: Team name
            description: Optional team description

        Returns:
            UUID of created team, or None on failure
        """
        mutation = """
        mutation CreateAITeam($workspaceId: UUID!, $name: String!, $description: String) {
            createAITeam(workspaceId: $workspaceId, name: $name, description: $description)
        }
        """

        variables = {
            "workspaceId": workspace_id,
            "name": name,
        }
        if description:
            variables["description"] = description

        try:
            result = await _run_graphql(
                mutation,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )
            team_id = result.get("createAITeam")
            if team_id:
                logger.info(f"Created AI team in GraphQL API: {team_id}")
                return team_id
            else:
                logger.warning("createAITeam mutation returned no team ID")
                return None
        except Exception as e:
            logger.warning(f"Failed to create AI team in GraphQL API: {e}")
            return None

    async def _create_ai_team_member(
        self,
        ai_team_id: str,
        agent_id: str,
        name: str,
        description: Optional[str] = None,
        role: str = "",
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[str]] = None,
        expertise: Optional[list[str]] = None,
        communication_style: Optional[str] = None
    ) -> Optional[str]:
        """
        Create an AI team member in the GraphQL API.

        Args:
            ai_team_id: AI team UUID
            agent_id: Agent identifier
            name: Member name
            description: Optional member description
            role: Member role
            system_prompt: Optional system prompt
            model: Optional model name
            temperature: Optional temperature setting
            max_tokens: Optional max tokens setting
            tools: Optional list of tool names
            expertise: Optional list of expertise areas
            communication_style: Optional communication style

        Returns:
            UUID of created team member, or None on failure
        """
        mutation = """
        mutation CreateAITeamMember(
            $aiTeamId: UUID!
            $agentId: String!
            $name: String!
            $description: String
            $role: String!
            $systemPrompt: String
            $model: String
            $temperature: Decimal
            $maxTokens: Int
            $tools: [String!]
            $expertise: [String!]
            $communicationStyle: String
        ) {
            createAITeamMember(
                aiTeamId: $aiTeamId
                agentId: $agentId
                name: $name
                description: $description
                role: $role
                systemPrompt: $systemPrompt
                model: $model
                temperature: $temperature
                maxTokens: $maxTokens
                tools: $tools
                expertise: $expertise
                communicationStyle: $communicationStyle
            )
        }
        """

        variables = {
            "aiTeamId": ai_team_id,
            "agentId": agent_id,
            "name": name,
            "role": role,
        }

        # Add optional fields only if provided
        if description:
            variables["description"] = description
        if system_prompt:
            variables["systemPrompt"] = system_prompt
        if model:
            variables["model"] = model
        if temperature is not None:
            variables["temperature"] = temperature
        if max_tokens is not None:
            variables["maxTokens"] = max_tokens
        if tools:
            variables["tools"] = tools
        if expertise:
            variables["expertise"] = expertise
        if communication_style:
            variables["communicationStyle"] = communication_style

        try:
            result = await _run_graphql(
                mutation,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )
            member_id = result.get("createAITeamMember")
            if member_id:
                logger.info(f"Created AI team member in GraphQL API: {member_id} (agent: {agent_id})")
                return member_id
            else:
                logger.warning("createAITeamMember mutation returned no member ID")
                return None
        except Exception as e:
            logger.warning(f"Failed to create AI team member in GraphQL API: {e}")
            return None

    def _build_system_prompt(self, conductor_or_specialist) -> str:
        """
        Build system prompt from agent definition.

        Args:
            conductor_or_specialist: TheoConductor or TheoSpecialist instance

        Returns:
            Combined system prompt string
        """
        lines = []

        # Add persona/background
        if hasattr(conductor_or_specialist, 'persona'):
            lines.append(f"## Background\n{conductor_or_specialist.persona.background}")
            lines.append(f"\n## Communication Style\n{conductor_or_specialist.persona.communication_style}")
            lines.append(f"\n## Personality\n{conductor_or_specialist.persona.personality}")
        elif hasattr(conductor_or_specialist, 'identity'):
            # For specialists, use identity as starting point
            lines.append(f"## Identity\n{conductor_or_specialist.identity.name} - {conductor_or_specialist.identity.focus}")

        # Add philosophy
        if hasattr(conductor_or_specialist, 'philosophy'):
            lines.append(f"\n## Problem-Solving Approach\n{conductor_or_specialist.philosophy.problem_solving_approach}")
            if hasattr(conductor_or_specialist.philosophy, 'decision_making_style'):
                lines.append(f"\n## Decision-Making Style\n{conductor_or_specialist.philosophy.decision_making_style}")
            if conductor_or_specialist.philosophy.guiding_principles:
                lines.append(f"\n## Guiding Principles\n" + "\n".join(f"- {p}" for p in conductor_or_specialist.philosophy.guiding_principles))

        # Add operations/instructions
        if hasattr(conductor_or_specialist, 'operations'):
            if hasattr(conductor_or_specialist.operations, 'solo_handling'):
                if conductor_or_specialist.operations.solo_handling:
                    lines.append(f"\n## Solo Handling\n" + "\n".join(f"- {h}" for h in conductor_or_specialist.operations.solo_handling))
            if hasattr(conductor_or_specialist.operations, 'delegation_triggers'):
                if conductor_or_specialist.operations.delegation_triggers:
                    lines.append(f"\n## Delegation Triggers\n" + "\n".join(f"- {t}" for t in conductor_or_specialist.operations.delegation_triggers))
            if hasattr(conductor_or_specialist.operations, 'called_when'):
                if conductor_or_specialist.operations.called_when:
                    lines.append(f"\n## Called When\n" + "\n".join(f"- {c}" for c in conductor_or_specialist.operations.called_when))

        return "\n".join(lines)

    def _extract_expertise(self, conductor_or_specialist, intent_package: Dict[str, Any]) -> list[str]:
        """
        Extract expertise areas from agent definition and intent package.

        Args:
            conductor_or_specialist: TheoConductor or TheoSpecialist instance
            intent_package: Intent package dictionary

        Returns:
            List of expertise areas
        """
        expertise = []

        # From intent package guidance
        guidance = intent_package.get("team_guidance", {})
        expertise_needed = guidance.get("expertise_needed", [])
        expertise.extend(expertise_needed)

        # From mission context
        if hasattr(conductor_or_specialist, 'mission'):
            # Could extract domain keywords from mission text if needed
            pass

        # From identity/focus
        if hasattr(conductor_or_specialist, 'identity'):
            if hasattr(conductor_or_specialist.identity, 'focus'):
                expertise.append(conductor_or_specialist.identity.focus)
            elif hasattr(conductor_or_specialist.identity, 'role'):
                expertise.append(conductor_or_specialist.identity.role)

        return list(set(expertise))  # Remove duplicates

    async def _save_team_bundle(self, team_bundle: TeamBundle) -> Path:
        """
        Save team bundle to disk and translate to Geodesic format.

        Why: Persists team for deployment and creates Geodesic-compatible agents.
        Tradeoff: All-in-one save (simple) vs separate steps (more control).

        Args:
            team_bundle: Complete team bundle to save

        Returns:
            Path to saved team directory

        File structure created:
            teams/{team_name}/
                agents/
                    {conductor_id}.yaml
                    {specialist_id}.yaml
                    ...
                composition.yaml
                manifest.yaml
                intent_package.json  (original intent for context)
                theo_definition.json  (original Theo format for reference)
        """
        team_name = team_bundle.team_name
        team_dir = self.teams_output_dir / team_name

        # Create team directory
        team_dir.mkdir(parents=True, exist_ok=True)

        # Save intent package (for context and exploration)
        # Why: Keep original intent alongside team definition for full context
        intent_path = team_dir / "intent_package.json"
        with open(intent_path, 'w', encoding='utf-8') as f:
            json.dump(
                team_bundle.intent_package,
                f,
                indent=2,
                default=str  # Handle datetime serialization
            )

        # Save original Theo definition (for reference/debugging)
        # Why: Keep original structured format alongside Geodesic translation
        theo_def_path = team_dir / "theo_definition.json"
        with open(theo_def_path, 'w', encoding='utf-8') as f:
            json.dump(
                team_bundle.team_definition.model_dump(),
                f,
                indent=2,
                default=str  # Handle datetime serialization
            )

        # Translate to Geodesic format and save
        # Why: Creates production-ready agent YAML files
        agent_paths = self.translator.translate(team_bundle, team_dir)

        print(f"\n✓ Team bundle saved to: {team_dir}")
        print(f"✓ Intent package saved to: intent_package.json")
        print(f"✓ Geodesic agents translated and ready")
        print(f"✓ Original Theo definition preserved in theo_definition.json")

        # Save to GraphQL API if workspace_id is provided
        if self.workspace_id:
            try:
                print(f"\nSaving team to GraphQL API...")
                
                # Get team description from intent package or report
                team_description = team_bundle.intent_package.get("summary")
                if not team_description:
                    team_description = team_bundle.team_definition.report.intent_summary
                
                # Create AI team
                ai_team_id = await self._create_ai_team(
                    workspace_id=self.workspace_id,
                    name=team_bundle.team_name.replace("_", " ").title(),
                    description=team_description
                )
                
                if ai_team_id:
                    print(f"✓ AI team created in GraphQL API: {ai_team_id}")
                    
                    # Create conductor member
                    # Use same ID generation as translator to ensure consistency
                    conductor = team_bundle.team_definition.conductor
                    conductor_id = self.translator._make_agent_id(conductor.identity.role)
                    
                    conductor_member_id = await self._create_ai_team_member(
                        ai_team_id=ai_team_id,
                        agent_id=conductor_id,
                        name=conductor.identity.name,
                        description=conductor.service_delivery.core_responsibility,
                        role=conductor.identity.role,
                        system_prompt=self._build_system_prompt(conductor),
                        tools=conductor.tools.available if conductor.tools.available else None,
                        expertise=self._extract_expertise(conductor, team_bundle.intent_package),
                        communication_style=conductor.persona.communication_style if hasattr(conductor, 'persona') else None
                    )
                    
                    if conductor_member_id:
                        print(f"✓ Conductor member created: {conductor.identity.name}")
                    
                    # Create specialist members
                    for specialist in team_bundle.team_definition.specialists:
                        # Use same ID generation as translator to ensure consistency
                        specialist_id = self.translator._make_agent_id(specialist.identity.name)
                        
                        specialist_member_id = await self._create_ai_team_member(
                            ai_team_id=ai_team_id,
                            agent_id=specialist_id,
                            name=specialist.identity.name,
                            description=specialist.service_delivery.core_responsibility,
                            role=specialist.identity.focus,
                            system_prompt=self._build_system_prompt(specialist),
                            tools=specialist.tools.available if specialist.tools.available else None,
                            expertise=self._extract_expertise(specialist, team_bundle.intent_package),
                            communication_style=None  # Specialists don't have persona.communication_style
                        )
                        
                        if specialist_member_id:
                            print(f"✓ Specialist member created: {specialist.identity.name}")
                    
                    print(f"✓ Team saved to GraphQL API successfully")
                else:
                    print(f"⚠ Failed to create AI team in GraphQL API (team still saved to disk)")
                    
            except Exception as e:
                # Don't fail team creation if GraphQL save fails
                logger.warning(f"Failed to save team to GraphQL API: {e}")
                print(f"⚠ Warning: Failed to save team to GraphQL API: {e}")
                print(f"  Team was still saved to disk at: {team_dir}")

        return team_dir

    def get_team_summary(self) -> Optional[str]:
        """
        Get user-facing summary of current team draft.

        Why: Useful for displaying team state during workflow.

        Returns:
            Formatted summary or None if no draft exists
        """
        if self.state.team_draft is None:
            return None

        team = self.state.team_draft
        conductor = team.conductor

        conductor_name = f"{conductor.identity.name} - {conductor.identity.role}"
        specialist_names = [s.identity.name for s in team.specialists]

        summary = f"""
Current Team Draft
{'='*60}

Conductor: {conductor_name}
Specialists: {', '.join(specialist_names) if specialist_names else 'None'}
Total Team Size: {1 + len(team.specialists)} agent(s)

Tools Available: {', '.join(team.get_all_tool_names())}
        """.strip()

        return summary


async def demo_team_building():
    """
    Demo the team builder with a sample intent package.

    Why: Demonstrates complete workflow from intent to deployed team.
    """
    import os
    from dotenv import load_dotenv
    from .intent_builder import IntentBuilder

    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return

    # Step 1: Build intent with Theo
    print("\n" + "="*60)
    print("DEMO: TWO-STAGE TEAM BUILDING")
    print("="*60)
    print("\nStage 1: Intent Discovery with Theo")
    print("Stage 2: Team Building with Theo (team mode)")
    print("\n" + "="*60 + "\n")

    intent_builder = IntentBuilder()
    initial_context = "I want to analyze sales performance and make strategic recommendations."

    intent_package = await intent_builder.start_conversation(initial_context)

    if not intent_package:
        print("\nIntent discovery cancelled.")
        return

    # Step 2: Build team with Theo (team mode)
    print("\n" + "="*60)
    print("STAGE 2: TEAM BUILDING")
    print("="*60 + "\n")

    team_builder = TeamBuilder()
    team_bundle = await team_builder.start_conversation(intent_package)

    if team_bundle:
        print("\n" + "="*60)
        print("DEMO COMPLETE!")
        print("="*60)
        print(f"\nTeam '{team_bundle.team_name}' is ready for deployment.")
        print(f"\nNext steps:")
        print(f"1. Review team files in: teams/{team_bundle.team_name}/")
        print(f"2. Deploy team using Geodesic orchestration engine")
        print(f"3. Test team with sample tasks")


if __name__ == "__main__":
    asyncio.run(demo_team_building())
