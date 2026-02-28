"""Entity-resolution workflow: re-run resolution only (expects Graphiti to have already run)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult

from app.workflows.document_indexing import storage
from app.workflows.document_indexing import entity_resolution_agent
from app.workflows.document_indexing.status_tracker import update_attachment_status

logger = logging.getLogger(__name__)

try:
    if getattr(__import__("app.config", fromlist=["Config"]).Config, "LOGFIRE_ENABLED", False):
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class EntityResolutionWorkflow(BaseWorkflow):
    """
    Entity-resolution workflow: query document subgraph for entities (with summary),
    reconcile each to the domain graph, upload resolved_entities.json.
    Expects Graphiti to have already run for this doc/tenant.
    Route by workflowId "entity-resolution".
    """

    def __init__(self):
        super().__init__(
            workflow_id="entity-resolution",
            name="Entity Resolution Workflow",
        )

    def _parse_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate and extract inputs (docId, tenantId, optional source, source_url, workspace_id, workspace_node_ids)."""
        doc_id = inputs.get("docId") or inputs.get("doc_id")
        tenant_id = inputs.get("tenantId") or inputs.get("tenant_id")
        source = inputs.get("source") or inputs.get("documentName") or inputs.get("filename") or "document"
        source_url = inputs.get("source_url") or inputs.get("sourceUrl") or inputs.get("documentUrl") or ""
        workspace_id = inputs.get("workspaceId") or inputs.get("workspace_id") or None
        workspace_node_ids = inputs.get("workspace_node_ids") or inputs.get("workspaceNodeIds") or None
        scratchpad_attachment_id = inputs.get("scratchpadAttachmentId") or inputs.get("scratchpad_attachment_id") or ""
        if not doc_id or not tenant_id:
            raise ValueError("inputs must contain docId and tenantId")
        return {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "source": source,
            "source_url": source_url,
            "workspace_id": workspace_id,
            "workspace_node_ids": workspace_node_ids,
            "scratchpad_attachment_id": scratchpad_attachment_id,
        }

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        start_time = datetime.utcnow()
        run_id = event.run_id or ""
        tenant_id = event.tenant_id or ""
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                "entity_resolution.execute",
                run_id=run_id,
                tenant_id=tenant_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            "Starting entity-resolution workflow run_id=%s tenant_id=%s",
            run_id[:8] if run_id else "",
            tenant_id[:8] if tenant_id else "",
        )

        try:
            inputs = self._parse_inputs(event.inputs_dict)
        except ValueError as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

        doc_id = inputs["doc_id"]
        tenant_id = inputs["tenant_id"]
        scratchpad_attachment_id = inputs.get("scratchpad_attachment_id", "")

        blob_client: Optional[Any] = None
        try:
            blob_client = storage.get_blob_service_client()
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Blob storage unavailable: {e}"
            if scratchpad_attachment_id:
                try:
                    await update_attachment_status(
                        scratchpad_attachment_id,
                        tenant_id,
                        processing_status="failed",
                        processing_error=error_msg,
                    )
                except Exception:
                    pass  # Don't let status update failure mask the original error
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )

        # Update status: assertion-mining (will be updated with progress during execution)
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="assertion-mining",
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        try:
            resolved_entities, path = await entity_resolution_agent.run_entity_resolution_only(
                tenant_id,
                doc_id,
                workspace_id=inputs.get("workspace_id"),
                workspace_node_ids=inputs.get("workspace_node_ids"),
                source=inputs.get("source", "document"),
                source_url=inputs.get("source_url", ""),
                blob_client=blob_client,
                scratchpad_attachment_id=scratchpad_attachment_id,
            )
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=f"Entity resolution failed: {e}",
                duration_seconds=duration,
            )

        duration = (datetime.utcnow() - start_time).total_seconds()
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:
                pass

        logger.info(
            "Entity-resolution completed docId=%s resolved_entities=%d path=%s in %.2fs",
            doc_id[:8] if doc_id else "",
            len(resolved_entities),
            path,
            duration,
        )
        # Update status to completed on successful workflow completion
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="completed",
                )
            except Exception:
                pass  # Don't let status update failure block workflow
        return WorkflowResult(
            run_id=run_id,
            workflow_id=self.workflow_id,
            success=True,
            result=f"docId={doc_id} resolved_entities={len(resolved_entities)} path={path}",
            duration_seconds=duration,
        )
