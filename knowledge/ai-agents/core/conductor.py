"""Conductor agent that orchestrates the team."""

from pydantic_ai import Agent
from pydantic import BaseModel, Field
from typing import Optional, Any
from app.models.task import Task, Subtask
from app.core.registry import AgentRegistry
from app.core.model_factory import create_model
from app.core.model_config import model_config
from app.utils.streaming import stream_with_logger


class SubtaskSpec(BaseModel):
    """Specification for a single subtask."""
    description: str = Field(..., description="Clear description of what needs to be done")
    agent_id: str = Field(..., description="ID of the agent to handle this subtask")
    depends_on: list[str] = Field(default_factory=list, description="IDs of subtasks that must complete first")


class TaskDecomposition(BaseModel):
    """Structured output for task decomposition."""
    subtasks: list[SubtaskSpec] = Field(..., description="List of subtasks to execute")


class ConductorDeps:
    """Dependencies for the conductor agent."""
    def __init__(self, registry: AgentRegistry, tool_registry=None):
        self.registry = registry
        self.tool_registry = tool_registry
        self.available_agents = {
            agent.id: {
                "role": agent.identity.role,
                "expertise": agent.identity.domain_expertise,
                "task_types": agent.behavior.task_types,
                "tools": agent.capability.tools,  # Include tools for better task decomposition
            }
            for agent in registry.all_agents()
        }


