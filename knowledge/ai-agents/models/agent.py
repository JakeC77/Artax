"""Agent definition models matching the 5-layer architecture."""

from typing import Literal
from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    """Layer 1: Identity - Who the agent is."""
    role: str
    domain_expertise: list[str]
    purpose: str
    communication_style: str


class AgentCognition(BaseModel):
    """Layer 2: Cognition - How the agent thinks."""
    system_prompt: str | None = None
    instructions: str | None = None
    reasoning_mode: Literal["react", "chain_of_thought"] = "react"
    max_reasoning_steps: int = 5
    reflection_enabled: bool = True

    def get_prompt(self) -> str:
        """Get the prompt text, preferring instructions over system_prompt."""
        return self.instructions or self.system_prompt or ""


class AgentCapability(BaseModel):
    """Layer 3: Capability - What the agent can do."""
    tools: list[str] = Field(default_factory=list)
    max_tool_calls_per_task: int = 5


class AgentBehavior(BaseModel):
    """Layer 4: Behavior - How the agent acts."""
    task_types: list[str]
    quality_checks: list[str] = Field(default_factory=list)


class AgentContext(BaseModel):
    """Layer 5: Context - What the agent remembers."""
    memory: dict[str, bool] = Field(
        default_factory=lambda: {"short_term": True, "long_term": True}
    )


class AgentDefinition(BaseModel):
    """Complete agent definition from YAML."""
    id: str
    version: str
    identity: AgentIdentity
    cognition: AgentCognition
    capability: AgentCapability
    behavior: AgentBehavior
    context: AgentContext = Field(default_factory=AgentContext)
    metadata: dict = Field(default_factory=dict)


