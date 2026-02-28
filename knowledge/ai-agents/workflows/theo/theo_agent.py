"""
theo_agent.py - Unified Theo agent with dynamic system prompt injection

Why: Theo operates in two modes (intent discovery and team building) with different
system prompts injected at runtime using Pydantic AI's @agent.system_prompt feature.

Design: Single agent definition, mode-specific prompts injected dynamically based on
state. Workflow controls mode switching deterministically.
"""

from pathlib import Path
from typing import Literal, Union, Optional
import logging
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import KnownModelName

from app.workflows.theo.config import load_config
from app.core.authenticated_graphql_client import execute_graphql

logger = logging.getLogger(__name__)


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from trident/prompts directory."""
    prompts_dir = Path(__file__).parent / "prompts"
    file_path = prompts_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_optional_prompt_file(filename: str) -> str:
    """Load a prompt file if it exists, return empty string otherwise."""
    prompts_dir = Path(__file__).parent / "prompts"
    file_path = prompts_dir / filename

    if not file_path.exists():
        return ""

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# Load all prompt components at module level (cached)
THEO_PERSONA = load_prompt_file("theo_persona.md")
THEO_INTENT_INSTRUCTIONS = load_prompt_file("theo_intent_instructions.md")
THEO_TEAM_INSTRUCTIONS = load_prompt_file("theo_team_instructions.md")
CONDUCTOR_TEMPLATE = load_prompt_file("conductor_template.txt")
SPECIALIST_TEMPLATE = load_prompt_file("specialist_template.txt")

# Optional company context (loaded if file exists)
COMPANY_CONTEXT = load_optional_prompt_file("company_context_phx.txt")

# Module-level cache for company context (keyed by workspace_id)
_company_context_cache: dict[str, str] = {}

# Module-level cache for intent instructions (keyed by workspace_id)
_intent_instructions_cache: dict[str, str] = {}


# GraphQL query for fetching workspace company data
_WORKSPACE_COMPANY_QUERY = """
query GetWorkspaceCompany($workspaceId: UUID!) {
  workspaceById(workspaceId: $workspaceId) {
    workspaceId
    companyId
    company {
      companyId
      tenantId
      name
      markdownContent
    }
  }
}
"""

# GraphQL query for fetching workspace ontology with domainExamples
_WORKSPACE_ONTOLOGY_QUERY = """
query GetWorkspaceWithOntology($workspaceId: UUID!) {
  workspaceById(workspaceId: $workspaceId) {
    workspaceId
    name
    ontologyId
    ontology {
      ontologyId
      tenantId
      name
      description
      domainExamples
      status
      jsonUri
      company { companyId name }
    }
  }
}
"""


def load_company_context(workspace_id: str, tenant_id: Optional[str] = None) -> str:
    """
    Load company context from GraphQL API, with fallback to file.
    
    Uses module-level caching to avoid repeated GraphQL queries for the same workspace.
    
    Args:
        workspace_id: Workspace UUID to fetch company data for
        tenant_id: Optional tenant ID for GraphQL authentication
        
    Returns:
        Company context markdown string, or empty string if not available
    """
    # Check cache first
    if workspace_id in _company_context_cache:
        return _company_context_cache[workspace_id]
    
    # Try GraphQL API first
    try:
        variables = {"workspaceId": workspace_id}
        data = execute_graphql(
            _WORKSPACE_COMPANY_QUERY,
            variables,
            tenant_id=tenant_id
        )
        
        # Extract markdownContent from response
        workspace_data = data.get("workspaceById")
        if workspace_data:
            company = workspace_data.get("company")
            if company:
                markdown_content = company.get("markdownContent")
                if markdown_content:
                    # Cache and return
                    _company_context_cache[workspace_id] = markdown_content
                    logger.info(f"Loaded company context from API for workspace {workspace_id[:8]}...")
                    return markdown_content
        
        # No company data in API response, fallback to file
        logger.debug(f"No company data found in API for workspace {workspace_id[:8]}..., using file fallback")
        
    except Exception as e:
        # GraphQL query failed, fallback to file
        logger.warning(f"Failed to load company context from API for workspace {workspace_id[:8]}...: {e}. Using file fallback.")
    
    # Fallback to file-based context
    fallback_context = COMPANY_CONTEXT
    if fallback_context:
        # Cache the fallback for this workspace to avoid repeated file reads
        _company_context_cache[workspace_id] = fallback_context
        logger.debug(f"Using file-based company context for workspace {workspace_id[:8]}...")
    
    return fallback_context


def load_intent_instructions(workspace_id: str, tenant_id: Optional[str] = None) -> str:
    """
    Load intent instructions from workspace ontology domainExamples, with fallback to file.
    
    Uses module-level caching to avoid repeated GraphQL queries for the same workspace.
    
    Args:
        workspace_id: Workspace UUID to fetch ontology data for
        tenant_id: Optional tenant ID for GraphQL authentication
        
    Returns:
        Intent instructions markdown string, or empty string if not available
    """
    # Check cache first
    if workspace_id in _intent_instructions_cache:
        return _intent_instructions_cache[workspace_id]
    
    # Try GraphQL API first
    try:
        variables = {"workspaceId": workspace_id}
        data = execute_graphql(
            _WORKSPACE_ONTOLOGY_QUERY,
            variables,
            tenant_id=tenant_id
        )
        
        # Extract domainExamples from response
        workspace_data = data.get("workspaceById")
        if workspace_data:
            ontology = workspace_data.get("ontology")
            if ontology:
                domain_examples = ontology.get("domainExamples")
                if domain_examples:
                    # Cache and return
                    _intent_instructions_cache[workspace_id] = domain_examples
                    logger.info(f"Loaded intent instructions from ontology API for workspace {workspace_id[:8]}...")
                    return domain_examples
        
        # No ontology or domainExamples in API response, fallback to file
        logger.debug(f"No domainExamples found in ontology for workspace {workspace_id[:8]}..., using file fallback")
        
    except Exception as e:
        # GraphQL query failed, fallback to file
        logger.warning(f"Failed to load intent instructions from API for workspace {workspace_id[:8]}...: {e}. Using file fallback.")
    
    # Fallback to file-based instructions
    fallback_instructions = THEO_INTENT_INSTRUCTIONS
    if fallback_instructions:
        # Cache the fallback for this workspace to avoid repeated file reads
        _intent_instructions_cache[workspace_id] = fallback_instructions
        logger.debug(f"Using file-based intent instructions for workspace {workspace_id[:8]}...")
    
    return fallback_instructions


class TheoState:
    """
    Base state for Theo agent - mode determines which prompts are injected.

    Why: Single state class that works for both modes. The mode field determines
    which @agent.system_prompt decorators are active.
    """
    def __init__(self, mode: Literal["intent", "team"] = "intent", workspace_id: Optional[str] = None, tenant_id: Optional[str] = None):
        self.mode: Literal["intent", "team"] = mode
        # Workspace context for company data lookup
        self.workspace_id: Optional[str] = workspace_id
        self.tenant_id: Optional[str] = tenant_id
        # Intent-specific state
        self.intent_package = None
        self.intent_proposed = False  # True when Theo calls propose_intent tool
        self.intent_finalized = False  # True when user confirms
        # Intent broadcast signals - set by tools, consumed by intent_builder
        self.intent_needs_broadcast = False  # True when user-facing fields changed
        self.last_update_summary: str | None = None  # Natural language summary of last update
        # User edit tracking - fields the user edited since last AI update
        self.user_edited_fields: list[str] = []
        # Team-specific state
        self.team_draft = None
        self.team_finalized = False
        self.team_bundle = None

    def clear_broadcast_signal(self):
        """Clear the broadcast signal after emitting intent_updated event."""
        self.intent_needs_broadcast = False
        self.last_update_summary = None

    def clear_user_edited_fields(self):
        """Clear user_edited_fields after AI updates intent."""
        self.user_edited_fields = []


def create_theo_agent(
    model: Union[str, KnownModelName] = None,
    temperature: float = None
) -> Agent[TheoState]:
    """
    Create the Theo agent with dynamic system prompt injection.

    Args:
        model: Optional model name override. If not provided, uses central config.
               The model factory will automatically use Azure OpenAI if configured.
        temperature: Optional temperature override. If not provided, uses central config.

    Returns:
        Configured Pydantic AI Agent with dynamic system prompts

    How it works:
        - Agent is created with empty system_prompt (prompts injected dynamically)
        - @agent.system_prompt decorators check state.mode and inject appropriate prompts
        - Intent mode: persona + intent_instructions
        - Team mode: persona + team_instructions + templates
    """
    # Get configuration from workflow config
    config = load_config()
    temp = temperature if temperature is not None else config.theo_temperature
    retries = config.theo_retries

    # Create model instance - use provided model or workflow config
    if model is not None:
        # Use provided model as-is (backward compatibility)
        model_instance = model
    else:
        # Use workflow config with multi-provider support
        model_instance = config.theo_model.create()

    # Create agent with no static system prompt (all prompts are dynamic)
    agent = Agent(
        model=model_instance,
        deps_type=TheoState,
        system_prompt=THEO_PERSONA,
        retries=retries
    )

    # Configure model parameters from workflow config
    # Why: Temperature 0.4 balances creativity (team design) with structure (following templates)
    # get_model_settings() also handles provider-specific settings like Google thinking config
    agent.model_settings = config.theo_model.get_model_settings(temperature_override=temp)

    # Dynamic system prompt 2: Mode-specific instructions
    @agent.instructions
    def inject_mode_instructions(ctx: RunContext[TheoState]) -> str:
        """Inject mode-specific instructions based on current state."""
        if ctx.deps.mode == "intent":
            # Try to load intent instructions dynamically if workspace_id is available
            if ctx.deps.workspace_id:
                return load_intent_instructions(ctx.deps.workspace_id, ctx.deps.tenant_id)
            else:
                # Fallback to file-based instructions if no workspace_id
                return THEO_INTENT_INSTRUCTIONS
        elif ctx.deps.mode == "team":
            return THEO_TEAM_INSTRUCTIONS
        return ""

    # Dynamic system prompt 3: Team mode templates (only active in team mode)
    @agent.instructions
    def inject_templates(ctx: RunContext[TheoState]) -> str:
        """Inject conductor and specialist templates - only in team mode."""
        if ctx.deps.mode == "team":
            # Inject templates with clear separation
            return f"""
