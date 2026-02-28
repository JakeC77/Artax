"""Load agent definitions from YAML files."""

import yaml
from pathlib import Path
from app.models.agent import AgentDefinition


def load_agent_from_yaml(file_path: str | Path) -> AgentDefinition:
    """Load a single agent definition from a YAML file."""
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return AgentDefinition(**data)


def load_agents_from_directory(directory: str | Path) -> dict[str, AgentDefinition]:
    """Load all agent definitions from a directory."""
    directory = Path(directory)

    if not directory.exists():
        if not directory.is_absolute():
            # Allow relative paths that are intended to be relative to app/
            module_root = Path(__file__).resolve().parent.parent
            candidate = module_root / directory
            if candidate.exists():
                directory = candidate
            else:
                cwd_target = (Path.cwd() / directory).resolve(strict=False)
                module_target = candidate.resolve(strict=False)
                raise FileNotFoundError(
                    f"Agent directory '{directory}' not found. "
                    f"Tried '{cwd_target}' and '{module_target}'."
                )
        else:
            raise FileNotFoundError(f"Agent directory '{directory}' not found.")

    agents = {}

    for yaml_file in directory.glob("*.yaml"):
        agent = load_agent_from_yaml(yaml_file)
        agents[agent.id] = agent

    return agents


