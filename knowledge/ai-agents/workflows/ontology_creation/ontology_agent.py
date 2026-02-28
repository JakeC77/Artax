"""
ontology_agent.py - Ontology creation agent with dynamic system prompt injection
"""

from pathlib import Path
from typing import Union
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import KnownModelName

from app.workflows.ontology_creation.config import load_config
from app.workflows.ontology_creation.models import OntologyState


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from prompts directory."""
    prompts_dir = Path(__file__).parent / "prompts"
    file_path = prompts_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# Load all prompt components at module level (cached)
ONTOLOGY_PERSONA = load_prompt_file("ontology_agent_persona.md")
ONTOLOGY_INSTRUCTIONS = load_prompt_file("ontology_instructions.md")
try:
    ONTOLOGY_CONVERSATION_INSTRUCTIONS = load_prompt_file("ontology_conversation_instructions.md")
except FileNotFoundError:
    ONTOLOGY_CONVERSATION_INSTRUCTIONS = ""


def create_ontology_agent(
    model: Union[str, KnownModelName] = None,
    temperature: float = None,
    conversation_mode: bool = False,
) -> Agent[OntologyState]:
    """
    Create the ontology creation agent with dynamic system prompt injection.

    Args:
        model: Optional model name override. If not provided, uses central config.
               The model factory will automatically use Azure OpenAI if configured.
        temperature: Optional temperature override. If not provided, uses central config.
        conversation_mode: If True, inject conversation-mode instructions (open-ended, DB-aware).

    Returns:
        Configured Pydantic AI Agent with dynamic system prompts
    """
    # Get configuration from workflow config
    config = load_config()
    temp = temperature if temperature is not None else config.ontology_agent_temperature
    retries = config.ontology_agent_retries

    # Create model instance - use provided model or workflow config
    if model is not None:
        # Use provided model as-is (backward compatibility)
        model_instance = model
    else:
        # Use workflow config with multi-provider support
        model_instance = config.ontology_agent_model.create()

    # Create agent with persona as base system prompt
    agent = Agent(
        model=model_instance,
        deps_type=OntologyState,
        system_prompt=ONTOLOGY_PERSONA,
        retries=retries
    )

    # Configure model parameters from workflow config
    agent.model_settings = config.ontology_agent_model.get_model_settings(temperature_override=temp)

    # Dynamic system prompt: Mode-specific instructions
    @agent.instructions
    def inject_instructions(ctx: RunContext[OntologyState]) -> str:
        """Inject ontology creation instructions; add conversation-mode instructions when enabled."""
        base = ONTOLOGY_INSTRUCTIONS
        if getattr(ctx.deps, "conversation_mode", False) and ONTOLOGY_CONVERSATION_INSTRUCTIONS:
            base = base + "\n\n" + ONTOLOGY_CONVERSATION_INSTRUCTIONS
        return base

    # Dynamic system prompt: Current ontology state
    @agent.instructions
    def inject_current_ontology_state(ctx: RunContext[OntologyState]) -> str:
        """Inject current ontology package so agent can see user edits."""
        if ctx.deps.ontology_package is not None:
            pkg = ctx.deps.ontology_package
            return f"""
## CURRENT ONTOLOGY STATE (LIVE FROM USER'S EDITOR)

This is the CURRENT state of the ontology. The user can edit fields directly in their editor.
Compare these values to what you've proposed—if a value here DIFFERS from what you set, the user has edited it.

GUIDELINES:
1. When the user asks "what does X say" - read from THIS state, not your memory
2. Be AWARE of user edits - if you're about to change something the user edited, acknowledge it
   Example: "I notice you refined the Patient entity. I'll update the relationships to align with your changes."
3. It's OK to refine or improve user edits when it makes sense - just be transparent about it
4. If the user's edit and your suggestion conflict, briefly explain your reasoning

CURRENT VALUES:
- Title: {pkg.title}
- Description: {pkg.description}
- Semantic Version: {pkg.semantic_version}
- Entities ({len(pkg.entities)}):
{chr(10).join(f"  - {e.name} ({e.entity_id}): {e.description}" for e in pkg.entities)}
- Relationships ({len(pkg.relationships)}):
{chr(10).join(f"  - {r.relationship_type}: {r.from_entity} -> {r.to_entity}" for r in pkg.relationships)}
"""
        return ""

    return agent
