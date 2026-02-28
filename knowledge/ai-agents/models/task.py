"""Task decomposition and activity tracking models."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4


class Subtask(BaseModel):
    """A decomposed subtask to be executed by an agent."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    agent_id: str
    depends_on: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: str | None = None


class Task(BaseModel):
    """Main task submitted by user."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    subtasks: list[Subtask] = Field(default_factory=list)
    final_result: str | None = None


class ActivityEvent(BaseModel):
    """Real-time activity event for streaming."""
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: Literal[
        "task_received",
        "task_decomposed",
        "subtask_assigned",
        "agent_started",
        "agent_thinking",
        "tool_called",
        "agent_completed",
        "synthesis_started",
        "task_completed",
        # Feedback events
        "feedback_requested",
        "feedback_received",
        "feedback_applied",
        "feedback_timeout",
        # User message events
        "user_message",
    ]
    agent_id: str | None = None
    message: str
    task_id: str | None = None
    metadata: dict = Field(default_factory=dict)


