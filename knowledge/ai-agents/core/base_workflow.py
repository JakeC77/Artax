"""Base workflow interface for all workflow implementations."""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from app.models.workflow_event import WorkflowEvent


class WorkflowResult:
    """Result of workflow execution."""
    
    def __init__(
        self,
        run_id: str,
        workflow_id: str,
        success: bool,
        result: Optional[str] = None,
        error: Optional[str] = None,
        duration_seconds: float = 0.0,
    ):
        self.run_id = run_id
        self.workflow_id = workflow_id
        self.success = success
        self.result = result
        self.error = error
        self.duration_seconds = duration_seconds
        self.completed_at = datetime.utcnow()


class BaseWorkflow(ABC):
    """Abstract base class for all workflows.
    
    All workflows must implement the execute method to process events.
    """
    
    def __init__(self, workflow_id: str, name: str):
        """Initialize workflow.
        
        Args:
            workflow_id: Unique identifier for this workflow
            name: Human-readable name for this workflow
        """
        self.workflow_id = workflow_id
        self.name = name
    
    @abstractmethod
    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the workflow for the given event.
        
        Args:
            event: WorkflowEvent containing all event data
            
        Returns:
            WorkflowResult with execution details
            
        Raises:
            Exception: If workflow execution fails
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of workflow."""
        return f"<{self.__class__.__name__}(id={self.workflow_id}, name={self.name})>"


