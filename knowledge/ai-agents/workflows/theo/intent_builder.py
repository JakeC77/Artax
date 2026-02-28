"""
intent_builder.py - Conversational intent discovery with Theo

This module orchestrates the conversation between the user and Theo
to build a well-formed Intent Package for team building.
"""

import asyncio
from pathlib import Path
from typing import Optional, Any
from pydantic_ai.models import KnownModelName
from app.utils.streaming import stream_with_logger
from app.workflows.theo.config import load_config
import logfire
from logfire import ConsoleOptions

from .models import IntentPackage, Mission, TeamBuildingGuidance
from .tools import THEO_TOOLS
from .theo_agent import TheoState, create_intent_agent
from pydantic import ValidationError


# Configure Logfire for observability
# Why: Enables tracing of intent discovery conversations
# Pattern: Geodesic framework standard (see examples/logfire_demo)
def _configure_logfire():
    """Configure Logfire with Geodesic framework patterns.

    Note: This configuration is skipped when ENVIRONMENT=sandbox/production,
    which allows the parent application (e.g., multi_workflow) to configure
    Logfire globally before importing this module.
    """
    import os

    # Skip if running in container (sandbox/production)
    # Why: Container app (app.py) configures Logfire globally
    # When: ENVIRONMENT=sandbox or ENVIRONMENT=production (set in .env or Azure)
    environment = os.getenv("ENVIRONMENT", "development")
    if environment in ("sandbox", "production"):
        return

    # Find repo root .logfire directory
    # From app/workflows/theo/intent_builder.py, go up 3 levels to repo root
    repo_root = Path(__file__).parent.parent.parent.parent
    logfire_dir = repo_root / ".logfire"

    # Check for verbose mode from environment variable
    verbose_mode = os.getenv("LOGFIRE_VERBOSE", "false").lower() == "true"

    logfire.configure(
        # Only send if token present (works locally without account)
        send_to_logfire='if-token-present',

        # Point to repo root credentials
        config_dir=logfire_dir if logfire_dir.exists() else None,

        # Service name for filtering in Logfire UI
        service_name='trident_intent_builder',

        # Development environment
        environment='development',

        # Show console output for local debugging
        # Set LOGFIRE_VERBOSE=true to enable detailed console logs
        console=ConsoleOptions(verbose=verbose_mode)
    )

    # Auto-instrument Pydantic AI agents
    logfire.instrument_pydantic_ai()


# Initialize Logfire once at module load (unless running in container)
_configure_logfire()


