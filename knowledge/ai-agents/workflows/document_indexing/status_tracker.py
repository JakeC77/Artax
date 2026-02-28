"""Status tracking for document processing workflows.

This module provides helper functions to update scratchpad attachment processing status
via GraphQL mutations. Status updates are non-blocking and failures are logged but
don't interrupt workflow execution.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)


async def update_attachment_status(
    scratchpad_attachment_id: str,
    tenant_id: str,
    processing_status: Optional[str] = None,
    processing_error: Optional[str] = None,
) -> None:
    """Update scratchpad attachment processing status via GraphQL mutation.

    This function is non-blocking - failures are logged but don't raise exceptions.
    This ensures status update failures don't interrupt workflow execution.

    Args:
        scratchpad_attachment_id: UUID of the scratchpad attachment to update
        tenant_id: Tenant ID for authentication
        processing_status: Optional processing status (e.g., "downloading-blob", "entity-extraction", "failed", "completed")
        processing_error: Optional error message (typically used with status="failed")

    Example:
        await update_attachment_status(
            scratchpad_attachment_id="0228c181-431e-4328-a4b6-d9bfa8b95974",
            tenant_id="tenant-123",
            processing_status="entity-extraction"
        )

        await update_attachment_status(
            scratchpad_attachment_id="0228c181-431e-4328-a4b6-d9bfa8b95974",
            tenant_id="tenant-123",
            processing_status="failed",
            processing_error="Invalid PDF: unable to extract text from page 3"
        )
    """
    if not scratchpad_attachment_id:
        logger.debug("Skipping status update: scratchpad_attachment_id is empty")
        return

    if not processing_status and not processing_error:
        logger.debug("Skipping status update: both processing_status and processing_error are None")
        return

    mutation = """
    mutation UpdateAttachmentStatus(
        $scratchpadAttachmentId: UUID!,
        $processingStatus: String,
        $processingError: String
    ) {
        updateScratchpadAttachment(
            scratchpadAttachmentId: $scratchpadAttachmentId,
            processingStatus: $processingStatus,
            processingError: $processingError
        )
    }
    """

    variables = {
        "scratchpadAttachmentId": scratchpad_attachment_id,
    }

    if processing_status is not None:
        variables["processingStatus"] = processing_status

    if processing_error is not None:
        variables["processingError"] = processing_error

    try:
        await run_graphql(mutation, variables, tenant_id=tenant_id)
        logger.debug(
            "Updated attachment status: attachment_id=%s status=%s error=%s",
            scratchpad_attachment_id[:8] if scratchpad_attachment_id else "",
            processing_status,
            "present" if processing_error else "none",
        )
    except Exception as e:
        # Log but don't raise - status updates shouldn't break workflow execution
        logger.warning(
            "Failed to update attachment status: attachment_id=%s status=%s error=%s: %s",
            scratchpad_attachment_id[:8] if scratchpad_attachment_id else "",
            processing_status,
            "present" if processing_error else "none",
            e,
            exc_info=True,
        )
