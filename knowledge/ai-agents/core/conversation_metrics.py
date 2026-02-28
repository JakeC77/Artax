"""Metrics tracking for conversations."""

import logging
from datetime import datetime
from typing import Dict
from threading import Lock

logger = logging.getLogger(__name__)


class ConversationMetrics:
    """Thread-safe metrics tracking for conversation management."""
    
    _lock = Lock()
    _active_conversations: int = 0
    _total_conversations: int = 0
    _completed_conversations: int = 0
    _failed_conversations: int = 0
    _max_concurrent: int = 0
    _total_duration_seconds: float = 0.0
    _durations: list[float] = []
    
    @classmethod
    def record_conversation_start(cls, run_id: str) -> None:
        """Record that a conversation has started.
        
        Args:
            run_id: Unique identifier for the conversation
        """
        with cls._lock:
            cls._active_conversations += 1
            cls._total_conversations += 1
            cls._max_concurrent = max(cls._max_concurrent, cls._active_conversations)
            logger.debug(
                f"Conversation started: {run_id}. "
                f"Active: {cls._active_conversations}, "
                f"Max concurrent: {cls._max_concurrent}"
            )
    
    @classmethod
    def record_conversation_end(
        cls, 
        run_id: str, 
        duration_seconds: float,
        success: bool = True
    ) -> None:
        """Record that a conversation has ended.
        
        Args:
            run_id: Unique identifier for the conversation
            duration_seconds: Duration of the conversation
            success: Whether the conversation completed successfully
        """
        with cls._lock:
            cls._active_conversations = max(0, cls._active_conversations - 1)
            if success:
                cls._completed_conversations += 1
            else:
                cls._failed_conversations += 1
            
            cls._total_duration_seconds += duration_seconds
            cls._durations.append(duration_seconds)
            
            # Keep only last 1000 durations to prevent memory growth
            if len(cls._durations) > 1000:
                cls._durations = cls._durations[-1000:]
            
            logger.debug(
                f"Conversation ended: {run_id}. "
                f"Duration: {duration_seconds:.1f}s, "
                f"Success: {success}, "
                f"Active: {cls._active_conversations}"
            )
    
    @classmethod
    def get_metrics(cls) -> Dict:
        """Get current metrics.
        
        Returns:
            Dictionary with current metrics
        """
        with cls._lock:
            avg_duration = 0.0
            if cls._durations:
                avg_duration = sum(cls._durations) / len(cls._durations)
            
            return {
                "active_conversations": cls._active_conversations,
                "total_conversations": cls._total_conversations,
                "completed_conversations": cls._completed_conversations,
                "failed_conversations": cls._failed_conversations,
                "max_concurrent": cls._max_concurrent,
                "average_duration_seconds": avg_duration,
                "total_duration_seconds": cls._total_duration_seconds,
            }
    
    @classmethod
    def reset(cls) -> None:
        """Reset all metrics (mainly for testing)."""
        with cls._lock:
            cls._active_conversations = 0
            cls._total_conversations = 0
            cls._completed_conversations = 0
            cls._failed_conversations = 0
            cls._max_concurrent = 0
            cls._total_duration_seconds = 0.0
            cls._durations = []