## CONDUCTOR TEMPLATE

{CONDUCTOR_TEMPLATE}

## SPECIALIST TEMPLATE

{SPECIALIST_TEMPLATE}
"""
        return ""

    # Dynamic system prompt 4: Company/domain context (intent mode only)
    @agent.instructions
    def inject_company_context(ctx: RunContext[TheoState]) -> str:
        """Inject company/domain context to help Theo understand the business domain."""
        if ctx.deps.mode != "intent":
            return ""
        
        # Try to load company context dynamically if workspace_id is available
        company_context = ""
        if ctx.deps.workspace_id:
            company_context = load_company_context(ctx.deps.workspace_id, ctx.deps.tenant_id)
        else:
            # Fallback to file-based context if no workspace_id
            company_context = COMPANY_CONTEXT
        
        if company_context:
            return f"""
## COMPANY/DOMAIN CONTEXT

The user works in the following business context. Use this to understand domain-specific
terminology, business processes, and what kinds of analyses are relevant.

{company_context}
"""
        return ""

    # Dynamic system prompt 5: Current intent state (intent mode only)
    # Why: User can edit intent fields directly in the frontend editor.
    # This injection ensures Theo sees the user's current state before responding,
    # enabling Theo to respect user edits and not overwrite them.
    @agent.instructions
    def inject_current_intent_state(ctx: RunContext[TheoState]) -> str:
        """Inject current intent package so Theo can see user edits."""
        if ctx.deps.mode == "intent" and ctx.deps.intent_package is not None:
            pkg = ctx.deps.intent_package
            return f"""