class IntentBuilder:
    """
    Orchestrates the conversation with Theo to extract user intent
    and build an Intent Package for team creation.
    """

    def __init__(
        self,
        model: KnownModelName = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize the Intent Builder.

        Args:
            model: Optional model name override. If not provided, uses workflow config.
                   The model factory will automatically use Azure OpenAI if configured.
            workspace_id: Optional workspace ID for company context lookup
            tenant_id: Optional tenant ID for GraphQL authentication
        """
        # Get configuration from workflow config
        config = load_config()
        self.state = TheoState(mode="intent", workspace_id=workspace_id, tenant_id=tenant_id)

        # Create the Theo agent with dynamic prompts
        # Use provided model or workflow config's intent_builder_model
        if model is not None:
            self.model = model
            self.agent = create_intent_agent(model=self.model)
        else:
            self.model = str(config.intent_builder_model)
            # Create agent using workflow config (theo_agent uses theo_model by default)
            # Pass the intent_builder_model explicitly
            model_instance = config.intent_builder_model.create()
            self.agent = create_intent_agent(model=model_instance)

        # Register Theo's intent discovery tools
        for tool_name, tool_func in THEO_TOOLS.items():
            self.agent.tool(tool_func)

    def _build_metadata_completion_prompt(self) -> str:
        """
        Build prompt for metadata completion step.

        This runs after user confirms to ensure all hidden metadata fields
        are populated based on the full conversation context.
        """
        current = self.state.intent_package

        prompt = f"""The user has confirmed their intent. Before finalizing, review the intent package and ensure ALL hidden metadata fields are complete.

Current Intent Package:
- Title: {current.title}
- Summary : {current.summary}
- Objective: {current.mission.objective}
- Why: {current.mission.why}
- Success: {current.mission.success_looks_like}

Current Metadata (check for gaps):
- Expertise Needed: {current.team_guidance.expertise_needed}
- Capabilities Needed: {current.team_guidance.capabilities_needed}
- Complexity Level: {current.team_guidance.complexity_level}
- Complexity Notes: {current.team_guidance.complexity_notes}
- Collaboration Pattern: {current.team_guidance.collaboration_pattern}
- Human Handshake Points: {current.team_guidance.human_ai_handshake_points}
- Workflow Pattern: {current.team_guidance.workflow_pattern}

Based on the conversation, call update_intent_package to fill any missing or exapand current metadata fields. Use the objective, why, and success criteria to infer:
- title: Short, descriptive workspace name
- summary: 2-3 sentence description of this workspace
- expertise_needed: What domains must the team understand?
- capabilities_needed: What must the team be able to DO?
- complexity_level: Simple / Moderate / Complex
- complexity_notes: What makes it that level?
- collaboration_pattern: Solo / Coordinated / Orchestrated
- human_ai_handshake_points: Where is human judgment critical?
- workflow_pattern: OneTime / Recurring / Exploratory

Call update_intent_package NOW with all missing fields, then respond with "Metadata complete."
"""
        return prompt

    def _sync_intent_from_user(self, user_package_data: dict) -> None:
        """
        Sync TheoState with the user's current intent package.

        This ensures Theo sees any edits the user made in the frontend editor
        before processing the new message. User edits are authoritative for
        user-facing fields (title, description, summary, mission.*).

        Args:
            user_package_data: Dict representation of the user's IntentPackage
        """
        try:
            user_package = IntentPackage(**user_package_data)

            if self.state.intent_package is None:
                # No existing package - use user's entirely
                self.state.intent_package = user_package
                logfire.info(
                    "Initialized intent from user",
                    title=user_package.title
                )
            else:
                # Merge: user-editable fields from user, metadata from existing
                self.state.intent_package = self._merge_user_edits(
                    existing=self.state.intent_package,
                    user_edited=user_package
                )
                logfire.info(
                    "Synced intent from user edits",
                    title=user_package.title,
                    version=self.state.intent_package.current_version
                )

        except ValidationError as e:
            logfire.warning(
                "Failed to parse user intent package - continuing with existing state",
                error=str(e)
            )
            # Continue with existing state if user package is malformed

    def _merge_user_edits(
        self,
        existing: IntentPackage,
        user_edited: IntentPackage
    ) -> IntentPackage:
        """
        Merge user's edits with existing AI metadata.

        User-editable fields (title, description, summary, mission.*) come from user_edited.
        AI metadata fields (team_guidance.*, conversation_transcript, iteration_history)
        are preserved from existing.

        Args:
            existing: The current IntentPackage in TheoState
            user_edited: The IntentPackage sent by the frontend with user's edits

        Returns:
            Merged IntentPackage with user's edits and preserved AI metadata
        """
        return IntentPackage(
            schema_version=existing.schema_version,

            # User-editable fields: take from user
            title=user_edited.title,
            description=user_edited.description,
            summary=user_edited.summary,
            mission=Mission(
                objective=user_edited.mission.objective,
                why=user_edited.mission.why,
                success_looks_like=user_edited.mission.success_looks_like
            ),

            # AI metadata: preserve existing
            team_guidance=existing.team_guidance,
            conversation_transcript=existing.conversation_transcript,
            iteration_history=existing.iteration_history,
            current_version=existing.current_version + 1,  # Increment version on user edit
            created_at=existing.created_at,
            confirmed=existing.confirmed,
        )

    async def _emit_intent_updated(
        self,
        log_streamer: any,
        update_summary: str | None = None
    ) -> None:
        """
        Emit intent_updated event with current package state.

        Called after Theo modifies user-facing intent fields via tools.
        The frontend uses this to update the structured editor in real-time.

        Args:
            log_streamer: GraphQL logger for emitting events
            update_summary: Optional natural language description of what changed
        """
        if self.state.intent_package is None:
            return

        if log_streamer is None:
            return

        try:
            await log_streamer.log_event(
                event_type="intent_updated",
                message="Intent package updated",
                metadata={
                    "intent_package": self.state.intent_package.to_dict(),
                    "update_summary": update_summary,
                },
                agent_id="theo",
            )
            logfire.info(
                "Emitted intent_updated event",
                title=self.state.intent_package.title
            )
        except Exception as e:
            logfire.warning("Failed to emit intent_updated event", error=str(e))

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
            - (None, "end_intent", metadata_dict) when user confirms intent via UI button
            - (None, "quit", None) if quit/exit or timeout
            - (None, "empty", None) if empty input (retry)

            metadata_dict may contain 'current_intent_package' with user's edited intent state
        """
        if message_source is None:
            # CLI mode: use stdin
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ['quit', 'exit']:
                    return None, "quit", None
                if user_input.lower() == 'confirm':
                    # CLI simulation of end_intent
                    return None, "end_intent", None
                return (user_input, "user_message", None) if user_input else (None, "empty", None)
            except (EOFError, KeyboardInterrupt):
                return None, "quit", None
        else:
            # Event stream mode: read from stream
            try:
                # Wait for user_message OR end_intent event with timeout
                event = await message_source.wait_for_event(
                    event_type=["user_message", "end_intent"],
                    timeout=timeout
                )

                if event:
                    event_type = event.get("event_type", "user_message")
                    # Extract metadata - check both top-level and nested metadata field
                    # Frontend sends current_intent_package at top level of event
                    metadata = event.get("metadata", {})

                    # current_intent_package may be at top level or in metadata
                    if "current_intent_package" in event:
                        metadata["current_intent_package"] = event["current_intent_package"]

                    # user_edited_fields tracks which fields user edited since last AI update
                    if "user_edited_fields" in event:
                        metadata["user_edited_fields"] = event["user_edited_fields"]

                    # For end_intent, frontend may send intent_package in data object
                    # or at top level - normalize to final_intent_package in metadata
                    if event_type == "end_intent":
                        # Check various locations where frontend might send the final package
                        final_pkg = None
                        if "data" in event and isinstance(event["data"], dict):
                            # Frontend sends {"data": {"intent_package": "..."}}
                            pkg_data = event["data"].get("intent_package")
                            if pkg_data:
                                # May be JSON string or dict
                                if isinstance(pkg_data, str):
                                    import json
                                    try:
                                        final_pkg = json.loads(pkg_data)
                                    except json.JSONDecodeError:
                                        pass
                                else:
                                    final_pkg = pkg_data
                        elif "intent_package" in event:
                            final_pkg = event["intent_package"]
                        elif "current_intent_package" in event:
                            final_pkg = event["current_intent_package"]

                        if final_pkg:
                            metadata["final_intent_package"] = final_pkg

                    if event_type == "end_intent":
                        logfire.info("Received end_intent event - user confirmed intent")
                        return None, "end_intent", metadata

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

    async def start_conversation(
        self,
        initial_context: Optional[str] = None,
        message_source: Optional[Any] = None,
        log_streamer: Optional[Any] = None
    ) -> Optional[IntentPackage]:
        """
        Start an interactive conversation with Theo to build the intent package.

        Args:
            initial_context: Optional initial context from the user
            message_source: Optional EventStreamReader for event stream mode, None for stdin (CLI mode)
            log_streamer: Optional GraphQL logger for logging responses

        Returns:
            The finalized IntentPackage, or None if cancelled

        Workflow:
            1. Theo opens with: "So—what are we trying to make happen?"
            2. User responds with their initial idea
            3. Theo asks clarifying questions to dig into:
               - The objective (what)
               - The why (3 layers deep)
               - Success criteria
               - Team needs (inferred)
            4. Theo presents the intent summary
            5. User confirms or provides feedback
            6. Theo iterates if needed
            7. Once confirmed, Theo sends the package
        """
        # Create top-level span for entire conversation
        with logfire.span("intent_discovery_conversation", initial_context=initial_context):
            logfire.info("Starting intent discovery conversation")

            # Only print CLI messages if in CLI mode (message_source is None)
            if message_source is None:
                print("\n" + "=" * 60)
                print("INTENT DISCOVERY WITH THEO")
                print("=" * 60)
                print("\nTheo will help you clarify what you're trying to accomplish.")
                print("This conversation will help build the right team for your needs.")
                print("\nType 'quit' or 'exit' to end the conversation early.")
                print("-" * 60 + "\n")

            # Start with Theo's opening
            # Accumulate full message history across all runs
            message_history = []

            # In the new flow, if initial_context is provided (user started with a question),
            # skip Theo's opening and wait for the user's first message.
            # Theo will respond to that message with context awareness.
            # Only send opening in CLI mode (message_source is None), not in event stream mode
            if not initial_context and message_source is None:
                # CLI mode or no initial context - Theo sends opening
                initial_prompt = "Start the conversation with your opening move."

                # Initial message from Theo
                with logfire.span("theo_opening_message"):
                    result = await self.agent.run(
                        initial_prompt,
                        deps=self.state
                    )
                    theo_message = result.output
                    logfire.info("Theo opened conversation", message_length=len(theo_message))

                # Accumulate messages from initial run
                message_history.extend(result.new_messages())

                # Log Theo's opening message
                if log_streamer:
                    await log_streamer.log_event(
                        event_type="agent_message",
                        message=theo_message,
                        agent_id="theo",
                    )

                if message_source is None:
                    print(f"Theo: {theo_message}\n")

            # Conversation loop
            exchange_count = 0
            intent_proposed_emitted = False  # Track if we've already emitted intent_proposed event
            first_message_handled = False  # Track if we've used initial_context

            while not self.state.intent_finalized:
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

                # Sync intent state from user before processing message
                # This ensures Theo sees any edits the user made in the frontend editor
                if event_metadata and event_type == "user_message":
                    user_intent_package = event_metadata.get("current_intent_package")
                    if user_intent_package:
                        self._sync_intent_from_user(user_intent_package)

                    # Track which fields user edited (for Theo's awareness)
                    user_edited_fields = event_metadata.get("user_edited_fields", [])
                    self.state.user_edited_fields = user_edited_fields

                # Handle end_intent event - user confirmed intent via UI button
                if event_type == "end_intent":
                    logfire.info("User confirmed intent via end_intent event",
                               exchanges=exchange_count,
                               intent_proposed=self.state.intent_proposed)

                    # Sync final intent package from user if provided
                    # This captures any last-minute edits before finalization
                    if event_metadata:
                        final_intent_package = event_metadata.get("final_intent_package")
                        if final_intent_package:
                            self._sync_intent_from_user(final_intent_package)

                    if self.state.intent_package:
                        # Mark as finalized
                        self.state.intent_finalized = True

                        # Emit intent_finalized event with full package
                        if log_streamer:
                            intent_text = self.state.intent_package.get_formatted_intent_text()
                            try:
                                await log_streamer.log_event(
                                    event_type="intent_finalized",
                                    message=f"Intent finalized: {self.state.intent_package.title}",
                                    metadata={
                                        "intent_package": self.state.intent_package.to_dict(),
                                        "intent_text": intent_text,
                                        "title": self.state.intent_package.title,
                                        "summary": self.state.intent_package.summary,
                                        "objective": self.state.intent_package.mission.objective,
                                        "why": self.state.intent_package.mission.why,
                                        "success_criteria": self.state.intent_package.mission.success_looks_like
                                    },
                                    agent_id="theo",
                                )
                            except Exception as e:
                                logfire.warning("Failed to emit intent_finalized event", error=str(e))

                        if message_source is None:
                            print("\n" + "=" * 60)
                            print("INTENT CONFIRMED")
                            print("=" * 60 + "\n")

                        # Exit the conversation loop
                        break
                    else:
                        # No intent package yet - shouldn't happen but handle gracefully
                        logfire.warning("end_intent received but no intent package exists")
                        if message_source is None:
                            print("Theo: I don't have an intent to confirm yet. Let's keep talking.\n")
                        continue

                if event_type == "quit":
                    # Quit, exit, or timeout
                    if message_source is None:
                        logfire.info("User quit conversation", exchanges=exchange_count)
                        print("\nTheo: No problem! We can pick this up later.")
                    else:
                        logfire.info("User quit or timeout", exchanges=exchange_count)
                    return None

                if event_type == "empty" or not user_input:
                    if message_source is None:
                        print("Theo: I didn't catch that. Could you say that again?\n")
                    continue

                # If user sends a message after intent was proposed, reset the flag
                # This allows Theo to update the intent and propose again if needed
                if intent_proposed_emitted:
                    logfire.info("User sent message after intent proposed - allowing re-proposal")
                    intent_proposed_emitted = False
                    # Also reset state flag so Theo can call propose_intent again
                    self.state.intent_proposed = False

                # Send to Theo with span tracking
                try:
                    with logfire.span("conversation_exchange",
                                     exchange=exchange_count,
                                     user_input_length=len(user_input)):
                        logfire.info("User message", exchange=exchange_count)

                        # DIAGNOSTIC: Print system prompt presence (set DEBUG=True to enable)
                        DEBUG = False
                        if DEBUG:
                            print("\n" + "="*60)
                            print(f"DEBUG: Exchange {exchange_count}")
                            print(f"Message history length: {len(message_history)}")
                            # Inspect message structure in detail
                            for i, msg in enumerate(message_history):
                                msg_type = type(msg).__name__
                                print(f"  Message {i+1}: type={msg_type}")

                                # Pydantic AI messages have 'parts' attribute
                                if hasattr(msg, 'parts'):
                                    parts = msg.parts
                                    print(f"    Parts count: {len(parts)}")
                                    for j, part in enumerate(parts):
                                        part_type = type(part).__name__
                                        print(f"      Part {j+1}: {part_type}")
                                        # Check for system prompt part
                                        if part_type == 'SystemPromptPart':
                                            content = getattr(part, 'content', '')
                                            preview = content[:100] + "..." if len(content) > 100 else content
                                            print(f"        SYSTEM PROMPT: {preview}")
                                        elif part_type == 'UserPromptPart':
                                            content = getattr(part, 'content', '')
                                            preview = content[:80] + "..." if len(content) > 80 else content
                                            print(f"        User: {preview}")
                                        elif part_type == 'TextPart':
                                            content = getattr(part, 'content', '')
                                            preview = content[:80] + "..." if len(content) > 80 else content
                                            print(f"        Text: {preview}")
                                        elif part_type == 'ToolCallPart':
                                            tool_name = getattr(part, 'tool_name', 'unknown')
                                            print(f"        Tool Call: {tool_name}")
                                        elif part_type == 'ToolReturnPart':
                                            tool_name = getattr(part, 'tool_name', 'unknown')
                                            print(f"        Tool Return: {tool_name}")
                            print("="*60 + "\n")

                        # Pass full accumulated message history
                        # Buffer text until tools complete, then send all at once
                        # Why: Tools like propose_intent must execute BEFORE user sees
                        # "click Continue" text, so events fire in correct order
                        theo_message = ""
                        result = None
                        if log_streamer:
                            from app.utils.streaming import stream_agent_text
                            from uuid import uuid4

                            # Buffer all text chunks - don't send until tools complete
                            text_buffer = []
                            message_id = str(uuid4())

                            # Stream and collect result (no on_batch - we buffer instead)
                            async for batch_text, acc_len, part_idx, metadata, event_result in stream_agent_text(
                                self.agent,
                                user_input,
                                deps=self.state,
                                message_history=message_history,
                                on_batch=None,  # Don't stream immediately
                                batch_size=30,
                                flush_interval=0.05,
                                message_id=message_id,
                            ):
                                # Collect text chunks
                                if batch_text:
                                    text_buffer.append(batch_text)
                                # The last yield will have the result
                                if event_result is not None:
                                    result = event_result
                                    if hasattr(result, 'output'):
                                        theo_message = result.output
                                    if hasattr(result, 'new_messages'):
                                        message_history.extend(result.new_messages())

                            # If we didn't get a result from streaming, run again to get it
                            # (fallback for compatibility)
                            if result is None:
                                result = await self.agent.run(
                                    user_input,
                                    deps=self.state,
                                    message_history=message_history
                                )
                                message_history.extend(result.new_messages())
                                theo_message = result.output

                            # NOW send the buffered text as a single message
                            # This happens AFTER tools have executed
                            if theo_message:
                                await log_streamer.log_event(
                                    event_type="agent_message",
                                    message=theo_message,
                                    agent_id="theo",
                                    metadata={
                                        "message_id": message_id,
                                        "completed": True,
                                        "buffered": True,  # Flag for debugging
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
                            theo_message = result.output
                        
                        logfire.info("Theo response",
                                   exchange=exchange_count,
                                   response_length=len(theo_message))

                    if message_source is None:
                        print(f"\nTheo: {theo_message}\n")

                    # Check if tools updated user-facing intent fields
                    # If so, emit intent_updated event to sync frontend editor
                    if self.state.intent_needs_broadcast and log_streamer:
                        await self._emit_intent_updated(
                            log_streamer=log_streamer,
                            update_summary=self.state.last_update_summary
                        )
                        self.state.clear_broadcast_signal()

                    # Check if Theo called propose_intent tool
                    # Emit intent_proposed event but DON'T end - wait for end_intent from user
                    if self.state.intent_proposed and not intent_proposed_emitted:
                        # Emit intent_proposed event with full intent package
                        if log_streamer:
                            if hasattr(log_streamer, "flush"):
                                await log_streamer.flush()
                            try:
                                await log_streamer.log_event(
                                    event_type="intent_proposed",
                                    message="Intent proposed for confirmation",
                                    metadata={
                                        "intent_package": self.state.intent_package.to_dict(),
                                        "ready": True
                                    },
                                    agent_id="theo",
                                )
                                logfire.info("Intent proposed event emitted - waiting for end_intent",
                                           title=self.state.intent_package.title)
                            except Exception as e:
                                # Don't fail workflow if event emission fails
                                logfire.warning("Failed to emit intent_proposed event", error=str(e))

                        # Mark as emitted
                        intent_proposed_emitted = True

                        if message_source is None:
                            print("\n[Intent proposed - type 'confirm' to finalize or continue chatting]\n")

                        # Continue the loop - wait for end_intent event or more user messages

                    # Check if finalized (set by end_intent handler above)
                    if self.state.intent_finalized:
                        logfire.info("Intent package finalized",
                                   exchanges=exchange_count,
                                   title=self.state.intent_package.title)
                        if log_streamer:
                            # Emit intent_finalized event with full intent text
                            intent_text = self.state.intent_package.get_formatted_intent_text()
                            try:
                                if hasattr(log_streamer, "flush"):
                                    await log_streamer.flush()
                                await log_streamer.log_event(
                                    event_type="intent_finalized",
                                    message=f"Intent finalized: {self.state.intent_package.title}",
                                    metadata={
                                        "intent_text": intent_text,
                                        "title": self.state.intent_package.title,
                                        "summary": self.state.intent_package.summary,
                                        "objective": self.state.intent_package.mission.objective,
                                        "why": self.state.intent_package.mission.why,
                                        "success_criteria": self.state.intent_package.mission.success_looks_like
                                    },
                                    agent_id="theo",
                                )
                            except Exception as e:
                                # Don't fail workflow if event emission fails
                                logfire.warning("Failed to emit intent_finalized event", error=str(e))
                        if message_source is None:
                            print("\n" + "=" * 60)
                            print("USER CONFIRMATION RECEIVED")
                            print("=" * 60)
                            print("\nFinalizing hidden metadata...\n")
                        break

                except Exception as e:
                    logfire.error("Conversation error",
                                exchange=exchange_count,
                                error=str(e))
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="error",
                            message=f"Error: {str(e)}",
                            agent_id="theo",
                        )
                    if message_source is None:
                        print(f"\nTheo: Hmm, I ran into an issue: {e}")
                        print("Let's try that again.\n")
                    continue

            # Metadata completion step - run after user confirms
            if self.state.intent_finalized and self.state.intent_package:
                with logfire.span("metadata_completion"):
                    logfire.info("Running metadata completion")

                    # Build metadata completion prompt
                    metadata_prompt = self._build_metadata_completion_prompt()

                    try:
                        # Run one final agent call to complete metadata
                        result = await self.agent.run(
                            metadata_prompt,
                            deps=self.state,
                            message_history=message_history
                        )

                        logfire.info("Metadata completion finished")
                        if message_source is None:
                            print("✓ Metadata finalized\n")

                    except Exception as e:
                        logfire.error("Metadata completion error", error=str(e))
                        print(f"Warning: Metadata completion had issues: {e}\n")
                        # Continue anyway - user-facing fields are complete

            # Capture conversation transcript for team building context
            if self.state.intent_package and message_history:
                transcript_lines = []
                for msg in message_history:
                    role = msg.role if hasattr(msg, 'role') else 'unknown'
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    transcript_lines.append(f"{role.upper()}: {content}")

                self.state.intent_package.conversation_transcript = "\n\n".join(transcript_lines)
                logfire.info("Conversation transcript captured", message_count=len(message_history))

            return self.state.intent_package

    async def quick_build(
        self,
        objective: str,
        why: str,
        success_criteria: str,
        expertise: list[str],
        capabilities: list[str]
    ) -> IntentPackage:
        """
        Quick build mode - create intent package directly without conversation.

        Useful for programmatic team creation or testing.

        Args:
            objective: What the user wants to accomplish
            why: Why this matters (the deeper motivation)
            success_criteria: How we'll know we've succeeded
            expertise: List of domain expertise needed
            capabilities: List of capabilities needed

        Returns:
            The finalized IntentPackage
        """
        # Create span for quick build
        with logfire.span("intent_quick_build",
                         expertise_count=len(expertise),
                         capabilities_count=len(capabilities)):
            logfire.info("Starting quick build mode")

            # Build the package directly
            prompt = f"""Create an intent package for this mission:

Objective: {objective}
Why: {why}
Success Criteria: {success_criteria}
Expertise Needed: {', '.join(expertise)}
Capabilities Needed: {', '.join(capabilities)}

Use update_intent_package to create the package with a good title and summary, then use send_intent_package to finalize it."""

            result = await self.agent.run(prompt, deps=self.state)

            if self.state.intent_package:
                logfire.info("Quick build completed",
                           title=self.state.intent_package.title,
                           version=self.state.intent_package.current_version)

            return self.state.intent_package

    def get_intent_summary(self) -> Optional[str]:
        """
        Get the current user-facing intent summary.

        Returns:
            Formatted summary or None if no package exists
        """
        if self.state.intent_package is None:
            return None

        return self.state.intent_package.get_user_facing_summary()


async def demo_conversation():
    """
    Demo the intent builder with a sample conversation.
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return

    builder = IntentBuilder()

    # Example: User wants to create a team for sales analysis
    initial_context = "I want to create a workflow that helps me analyze our sales data and make recommendations."

    intent_package = await builder.start_conversation(initial_context)

    if intent_package:
        print("\n" + "=" * 60)
        print("FINAL INTENT PACKAGE")
        print("=" * 60)
        print(intent_package.get_user_facing_summary())
        print("\nHandoff package:")
        import json
        print(json.dumps(intent_package.to_handoff_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(demo_conversation())
