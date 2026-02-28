"""Data models for document indexing workflows (spans, locators, semantic entities, chunks)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Locator:
    """Addressable location within a document (page, slide, sheet, etc.)."""

    type: str  # pdf | pptx | xlsx | docx | image
    page: Optional[int] = None
    block: Optional[int] = None
    bbox: Optional[list[float]] = None
    slide: Optional[int] = None
    shape_id: Optional[str] = None
    sheet: Optional[str] = None
    row: Optional[int] = None
    column: Optional[int] = None
    a1: Optional[str] = None
    section: Optional[str] = None
    paragraph_index: Optional[int] = None
    line_index: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type}
        if self.page is not None:
            out["page"] = self.page
        if self.block is not None:
            out["block"] = self.block
        if self.bbox is not None:
            out["bbox"] = self.bbox
        if self.slide is not None:
            out["slide"] = self.slide
        if self.shape_id is not None:
            out["shapeId"] = self.shape_id
        if self.sheet is not None:
            out["sheet"] = self.sheet
        if self.row is not None:
            out["row"] = self.row
        if self.column is not None:
            out["column"] = self.column
        if self.a1 is not None:
            out["a1"] = self.a1
        if self.section is not None:
            out["section"] = self.section
        if self.paragraph_index is not None:
            out["paragraphIndex"] = self.paragraph_index
        if self.line_index is not None:
            out["lineIndex"] = self.line_index
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Locator:
        return cls(
            type=d.get("type", "pdf"),
            page=d.get("page"),
            block=d.get("block"),
            bbox=d.get("bbox"),
            slide=d.get("slide"),
            shape_id=d.get("shapeId"),
            sheet=d.get("sheet"),
            row=d.get("row"),
            column=d.get("column"),
            a1=d.get("a1"),
            section=d.get("section"),
            paragraph_index=d.get("paragraphIndex"),
            line_index=d.get("lineIndex"),
        )


@dataclass
class Span:
    """Smallest addressable unit of meaning; references a locator."""

    span_id: str
    doc_id: str
    tenant_id: str
    text: str
    locator: Locator

    def to_dict(self) -> dict[str, Any]:
        return {
            "spanId": self.span_id,
            "docId": self.doc_id,
            "tenantId": self.tenant_id,
            "text": self.text,
            "locator": self.locator.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Span:
        loc = d.get("locator", {})
        if isinstance(loc, dict):
            locator = Locator.from_dict(loc)
        else:
            locator = loc
        return cls(
            span_id=d.get("spanId", str(uuid.uuid4())),
            doc_id=d["docId"],
            tenant_id=d["tenantId"],
            text=d.get("text", ""),
            locator=locator,
        )


@dataclass
class SemanticEntityField:
    """Field on a semantic entity (from semanticEntities query)."""

    name: str
    data_type: Optional[str] = None
    description: Optional[str] = None
    range_info: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SemanticEntityField:
        return cls(
            name=d.get("name", ""),
            data_type=d.get("dataType", d.get("data_type")),
            description=d.get("description"),
            range_info=d.get("rangeInfo", d.get("range_info")),
        )


@dataclass
class SemanticEntity:
    """Entity from semanticEntities GraphQL query (name, nodeLabel, fields, etc.)."""

    semantic_entity_id: str
    node_label: str
    name: str
    description: Optional[str] = None
    created_on: Optional[str] = None
    fields: list[SemanticEntityField] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SemanticEntity:
        raw_fields = d.get("fields") or []
        fields = [
            SemanticEntityField.from_dict(f) if isinstance(f, dict) else f
            for f in raw_fields
        ]
        return cls(
            semantic_entity_id=d.get("semanticEntityId", d.get("semantic_entity_id", "")),
            node_label=d.get("nodeLabel", d.get("node_label", "")),
            name=d.get("name", ""),
            description=d.get("description"),
            created_on=d.get("createdOn", d.get("created_on")),
            fields=fields,
        )


@dataclass
class Chunk:
    """A chunk of document text for LLM processing; tracks source span(s) for references."""

    chunk_id: str
    text: str
    span_ids: list[str] = field(default_factory=list)
    locators: list[dict[str, Any]] = field(default_factory=list)

    def primary_span_id(self) -> str:
        """Span ID to use for mention references (first span in chunk)."""
        return self.span_ids[0] if self.span_ids else ""

    def primary_locator(self) -> dict[str, Any]:
        """Locator to use for mention references (first span's locator)."""
        return self.locators[0] if self.locators else {}


@dataclass
class DocMeta:
    """Metadata for a processed document."""

    doc_id: str
    tenant_id: str
    content_type: str
    blob_uri: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None
    span_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "docId": self.doc_id,
            "tenantId": self.tenant_id,
            "contentType": self.content_type,
            "spanCount": self.span_count,
        }
        if self.blob_uri is not None:
            d["blobUri"] = self.blob_uri
        if self.uploaded_by is not None:
            d["uploadedBy"] = self.uploaded_by
        if self.uploaded_at is not None:
            d["uploadedAt"] = self.uploaded_at
        return d


def spans_to_jsonl(spans: list[Span]) -> str:
    """Serialize spans to JSONL (one JSON object per line)."""
    return "\n".join(json.dumps(s.to_dict()) for s in spans)


