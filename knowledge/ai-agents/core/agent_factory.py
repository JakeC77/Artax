"""Factory for creating Pydantic AI agents from YAML configurations.

Design philosophy: Use Pydantic AI natively, no custom abstraction layers.

Why: Pydantic AI handles tool attachment, schema generation, and execution.
Tradeoff: Less control over tool behavior, but 10x simpler and more maintainable.
"""

import logging
import os
from typing import Dict, Any, Union
from pydantic_ai import Agent

from app.models.agent import AgentDefinition
from app.core.model_factory import create_model
from app.core.model_config import model_config

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory for creating Pydantic AI agents from AgentDefinition configs.

    Simplified design using Pydantic AI natively:
    1. Build system prompt from YAML config layers
    2. Create Agent with OpenAI model
    3. Attach tools directly using agent.tool()
    4. Return configured agent

    Why: No adapter layer needed - Pydantic AI's @agent.tool() is perfect.
    """

    def __init__(
        self,
        tool_registry: Dict[str, Any] | None = None,
        model: str = None,
    ):
        """Initialize the factory.

        Args:
            tool_registry: Dictionary mapping tool names to tool functions (defaults to tools.TOOL_REGISTRY)
            model: Optional model name override. If not provided, uses central config.
                   The model factory will automatically use Azure OpenAI if configured,
                   otherwise falls back to OpenAI.
        """
        # Import tool registry if not provided
        if tool_registry is None:
            try:
                from app.tools import TOOL_REGISTRY
                tool_registry = TOOL_REGISTRY
            except ImportError:
                logger.warning("Could not import app.tools.TOOL_REGISTRY. Tools will not be available.")
                tool_registry = {}

        self.tool_registry = tool_registry

        # Get configuration from central model config
        config = model_config.get("agent_factory")
        self.model_name = model or config.model
        self._provider = config.provider

        logger.info(
            "AgentFactory initialized",
            extra={
                "num_tools_available": len(tool_registry),
                "default_model": self.model_name,
            }
        )

    def build_system_prompt(self, agent_def: AgentDefinition) -> str:
        """Build comprehensive system prompt from agent definition layers.

        Combines Identity + Cognition + Behavior + Capabilities into one prompt.

        Why: Rich context helps agents understand their role and responsibilities.
        Tradeoff: Longer prompts cost more tokens, but significantly improve quality.

        Args:
            agent_def: AgentDefinition from YAML

        Returns:
            Complete system prompt string
        """
        sections = []

        # Layer 1: Identity - Who you are
        identity = agent_def.identity
        sections.append("# IDENTITY")
        sections.append(f"Role: {identity.role}")
        sections.append(f"Domain Expertise: {', '.join(identity.domain_expertise)}")
        sections.append(f"Purpose: {identity.purpose}")
        sections.append(f"Communication Style: {identity.communication_style}")
        sections.append("")

        # Layer 2: Cognition - How you think
        cognition = agent_def.cognition

        if cognition.instructions:
            # New format: instructions already include ReAct patterns and tool examples
            sections.append(cognition.instructions)
            sections.append("")
        else:
            # Legacy format: build from system_prompt
            sections.append("# COGNITION")
            sections.append(cognition.system_prompt or "")
            sections.append(f"\nReasoning Mode: {cognition.reasoning_mode}")

            if cognition.reflection_enabled:
                sections.append(
                    "Reflection: Review your reasoning before responding"
                )

            sections.append(f"Max Reasoning Steps: {cognition.max_reasoning_steps}")
            sections.append("")

        # Layer 3: Behavior - What you do
        behavior = agent_def.behavior
        sections.append("# BEHAVIOR")
        sections.append(f"Task Types: {', '.join(behavior.task_types)}")

        if behavior.quality_checks:
            sections.append(f"Quality Checks: {', '.join(behavior.quality_checks)}")

        sections.append("")

        # Layer 4: Capabilities - Tools available (brief mention, Pydantic AI shows schema)
        capability = agent_def.capability
        if capability.tools:
            sections.append("# CAPABILITIES")
            sections.append(f"Available Tools: {', '.join(capability.tools)}")
            sections.append(
                f"Max Tool Calls Per Task: {capability.max_tool_calls_per_task}"
            )
            sections.append("")

        system_prompt = "\n".join(sections)

        logger.debug(
            f"Built system prompt for agent '{agent_def.id}'",
            extra={
                "agent_id": agent_def.id,
                "prompt_length": len(system_prompt),
                "num_tools": len(capability.tools),
            }
        )

        return system_prompt

    def create_agent(
        self,
        agent_def: AgentDefinition,
        model_name: str | None = None,
        deps_type: type = dict,
    ) -> Agent:
        """Create a Pydantic AI Agent from an AgentDefinition.

        Uses native Pydantic AI patterns:
        - Agent() with @agent.instructions decorator
        - agent.tool() to attach tools directly
        - No adapter layer needed

        Args:
            agent_def: AgentDefinition loaded from YAML
            model_name: Model name (e.g., "gpt-4o-mini"). If None, uses factory default.
                       The model factory will automatically use Azure OpenAI if configured.
            deps_type: Type for agent dependencies (default: dict)

        Returns:
            Configured Pydantic AI Agent instance

        Example:
            >>> factory = AgentFactory()
            >>> agent_def = registry.get("research_analyst")
            >>> agent = factory.create_agent(agent_def)
            >>> result = await agent.run("Research competitor pricing")
        """
        # Use model factory to create the appropriate model
        model_to_use = model_name or self.model_name
        model = create_model(model_to_use, self._provider)
        
        logger.info(
            f"Creating agent '{agent_def.id}' v{agent_def.version}",
            extra={
                "agent_id": agent_def.id,
                "role": agent_def.identity.role,
                "num_tools": len(agent_def.capability.tools),
                "model_name": model_to_use,
                "model_type": type(model).__name__ if not isinstance(model, str) else "string",
            }
        )

        try:
            # Step 1: Create Pydantic AI Agent with dynamic instructions
            agent = Agent(
                model=model,
                deps_type=deps_type,
            )

            # Define dynamic instructions function
            # This is called on EVERY agent.run() with access to ctx.deps
            @agent.instructions
            def get_instructions(ctx) -> str:
                """Build instructions dynamically with injected context."""
                # Start with base prompt from YAML
                base_prompt = self.build_system_prompt(agent_def)
                
                # For now, just return base prompt
                # Future: Can inject memory context, user prefs, etc. from ctx.deps
                return base_prompt

            logger.debug(
                f"Created Pydantic AI agent",
                extra={"agent_id": agent_def.id}
            )

            # Step 2: Attach tools directly using Pydantic AI's native method
            # Why: agent.tool() is how Pydantic AI wants us to attach tools
            if agent_def.capability.tools:
                for tool_name in agent_def.capability.tools:
                    # Get tool function from registry
                    tool_func = self.tool_registry.get(tool_name)

                    if not tool_func:
                        logger.warning(
                            f"Tool '{tool_name}' not found in registry. "
                            f"Available: {list(self.tool_registry.keys())}",
                            extra={"agent_id": agent_def.id, "tool": tool_name}
                        )
                        continue

                    # Attach tool directly to agent (native Pydantic AI)
                    # Why: No adapter needed - Pydantic AI reads type hints and docstring
                    agent.tool(tool_func)

                    logger.debug(
                        f"Attached tool '{tool_name}'",
                        extra={"agent_id": agent_def.id, "tool": tool_name}
                    )

                logger.info(
                    f"Attached {len(agent_def.capability.tools)} tools",
                    extra={
                        "agent_id": agent_def.id,
                        "tools": agent_def.capability.tools,
                    }
                )

            # Success!
            logger.info(
                f"Successfully created agent '{agent_def.id}'",
                extra={
                    "agent_id": agent_def.id,
                    "num_tools": len(agent_def.capability.tools),
                }
            )

            return agent

        except ValueError as e:
            logger.error(
                f"Configuration error creating agent '{agent_def.id}': {e}",
                exc_info=True
            )
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error creating agent '{agent_def.id}': {e}",
                exc_info=True
            )
            raise RuntimeError(
                f"Failed to create agent '{agent_def.id}': {str(e)}"
            ) from e


__all__ = ["AgentFactory"]