class Conductor:
    """High-level orchestrator that decomposes tasks and routes to specialists."""

    def __init__(self, registry: AgentRegistry, tool_registry=None, model: str = None):
        self.registry = registry
        self.tool_registry = tool_registry

        # Get configuration from central model config
        config = model_config.get("conductor")
        self.model_name = model or config.model
        self._retries = config.retries

        # Use model factory to create the appropriate model
        model_instance = create_model(self.model_name, config.provider)

        # Create Pydantic AI agent for decomposition
        self.decomposer = Agent(
            model=model_instance,
            deps_type=ConductorDeps,
            output_type=TaskDecomposition,
            name="conductor_decomposer",
            retries=self._retries,
        )
        
        # System prompt for task decomposition
        @self.decomposer.instructions
        def decomposition_instructions(ctx) -> str:
            agent_info = "\n".join([
                f"- {agent_id}: {info['role']} (expertise: {', '.join(info['expertise'])}, "
                f"handles: {', '.join(info['task_types'])}, "
                f"tools: {', '.join(info.get('tools', []))})"
                for agent_id, info in ctx.deps.available_agents.items()
            ])
            
            return f"""You are a task orchestrator. Break down user complex user tasks into 1-6 subtasks. If it is a simple command/question, just return a single subtask.

Available agents:
{agent_info}

IMPORTANT: When creating subtask descriptions, consider the tools available to each agent. 
For example, if an agent has "graph_node_lookup" tool, you can instruct them to use it to get detailed information.
If an agent has "workspace_items_lookup", they can search the workspace for items.

For each subtask, you must specify:
- description: Clear, actionable description that may reference available tools when appropriate
- agent_id: Must be one of the agent IDs listed above
- depends_on: List of subtask indices that must finish first (empty list if none)

Example output format:
{{
  "subtasks": [
    {{
      "description": "Research competitor pricing data",
      "agent_id": "research_analyst",
      "depends_on": []
    }},
    {{
      "description": "Analyze pricing patterns using available data tools",
      "agent_id": "data_analyst", 
      "depends_on": []
    }},
    {{
      "description": "Get detailed information about each member using graph_node_lookup tool",
      "agent_id": "data_analyst",
      "depends_on": []
    }}
  ]
}}

Rules:
1. Keep to 1-6 subtasks max
2. Make each subtask specific and actionable
3. Use only agent_ids from the available agents list
4. Most subtasks can run independently (empty depends_on)
5. When appropriate, mention relevant tools in subtask descriptions to guide the agent"""
    
    async def decompose_task(
        self, 
        task_description: str,
        current_plan: list[SubtaskSpec] | None = None,
        conversation_history: list[str] | None = None
    ) -> Task:
        """Decompose a task into subtasks.
        
        Args:
            task_description: Description of the task to decompose or user feedback
            current_plan: Optional current plan to modify (for feedback scenarios)
            conversation_history: Optional conversation history for context
        """
        deps = ConductorDeps(self.registry, self.tool_registry)
        
        # Build context from conversation history
        context_parts = []
        if conversation_history:
            # Include workflow results (they start with "WORKFLOW RESULT")
            workflow_results = [msg for msg in conversation_history if msg.startswith("WORKFLOW RESULT")]
            other_history = [msg for msg in conversation_history if not msg.startswith("WORKFLOW RESULT")]
            
            # Always include workflow results if present
            if workflow_results:
                context_parts.append("WORKFLOW RESULTS FROM PREVIOUS EXECUTIONS:")
                context_parts.extend(workflow_results)
                context_parts.append("")  # Empty line separator
            
            # Include recent conversation history (last 3 non-workflow messages)
            if other_history:
                history_text = "\n".join([f"Previous: {msg}" for msg in other_history[-3:]])
                context_parts.append(history_text)
        
        if current_plan:
            # Modify existing plan based on feedback
            current_plan_text = "\n".join([
                f"{i+1}. **{st.agent_id}**: {st.description}"
                for i, st in enumerate(current_plan)
            ])
            
            context_section = "\n\n".join(context_parts) if context_parts else ""
            if context_section:
                context_section = f"\n\nCONVERSATION CONTEXT:\n{context_section}\n"
            
            prompt = f"""Modify the following plan based on user feedback.{context_section}

Current plan:
{current_plan_text}

User feedback: {task_description}

Instructions:
- If the feedback asks to ADD something, add it to the plan
- If the feedback asks to REMOVE something, remove it
- If the feedback asks to MODIFY something, update that specific subtask
- If the feedback asks to "put task X back in" or "restore task X", restore that task
- Keep all other subtasks that weren't mentioned in the feedback unchanged
- Maintain the same structure and agent assignments where possible
- Preserve the order of existing tasks unless the feedback specifically requests reordering
- Consider the conversation context when understanding the user's intent

Return the complete updated plan with all subtasks."""
        else:
            # Initial decomposition
            context_section = "\n\n".join(context_parts) if context_parts else ""
            if context_section:
                context_section = f"\n\nCONVERSATION CONTEXT:\n{context_section}\n"
            
            prompt = f"Decompose this task: {task_description}{context_section}"
        
        result = await self.decomposer.run(
            prompt,
            deps=deps,
        )
        
        # Create Task with structured subtasks
        task = Task(description=task_description)
        
        for subtask_spec in result.output.subtasks:
            subtask = Subtask(
                description=subtask_spec.description,
                agent_id=subtask_spec.agent_id,
                depends_on=subtask_spec.depends_on,
            )
            task.subtasks.append(subtask)
        
        return task
    
    async def synthesize_results(
        self, 
        task: Task, 
        model: str | None = None,
        log_streamer: Optional[Any] = None
    ) -> str:
        """Synthesize subtask results into final output.
        
        Args:
            task: Task with subtask results to synthesize
            model: Optional model name override
            log_streamer: Optional GraphQL logger for streaming text deltas
        
        Returns:
            Synthesized final output
        """
        # Use model factory to create the appropriate model
        model_name = model or self.model_name
        model_instance = create_model(model_name)
        
        synthesis_agent = Agent(
            model=model_instance,
            name="conductor_synthesizer",
        )
        
        @synthesis_agent.instructions
        def synthesis_instructions() -> str:
            return """You are synthesizing results from multiple specialist agents.
Create a coherent, comprehensive response that combines all subtask results.
Be concise but complete. Focus on answering the original task."""
        
        subtask_results = "\n\n".join([
            f"Subtask: {st.description}\nAgent: {st.agent_id}\nResult: {st.result}"
            for st in task.subtasks if st.result
        ])
        
        prompt = f"Original task: {task.description}\n\nSubtask results:\n{subtask_results}\n\n" \
                 f"Synthesize into a final answer."
        
        # Stream text deltas if log_streamer is provided
        if log_streamer:
            return await stream_with_logger(
                synthesis_agent,
                prompt,
                log_streamer,
                "conductor",
                track_full_text=True
            )
        else:
            # Fallback to non-streaming if no log_streamer
            result = await synthesis_agent.run(prompt)
            return result.output


