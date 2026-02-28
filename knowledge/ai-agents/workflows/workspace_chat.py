"""Workspace chat workflow for continuous conversation about a workspace."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.core.chat_conductor import ChatConductor
from app.core.conductor import Conductor, SubtaskSpec
from app.core.registry import AgentRegistry
from app.core.team_execution import TeamExecutionEngine
from app.core.conversation_context import ConversationContext
from app.core.conversation_metrics import ConversationMetrics
from app.core.model_config import model_config
from app.models.task import Task, ActivityEvent
from app.config import Config

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class WorkspaceChatWorkflow(BaseWorkflow):
    """Workspace chat workflow with continuous conversation loop."""
    
    def __init__(self, agent_registry: AgentRegistry, tool_registry=None):
        """Initialize workspace chat workflow.
        
        Args:
            agent_registry: AgentRegistry with available agents
            tool_registry: Optional tool registry
        """
        super().__init__(
            workflow_id="workspace-chat",
            name="Workspace Chat Workflow"
        )
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        
        # Initialize components
        self.chat_conductor = ChatConductor()
        self.conductor = Conductor(agent_registry, tool_registry)
        self.team_engine = TeamExecutionEngine(agent_registry, self.conductor, tool_registry)
        
        # Note: Conversation state is now stored in ConversationContext instances
        # created per conversation, not in instance-level dictionaries.
        # This prevents race conditions when handling multiple concurrent conversations.
    
    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the workspace chat workflow.

        Args:
            event: WorkflowEvent containing all event data

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id

        # Create Logfire span for entire conversation session
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'workspace_chat.conversation_session',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        # Create isolated conversation context for this run
        context = ConversationContext(run_id=run_id)
        ConversationMetrics.record_conversation_start(run_id)

        logger.info(
            f"Starting workspace chat workflow for run_id={run_id}, "
            f"workspace_id={event.workspace_id}"
        )

        if logfire:
            logfire.info(
                'conversation_started',
                run_id=run_id,
                workspace_id=event.workspace_id,
            )
        
        # Initialize GraphQL logger
        log_streamer = None
        if Config.GRAPHQL_LOGGING_ENABLED:
            try:
                log_streamer = ScenarioRunLogger(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    enabled=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize GraphQL logger: {e}")
        
        # Initialize event stream reader
        event_reader = None
        try:
            event_reader = EventStreamReader(
                run_id=run_id,
                tenant_id=tenant_id,
                graphql_endpoint=Config.GRAPHQL_ENDPOINT,
            )
            await event_reader.start()
        except Exception as e:
            logger.error(f"Failed to start event stream reader: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Close span before early return
            if span_ctx:
                span_ctx.set_attribute('success', False)
                span_ctx.set_attribute('error', f"Failed to start event stream: {str(e)}")
                span_ctx.__exit__(None, None, None)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=f"Failed to start event stream: {str(e)}",
                duration_seconds=duration,
            )
        
        try:
            # Log workflow start
            if log_streamer:
                await log_streamer.append_log(
                    f"  **Workspace Chat Workflow Started**\n"
                    f"- **Workspace ID:** {event.workspace_id}\n"
                    f"- **Run ID:** {run_id}"
                )
            
            # Get initial prompt from event
            initial_prompt = event.prompt or ""
            
            # Track messages we've already processed to avoid duplicates from event stream
            processed_messages = set()
            
            # Process initial prompt if provided
            if initial_prompt:
                context.add_message(initial_prompt)
                processed_messages.add(initial_prompt.strip().lower())  # Track processed message
                await self._process_message(
                    initial_prompt,
                    context,
                    log_streamer,
                    event_reader,
                    workspace_id=event.workspace_id,
                    tenant_id=event.tenant_id,
                )
            
            # Continuous chat loop - wait for user messages from event stream
            logger.info("Entering continuous chat loop...")
            logger.info(f"Event reader running: {event_reader._running if hasattr(event_reader, '_running') else 'unknown'}")
            if log_streamer:
                await log_streamer.log_event(
                    event_type="task_received",
                    message="Chat workflow ready. Waiting for user messages...",
                    agent_id="conductor",
                )
            
            # Read user messages from event stream with timeout
            logger.info("Starting to read events from stream...")
            event_count = 0
            idle_timeout = Config.CONVERSATION_IDLE_TIMEOUT_SECONDS
            max_duration = Config.MAX_CONVERSATION_DURATION_SECONDS
            
            # Create a cancellation event for timeout handling
            timeout_event = asyncio.Event()
            
            # Background task to check for timeouts
            async def check_timeouts():
                """Background task to check for conversation timeouts."""
                while not timeout_event.is_set():
                    await asyncio.sleep(10)  # Check every 10 seconds
                    
                    # Check max duration
                    if context.get_age_seconds() > max_duration:
                        logger.warning(f"Conversation {run_id} exceeded max duration ({max_duration}s)")
                        timeout_event.set()
                        break
                    
                    # Check idle timeout
                    if context.get_idle_seconds() > idle_timeout:
                        logger.info(f"Conversation {run_id} idle timeout ({idle_timeout}s)")
                        timeout_event.set()
                        break
            
            timeout_task = asyncio.create_task(check_timeouts())
            
            try:
                # Only read user_message and feedback_received events to avoid reading back
                # our own task_completed, task_received, and other internal events
                async for stream_event in event_reader.read_events(event_types=["user_message", "feedback_received"]):
                    # Check if timeout was triggered
                    if timeout_event.is_set():
                        break
                    
                    event_count += 1
                    logger.info(f"Received event #{event_count} from stream: {stream_event.get('event_type', 'unknown')}")
                    
                    if stream_event.get("event_type") == "user_message":
                        # Skip user_message events if we're waiting for feedback
                        # (they will be handled by the feedback waiter)
                        if context.waiting_for_feedback:
                            logger.debug(f"Skipping user_message event - waiting for feedback (run_id={run_id})")
                            continue
                        
                        user_message = stream_event.get("message", "")
                        if user_message:
                            # Skip if we've already processed this message (e.g., from initial_prompt)
                            message_key = user_message.strip().lower()
                            if message_key in processed_messages:
                                logger.debug(f"Skipping duplicate user_message event - already processed (run_id={run_id}, message: {user_message[:50]}...)")
                                continue
                            
                            # Mark as processed
                            processed_messages.add(message_key)
                            context.add_message(user_message)
                            await self._process_message(
                                user_message,
                                context,
                                log_streamer,
                                event_reader,
                                workspace_id=event.workspace_id,
                                tenant_id=event.tenant_id,
                            )
                    elif stream_event.get("event_type") == "feedback_received":
                        # Handle feedback (will be processed in _process_message)
                        pass
            finally:
                # Cancel timeout task
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            ConversationMetrics.record_conversation_end(run_id, duration, success=True)

            if logfire:
                logfire.info(
                    'conversation_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    message_count=event_count,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('message_count', event_count)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result="Chat workflow completed",
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Workspace chat workflow failed: {str(e)}"
            logger.exception(error_msg)

            ConversationMetrics.record_conversation_end(run_id, duration, success=False)

            if logfire:
                logfire.error(
                    'conversation_failed',
                    run_id=run_id,
                    error=error_msg,
                    error_type=type(e).__name__,
                    duration_seconds=duration,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', False)
                    span_ctx.set_attribute('error', error_msg)
                    span_ctx.record_exception(e)

            if log_streamer:
                await log_streamer.log_error(error_msg)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )

        finally:
            # Close Logfire span
            if span_ctx:
                span_ctx.__exit__(None, None, None)

            if event_reader:
                await event_reader.stop()
            logger.info(f"Conversation {run_id} cleanup complete")
    
    
    async def _process_message(
        self,
        message: str,
        context: ConversationContext,
        log_streamer: Optional[ScenarioRunLogger],
        event_reader: EventStreamReader,
        workspace_id: str | None = None,
        tenant_id: str | None = None,
    ):
        """Process a user message.
        
        Args:
            message: User's message
            context: Conversation context with isolated state
            log_streamer: GraphQL logger for streaming events
            event_reader: Event stream reader for feedback
            workspace_id: Workspace ID for tools
            tenant_id: Tenant ID for tools
        """
        logger.info(f"Processing message: {message[:100]}... (run_id={context.run_id})")
        
        # Build enhanced conversation history with workflow results
        enhanced_history = context.get_enhanced_history()
        
        # Decide: quick answer or decomposition
        decision = await self.chat_conductor.decide(message, enhanced_history)
        
        if not decision.needs_decomposition:
            # Quick answer path
            logger.info("Decision: Quick answer")
            
            # answer_quickly now streams text deltas if log_streamer is provided
            answer = await self.chat_conductor.answer_quickly(
                message, 
                enhanced_history,
                log_streamer=log_streamer
            )
            
            if log_streamer:
                await log_streamer.log_event(
                    event_type="task_completed",
                    message="",  # Empty since text was already streamed
                    agent_id="conductor",
                )
               # await log_streamer.log_result(answer)
        else:
            # Multi-agent decomposition path
            logger.info("Decision: Multi-agent decomposition")
            await self._execute_multi_agent_workflow(
                message,
                context,
                log_streamer,
                event_reader,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
    
    async def _classify_feedback_intent(
        self, 
        feedback_text: str, 
        current_plan: list
    ) -> str:
        """Classify user feedback intent using LLM.
        
        Args:
            feedback_text: User's feedback text
            current_plan: Current list of subtasks
            
        Returns:
            "approve", "modify", or "question"
        """
        from pydantic_ai import Agent
        from pydantic import BaseModel, Field
        from app.core.model_factory import create_model
        
        class FeedbackIntent(BaseModel):
            intent: str = Field(..., description="One of: approve, modify, question")
            confidence: float = Field(..., description="Confidence 0-1")
        
        # Get configuration from central model config
        config = model_config.get("feedback_classifier")
        model_instance = create_model(config.model, config.provider)

        classifier = Agent(
            model=model_instance,
            output_type=FeedbackIntent,
            name="feedback_classifier",
            retries=config.retries,
        )
        
        @classifier.instructions
        def classifier_instructions() -> str:
            return """Classify user feedback into one of three categories:
