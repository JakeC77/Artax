"""
ontology_builder.py - Conversational ontology creation with agent

This module orchestrates the conversation between the user and the agent
to build a well-formed Ontology Package.
"""

import asyncio
from pathlib import Path
from typing import Optional, Any
from pydantic_ai.models import KnownModelName
from app.utils.streaming import stream_with_logger
from app.workflows.ontology_creation.config import load_config
import logfire
from logfire import ConsoleOptions

from .models import OntologyPackage, OntologyState
from .tools import ONTOLOGY_TOOLS
from .ontology_agent import create_ontology_agent
from .storage import save_ontology_draft, load_ontology_draft
from pydantic import ValidationError

# Import tools module to ensure decorators run and tools are registered
import app.workflows.ontology_creation.tools  # noqa: F401


# Configure Logfire for observability
def _configure_logfire():
    """Configure Logfire with Geodesic framework patterns."""
    import os

    # Skip if running in container (sandbox/production)
    environment = os.getenv("ENVIRONMENT", "development")
    if environment in ("sandbox", "production"):
        return

    # Find repo root .logfire directory
    repo_root = Path(__file__).parent.parent.parent.parent
    logfire_dir = repo_root / ".logfire"

    # Check for verbose mode from environment variable
    verbose_mode = os.getenv("LOGFIRE_VERBOSE", "false").lower() == "true"

    logfire.configure(
        send_to_logfire='if-token-present',
        config_dir=logfire_dir if logfire_dir.exists() else None,
        service_name='ontology_creation_builder',
        environment='development',
        console=ConsoleOptions(verbose=verbose_mode)
    )

    # Auto-instrument Pydantic AI agents
    logfire.instrument_pydantic_ai()


# Initialize Logfire once at module load (unless running in container)
_configure_logfire()


