"""Python model for WorkflowEvent extending ScenarioRunCreatedEvent with workflow_id."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json


@dataclass
class WorkflowEvent:
    """Represents a workflow event from Service Bus with workflow routing.
    
    Extends ScenarioRunCreatedEvent with a workflow_id field for routing
    to different agentic workflows.
    
    This matches the C# record structure with additional WorkflowId field:
    public record WorkflowEvent
    {
        public Guid TenantId { get; init; }
        public Guid WorkspaceId { get; init; }
        public Guid ScenarioId { get; init; }
        public Guid RunId { get; init; }
        public Guid? RelatedChangesetId { get; init; }
        public string Engine { get; init; } = "";
        public string Inputs { get; init; } = "{}";
        public string? Prompt { get; init; }
        public string Status { get; init; } = "queued";
        public DateTimeOffset RequestedAt { get; init; } = DateTimeOffset.UtcNow;
        public string WorkflowId { get; init; } = "";  // New field for routing
    }
    """
    
    tenant_id: str
    workspace_id: str
    scenario_id: str
    run_id: str
    workflow_id: str  # New field for routing to workflows
    related_changeset_id: Optional[str] = None
    engine: str = ""
    inputs: str = "{}"
    prompt: Optional[str] = None
    status: str = "queued"
    requested_at: datetime = None
    
    def __post_init__(self):
        """Parse inputs JSON and handle requested_at."""
        if self.requested_at is None:
            self.requested_at = datetime.utcnow()
        elif isinstance(self.requested_at, str):
            # Parse ISO format datetime string
            try:
                self.requested_at = datetime.fromisoformat(self.requested_at.replace('Z', '+00:00'))
            except ValueError:
                self.requested_at = datetime.utcnow()
    
    @property
    def inputs_dict(self) -> dict:
        """Parse inputs JSON string to dict."""
        try:
            return json.loads(self.inputs) if self.inputs else {}
        except json.JSONDecodeError:
            return {}
    
    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowEvent":
        """Create event from JSON string.
        
        If workflow_id is missing from the payload, it defaults to "workspace-chat".
        
        Raises:
            ValueError: If required fields (run_id, tenant_id, workspace_id, scenario_id) are missing
        """
        data = json.loads(json_str)
        
        # Extract required fields with validation
        run_id = data.get("runId") or data.get("run_id")
        tenant_id = data.get("tenantId") or data.get("tenant_id")
        workspace_id = data.get("workspaceId") or data.get("workspace_id")
        scenario_id = data.get("scenarioId") or data.get("scenario_id")
        workflow_id = data.get("workflowId") or data.get("workflow_id") or data.get("ai_workflow_id", "")
        
        # Default workflow_id to "workspace-chat" if missing
        if not workflow_id:
            workflow_id = "workspace-chat"
        
        # Validate required fields
        if not run_id:
            raise ValueError("RunId is required but missing from event data")
        if not tenant_id:
            raise ValueError("TenantId is required but missing from event data")
        if not workspace_id:
            raise ValueError("WorkspaceId is required but missing from event data")
        if not scenario_id:
            raise ValueError("ScenarioId is required but missing from event data")
        
        return cls(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            run_id=run_id,
            workflow_id=workflow_id,
            related_changeset_id=data.get("RelatedChangesetId") or data.get("related_changeset_id"),
            engine=data.get("Engine") or data.get("engine", ""),
            inputs=data.get("Inputs") or data.get("inputs", "{}"),
            prompt=data.get("Prompt") or data.get("prompt"),
            status=data.get("Status") or data.get("status", "queued"),
            requested_at=data.get("RequestedAt") or data.get("requested_at"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "scenario_id": self.scenario_id,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "related_changeset_id": self.related_changeset_id,
            "engine": self.engine,
            "inputs": self.inputs,
            "prompt": self.prompt,
            "status": self.status,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
        }


