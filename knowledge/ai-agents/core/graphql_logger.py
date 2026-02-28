"""GraphQL client for streaming scenario run logs and results."""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from app.core.authenticated_graphql_client import execute_graphql, run_graphql

logger = logging.getLogger(__name__)

_APPEND_SCENARIO_RUN_LOG_MUTATION = """
mutation AppendScenarioRunLog($runId: UUID!, $content: String!) {
    appendScenarioRunLog(runId: $runId, content: $content)
}
""".strip()


def _execute_graphql(query: str, variables: dict[str, Any], tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Execute a GraphQL mutation with authentication support.
    
    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
    """
    return execute_graphql(query, variables, graphql_endpoint=None, tenant_id=tenant_id)


async def _run_graphql(query: str, variables: dict[str, Any], tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Run the blocking GraphQL call in a background thread.
    
    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
    """
    return await run_graphql(query, variables, graphql_endpoint=None, tenant_id=tenant_id)


class ScenarioRunLogger:
    """Streams logs and results to GraphQL API for scenario runs."""
    
    def __init__(
        self,
        run_id: str,
        tenant_id: Optional[str] = None,
        enabled: bool = True,
        flush_interval: float = 0.05,
    ):
        """Initialize logger for a scenario run.
        
        Args:
            run_id: UUID of the scenario run (required)
            tenant_id: UUID of the tenant (optional, added as X-Tenant-Id header)
            enabled: Whether logging is enabled (can be disabled for testing)
            flush_interval: How often to flush buffered events (seconds)
        
        Raises:
            ValueError: If run_id is None or empty
        """
        if not run_id:
            raise ValueError("run_id is required and cannot be None or empty")
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.enabled = enabled
        self._log_count = 0
        self._event_buffer: list[str] = []
        self._event_buffer_bytes = 0
        self._buffer_message_id: Optional[str] = None
        self._buffer_contains_agent_message = False
        self._flush_interval = flush_interval
        self._flush_lock = asyncio.Lock()
        self._last_flush = time.monotonic()
    
    async def append_log(self, content: str) -> Optional[int]:
        """Append a log entry to the scenario run.
        
        Args:
            content: Log content to append
            
        Returns:
            Log entry ID (Long!) or None if disabled/failed
        """
        if not self.enabled:
            return None
        
        # Validate run_id is set
        if not self.run_id:
            logger.error("Cannot append log: run_id is None or empty")
            return None
        
        try:
            result = await _run_graphql(
                _APPEND_SCENARIO_RUN_LOG_MUTATION,
                {
                    "runId": self.run_id,
                    "content": content + "\n"
                },
                tenant_id=self.tenant_id
            )
            log_id = result.get("appendScenarioRunLog")
            self._log_count += 1
            logger.debug(f"Appended log #{self._log_count} for run_id={self.run_id}, log_id={log_id}")
            return log_id
        except Exception as e:
            # Don't fail the workflow if logging fails
            logger.warning(f"Failed to append log for run_id={self.run_id}: {e}")
            return None

    async def _append_log_raw(self, content: str) -> Optional[int]:
        """Append raw log content without adding newline.

        Used for structured JSON events where the newline would break parsing.

        Args:
            content: Log content to append (no newline added)

        Returns:
            Log entry ID (Long!) or None if disabled/failed
        """
        if not self.enabled:
            return None

        if not self.run_id:
            logger.error("Cannot append log: run_id is None or empty")
            return None

        try:
            result = await _run_graphql(
                _APPEND_SCENARIO_RUN_LOG_MUTATION,
                {
                    "runId": self.run_id,
                    "content": content  # No newline added
                },
                tenant_id=self.tenant_id
            )
            log_id = result.get("appendScenarioRunLog")
            self._log_count += 1
            logger.debug(f"Appended raw log #{self._log_count} for run_id={self.run_id}, log_id={log_id}")
            return log_id
        except Exception as e:
            logger.warning(f"Failed to append raw log for run_id={self.run_id}: {e}")
            return None

    async def _flush_buffer_locked(self) -> None:
        if not self._event_buffer:
            return

        batch_content = "\n".join(self._event_buffer)
        self._event_buffer = []
        self._event_buffer_bytes = 0
        self._buffer_message_id = None
        self._buffer_contains_agent_message = False
        self._last_flush = time.monotonic()
        await self._append_log_raw(batch_content)

    async def _flush_buffer(self) -> None:
        async with self._flush_lock:
            await self._flush_buffer_locked()

    async def flush(self) -> None:
        """Force flush buffered events."""
        if not self.enabled:
            return
        await self._flush_buffer()

    async def log_event(self, event_type: str, message: str = None, metadata: Optional[dict] = None, agent_id: Optional[str] = None, **kwargs):
        """Log an activity event as structured JSON.

        Args:
            event_type: Type of event (e.g., "task_received", "agent_completed")
            message: Human-readable message
            metadata: Optional structured metadata (can include "stage" for workflow stage filtering)
            agent_id: Agent ID sending the log (required, will use metadata.agent_id if not provided)
            **kwargs: Additional top-level fields to include in the event (e.g., entity_type, node_ids, status)
        """
        # Build the structured JSON event
        if not self.enabled:
            return

        event_data = {
            "event_type": event_type,
        }

        # Include message if provided
        if message is not None:
            event_data["message"] = message
        
        # Always include agent_id - prefer parameter, then metadata, then None
        # Check if agent_id was explicitly provided (including None)
        if agent_id is not None:
            event_data["agent_id"] = agent_id
        elif metadata and "agent_id" in metadata:
            event_data["agent_id"] = metadata["agent_id"]
        else:
            event_data["agent_id"] = None
        
        # Include all metadata fields when present
        if metadata:
            # Include all metadata fields (excluding agent_id since we handle it above)
            for key, value in metadata.items():
                if key != "agent_id":  # Skip agent_id as it's handled separately above
                    event_data[key] = value

        # Include any additional kwargs as top-level fields
        # This allows callers to pass fields like entity_type, node_ids, status directly
        for key, value in kwargs.items():
            if key not in event_data:  # Don't override existing fields
                event_data[key] = value

        # Format as JSON string (compact, no extra whitespace)
        # Use default=str to handle non-serializable types gracefully
        log_entry = json.dumps(event_data, ensure_ascii=False, default=str)
        log_entry_bytes = len(log_entry.encode("utf-8"))
        is_agent_message = event_type == "agent_message"
        message_id = event_data.get("message_id")
        completed = bool(event_data.get("completed"))
        turn_end = False

        async with self._flush_lock:
            if not is_agent_message:
                # Non-streaming / control events (intent_proposed, clarification_needed, etc.)
                # must be delivered immediately to avoid UI lag.
                if self._event_buffer:
                    await self._flush_buffer_locked()
                await self._append_log_raw(log_entry)
                self._last_flush = time.monotonic()
                return

            if self._event_buffer:
                if self._buffer_contains_agent_message:
                    if message_id != self._buffer_message_id:
                        await self._flush_buffer_locked()
                else:
                    await self._flush_buffer_locked()
            self._buffer_message_id = message_id
            self._buffer_contains_agent_message = True

            self._event_buffer.append(log_entry)
            self._event_buffer_bytes += log_entry_bytes

            now = time.monotonic()
            should_flush = now - self._last_flush >= self._flush_interval

            # Safeguard against oversized mutations
            if len(self._event_buffer) >= 200 or self._event_buffer_bytes >= 256 * 1024:
                should_flush = True

            if is_agent_message and completed:
                should_flush = True

            if should_flush:
                await self._flush_buffer_locked()
    
    async def log_result(self, result: str):
        """Log the final workflow result.
        
        Args:
            result: Final workflow result text
        """
        await self.append_log(f"\n## WORKFLOW RESULT\n\n{result}\n")
    
    async def log_error(self, error: str):
        """Log an error.
        
        Args:
            error: Error message
        """
        await self.append_log(f"\n❌ ERROR: {error}\n")
    
    async def log_summary(self, metrics: dict):
        """Log execution summary/metrics.
        
        Args:
            metrics: Dictionary with metrics like subtasks_completed, duration, etc.
        """
        summary_lines = ["\n## EXECUTION SUMMARY\n"]
        for key, value in metrics.items():
            summary_lines.append(f"- **{key}**: {value}")
        summary_lines.append("")
        
        await self.append_log("\n".join(summary_lines))