class OntologyBuilder:
    """
    Orchestrates the conversation with the agent to extract domain information
    and build an Ontology Package.
    """

    def __init__(
        self,
        model: KnownModelName = None,
        tenant_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        conversation_mode: bool = False,
    ):
        """
        Initialize the Ontology Builder.

        Args:
            model: Optional model name override. If not provided, uses workflow config.
            tenant_id: Tenant ID for storage operations
            ontology_id: Optional ontology ID for resuming existing session
            conversation_mode: If True, use conversation-mode instructions (ontology-conversation workflow).
        """
        # Get configuration from workflow config
        config = load_config()
        self.state = OntologyState()
        self.tenant_id = tenant_id
        self.ontology_id = ontology_id
        self.state.conversation_mode = conversation_mode

        # Set ontology_id in state if provided
        if ontology_id:
            self.state.ontology_id = ontology_id

        # Create the agent with dynamic prompts
        if model is not None:
            self.model = model
            self.agent = create_ontology_agent(model=self.model, conversation_mode=conversation_mode)
        else:
            self.model = str(config.ontology_agent_model)
            model_instance = config.ontology_agent_model.create()
            self.agent = create_ontology_agent(model=model_instance, conversation_mode=conversation_mode)

        # Register ontology tools
        for tool_name, tool_func in ONTOLOGY_TOOLS.items():
            self.agent.tool(tool_func)

    def _sync_ontology_from_user(self, user_package_data: dict) -> None:
        """
        Sync OntologyState with the user's current ontology package.

        This ensures the agent sees any edits the user made in the frontend editor
        before processing the new message. User edits are authoritative.

        Args:
            user_package_data: Dict representation of the user's OntologyPackage
        """
        try:
            user_package = OntologyPackage(**user_package_data)

            if self.state.ontology_package is None:
                # No existing package - use user's entirely
                self.state.ontology_package = user_package
                logfire.info(
                    "Initialized ontology from user",
                    title=user_package.title
                )
            else:
                # Merge: user-editable fields from user, preserve internal state
                self.state.ontology_package = self._merge_user_edits(
                    existing=self.state.ontology_package,
                    user_edited=user_package
                )
                logfire.info(
                    "Synced ontology from user edits",
                    title=user_package.title,
                    version=self.state.ontology_package.current_version
                )

        except ValidationError as e:
            logfire.warning(
                "Failed to parse user ontology package - continuing with existing state",
                error=str(e)
            )

    def _merge_user_edits(
        self,
        existing: OntologyPackage,
        user_edited: OntologyPackage
    ) -> OntologyPackage:
        """
        Merge user's edits with existing ontology state.

        User-editable fields come from user_edited.
        Internal metadata (conversation_transcript, iteration_history) preserved from existing.

        Args:
            existing: The current OntologyPackage in OntologyState
            user_edited: The OntologyPackage sent by the frontend with user's edits

        Returns:
            Merged OntologyPackage with user's edits and preserved internal state
        """
        return OntologyPackage(
            schema_version=existing.schema_version,
            ontology_id=existing.ontology_id,
            semantic_version=user_edited.semantic_version,  # User can edit version
            title=user_edited.title,
            description=user_edited.description,
            entities=user_edited.entities,
            relationships=user_edited.relationships,
            conversation_transcript=existing.conversation_transcript,
            iteration_history=existing.iteration_history,
            current_version=existing.current_version + 1,  # Increment version on user edit
            created_at=existing.created_at,
            updated_at=user_edited.updated_at if hasattr(user_edited, 'updated_at') else existing.updated_at,
            finalized=user_edited.finalized,
        )

    async def _emit_ontology_updated(
        self,
        log_streamer: any,
        update_summary: str | None = None
    ) -> None:
        """
        Emit ontology_updated event with current package state.

        Called after agent modifies ontology via tools.
        The frontend uses this to update the structured editor in real-time.

        Args:
            log_streamer: GraphQL logger for emitting events
            update_summary: Optional natural language description of what changed
        """
        if self.state.ontology_package is None:
            return

        if log_streamer is None:
            return

        try:
            await log_streamer.log_event(
                event_type="ontology_updated",
                message="Ontology package updated",
                metadata={
                    "ontology_package": self.state.ontology_package.to_dict(),
                    "update_summary": update_summary,
                },
                agent_id="ontology_agent",
            )
            logfire.info(
                "Emitted ontology_updated event",
                title=self.state.ontology_package.title
            )
        except Exception as e:
            logfire.warning("Failed to emit ontology_updated event", error=str(e))

    async def get_next_user_message(
        self,
        message_source: Optional[Any] = None,
        timeout: Optional[float] = None
    ) -> tuple[Optional[str], str, Optional[dict]]:
        """
        Get next user message or control event from message source (event stream) or stdin.

        Args:
            message_source: EventStreamReader instance or None for stdin
            timeout: Optional timeout in seconds for event stream reads

        Returns:
            Tuple of (message, event_type, metadata):
            - ("message text", "user_message", metadata_dict) for normal user messages
            - (None, "finalize_ontology", metadata_dict) when user confirms ontology via UI button
            - (None, "quit", None) if quit/exit or timeout
            - (None, "empty", None) if empty input (retry)

            metadata_dict may contain 'current_ontology_package' with user's edited ontology state
        """
        if message_source is None:
            # CLI mode: use stdin
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ['quit', 'exit']:
                    return None, "quit", None
                if user_input.lower() == 'finalize':
                    # CLI simulation of finalize_ontology
                    return None, "finalize_ontology", None
                return (user_input, "user_message", None) if user_input else (None, "empty", None)
            except (EOFError, KeyboardInterrupt):
                return None, "quit", None
        else:
            # Event stream mode: read from stream
            try:
                # Wait for user_message OR finalize_ontology event with timeout
                event = await message_source.wait_for_event(
                    event_type=["user_message", "finalize_ontology"],
                    timeout=timeout
                )

                if event:
                    event_type = event.get("event_type", "user_message")
                    metadata = event.get("metadata", {})

                    # current_ontology_package may be at top level or in metadata
                    if "current_ontology_package" in event:
                        metadata["current_ontology_package"] = event["current_ontology_package"]

                    # For finalize_ontology, frontend may send ontology_package in data object
                    if event_type == "finalize_ontology":
                        final_pkg = None
                        if "data" in event and isinstance(event["data"], dict):
                            pkg_data = event["data"].get("ontology_package")
                            if pkg_data:
                                if isinstance(pkg_data, str):
                                    import json
                                    try:
                                        final_pkg = json.loads(pkg_data)
                                    except json.JSONDecodeError:
                                        pass
                                else:
                                    final_pkg = pkg_data
                        elif "ontology_package" in event:
                            final_pkg = event["ontology_package"]
                        elif "current_ontology_package" in event:
                            final_pkg = event["current_ontology_package"]

                        if final_pkg:
                            metadata["final_ontology_package"] = final_pkg

                    if event_type == "finalize_ontology":
                        logfire.info("Received finalize_ontology event - user confirmed ontology")
                        return None, "finalize_ontology", metadata

                    # Regular user message
                    user_message = event.get("message", "").strip()
                    if user_message.lower() in ['quit', 'exit']:
                        return None, "quit", None
                    return (user_message, "user_message", metadata) if user_message else (None, "empty", None)
                else:
                    # Timeout
                    return None, "quit", None
            except Exception as e:
                logfire.error("Error reading from event stream", error=str(e))
                return None, "quit", None

    async def run_one_turn(
        self,
        user_input: str,
        message_history: list,
        log_streamer: Optional[Any] = None,
    ) -> str:
        """
        Run a single conversation turn: agent responds to user_input with given message_history.
        Extends message_history in place with the new exchange. Saves draft and emits ontology
        events if tools updated state. Used by ontology-conversation workflow.

        Returns:
            Agent response text.
        """
        result = None
        agent_message = ""
        if log_streamer:
            from app.utils.streaming import stream_agent_text
            from uuid import uuid4
            text_buffer = []
            message_id = str(uuid4())
            async for batch_text, _acc_len, _part_idx, _metadata, event_result in stream_agent_text(
                self.agent,
                user_input,
                deps=self.state,
                message_history=message_history,
                on_batch=None,
                batch_size=30,
                flush_interval=0.05,
                message_id=message_id,
            ):
                if batch_text:
                    text_buffer.append(batch_text)
                if event_result is not None:
                    result = event_result
                    if hasattr(result, "output"):
                        agent_message = result.output
                    if hasattr(result, "new_messages"):
                        message_history.extend(result.new_messages())
            if result is None:
                result = await self.agent.run(
                    user_input,
                    deps=self.state,
                    message_history=message_history,
                )
                message_history.extend(result.new_messages())
                agent_message = result.output
            if agent_message:
                await log_streamer.log_event(
                    event_type="agent_message",
                    message=agent_message,
                    agent_id="ontology_agent",
                    metadata={"message_id": message_id, "completed": True, "buffered": True},
                )
            if hasattr(log_streamer, "flush"):
                await log_streamer.flush()
        else:
            result = await self.agent.run(
                user_input,
                deps=self.state,
                message_history=message_history,
            )
            message_history.extend(result.new_messages())
            agent_message = result.output
        if self.state.ontology_needs_broadcast and log_streamer:
            await self._emit_ontology_updated(
                log_streamer=log_streamer,
                update_summary=self.state.last_update_summary,
            )
            self.state.clear_broadcast_signal()
        await self.save_draft()
        return agent_message or ""

    async def load_draft(self, ontology_id: str) -> Optional[OntologyPackage]:
        """
        Load an existing ontology draft from storage.

        Args:
            ontology_id: Ontology ID to load

        Returns:
            OntologyPackage if found, None otherwise
        """
        if not self.tenant_id:
            logfire.warning("Cannot load draft without tenant_id")
            return None

        package = load_ontology_draft(self.tenant_id, ontology_id)
        if package:
            self.state.ontology_package = package
            self.ontology_id = ontology_id
            self.state.ontology_id = ontology_id
            logfire.info("Loaded ontology draft", ontology_id=ontology_id, title=package.title)
        return package

    async def save_draft(self) -> None:
        """
        Save the current ontology package as a draft to blob storage.
        """
        if not self.state.ontology_package:
            return

        if not self.tenant_id:
            logfire.warning("Cannot save draft without tenant_id")
            return

        ontology_id = self.state.ontology_package.ontology_id
        try:
            save_ontology_draft(self.tenant_id, ontology_id, self.state.ontology_package)
            logfire.info("Saved ontology draft", ontology_id=ontology_id)
        except Exception as e:
            logfire.error("Failed to save ontology draft", error=str(e))

    async def start_conversation(
        self,
        initial_context: Optional[str] = None,
        message_source: Optional[Any] = None,
        log_streamer: Optional[Any] = None,
        initial_message_history: Optional[list] = None,
    ) -> Optional[OntologyPackage]:
        """
        Start an interactive conversation to build the ontology package.

        Args:
            initial_context: Optional initial context from the user
            message_source: Optional EventStreamReader for event stream mode, None for stdin (CLI mode)
            log_streamer: Optional GraphQL logger for logging responses
            initial_message_history: Optional list of message dicts (role, content) for resume;
                used to seed message_history so the agent sees prior context (e.g. from get_run_log_messages).

        Returns:
            The finalized OntologyPackage, or None if cancelled
        """
        # Create top-level span for entire conversation
        with logfire.span("ontology_creation_conversation", initial_context=initial_context):
            logfire.info("Starting ontology creation conversation")

            # Load existing draft if ontology_id provided
            is_editing_existing = False
            if self.ontology_id:
                loaded_package = await self.load_draft(self.ontology_id)
                if loaded_package:
                    is_editing_existing = True
                    logfire.info("Resumed ontology draft", ontology_id=self.ontology_id)

            # Only print CLI messages if in CLI mode (message_source is None)
            if message_source is None:
                print("\n" + "=" * 60)
                if is_editing_existing:
                    print("ONTOLOGY EDITING")
                else:
                    print("ONTOLOGY CREATION")
                print("=" * 60)
                if is_editing_existing:
                    print("\nResuming work on existing ontology.")
                else:
                    print("\nI'll help you create an ontology for your domain.")
                    print("We'll work together to identify entities, fields, and relationships.")
                print("\nType 'quit' or 'exit' to end the conversation early.")
                print("-" * 60 + "\n")

            # Start with agent's opening; seed from prior context if resuming
            message_history = list(initial_message_history) if initial_message_history else []

            # Send opening message when no initial_context is provided (both CLI and event stream mode)
            # Skip opening if we already have message history (resume case)
            if not initial_context and not message_history:
                if is_editing_existing:
                    # When editing existing ontology, send welcome back message
                    welcome_message = "Welcome back! I've loaded your existing ontology. Let me know if you want me to make any changes."
                    
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="agent_message",
                            message=welcome_message,
                            agent_id="ontology_agent",
                        )
                    
                    if message_source is None:
                        print(f"Agent: {welcome_message}\n")
                    
                    logfire.info("Sent welcome back message for editing mode")
                else:
                    # New ontology creation - use agent's opening
                    initial_prompt = "Start the conversation with your opening move."

                    with logfire.span("agent_opening_message"):
                        result = await self.agent.run(
                            initial_prompt,
                            deps=self.state
                        )
                        agent_message = result.output
                        logfire.info("Agent opened conversation", message_length=len(agent_message))

                    message_history.extend(result.new_messages())

                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="agent_message",
                            message=agent_message,
                            agent_id="ontology_agent",
                        )

                    if message_source is None:
                        print(f"Agent: {agent_message}\n")

            # Conversation loop
            exchange_count = 0
            ontology_proposed_emitted = False
            first_message_handled = False

            while not self.state.ontology_finalized:
                exchange_count += 1

                # For the first exchange, use initial_context if provided
                if initial_context and not first_message_handled:
                    user_input = initial_context
                    event_type = "user_message"
                    event_metadata = None
                    first_message_handled = True
                else:
                    # Get user input from message source (event stream or stdin)
                    user_input, event_type, event_metadata = await self.get_next_user_message(
                        message_source=message_source,
                        timeout=300.0 if message_source else None  # 5 minute timeout for event stream
                    )

                # Sync ontology state from user before processing message
                if event_metadata and event_type == "user_message":
                    user_ontology_package = event_metadata.get("current_ontology_package")
                    if user_ontology_package:
                        self._sync_ontology_from_user(user_ontology_package)

                # Handle finalize_ontology event - user confirmed ontology via UI button
                if event_type == "finalize_ontology":
                    logfire.info("User confirmed ontology via finalize_ontology event",
                               exchanges=exchange_count,
                               ontology_proposed=self.state.ontology_proposed)

                    # Sync final ontology package from user if provided
                    if event_metadata:
                        final_ontology_package = event_metadata.get("final_ontology_package")
                        if final_ontology_package:
                            self._sync_ontology_from_user(final_ontology_package)

                    if self.state.ontology_package:
                        # Mark as finalized (tool will be called by agent if needed)
                        if not self.state.ontology_package.finalized:
                            # Create a mock context for the tool
                            from pydantic_ai import RunContext
                            class MockContext:
                                def __init__(self, state):
                                    self.deps = state
                            mock_ctx = MockContext(self.state)
                            from .tools import finalize_ontology
                            await finalize_ontology(mock_ctx)
                        
                        self.state.ontology_finalized = True

                        # Save final version
                        await self.save_draft()

                        # Emit ontology_finalized event
                        if log_streamer:
                            ontology_text = self.state.ontology_package.get_formatted_ontology_text()
                            try:
                                await log_streamer.log_event(
                                    event_type="ontology_finalized",
                                    message=f"Ontology finalized: {self.state.ontology_package.title}",
                                    metadata={
                                        "ontology_package": self.state.ontology_package.to_dict(),
                                        "ontology_text": ontology_text,
                                        "title": self.state.ontology_package.title,
                                        "semantic_version": self.state.ontology_package.semantic_version,
                                    },
                                    agent_id="ontology_agent",
                                )
                            except Exception as e:
                                logfire.warning("Failed to emit ontology_finalized event", error=str(e))

                        if message_source is None:
                            print("\n" + "=" * 60)
                            print("ONTOLOGY CONFIRMED")
                            print("=" * 60 + "\n")

                        break
                    else:
                        logfire.warning("finalize_ontology received but no ontology package exists")
                        if message_source is None:
                            print("Agent: I don't have an ontology to finalize yet. Let's keep talking.\n")
                        continue

                if event_type == "quit":
                    if message_source is None:
                        logfire.info("User quit conversation", exchanges=exchange_count)
                        print("\nAgent: No problem! Your draft has been saved. We can pick this up later.")
                    else:
                        logfire.info("User quit or timeout", exchanges=exchange_count)
                    # Save draft before quitting
                    await self.save_draft()
                    return None

                if event_type == "empty" or not user_input:
                    if message_source is None:
                        print("Agent: I didn't catch that. Could you say that again?\n")
                    continue

                # If user sends a message after ontology was proposed, reset the flag
                if ontology_proposed_emitted:
                    logfire.info("User sent message after ontology proposed - allowing re-proposal")
                    ontology_proposed_emitted = False
                    self.state.ontology_proposed = False

                # Send to agent with span tracking
                try:
                    with logfire.span("conversation_exchange",
                                     exchange=exchange_count,
                                     user_input_length=len(user_input)):
                        logfire.info("User message", exchange=exchange_count)

                        agent_message = ""
                        result = None
                        if log_streamer:
                            from app.utils.streaming import stream_agent_text
                            from uuid import uuid4

                            text_buffer = []
                            message_id = str(uuid4())

                            async for batch_text, acc_len, part_idx, metadata, event_result in stream_agent_text(
                                self.agent,
                                user_input,
                                deps=self.state,
                                message_history=message_history,
                                on_batch=None,
                                batch_size=30,
                                flush_interval=0.05,
                                message_id=message_id,
                            ):
                                if batch_text:
                                    text_buffer.append(batch_text)
                                if event_result is not None:
                                    result = event_result
                                    if hasattr(result, 'output'):
                                        agent_message = result.output
                                    if hasattr(result, 'new_messages'):
                                        message_history.extend(result.new_messages())

                            if result is None:
                                result = await self.agent.run(
                                    user_input,
                                    deps=self.state,
                                    message_history=message_history
                                )
                                message_history.extend(result.new_messages())
                                agent_message = result.output

                            if agent_message:
                                await log_streamer.log_event(
                                    event_type="agent_message",
                                    message=agent_message,
                                    agent_id="ontology_agent",
                                    metadata={
                                        "message_id": message_id,
                                        "completed": True,
                                        "buffered": True,
                                    }
                                )

                            if hasattr(log_streamer, "flush"):
                                await log_streamer.flush()
                        else:
                            # Non-streaming path
                            result = await self.agent.run(
                                user_input,
                                deps=self.state,
                                message_history=message_history
                            )
                            message_history.extend(result.new_messages())
                            agent_message = result.output
                        
                        logfire.info("Agent response",
                                   exchange=exchange_count,
                                   response_length=len(agent_message))

                    if message_source is None:
                        print(f"\nAgent: {agent_message}\n")

                    # Check if tools updated ontology
                    if self.state.ontology_needs_broadcast and log_streamer:
                        await self._emit_ontology_updated(
                            log_streamer=log_streamer,
                            update_summary=self.state.last_update_summary
                        )
                        self.state.clear_broadcast_signal()

                    # Save draft periodically
                    await self.save_draft()

                    # Check if agent called propose_ontology tool
                    if self.state.ontology_proposed and not ontology_proposed_emitted:
                        if log_streamer:
                            if hasattr(log_streamer, "flush"):
                                await log_streamer.flush()
                            try:
                                await log_streamer.log_event(
                                    event_type="ontology_proposed",
                                    message="Ontology proposed for review",
                                    metadata={
                                        "ontology_package": self.state.ontology_package.to_dict(),
                                        "ready": True
                                    },
                                    agent_id="ontology_agent",
                                )
                                logfire.info("Ontology proposed event emitted",
                                           title=self.state.ontology_package.title)
                            except Exception as e:
                                logfire.warning("Failed to emit ontology_proposed event", error=str(e))

                        ontology_proposed_emitted = True

                        if message_source is None:
                            print("\n[Ontology proposed - review and edit as needed, or type 'finalize' to complete]\n")

                    # Check if finalized
                    if self.state.ontology_finalized:
                        logfire.info("Ontology package finalized",
                                   exchanges=exchange_count,
                                   title=self.state.ontology_package.title)
                        break

                except Exception as e:
                    logfire.error("Conversation error",
                                exchange=exchange_count,
                                error=str(e))
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="error",
                            message=f"Error: {str(e)}",
                            agent_id="ontology_agent",
                        )
                    if message_source is None:
                        print(f"\nAgent: Hmm, I ran into an issue: {e}")
                        print("Let's try that again.\n")
                    continue

            # Capture conversation transcript
            if self.state.ontology_package and message_history:
                transcript_lines = []
                for msg in message_history:
                    role = msg.role if hasattr(msg, 'role') else 'unknown'
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    transcript_lines.append(f"{role.upper()}: {content}")

                self.state.ontology_package.conversation_transcript = "\n\n".join(transcript_lines)
                logfire.info("Conversation transcript captured", message_count=len(message_history))

            # Final save
            await self.save_draft()

            return self.state.ontology_package
