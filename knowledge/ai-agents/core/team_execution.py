"""Simplified team execution engine for workspace chat workflow."""

import logging
from typing import AsyncIterator, Any
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from app.utils.streaming import stream_agent_text

from app.models.task import Task, Subtask, ActivityEvent
from app.models.agent import AgentDefinition
from app.core.agent_factory import AgentFactory

logger = logging.getLogger(__name__)


class TeamExecutionEngine:
    """Simplified team execution engine for chat workflows."""
    
    def __init__(self, agent_registry, conductor, tool_registry=None):
        """Initialize team execution engine.
        
        Args:
            agent_registry: AgentRegistry with available agents
            conductor: Conductor for task decomposition
            tool_registry: Optional tool registry (will be passed to AgentFactory)
        """
        self.agent_registry = agent_registry
        self.conductor = conductor
        self.tool_registry = tool_registry
        
        # Initialize AgentFactory for creating agents with tools
        # Model factory will automatically use Azure OpenAI if configured
        self.agent_factory = AgentFactory(
            tool_registry=tool_registry,
            model="gpt-4o-mini",
        )
        
        self._agent_cache: dict[str, Agent] = {}
    
    def _create_pydantic_agent(self, agent_def: AgentDefinition) -> Agent:
        """Create a Pydantic AI agent from definition using AgentFactory.
        
        This ensures agents are created with proper tools attached.
        """
        if agent_def.id in self._agent_cache:
            return self._agent_cache[agent_def.id]
        
        # Use AgentFactory to create agent with tools
        agent = self.agent_factory.create_agent(agent_def)
        
        self._agent_cache[agent_def.id] = agent
        return agent
    
    async def execute_subtask(
        self,
        subtask: Subtask,
        task: Task,
        workspace_id: str | None = None,
        tenant_id: str | None = None,
        memory_context: dict | None = None,
        conversation_history: list[str] | None = None,
    ) -> AsyncIterator[ActivityEvent]:
        """Execute a single subtask and stream events.
        
        Args:
            subtask: Subtask to execute
            task: Parent task
            workspace_id: Workspace ID for workspace tools
            tenant_id: Tenant ID for workspace tools
            memory_context: Memory context for memory_retrieve tool
            conversation_history: Optional conversation history for context
        """
        agent_def = self.agent_registry.get(subtask.agent_id)
        agent = self._create_pydantic_agent(agent_def)
        
        yield ActivityEvent(
            event_type="agent_started",
            agent_id=subtask.agent_id,
            message=f"[{agent_def.identity.role}] Starting: {subtask.description}",
            task_id=task.id,
            metadata={"subtask_id": subtask.id},
        )
        
        subtask.status = "running"
        
        try:
            usage_limits = UsageLimits(
                tool_calls_limit=agent_def.capability.max_tool_calls_per_task
            )
            
            # Build dependencies dict for tools
            deps = {}
            if workspace_id:
                deps["workspace_id"] = workspace_id
            if tenant_id:
                deps["tenant_id"] = tenant_id
            if memory_context:
                deps["memory_context"] = memory_context
            
            # Build enhanced prompt with conversation history
            enhanced_prompt = subtask.description
            if conversation_history:
                # Include workflow results (they start with "WORKFLOW RESULT")
                workflow_results = [msg for msg in conversation_history if msg.startswith("WORKFLOW RESULT")]
                other_history = [msg for msg in conversation_history if not msg.startswith("WORKFLOW RESULT")]
                
                context_parts = []
                
                # Always include workflow results if present
                if workflow_results:
                    context_parts.append("WORKFLOW RESULTS FROM PREVIOUS EXECUTIONS:")
                    context_parts.extend(workflow_results)
                    context_parts.append("")  # Empty line separator
                
                # Include recent conversation history (last 3 non-workflow messages)
                if other_history:
                    history_text = "\n".join([f"Previous message: {msg}" for msg in other_history[-3:]])
                    context_parts.append(history_text)
                
                if context_parts:
                    context_section = "\n\n".join(context_parts)
                    enhanced_prompt = f"""{subtask.description}

CONVERSATION CONTEXT:
{context_section}

Use the conversation context above to understand the full context of this task. Reference previous workflow results when relevant."""
            
            # Stream text deltas as they're generated
            result = None
            
            async for batch_text, acc_len, part_idx, metadata, event_result in stream_agent_text(
                agent,
                enhanced_prompt,
                deps=deps if deps else None,
                usage_limits=usage_limits
            ):
                # Add subtask-specific metadata
                metadata.update({
                    "subtask_id": subtask.id,
                    "delta_type": "text",
                })
                
                # Yield ActivityEvent for each batch
                yield ActivityEvent(
                    event_type="agent_thinking",
                    agent_id=subtask.agent_id,
                    message=batch_text,
                    task_id=task.id,
                    metadata=metadata,
                )
                
                # Capture result from the last yield
                if event_result is not None:
                    result = event_result
                    if hasattr(result, 'output'):
                        subtask.result = result.output
                    else:
                        subtask.result = "Agent completed but returned no result"
            
            # If we didn't get a result from streaming, run again to get it
            # (fallback for compatibility)
            if result is None:
                result = await agent.run(
                    enhanced_prompt,
                    deps=deps if deps else None,
                    usage_limits=usage_limits
                )
                subtask.result = result.output
            subtask.status = "completed"
            
            yield ActivityEvent(
                event_type="agent_completed",
                agent_id=subtask.agent_id,
                message=f"[{agent_def.identity.role}] Completed subtask",
                task_id=task.id,
                metadata={
                    "subtask_id": subtask.id,
                    "result_preview": subtask.result[:200] if subtask.result else "",
                },
            )
        
        except UsageLimitExceeded:
            subtask.status = "completed"
            subtask.result = f"Reached tool limit ({agent_def.capability.max_tool_calls_per_task} calls). Results based on available data."
            
            yield ActivityEvent(
                event_type="agent_completed",
                agent_id=subtask.agent_id,
                message=f"[{agent_def.identity.role}] Tool limit reached",
                task_id=task.id,
                metadata={
                    "subtask_id": subtask.id,
                    "reason": "tool_limit_exceeded",
                },
            )
        
        except Exception as e:
            subtask.status = "failed"
            subtask.result = f"Error: {str(e)}"
            
            yield ActivityEvent(
                event_type="agent_completed",
                agent_id=subtask.agent_id,
                message=f"[{agent_def.identity.role}] Failed: {str(e)}",
                task_id=task.id,
                metadata={"subtask_id": subtask.id, "error": str(e)},
            )
    
    async def execute_task(
        self,
        task: Task,  # Changed: now requires a Task object, not a string
        workspace_id: str | None = None,
        tenant_id: str | None = None,
        memory_context: dict | None = None,
        conversation_history: list[str] | None = None,
        log_streamer: Any | None = None,
    ) -> AsyncIterator[ActivityEvent]:
        """Execute a complete task with streaming events.
        
        Args:
            task: Pre-decomposed Task object with subtasks
            workspace_id: Workspace ID for workspace tools
            tenant_id: Tenant ID for workspace tools
            memory_context: Memory context for memory_retrieve tool
            conversation_history: Optional conversation history for context
        """
        yield ActivityEvent(
            event_type="task_received",
            agent_id="conductor",
            message=f"Task received: {task.description}",
            task_id=task.id,
        )
        
        # Task is already decomposed - no need to decompose again
        yield ActivityEvent(
            event_type="task_decomposed",
            agent_id="conductor",
            message=f"Decomposed into {len(task.subtasks)} subtasks",
            task_id=task.id,
            metadata={"subtask_count": len(task.subtasks)},
        )
        
        # Execute subtasks
        for subtask in task.subtasks:
            yield ActivityEvent(
                event_type="subtask_assigned",
                agent_id=subtask.agent_id,
                message=f"Assigned to {subtask.agent_id}: {subtask.description}",
                task_id=task.id,
                metadata={"subtask_id": subtask.id},
            )
            
            async for event in self.execute_subtask(
                subtask, 
                task,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                memory_context=memory_context,
                conversation_history=conversation_history,
            ):
                yield event
        
        # Synthesize results
        yield ActivityEvent(
            event_type="synthesis_started",
            agent_id="conductor",
            message="Synthesizing results from all agents",
            task_id=task.id,
        )
        
        final_result = await self.conductor.synthesize_results(
            task,
            log_streamer=log_streamer
        )
        task.final_result = final_result
        
        yield ActivityEvent(
            event_type="task_completed",
            agent_id="conductor",
            message="Task completed successfully",
            task_id=task.id,
            metadata={"result": final_result},
        )


