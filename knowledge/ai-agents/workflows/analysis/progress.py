"""Progress event emission for Levels 1 and 2."""

from typing import Optional, Dict, Any
from app.core.graphql_logger import ScenarioRunLogger


class AnalysisProgressTracker:
    """Emit Level 1 (phase) and Level 2 (task) progress events.

    4-Phase Model (matches frontend):
    1. planning_analysis - Fetching data and creating analysis plan
    2. executing_analysis - Running each analysis workstream
    3. planning_scenarios - Creating scenario plans for each analysis
    4. executing_scenarios - Running scenario executions
    """

    PHASES = [
        "planning_analysis",
        "executing_analysis",
        "planning_scenarios",
        "executing_scenarios"
    ]

    # User-friendly messages for each phase
    PHASE_MESSAGES = {
        "planning_analysis": "Planning analysis...",
        "executing_analysis": "Running analyses...",
        "planning_scenarios": "Planning scenarios...",
        "executing_scenarios": "Running scenarios..."
    }

    def __init__(self, logger: ScenarioRunLogger, agent_id: str = "analysis_workflow"):
        self.logger = logger
        self.agent_id = agent_id
        self.current_phase_index = 0

    # ==================
    # Level 1: Phase Events
    # ==================

    async def phase_started(self, phase_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Emit workflow_phase event for phase start."""
        self.current_phase_index = self.PHASES.index(phase_name) if phase_name in self.PHASES else self.current_phase_index

        message = self.PHASE_MESSAGES.get(phase_name, self._format_phase_name(phase_name))

        await self.logger.log_event(
            event_type="workflow_phase",
            message=message,
            agent_id=self.agent_id,
            metadata={
                "phase_index": self.current_phase_index + 1,
                "phase_total": len(self.PHASES),
                "phase_name": phase_name,
                "status": "started",
                **(metadata or {})
            }
        )

    async def phase_complete(self, phase_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Emit workflow_phase event for phase completion."""
        await self.logger.log_event(
            event_type="workflow_phase",
            message=self.PHASE_MESSAGES.get(phase_name, self._format_phase_name(phase_name)),
            agent_id=self.agent_id,
            metadata={
                "phase_index": self.current_phase_index + 1,
                "phase_total": len(self.PHASES),
                "phase_name": phase_name,
                "status": "completed",
                **(metadata or {})
            }
        )

    # ==================
    # Level 2: Task Events
    # ==================

    async def task_started(
        self,
        task_type: str,  # "analysis" or "scenario"
        task_id: str,
        task_index: int,
        task_total: int,
        title: str
    ):
        """Emit task_progress event for task start."""
        # User-friendly message without indices
        if task_type == "analysis":
            message = f"Analyzing: {title}"
        elif task_type == "scenario":
            message = f"Running scenario: {title}"
        else:
            message = f"{title}"

        await self.logger.log_event(
            event_type="task_progress",
            message=message,
            agent_id=self.agent_id,
            metadata={
                "task_type": task_type,
                "task_id": task_id,
                "task_index": task_index,
                "task_total": task_total,
                "title": title,
                "status": "running"
            }
        )

    async def task_complete(
        self,
        task_type: str,
        task_id: str,
        task_index: int,
        task_total: int,
        title: str,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Emit task_progress event for task completion."""
        status = "completed" if success else "failed"

        # User-friendly message
        if success:
            message = f"Completed: {title}"
        else:
            message = f"Failed: {title}"

        await self.logger.log_event(
            event_type="task_progress",
            message=message,
            agent_id=self.agent_id,
            metadata={
                "task_type": task_type,
                "task_id": task_id,
                "task_index": task_index,
                "task_total": task_total,
                "title": title,
                "status": status,
                "error": error
            }
        )

    def _format_phase_name(self, phase_name: str) -> str:
        """Convert phase_name to human-readable format."""
        return phase_name.replace("_", " ").title()
