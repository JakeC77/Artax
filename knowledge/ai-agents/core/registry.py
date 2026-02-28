"""Agent registry for managing and looking up agents."""

from pathlib import Path
from app.models.agent import AgentDefinition
from app.utils.yaml_loader import load_agents_from_directory


class AgentRegistry:
    """Registry for managing agent definitions."""
    
    def __init__(self):
        self._agents: dict[str, AgentDefinition] = {}
    
    def load_from_directory(self, directory: str | Path) -> None:
        """Load all agents from a directory of YAML files."""
        agents = load_agents_from_directory(directory)
        self._agents.update(agents)
        print(f"Loaded {len(agents)} agents: {list(agents.keys())}")
    
    def register(self, agent: AgentDefinition) -> None:
        """Register a single agent."""
        self._agents[agent.id] = agent
    
    def get(self, agent_id: str) -> AgentDefinition:
        """Get an agent by ID."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent '{agent_id}' not found in registry")
        return self._agents[agent_id]
    
    def find_by_task_type(self, task_type: str) -> list[AgentDefinition]:
        """Find agents that can handle a specific task type."""
        return [
            agent for agent in self._agents.values()
            if task_type in agent.behavior.task_types
        ]
    
    def all_agents(self) -> list[AgentDefinition]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def agent_ids(self) -> list[str]:
        """Get all agent IDs."""
        return list(self._agents.keys())


