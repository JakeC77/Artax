"""
data_loader_agent.py - Data loading agent with dynamic system prompt injection
"""

from pathlib import Path
from typing import Union
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import KnownModelName

from app.workflows.data_loading.config import load_config
from app.workflows.data_loading.models import DataLoadingState
from app.workflows.data_loading import tools


def load_prompt_file(filename: str) -> str:
    """Load a prompt file from prompts directory."""
    prompts_dir = Path(__file__).parent / "prompts"
    file_path = prompts_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# Load all prompt components at module level (cached)
DATA_LOADER_PERSONA = load_prompt_file("data_loader_persona.md")
DATA_LOADER_INSTRUCTIONS = load_prompt_file("data_loader_instructions.md")


def create_data_loader_agent(
    model: Union[str, KnownModelName] = None,
    temperature: float = None
) -> Agent[dict]:
    """
    Create the data loading agent with dynamic system prompt injection.

    Args:
        model: Optional model name override. If not provided, uses central config.
        temperature: Optional temperature override. If not provided, uses central config.

    Returns:
        Configured Pydantic AI Agent with dynamic system prompts
    """
    # Get configuration from workflow config
    config = load_config()
    temp = temperature if temperature is not None else config.data_loader_temperature
    retries = config.data_loader_retries

    # Create model instance - use provided model or workflow config
    if model is not None:
        # Use provided model as-is (backward compatibility)
        model_instance = model
    else:
        # Use workflow config with multi-provider support
        model_instance = config.data_loader_model.create()

    # Create agent with persona as base system prompt
    agent = Agent(
        model=model_instance,
        deps_type=dict,  # Use dict for flexible context
        system_prompt=DATA_LOADER_PERSONA,
        retries=retries
    )

    # Configure model parameters from workflow config
    agent.model_settings = config.data_loader_model.get_model_settings(temperature_override=temp)

    # Dynamic system prompt: Mode-specific instructions
    @agent.instructions
    def inject_instructions(ctx: RunContext[dict]) -> str:
        """Inject data loading instructions."""
        return DATA_LOADER_INSTRUCTIONS

    # Dynamic system prompt: Current CSV structure
    @agent.instructions
    def inject_csv_structure(ctx: RunContext[dict]) -> str:
        """Inject current CSV structure so agent can see what it's working with."""
        csv_structure = ctx.deps.get("csv_structure")
        if csv_structure:
            from app.workflows.data_loading.models import CSVStructure
            if isinstance(csv_structure, CSVStructure):
                cols_info = "\n".join([
                    f"  - {col.name} ({col.data_type})" + (" [nullable]" if col.nullable else "")
                    for col in csv_structure.columns
                ])
                return f"""
## CURRENT CSV STRUCTURE

Columns ({len(csv_structure.columns)}):
{cols_info}

Row count: {csv_structure.row_count}
Has headers: {csv_structure.has_headers}
"""
        return ""

    # Dynamic system prompt: Current mapping
    @agent.instructions
    def inject_mapping(ctx: RunContext[dict]) -> str:
        """Inject current mapping so agent can see what's been mapped."""
        mapping = ctx.deps.get("mapping")
        if mapping:
            from app.workflows.data_loading.models import DataMapping
            if isinstance(mapping, DataMapping):
                entity_info = "\n".join([
                    f"  - {em.entity_name}: {', '.join(em.csv_columns)}"
                    for em in mapping.entity_mappings
                ])
                rel_info = "\n".join([
                    f"  - {rm.relationship_type}: {rm.from_entity} → {rm.to_entity}"
                    for rm in mapping.relationship_mappings
                ])
                return f"""
## CURRENT MAPPING

Entity Mappings ({len(mapping.entity_mappings)}):
{entity_info}

Relationship Mappings ({len(mapping.relationship_mappings)}):
{rel_info}

Unmapped Columns: {', '.join(mapping.unmapped_columns) if mapping.unmapped_columns else 'None'}
"""
        return ""

    # Register all tools
    for tool_name, tool_func in tools.DATA_LOADING_TOOLS.items():
        agent.tool(tool_func)

    return agent