- "approve": User wants to proceed with the current plan (e.g., "looks good", "sounds good", "approve", "yes", "that works")
- "modify": User wants to change the plan (e.g., "add a task", "remove task 2", "change X to Y")
- "question": User is asking a question about the plan (e.g., "why is X?", "what does Y mean?", "how does Z work?")

Be conservative - if unsure, default to "question"."""
        
        plan_summary = "\n".join([
            f"{i+1}. {st.agent_id}: {st.description}"
            for i, st in enumerate(current_plan)
        ])
        
        result = await classifier.run(
            f"""Current plan:
{plan_summary}

User feedback: {feedback_text}

Classify the user's intent."""
        )
        
        return result.output.intent
    
    async def _answer_question(
        self,
        question: str,
        current_plan: list,
        log_streamer: Optional[ScenarioRunLogger],
    ) -> None:
        """Answer a user question about the current plan without modifying it.
        
        Args:
            question: User's question
            current_plan: Current list of subtasks
            log_streamer: GraphQL logger for streaming responses
        """
        from pydantic_ai import Agent
        from app.core.model_factory import create_model
        
        # Get configuration from central model config
        config = model_config.get("answer_agent")
        model_instance = create_model(config.model, config.provider)

        answer_agent = Agent(
            model=model_instance,
            name="plan_question_answerer",
            retries=config.retries,
        )
        
        @answer_agent.instructions
        def answer_instructions() -> str:
            return """You are helping a user understand their current plan. 
Answer their question clearly and helpfully. Reference specific tasks in the plan when relevant.
Be concise but thorough."""
        
        plan_text = "\n".join([
            f"{i+1}. **{st.agent_id}**: {st.description}"
            for i, st in enumerate(current_plan)
        ])
        
        result = await answer_agent.run(
            f"""Current plan:
{plan_text}

User question: {question}

Provide a helpful answer."""
        )
        
        if log_streamer:
            await log_streamer.log_event(
                event_type="feedback_received",
                message=result.output,
                agent_id="conductor",
                metadata={"type": "question_answer"},
            )
            # Show the plan again after answering
            await log_streamer.log_event(
                event_type="feedback_requested",
                message=f"Current plan:\n\n## Plan\n\n{plan_text}\n\nProvide feedback or approve to continue.",
                agent_id="conductor",
            )
    
    async def _modify_plan_with_feedback(
        self,
        feedback_text: str,
        current_task: Task,
        original_message: str,
        log_streamer: Optional[ScenarioRunLogger],
        conversation_history: list[str] | None = None,
    ) -> None:
        """Modify the current plan based on feedback, preserving existing tasks.
        
        Args:
            feedback_text: User's modification feedback
            current_task: Current task object to modify
            original_message: Original user message
            log_streamer: GraphQL logger
            conversation_history: Optional conversation history for context
        """
        # Extract current subtask specs for context
        current_subtasks = [
            SubtaskSpec(
                description=st.description,
                agent_id=st.agent_id,
                depends_on=st.depends_on,
            )
            for st in current_task.subtasks
        ]
        
        # Decompose with current plan context so LLM can modify incrementally
        modified_task = await self.conductor.decompose_task(
            feedback_text,
            current_plan=current_subtasks,
            conversation_history=conversation_history
        )
        
        # Update the task object
        current_task.subtasks = modified_task.subtasks
        current_task.description = f"{original_message}\n\nUser feedback: {feedback_text}"
        
        # Update plan text
        plan_text = "## Updated Plan\n\n"
        for i, subtask in enumerate(current_task.subtasks, 1):
            plan_text += f"{i}. **{subtask.agent_id}**: {subtask.description}\n"
        
        if log_streamer:
            await log_streamer.log_event(
                event_type="feedback_applied",
                message=f"Plan updated based on feedback:\n\n{plan_text}",
                agent_id="conductor",
            )
            # Request feedback again on updated plan
            await log_streamer.log_event(
                event_type="feedback_requested",
                message=f"Review the updated plan:\n\n{plan_text}\n\nProvide feedback or approve to continue.",
                agent_id="conductor",
                metadata={
                    "checkpoint": "decomposition",
                    "subtasks": [st.model_dump() for st in current_task.subtasks],
                    "options": ["approve", "modify", "cancel"],
                },
            )
    
    async def _execute_multi_agent_workflow(
        self,
        message: str,
        context: ConversationContext,
        log_streamer: Optional[ScenarioRunLogger],
        event_reader: EventStreamReader,
        workspace_id: str | None = None,
        tenant_id: str | None = None,
    ):
        """Execute multi-agent workflow with feedback loop.

        Args:
            message: User's message
            context: Conversation context with isolated state
            log_streamer: GraphQL logger
            event_reader: Event stream reader for feedback
            workspace_id: Workspace ID for tools
            tenant_id: Tenant ID for tools
        """
        # Create span for multi-agent workflow
        workflow_span = None
        if logfire:
            workflow_span = logfire.span(
                'workspace_chat.multi_agent_workflow',
                run_id=context.run_id,
            ).__enter__()

        try:
            # Build enhanced conversation history with workflow results
            enhanced_history = context.get_enhanced_history()

            # Decompose task with conversation history
            task = await self.conductor.decompose_task(message, conversation_history=enhanced_history)

            # Format plan for user
            plan_text = "## Plan\n\n"
            for i, subtask in enumerate(task.subtasks, 1):
                plan_text += f"{i}. **{subtask.agent_id}**: {subtask.description}\n"

            # Request feedback on plan
            if log_streamer:
                await log_streamer.log_event(
                    event_type="feedback_requested",
                    message=f"Review the plan:\n\n{plan_text}\n\nProvide feedback or approve to continue.",
                    agent_id="conductor",
                    metadata={
                        "checkpoint": "decomposition",
                        "subtasks": [st.model_dump() for st in task.subtasks],
                        "options": ["approve", "modify", "cancel"],
                    },
                )

            # Mark that we're waiting for feedback (so main loop skips user_message events)
            context.mark_waiting_for_feedback(True)
            logger.info(f"Marked run_id={context.run_id} as waiting for feedback")

            # Feedback loop: wait for approval, modify, or cancel
            max_feedback_iterations = 5
            iteration = 0
            approved = False

            try:
                while not approved and iteration < max_feedback_iterations:
                    iteration += 1

                    # Wait for feedback (with timeout)
                    # Accept both feedback_received and user_message events
                    # user_message events are treated as feedback when waiting for plan approval
                    feedback = None
                    try:
                        # Wait for either feedback_received or user_message
                        feedback_event = await event_reader.wait_for_event(
                            ["feedback_received", "user_message"],
                            timeout=300.0
                        )

                        if feedback_event:
                            event_type = feedback_event.get("event_type")
                            feedback_text = feedback_event.get("message", "")

                            # If it's a user_message, classify the intent
                            if event_type == "user_message":
                                text_lower = feedback_text.strip().lower()

                                # Simple approval phrases
                                approval_phrases = [
                                    "approve", "yes", "ok", "continue", "proceed",
                                    "looks good", "sounds good", "good", "fine",
                                    "that works", "perfect", "go ahead", "sounds great",
                                    "that's good", "that's fine", "sure", "yep", "yeah"
                                ]

                                # Question indicators (simple pattern matching first)
                                question_indicators = [
                                    "why", "what", "how", "when", "where", "who",
                                    "?", "explain", "clarify", "understand", "confused",
                                    "don't understand", "don't get", "not sure", "i don't understand"
                                ]

                                # Modification indicators
                                modification_indicators = [
                                    "add", "remove", "change", "modify", "update",
                                    "replace", "delete", "include", "exclude", "put back",
                                    "restore", "take out", "drop", "edit"
                                ]

                                if text_lower in approval_phrases:
                                    feedback_action = "approve"
                                    logger.info("User message treated as approval")
                                elif any(indicator in text_lower for indicator in question_indicators):
                                    feedback_action = "question"
                                    logger.info("User message treated as question")
                                elif any(indicator in text_lower for indicator in modification_indicators):
                                    feedback_action = "modify"
                                    logger.info("User message treated as modification request")
                                else:
                                    # Ambiguous - use LLM to classify
                                    feedback_action = await self._classify_feedback_intent(
                                        feedback_text,
                                        current_plan=task.subtasks
                                    )
                                    logger.info(f"LLM classified feedback as: {feedback_action}")
                            else:
                                # It's a feedback_received event
                                feedback_action = feedback_event.get("metadata", {}).get("action", "approve")

                            feedback = {
                                "text": feedback_text,
                                "action": feedback_action,
                            }
                    except asyncio.TimeoutError:
                        logger.warning("Feedback timeout, proceeding with plan")
                        if log_streamer:
                            await log_streamer.log_event(
                                event_type="feedback_timeout",
                                message="No feedback received, proceeding with plan",
                                agent_id="conductor",
                            )
                        # Proceed without feedback
                        approved = True
                        break

                    # Handle feedback action
                    if feedback:
                        if feedback["action"] == "approve":
                            approved = True
                            if log_streamer:
                                await log_streamer.log_event(
                                    event_type="feedback_received",
                                    message="Plan approved by user",
                                    agent_id="conductor",
                                )
                            break
                        elif feedback["action"] == "question":
                            # Answer the question without modifying the plan
                            await self._answer_question(
                                feedback["text"],
                                task.subtasks,
                                log_streamer,
                            )
                            # Continue waiting for feedback (don't break)
                            continue
                        elif feedback["action"] == "modify":
                            # Modify plan with feedback, preserving existing tasks
                            await self._modify_plan_with_feedback(
                                feedback["text"],
                                task,
                                message,
                                log_streamer,
                                conversation_history=enhanced_history,
                            )
                            # Continue waiting for feedback (don't break)
                            continue
                        elif feedback["action"] == "cancel":
                            if log_streamer:
                                await log_streamer.log_event(
                                    event_type="task_completed",
                                    message="Task cancelled by user",
                                    agent_id="conductor",
                                )
                            return
            finally:
                # Clear feedback waiting flag
                context.mark_waiting_for_feedback(False)
                logger.info(f"Cleared feedback waiting flag for run_id={context.run_id}")

            # Execute workflow
            if log_streamer:
                await log_streamer.log_event(
                    event_type="task_decomposed",
                    message=f"Executing plan with {len(task.subtasks)} subtasks",
                    agent_id="conductor",
                    metadata={"subtask_count": len(task.subtasks)},
                )

            final_result = None

            # Build memory context (empty for now, can be populated from memory system if available)
            memory_context = {}

            async for activity_event in self.team_engine.execute_task(
                task,  # Pass the already-decomposed task object
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                memory_context=memory_context if memory_context else None,
                conversation_history=enhanced_history,
                log_streamer=log_streamer,
            ):
                # Stream all events to GraphQL
                if log_streamer:
                    await log_streamer.log_event(
                        event_type=activity_event.event_type,
                        message=activity_event.message,
                        metadata=activity_event.metadata,
                        agent_id=activity_event.agent_id,
                    )

                # Capture final result
                if activity_event.event_type == "task_completed":
                    final_result = activity_event.metadata.get("result", "")

            # Log final result (after loop completes)
            if final_result and log_streamer:
                await log_streamer.log_result(final_result)

            # Store workflow result in conversation context for future questions
            if final_result:
                context.add_workflow_result(final_result)

            # Set workflow span attributes
            if logfire and workflow_span:
                workflow_span.set_attribute('subtask_count', len(task.subtasks))
                workflow_span.set_attribute('has_result', final_result is not None)

        finally:
            # Close workflow span
            if workflow_span:
                workflow_span.__exit__(None, None, None)


