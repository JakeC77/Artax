"""Conversation context for isolated state per conversation."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ConversationContext:
    """Isolated state per conversation to prevent race conditions.
    
    Each conversation gets its own context instance, ensuring that
    concurrent conversations don't interfere with each other's state.
    """
    
    def __init__(self, run_id: str):
        """Initialize conversation context.
        
        Args:
            run_id: Unique identifier for this conversation
        """
        self.run_id = run_id
        self.waiting_for_feedback: bool = False
        self.workflow_results: list[str] = []
        self.conversation_history: list[str] = []
        self.created_at = datetime.utcnow()
        self.last_activity_at = datetime.utcnow()
        self.message_count = 0
        
    def add_message(self, message: str):
        """Add a message to conversation history."""
        self.conversation_history.append(message)
        self.message_count += 1
        self.last_activity_at = datetime.utcnow()
    
    def add_workflow_result(self, result: str):
        """Add a workflow result to the conversation context."""
        workflow_result_text = f"WORKFLOW RESULT\n\n{result}"
        if workflow_result_text not in self.workflow_results:
            self.workflow_results.append(workflow_result_text)
        # Also add to conversation history if not already present
        if workflow_result_text not in self.conversation_history:
            self.conversation_history.append(workflow_result_text)
        self.last_activity_at = datetime.utcnow()
    
    def get_enhanced_history(self) -> list[str]:
        """Get conversation history with workflow results included."""
        return list(self.conversation_history)
    
    def mark_waiting_for_feedback(self, waiting: bool = True):
        """Mark whether we're waiting for user feedback."""
        self.waiting_for_feedback = waiting
        if waiting:
            self.last_activity_at = datetime.utcnow()
    
    def get_idle_seconds(self) -> float:
        """Get seconds since last activity."""
        return (datetime.utcnow() - self.last_activity_at).total_seconds()
    
    def get_age_seconds(self) -> float:
        """Get seconds since conversation was created."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ConversationContext(run_id={self.run_id}, "
            f"messages={self.message_count}, "
            f"age={self.get_age_seconds():.1f}s, "
            f"idle={self.get_idle_seconds():.1f}s)"
        )



