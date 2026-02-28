"""Shared utility for streaming text from pydantic_ai agents with batching support."""

import time
from typing import AsyncIterator, Callable, Optional, Any
from uuid import uuid4
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    PartStartEvent,
    PartDeltaEvent,
    TextPartDelta,
    TextPart,
)


async def stream_agent_text(
    agent: Agent,
    prompt: str,
    *,
    batch_size: int = 30,
    flush_interval: float = 0.05,
    track_full_text: bool = False,
    on_batch: Optional[Callable[[str, int, Optional[int], dict], Any]] = None,
    deps: Optional[dict] = None,
    message_history: Optional[list] = None,
    usage_limits: Optional[Any] = None,
    message_id: Optional[str] = None,
) -> AsyncIterator[tuple[str, int, Optional[int], dict, Optional[Any]]]:
    """
    Stream text from an agent with batching support.
    
    Args:
        agent: The pydantic_ai Agent to stream from
        prompt: The prompt to send to the agent
        batch_size: Size of text chunks to batch before yielding (default: 30)
        flush_interval: Maximum time to wait before yielding partial batch (default: 0.05s)
        track_full_text: If True, also accumulate and return full text
        on_batch: Optional async callback function called for each batch:
                 (batch_text, accumulated_length, part_index, metadata) -> None
        deps: Optional dependencies to pass to agent
        message_history: Optional message history
        usage_limits: Optional usage limits
        message_id: Optional unique message ID for grouping chunks. If not provided, generates one.
        
    Yields:
        Tuples of (batch_text, accumulated_length, part_index, metadata, result)
        - batch_text: The batched text chunk
        - accumulated_length: Total characters accumulated so far
        - part_index: The part index from the event (None if not available)
        - metadata: Dictionary with part_index, accumulated_length, completed flag, and message_id
        - result: AgentRunResultEvent.result if available, None otherwise
    """
    # Generate unique message ID for this stream if not provided
    if message_id is None:
        message_id = str(uuid4())
    
    batch_buffer = ""
    accumulated_length = 0
    last_part_index = None
    full_text = ""
    result = None
    last_flush = time.monotonic()
    
    async for event in agent.run_stream_events(
        prompt,
        deps=deps if deps else None,
        message_history=message_history,
        usage_limits=usage_limits
    ):
        # Handle PartStartEvent - may contain initial text content
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, TextPart):
                initial_text = event.part.content
                if initial_text:
                    if track_full_text:
                        full_text += initial_text
                    batch_buffer += initial_text
                    accumulated_length += len(initial_text)
                    last_part_index = event.index
                    
                    # Send batch when size or time threshold reached
                    now = time.monotonic()
                    should_flush = (
                        len(batch_buffer) >= batch_size
                        or (batch_buffer and now - last_flush >= flush_interval)
                    )
                    if should_flush:
                        metadata = {
                            "part_index": event.index,
                            "accumulated_length": accumulated_length,
                            "completed": False,  # Not the final batch
                            "message_id": message_id,  # Include message ID for grouping chunks
                        }
                        if on_batch:
                            await on_batch(batch_buffer, accumulated_length, event.index, metadata)
                        yield (batch_buffer, accumulated_length, event.index, metadata, None)
                        batch_buffer = ""
                        last_flush = now
        
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                delta_text = event.delta.content_delta
                if track_full_text:
                    full_text += delta_text
                batch_buffer += delta_text
                accumulated_length += len(delta_text)
                last_part_index = event.index
                
                # Send batch when size or time threshold reached
                now = time.monotonic()
                should_flush = (
                    len(batch_buffer) >= batch_size
                    or (batch_buffer and now - last_flush >= flush_interval)
                )
                if should_flush:
                    metadata = {
                        "part_index": event.index,
                        "accumulated_length": accumulated_length,
                        "completed": False,  # Not the final batch
                        "message_id": message_id,  # Include message ID for grouping chunks
                    }
                    if on_batch:
                        await on_batch(batch_buffer, accumulated_length, event.index, metadata)
                    yield (batch_buffer, accumulated_length, event.index, metadata, None)
                    batch_buffer = ""
                    last_flush = now
        
        elif isinstance(event, AgentRunResultEvent):
            if event.result and hasattr(event.result, 'output'):
                result = event.result
    
    # Send any remaining text in buffer (this is the final batch)
    if batch_buffer:
        metadata = {
            "part_index": last_part_index,
            "accumulated_length": accumulated_length,
            "completed": True,  # This is the final batch - stream is complete
            "message_id": message_id,  # Include message ID for grouping chunks
        }
        if on_batch:
            await on_batch(batch_buffer, accumulated_length, last_part_index, metadata)
        yield (batch_buffer, accumulated_length, last_part_index, metadata, result)
    elif result is not None and accumulated_length == 0:
        # Edge case: result available but no text was streamed (shouldn't happen in practice)
        # Yield empty batch with result so callers can access it
        metadata = {
            "part_index": last_part_index,
            "accumulated_length": accumulated_length,
            "completed": True,  # Stream is complete
            "message_id": message_id,  # Include message ID for grouping chunks
        }
        yield ("", accumulated_length, last_part_index, metadata, result)
    elif result is not None:
        # Edge case: result available but no remaining buffer (all text was already sent)
        # Yield a completion marker so callers know the stream is complete
        metadata = {
            "part_index": last_part_index,
            "accumulated_length": accumulated_length,
            "completed": True,  # Stream is complete
            "message_id": message_id,  # Include message ID for grouping chunks
        }
        if on_batch:
            await on_batch("", accumulated_length, last_part_index, metadata)
        yield ("", accumulated_length, last_part_index, metadata, result)
    
    # If track_full_text, we need to return it somehow
    # For now, we'll just track it but not return it in the iterator
    # The caller can accumulate from the batches if needed


async def stream_with_logger(
    agent: Agent,
    prompt: str,
    log_streamer: Any,
    agent_id: str,
    *,
    batch_size: int = 30,
    flush_interval: float = 0.05,
    track_full_text: bool = False,
    deps: Optional[dict] = None,
    message_history: Optional[list] = None,
    usage_limits: Optional[Any] = None,
    message_id: Optional[str] = None,
) -> str:
    """
    Convenience function for streaming with log_streamer pattern.
    
    Args:
        agent: The pydantic_ai Agent to stream from
        prompt: The prompt to send to the agent
        log_streamer: The log streamer with log_event method
        agent_id: The agent ID to use in log events
        batch_size: Size of text chunks to batch (default: 30)
        flush_interval: Maximum time between flushes (default: 0.05s)
        track_full_text: If True, return full accumulated text
        deps: Optional dependencies to pass to agent
        message_history: Optional message history
        usage_limits: Optional usage limits
        message_id: Optional unique message ID for grouping chunks. If not provided, generates one.
        
    Returns:
        Full text if track_full_text=True, empty string otherwise
    """
    full_text = ""
    
    async def on_batch(batch_text: str, acc_len: int, part_idx: Optional[int], metadata: dict):
        await log_streamer.log_event(
            event_type="agent_message",
            message=batch_text,
            agent_id=agent_id,
            metadata=metadata
        )
    
    async for batch_text, acc_len, part_idx, metadata, result in stream_agent_text(
        agent,
        prompt,
        batch_size=batch_size,
        flush_interval=flush_interval,
        track_full_text=track_full_text,
        on_batch=on_batch,
        deps=deps,
        message_history=message_history,
        usage_limits=usage_limits,
        message_id=message_id,  # Pass message_id through
    ):
        if track_full_text:
            full_text += batch_text

    if hasattr(log_streamer, "flush"):
        await log_streamer.flush()

    return full_text

