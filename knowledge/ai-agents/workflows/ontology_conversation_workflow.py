"""Ontology conversation workflow: never-ending, resumable chat with ontology agent."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.core.run_log_reader import get_run_log_messages, get_recent_messages
from app.config import Config
from app.workflows.ontology_creation.ontology_builder import OntologyBuilder
from app.workflows.ontology_creation.storage import (
    load_conversation_summary,
    save_conversation_summary,
)
from app.workflows.ontology_creation.tools import finalize_ontology

logger = logging.getLogger(__name__)

try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None

# Defaults for sliding window
DEFAULT_MAX_MESSAGES = 30
DEFAULT_MAX_TOKENS = 80000


class OntologyConversationWorkflow(BaseWorkflow):
    """
    Never-ending ontology conversation: chat-style loop with idle/max timeout.
    Resumable via getScenarioRunLogsByRunId + optional conversation summary.
    Supports finalize_ontology as an action (does not exit the loop).
    """

    def __init__(self):
        super().__init__(
            workflow_id="ontology-conversation",
            name="Ontology Conversation Workflow",
        )

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id
        inputs = event.inputs_dict or {}
        ontology_id = inputs.get("ontology_id") or run_id  # use run_id as draft key if no ontology_id
        initial_context = inputs.get("initial_context") or event.prompt

        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                "ontology_conversation_workflow.execute",
                run_id=run_id,
                tenant_id=tenant_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            "Starting ontology conversation workflow run_id=%s ontology_id=%s",
            run_id[:8] if run_id else "",
            ontology_id[:8] if ontology_id else "",
        )

        log_streamer = None
        if Config.GRAPHQL_LOGGING_ENABLED:
            try:
                log_streamer = ScenarioRunLogger(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    enabled=True,
                )
            except Exception as e:
                logger.warning("Failed to initialize GraphQL logger: %s", e)

        event_reader = None
        try:
            event_reader = EventStreamReader(
                run_id=run_id,
                tenant_id=tenant_id,
                graphql_endpoint=Config.GRAPHQL_ENDPOINT,
            )
            await event_reader.start()
        except Exception as e:
            logger.error("Failed to start event stream: %s", e)
            duration = (datetime.utcnow() - start_time).total_seconds()
            if span_ctx:
                span_ctx.__exit__(None, None, None)
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

        try:
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Ontology conversation started",
                    metadata={"stage": "ontology_conversation"},
                    agent_id="ontology_agent",
                )

            # Load prior context for resume
            all_messages = await get_run_log_messages(
                run_id=run_id,
                tenant_id=tenant_id,
                within_days=7,
            )
            recent = get_recent_messages(
                all_messages,
                max_messages=DEFAULT_MAX_MESSAGES,
                max_tokens=DEFAULT_MAX_TOKENS,
            )
            summary_data = None
            summary_key_run = ontology_id == run_id
            if getattr(Config, "ONTOLOGY_CONVERSATION_SAVE_SUMMARY", False):
                summary_data = load_conversation_summary(
                    tenant_id=tenant_id,
                    run_id=run_id if summary_key_run else None,
                    ontology_id=None if summary_key_run else ontology_id,
                )
            initial_message_history = []
            if summary_data and summary_data.get("summary"):
                initial_message_history.append({
                    "role": "user",
                    "content": f"Summary of previous conversation:\n{summary_data['summary']}\n\n[Recent messages below.]",
                })
            initial_message_history.extend(recent)

            builder = OntologyBuilder(
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                conversation_mode=True,
            )
            if ontology_id:
                await builder.load_draft(ontology_id)
            message_history = list(initial_message_history)
            is_return = bool(message_history) or (builder.state.ontology_package is not None)

            # Send an opening so the user sees the agent immediately (not stuck waiting for first event)
            if initial_context and not message_history:
                await builder.run_one_turn(initial_context, message_history, log_streamer)
            elif not message_history:
                # No prior messages: new ontology or return with only a draft—send fixed opening
                if is_return:
                    pkg = builder.state.ontology_package
                    if pkg and pkg.title:
                        opening = f"Welcome back. We were working on **{pkg.title}**. What would you like to do next?"
                    else:
                        opening = "Welcome back—picking up where we left off. What would you like to do next?"
                else:
                    opening = "Let's talk ontology—what are you trying to do?"
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="agent_message",
                        message=opening,
                        agent_id="ontology_agent",
                    )
                message_history.append({"role": "assistant", "content": opening})

            idle_timeout = Config.CONVERSATION_IDLE_TIMEOUT_SECONDS
            max_duration = Config.MAX_CONVERSATION_DURATION_SECONDS
            timeout_event = asyncio.Event()
            last_activity = datetime.utcnow()

            async def check_timeouts():
                while not timeout_event.is_set():
                    await asyncio.sleep(10)
                    now = datetime.utcnow()
                    if (now - start_time).total_seconds() > max_duration:
                        logger.info("Ontology conversation max duration reached")
                        timeout_event.set()
                        break
                    if (now - last_activity).total_seconds() > idle_timeout:
                        logger.info("Ontology conversation idle timeout")
                        timeout_event.set()
                        break

            timeout_task = asyncio.create_task(check_timeouts())
            event_count = 0

            try:
                async for stream_event in event_reader.read_events(
                    event_types=["user_message", "finalize_ontology"],
                ):
                    if timeout_event.is_set():
                        break
                    event_type = stream_event.get("event_type")
                    if event_type == "finalize_ontology":
                        # Handle as action: sync package, finalize, save, emit; do not exit
                        pkg_data = None
                        if isinstance(stream_event.get("data"), dict):
                            pkg_data = stream_event["data"].get("ontology_package")
                        if not pkg_data and "ontology_package" in stream_event:
                            pkg_data = stream_event["ontology_package"]
                        if pkg_data:
                            builder._sync_ontology_from_user(pkg_data)
                        if builder.state.ontology_package and not builder.state.ontology_package.finalized:
                            class MockCtx:
                                def __init__(self, state):
                                    self.deps = state
                            await finalize_ontology(MockCtx(builder.state))
                        builder.state.ontology_finalized = True
                        await builder.save_draft()
                        if log_streamer and builder.state.ontology_package:
                            await log_streamer.log_event(
                                event_type="ontology_finalized",
                                message=f"Ontology finalized: {builder.state.ontology_package.title}",
                                metadata={
                                    "ontology_package": builder.state.ontology_package.to_dict(),
                                    "title": builder.state.ontology_package.title,
                                    "semantic_version": builder.state.ontology_package.semantic_version,
                                },
                                agent_id="ontology_agent",
                            )
                        continue
                    if event_type == "user_message":
                        user_message = (stream_event.get("message") or "").strip()
                        if not user_message:
                            continue
                        last_activity = datetime.utcnow()
                        event_count += 1
                        # Sync current_ontology_package from event if present
                        meta = stream_event.get("metadata") or {}
                        if meta.get("current_ontology_package"):
                            builder._sync_ontology_from_user(meta["current_ontology_package"])
                        agent_response = await builder.run_one_turn(
                            user_message,
                            message_history,
                            log_streamer,
                        )
                        if builder.state.ontology_proposed and log_streamer and builder.state.ontology_package:
                            await log_streamer.log_event(
                                event_type="ontology_proposed",
                                message="Ontology proposed for review",
                                metadata={"ontology_package": builder.state.ontology_package.to_dict(), "ready": True},
                                agent_id="ontology_agent",
                            )
            finally:
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass

            # On session end: optionally save conversation summary (experimental)
            if getattr(Config, "ONTOLOGY_CONVERSATION_SAVE_SUMMARY", False) and message_history:
                try:
                    summary_prompt = (
                        "Summarize the following conversation in 2-4 sentences for context when we resume later. "
                        "Focus on: domain discussed, ontology entities/relationships mentioned, and any database or next steps. "
                        "Conversation:\n"
                    )
                    summary_input = summary_prompt + "\n".join(
                        f"{m.get('role', '?')}: {m.get('content', '')[:500]}"
                        for m in message_history[-20:]
                    )
                    result = await builder.agent.run(
                        summary_input,
                        deps=builder.state,
                    )
                    summary_text = (result.output or "").strip()
                    if summary_text:
                        save_conversation_summary(
                            tenant_id=tenant_id,
                            summary=summary_text,
                            message_count_at_summary=len(message_history),
                            run_id=run_id if summary_key_run else None,
                            ontology_id=None if summary_key_run else ontology_id,
                        )
                except Exception as e:
                    logger.warning("Failed to save conversation summary: %s", e)

            await event_reader.stop()
            duration = (datetime.utcnow() - start_time).total_seconds()
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message="Ontology conversation session ended",
                    agent_id="ontology_agent",
                )
            if span_ctx:
                span_ctx.__exit__(None, None, None)
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result="Ontology conversation completed",
                duration_seconds=duration,
            )
        except Exception as e:
            logger.exception("Ontology conversation workflow failed")
            duration = (datetime.utcnow() - start_time).total_seconds()
            if event_reader:
                try:
                    await event_reader.stop()
                except Exception:
                    pass
            if span_ctx:
                span_ctx.__exit__(None, None, None)
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )
