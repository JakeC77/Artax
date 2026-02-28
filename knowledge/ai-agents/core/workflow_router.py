"""Workflow router for routing events to appropriate workflows."""

import logging
from datetime import datetime

from app.models.workflow_event import WorkflowEvent
from app.core.workflow_registry import WorkflowRegistry
from app.core.base_workflow import BaseWorkflow, WorkflowResult

logger = logging.getLogger(__name__)


class WorkflowRouter:
    """Routes events to appropriate workflows based on workflow_id."""
    
    def __init__(self, registry: WorkflowRegistry):
        """Initialize router with workflow registry.
        
        Args:
            registry: WorkflowRegistry containing all registered workflows
        """
        self.registry = registry
        self._routing_metrics = {
            "total_routed": 0,
            "successful_routes": 0,
            "failed_routes": 0,
            "unknown_workflow": 0,
        }
    
    async def route(self, event: WorkflowEvent) -> WorkflowResult:
        """Route an event to the appropriate workflow.
        
        Args:
            event: WorkflowEvent to route
            
        Returns:
            WorkflowResult with execution details
            
        Raises:
            ValueError: If workflow_id is not found in registry
        """
        workflow_id = event.workflow_id
        start_time = datetime.utcnow()
        
        self._routing_metrics["total_routed"] += 1
        
        logger.info(
            f"Routing event run_id={event.run_id} to workflow_id={workflow_id}"
        )
        
        # Check if workflow exists
        if not self.registry.has(workflow_id):
            self._routing_metrics["unknown_workflow"] += 1
            error_msg = (
                f"Unknown workflow_id '{workflow_id}' for run_id={event.run_id}. "
                f"Available workflows: {self.registry.workflow_ids()}"
            )
            logger.error(error_msg)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            return WorkflowResult(
                run_id=event.run_id,
                workflow_id=workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )
        
        # Get workflow and execute
        try:
            workflow: BaseWorkflow = self.registry.get(workflow_id)
            logger.debug(f"Executing workflow: {workflow}")
            
            result = await workflow.execute(event)
            
            if result.success:
                self._routing_metrics["successful_routes"] += 1
                logger.info(
                    f"Workflow {workflow_id} completed successfully for run_id={event.run_id}"
                )
            else:
                self._routing_metrics["failed_routes"] += 1
                logger.warning(
                    f"Workflow {workflow_id} failed for run_id={event.run_id}: {result.error}"
                )
            
            return result
            
        except Exception as e:
            self._routing_metrics["failed_routes"] += 1
            error_msg = f"Error executing workflow {workflow_id}: {str(e)}"
            logger.exception(error_msg)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            return WorkflowResult(
                run_id=event.run_id,
                workflow_id=workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )
    
    def get_metrics(self) -> dict:
        """Get routing metrics.
        
        Returns:
            Dictionary with routing statistics
        """
        return self._routing_metrics.copy()


