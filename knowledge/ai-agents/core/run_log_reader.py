"""
Run log reader for ontology conversation (and other) workflows.

Fetches scenario run log entries via getScenarioRunLogsByRunId and parses
them into a list of message dicts (role, content) for resumable conversation context.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)

GET_SCENARIO_RUN_LOGS_QUERY = """
query GetScenarioRunLogs($runId: UUID!, $withinDays: Int) {
  getScenarioRunLogsByRunId(runId: $runId, withinDays: $withinDays) {
    logId
    runId
    tenantId
    content
    createdAt
  }
}
""".strip()


def _parse_log_content_to_messages(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Parse run log entries into a chronological list of {role, content} messages.

    Expects each entry to have "content" that is JSON written by ScenarioRunLogger.log_event:
    event_type, message, agent_id, etc. We map user_message -> user, agent_message -> assistant.
    """
    messages: list[dict[str, str]] = []
    for entry in entries:
        content = entry.get("content") or ""
        if not content.strip():
            continue
        # Content may be a single JSON object or newline-separated JSON lines
        for raw in content.strip().split("\n"):
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            event_type = data.get("event_type") or ""
            msg = data.get("message") or ""
            if event_type == "user_message":
                messages.append({"role": "user", "content": msg})
            elif event_type == "agent_message":
                messages.append({"role": "assistant", "content": msg})
    return messages


async def get_run_log_messages(
    run_id: str,
    tenant_id: Optional[str] = None,
    within_days: Optional[int] = None,
    timeout: Optional[float] = None,
) -> list[dict[str, str]]:
    """Fetch run log entries for a scenario run and return parsed user/assistant messages.

    Args:
        run_id: Scenario run UUID.
        tenant_id: Optional tenant ID for the GraphQL request.
        within_days: Optional limit to logs within this many days.
        timeout: Optional request timeout in seconds.

    Returns:
        List of {"role": "user"|"assistant", "content": "..."} in chronological order.
    """
    variables: dict[str, Any] = {"runId": run_id}
    if within_days is not None:
        variables["withinDays"] = within_days

    try:
        result = await run_graphql(
            GET_SCENARIO_RUN_LOGS_QUERY,
            variables,
            tenant_id=tenant_id,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("Failed to fetch run log for run_id=%s: %s", run_id[:8] if run_id else "", e)
        return []

    data = result.get("getScenarioRunLogsByRunId")
    if not isinstance(data, list):
        return []

    return _parse_log_content_to_messages(data)


def get_recent_messages(
    messages: list[dict[str, str]],
    max_messages: int = 30,
    max_tokens: Optional[int] = 80000,
) -> list[dict[str, str]]:
    """Return a sliding window of the most recent messages, optionally capped by token estimate.

    Args:
        messages: Full list of {role, content} from get_run_log_messages.
        max_messages: Maximum number of messages to return (count of user + assistant turns).
        max_tokens: Optional cap; estimated as ~4 chars per token. Trim from front until under.

    Returns:
        Sublist of messages (most recent) suitable for agent context.
    """
    if not messages:
        return []
    window = messages[-max_messages:] if len(messages) > max_messages else messages
    if max_tokens is None or max_tokens <= 0:
        return window
    total_chars = sum(len(m.get("content", "")) for m in window)
    estimated_tokens = total_chars // 4
    while estimated_tokens > max_tokens and len(window) > 1:
        window = window[1:]
        total_chars = sum(len(m.get("content", "")) for m in window)
        estimated_tokens = total_chars // 4
    return window
