"""Workflow registry for managing and looking up workflows."""

import logging
from pathlib import Path
from typing import Optional

from app.core.base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """Registry for managing workflow definitions."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._workflows: dict[str, BaseWorkflow] = {}
    
    def register(self, workflow: BaseWorkflow) -> None:
        """Register a workflow.
        
        Args:
            workflow: Workflow instance to register
            
        Raises:
            ValueError: If workflow_id already exists
        """
        if workflow.workflow_id in self._workflows:
            raise ValueError(
                f"Workflow '{workflow.workflow_id}' already registered. "
                f"Existing: {self._workflows[workflow.workflow_id]}, "
                f"New: {workflow}"
            )
        
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.workflow_id} ({workflow.name})")
    
    def get(self, workflow_id: str) -> BaseWorkflow:
        """Get a workflow by ID.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            BaseWorkflow instance
            
        Raises:
            ValueError: If workflow_id not found
        """
        if workflow_id not in self._workflows:
            available = list(self._workflows.keys())
            raise ValueError(
                f"Workflow '{workflow_id}' not found in registry. "
                f"Available workflows: {available}"
            )
        return self._workflows[workflow_id]
    
    def has(self, workflow_id: str) -> bool:
        """Check if a workflow is registered.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if workflow exists, False otherwise
        """
        return workflow_id in self._workflows
    
    def all_workflows(self) -> list[BaseWorkflow]:
        """Get all registered workflows.
        
        Returns:
            List of all registered workflow instances
        """
        return list(self._workflows.values())
    
    def workflow_ids(self) -> list[str]:
        """Get all workflow IDs.
        
        Returns:
            List of all registered workflow IDs
        """
        return list(self._workflows.keys())
    
    def count(self) -> int:
        """Get the number of registered workflows.
        
        Returns:
            Number of registered workflows
        """
        return len(self._workflows)
    
    def load_from_directory(self, directory: str | Path) -> None:
        """Load workflows from a directory.
        
        This is a placeholder for future YAML-based workflow discovery.
        For now, workflows must be registered programmatically.
        
        Args:
            directory: Directory path (not used yet, reserved for future)
        """
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Workflow directory '{directory}' does not exist. Skipping.")
            return
        
        # TODO: Implement YAML-based workflow loading similar to agent registry
        # For now, this is a placeholder
        logger.info(f"Workflow directory scanning not yet implemented. Use register() to add workflows programmatically.")


