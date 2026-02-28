"""Chat conductor that decides between quick answers and multi-agent decomposition."""

from pydantic_ai import Agent
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from app.core.model_factory import create_model
from app.core.model_config import model_config
from app.utils.streaming import stream_with_logger

logger = None
try:
    import logging
    logger = logging.getLogger(__name__)
except ImportError:
    pass


class ChatDecision(BaseModel):
    """Decision made by chat conductor."""
    needs_decomposition: bool = Field(..., description="True if question needs multi-agent decomposition, False for quick answer")
    reasoning: str = Field(..., description="Explanation of the decision")


class ChatConductor:
    """Conductor optimized for chat that decides between quick answer and decomposition."""

    def __init__(self, model: str = None):
        """Initialize chat conductor.

        Args:
            model: Optional model name override. If not provided, uses central config.
                   The model factory will automatically use Azure OpenAI if configured.
        """
        # Get configuration from central model config
        config = model_config.get("chat_conductor")
        self.model_name = model or config.model
        self._retries = config.retries

        # Use model factory to create the appropriate model
        model_instance = create_model(self.model_name, config.provider)

        # Create decision agent
        self.decision_agent = Agent(
            model=model_instance,
            output_type=ChatDecision,
            name="chat_conductor",
            retries=self._retries,
        )
        
        @self.decision_agent.instructions
        def decision_instructions() -> str:
            return """You are a chat conductor that decides whether a user's question needs a quick direct answer 
or should be decomposed into multiple subtasks for a team of specialized agents.

Quick answers are appropriate for:
- Simple factual questions
- Direct requests for information
- Single-step tasks
- Questions that can be answered in 1-2 sentences

Multi-agent decomposition is needed for:
- Complex questions requiring research
- Tasks that need multiple steps or different expertise
- Analysis requiring data gathering and synthesis
- Questions that would benefit from specialized agents

Make your decision based on the complexity and scope of the question."""
    
    async def decide(self, question: str, conversation_history: list[str] = None) -> ChatDecision:
        """Decide if question needs decomposition or can be answered directly.
        
        Args:
            question: User's question
            conversation_history: Optional list of previous messages for context
        
        Returns:
            ChatDecision with needs_decomposition flag and reasoning
        """
        # Build context with conversation history and workflow results
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
        
        context_parts.append(f"Current question: {question}")
        context = "\n\n".join(context_parts)
        
        result = await self.decision_agent.run(
            f"Decide if this question needs multi-agent decomposition or can be answered quickly:\n\n{context}"
        )
        
        return result.output
    
    async def answer_quickly(
        self, 
        question: str, 
        conversation_history: list[str] = None,
        log_streamer: Optional[Any] = None
    ) -> str:
        """Provide a quick direct answer to a simple question.
        
        Args:
            question: User's question
            conversation_history: Optional list of previous messages for context
            log_streamer: Optional GraphQL logger for streaming text deltas
        
        Returns:
            Direct answer to the question
        """
        # Use model factory to create the appropriate model
        model_instance = create_model(self.model_name)
        
        answer_agent = Agent(
            model=model_instance,
            name="chat_quick_answer",
        )
        
        @answer_agent.instructions
        def answer_instructions() -> str:
            return """You are a helpful assistant answering questions about a workspace.
You have access to workflow results from previous executions in this conversation.

Available tools through specialized agents:
- graph_node_lookup: Get detailed information about nodes (members, medications, pharmacies, plans, etc.)
- workspace_items_lookup: Find and list items in the workspace
- graph_edge_lookup: Get information about relationships between nodes
- graph_neighbors_lookup: Find connected nodes
- web_search: Search the web for external information
- calculator: Perform mathematical calculations
- memory_retrieve: Retrieve information from memory
- And more specialized tools...

When answering questions:
- If the user asks about "the result", "the report", "the workflow result", or refers to previous output, 
  look for "WORKFLOW RESULT" sections in the context and use that information to answer.
- If the user asks about specific entities (members, medications, pharmacies, etc.) and you only have IDs,
  suggest that detailed information can be retrieved using the graph_node_lookup tool through a specialized agent.
- If the user asks for more detailed information about something mentioned in workflow results,
  suggest decomposing the task to use appropriate tools like graph_node_lookup.
- Provide clear, concise, and accurate answers based on the workflow results when available.
- Reference specific details from the workflow results when answering questions.
- If you don't know something or can't find the information, suggest using available tools to get it.
Be conversational and helpful."""
        
        # Build context with conversation history and workflow results
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
                history_text = "\n".join([f"Previous message: {msg}" for msg in other_history[-3:]])
                context_parts.append(history_text)
        
        context_parts.append(f"Current question: {question}")
        context = "\n\n".join(context_parts)
        
        # Stream text deltas if log_streamer is provided
        if log_streamer:
            return await stream_with_logger(
                answer_agent,
                context,
                log_streamer,
                "conductor",
                batch_size=30,
                flush_interval=0.05,
                track_full_text=True
            )
        else:
            # Fallback to non-streaming if no log_streamer
            result = await answer_agent.run(context)
            return result.output


