"""Chunking: turn spans into LLM-sized chunks with span/locator metadata."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.workflows.document_indexing.models import Chunk, Span

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 6000
DEFAULT_OVERLAP = 0


def spans_to_chunks(
    spans: list[Span],
    max_chars: Optional[int] = None,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """
    Turn a list of spans into chunks suitable for LLM context.

    Concatenates spans in order; splits so no chunk exceeds max_chars.
    Each chunk records span_ids and locators so LLM mentions can be
    mapped back to span_id + locator for the index.

    Args:
        spans: List of spans from normalization.
        max_chars: Max characters per chunk (default 6000).
        overlap: Character overlap between consecutive chunks (default 0).

    Returns:
        List of Chunk with text, span_ids, and locators.
    """
    if not spans:
        return []

    limit = max_chars if max_chars is not None else DEFAULT_MAX_CHARS
    if limit <= 0:
        limit = DEFAULT_MAX_CHARS

    chunks: list[Chunk] = []
    current_text_parts: list[str] = []
    current_span_ids: list[str] = []
    current_locators: list[dict] = []
    current_len = 0

    for span in spans:
        text = span.text or ""
        if not text.strip():
            continue
        span_id = span.span_id
        locator_dict = span.locator.to_dict()

        # If adding this span would exceed limit, flush current chunk first
        if current_len + len(text) > limit and current_text_parts:
            chunk_id = str(uuid.uuid4())
            chunk_text = "\n\n".join(current_text_parts)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    span_ids=list(current_span_ids),
                    locators=list(current_locators),
                )
            )
            # Start new chunk with overlap from end of previous
            if overlap > 0 and chunk_text:
                overlap_text = chunk_text[-overlap:] if len(chunk_text) >= overlap else chunk_text
                current_text_parts = [overlap_text]
                current_span_ids = [current_span_ids[-1]] if current_span_ids else []
                current_locators = [current_locators[-1]] if current_locators else []
                current_len = len(overlap_text)
            else:
                current_text_parts = []
                current_span_ids = []
                current_locators = []
                current_len = 0

        current_text_parts.append(text)
        current_span_ids.append(span_id)
        current_locators.append(locator_dict)
        current_len = len("\n\n".join(current_text_parts))

    if current_text_parts:
        chunk_id = str(uuid.uuid4())
        chunk_text = "\n\n".join(current_text_parts)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                span_ids=list(current_span_ids),
                locators=list(current_locators),
            )
        )

    logger.debug("Chunked %d spans into %d chunks (max_chars=%d)", len(spans), len(chunks), limit)
    return chunks