## CURRENT INTENT STATE (LIVE FROM USER'S EDITOR)

This is the CURRENT state of the intent. The user can edit fields directly in their editor.
Compare these values to the "values_set" in your previous update_intent_package tool calls -
if a value here DIFFERS from what you set, the user has edited it.

GUIDELINES:
1. When the user asks "what does X say" - read from THIS state, not your memory
2. Be AWARE of user edits - if you're about to change something the user edited, acknowledge it
   Example: "I notice you refined the objective. I'll update the success criteria to align with your changes."
3. It's OK to refine or improve user edits when it makes sense - just be transparent about it
4. If the user's edit and your suggestion conflict, briefly explain your reasoning

CURRENT VALUES:
- Title: {pkg.title}
- Description: {pkg.description}
- Summary: {pkg.summary}
- Objective: {pkg.mission.objective}
- Why: {pkg.mission.why}
- Success Looks Like: {pkg.mission.success_looks_like}
"""
        return ""

    # Dynamic system prompt 6: User edited fields (intent mode only)
    # Why: Frontend tracks which fields user edited since last AI update.
    # This allows Theo to acknowledge user edits naturally.
    @agent.instructions
    def inject_user_edit_awareness(ctx: RunContext[TheoState]) -> str:
        """Inject user edited fields so Theo knows what the user changed."""
        if ctx.deps.mode == "intent" and ctx.deps.user_edited_fields:
            fields_list = ", ".join(ctx.deps.user_edited_fields)
            return f"""
## USER EDITS

The user has edited the following fields since your last update: {fields_list}

Acknowledge briefly if relevant. Do not overwrite these unless explicitly asked.
"""
        return ""

    return agent


def create_intent_agent(
    model: Union[str, KnownModelName] = "gpt-4o-mini"
) -> Agent[TheoState]:
    """
    Create Theo agent configured for intent discovery mode.

    Convenience function that creates agent and ensures it starts in intent mode.
    State will have mode="intent" by default.
    
    Args:
        model: Model name to use. The model factory will automatically use
               Azure OpenAI if configured. Default: "gpt-4o-mini"
    """
    return create_theo_agent(model=model)


def create_team_agent(
    model: Union[str, KnownModelName] = "gpt-4o-mini"
) -> Agent[TheoState]:
    """
    Create Theo agent configured for team building mode.

    Convenience function for team building. Note: You must create state with
    mode="team" when running this agent.
    
    Args:
        model: Model name to use. The model factory will automatically use
               Azure OpenAI if configured. Default: "gpt-4o-mini"
    """
    return create_theo_agent(model=model)
