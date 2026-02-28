"""Document-graphiti workflow: normalize -> ingest into Graphiti knowledge graph."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult

from app.workflows.document_indexing import storage
from app.workflows.document_indexing import normalization
from app.workflows.document_indexing import chunking
from app.config import Config
from app.workflows.document_indexing import graphiti_ingest
from app.workflows.document_indexing.status_tracker import update_attachment_status
from app.workflows.document_indexing.config import load_config

logger = logging.getLogger(__name__)

try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class DocumentGraphitiWorkflow(BaseWorkflow):
    """
    Document-graphiti workflow: download document from blob, normalize to spans,
    then ingest into Graphiti knowledge graph (Neo4j) as episodes.
    Same event shape as document-indexing; route by workflowId "document-graphiti".
    """

    def __init__(self):
        super().__init__(
            workflow_id="document-graphiti",
            name="Document Graphiti Workflow",
        )

    def _parse_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate and extract required inputs (same as document-indexing). Optional source, source_url, workspace_id, workspace_node_ids for entity resolution."""
        doc_id = inputs.get("docId") or inputs.get("doc_id")
        tenant_id = inputs.get("tenantId") or inputs.get("tenant_id")
        blob_path = inputs.get("blobPath") or inputs.get("blob_uri") or inputs.get("blobUri")
        content_type = inputs.get("contentType") or inputs.get("content_type") or ""
        filename = inputs.get("filename") or ""
        source = inputs.get("source") or inputs.get("documentName") or ""
        source_url = inputs.get("source_url") or inputs.get("sourceUrl") or inputs.get("documentUrl") or ""
        workspace_id = inputs.get("workspaceId") or inputs.get("workspace_id") or ""
        workspace_node_ids = inputs.get("workspace_node_ids") or inputs.get("workspaceNodeIds") or None
        scratchpad_attachment_id = inputs.get("scratchpadAttachmentId") or inputs.get("scratchpad_attachment_id") or ""
        if not doc_id or not tenant_id:
            raise ValueError("inputs must contain docId and tenantId")
        if not blob_path and not filename:
            raise ValueError("inputs must contain blobPath (or blobUri) or filename")
        if not filename and blob_path:
            parts = blob_path.replace("\\", "/").strip("/").split("/")
            filename = parts[-1] if len(parts) >= 1 else "document"
        if not filename:
            filename = "document"
        if not source:
            source = filename
        return {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "blob_path": blob_path or f"raw/{tenant_id}/{doc_id}/final/{filename}",
            "content_type": content_type,
            "filename": filename,
            "source": source,
            "source_url": source_url,
            "workspace_id": workspace_id or None,
            "workspace_node_ids": workspace_node_ids,
            "scratchpad_attachment_id": scratchpad_attachment_id,
        }

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        start_time = datetime.utcnow()
        run_id = event.run_id or ""
        tenant_id = event.tenant_id or ""

        if logfire:
            span_ctx = logfire.span(
                "document_graphiti.execute",
                run_id=run_id,
                tenant_id=tenant_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            "Starting document-graphiti workflow run_id=%s tenant_id=%s",
            run_id[:8] if run_id else "",
            tenant_id[:8] if tenant_id else "",
        )

        try:
            inputs = self._parse_inputs(event.inputs_dict)
        except ValueError as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            # Try to update status if we have scratchpad_attachment_id from event inputs
            scratchpad_attachment_id = event.inputs_dict.get("scratchpadAttachmentId") or event.inputs_dict.get("scratchpad_attachment_id") or ""
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

        doc_id = inputs["doc_id"]
        tenant_id = inputs["tenant_id"]
        filename = inputs["filename"]
        content_type = inputs["content_type"]
        blob_path = inputs["blob_path"]
        scratchpad_attachment_id = inputs.get("scratchpad_attachment_id", "")

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

        # Update status: downloading blob
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="downloading-blob",
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        try:
            raw_bytes = storage.download_raw_blob(
                tenant_id, doc_id, filename, blob_client, blob_path=blob_path
            )
            logger.info(
                "Downloaded blob: doc_id=%s filename=%s size=%d bytes",
                doc_id[:8] if doc_id else "",
                filename,
                len(raw_bytes),
            )
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Failed to download raw blob: {e}"
            logger.error(error_msg, exc_info=True)
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

        # Update status: chunking/normalizing
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="chunking/normalizing",
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        try:
            spans = normalization.normalize_to_spans(
                raw_bytes,
                doc_id,
                tenant_id,
                filename=filename,
                content_type=content_type or None,
            )
        except normalization.UnsupportedFileTypeError as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Unsupported file type: {e}"
            logger.error(error_msg)
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
        except normalization.NormalizationError as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Normalization failed: {e}"
            logger.error(error_msg, exc_info=True)
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
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Unexpected error during normalization: {e}"
            logger.error(error_msg, exc_info=True)
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
        
        if not spans:
            duration = (datetime.utcnow() - start_time).total_seconds()
            # Update status to completed even if no spans extracted
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
                result=f"docId={doc_id} spans=0 episodes=0 (no content extracted)",
                duration_seconds=duration,
            )

        # Estimate episode count from spans (will be chunked for Graphiti)
        estimated_episode_count = 0
        if scratchpad_attachment_id:
            try:
                workflow_config = load_config()
                default_max_chars = getattr(Config, "DOCUMENT_INDEXING_CHUNK_MAX_CHARS", None) or workflow_config.chunk_max_chars
                chunks = chunking.spans_to_chunks(spans, max_chars=default_max_chars)
                estimated_episode_count = len(chunks)
            except Exception:
                # If chunking fails, estimate from spans
                estimated_episode_count = len(spans)

        # Update status: entity extraction (with episode count)
        if scratchpad_attachment_id:
            try:
                status_msg = "entity-extraction"
                if estimated_episode_count > 0:
                    status_msg = f"entity-extraction ({estimated_episode_count} episodes)"
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status=status_msg,
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        try:
            episode_count = await graphiti_ingest.ingest_document_into_graphiti(
                tenant_id, doc_id, spans
            )
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Graphiti ingest failed: {e}"
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

        # Update status: entities extracted (after Graphiti extraction, before assertion mining)
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="entities-extracted",
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        # Entity resolution (chained): run after successful Graphiti ingest
        # Update status: assertion-mining (before starting assertion mining)
        if scratchpad_attachment_id:
            try:
                await update_attachment_status(
                    scratchpad_attachment_id,
                    tenant_id,
                    processing_status="assertion-mining",
                )
            except Exception:
                pass  # Don't let status update failure block workflow

        resolution_path = ""
        try:
            from app.workflows.document_indexing import entity_resolution_agent

            _, resolution_path = await entity_resolution_agent.run_entity_resolution(
                tenant_id,
                doc_id,
                workspace_id=inputs.get("workspace_id"),
                workspace_node_ids=inputs.get("workspace_node_ids"),
                source=inputs.get("source", filename),
                source_url=inputs.get("source_url", ""),
                blob_client=blob_client,
                scratchpad_attachment_id=scratchpad_attachment_id,
            )
            logger.info(
                "Resolved entities completed docId=%s path=%s",
                doc_id[:8] if doc_id else "",
                resolution_path,
            )
        except Exception as e:
            logger.warning(
                "Resolved entities failed (ingest succeeded) docId=%s: %s",
                doc_id[:8] if doc_id else "",
                e,
                exc_info=True,
            )
            # Ingest succeeded; report resolution failure in result but do not fail the workflow
            resolution_path = f"(resolution failed: {e})"
            # Update status with resolution failure (but workflow still succeeds)
            if scratchpad_attachment_id:
                try:
                    await update_attachment_status(
                        scratchpad_attachment_id,
                        tenant_id,
                        processing_status="failed",
                        processing_error=f"Entity resolution failed: {e}",
                    )
                except Exception:
                    pass  # Don't let status update failure block workflow

        duration = (datetime.utcnow() - start_time).total_seconds()
        if logfire:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:
                pass

        result_msg = f"docId={doc_id} spans={len(spans)} episodes={episode_count}"
        if resolution_path and not resolution_path.startswith("("):
            result_msg += f" resolution={resolution_path}"
        logger.info(
            "Document-graphiti completed docId=%s spans=%d episodes=%d in %.2fs",
            doc_id[:8] if doc_id else "",
            len(spans),
            episode_count,
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
            result=result_msg,
            duration_seconds=duration,
        )
