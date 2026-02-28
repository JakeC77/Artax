"""Azure Blob Storage client for document indexing (raw + processed)."""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any, Optional

from app.config import Config
from app.workflows.document_indexing.models import DocMeta, Span, spans_to_jsonl

logger = logging.getLogger(__name__)

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    _BLOB_AVAILABLE = True
except ImportError:
    _BLOB_AVAILABLE = False
    BlobServiceClient = None
    DefaultAzureCredential = None


def get_blob_service_client() -> "BlobServiceClient":
    """Get Azure Blob Storage client (connection string or account name + credential)."""
    if not _BLOB_AVAILABLE:
        raise ImportError(
            "azure-storage-blob is required for document indexing. "
            "Install with: pip install azure-storage-blob"
        )
    conn_str = Config.AZURE_STORAGE_CONNECTION_STRING
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)
    account_name = Config.AZURE_STORAGE_ACCOUNT_NAME
    if account_name:
        credential = DefaultAzureCredential(
            exclude_workload_identity_credential=True,
            exclude_developer_cli_credential=True,
            exclude_powershell_credential=True,
            exclude_visual_studio_code_credential=True,
            exclude_shared_token_cache_credential=True,
        )
        account_url = f"https://{account_name}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=credential)
    raise ValueError(
        "Document indexing requires Azure Blob: set AZURE_STORAGE_CONNECTION_STRING "
        "or AZURE_STORAGE_ACCOUNT_NAME (with azure-identity)."
    )


def raw_blob_path(tenant_id: str, doc_id: str, filename: str) -> str:
    """Path for raw blob: raw/{tenantId}/{docId}/final/{filename}."""
    return f"raw/{tenant_id}/{doc_id}/final/{filename}"


def processed_prefix(tenant_id: str, doc_id: str) -> str:
    """Prefix for processed artifacts: processed/{tenantId}/{docId}/."""
    return f"processed/{tenant_id}/{doc_id}/"


# Agent note guardrails (same container as processed blobs)
AGENT_NOTE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
AGENT_NOTE_MAX_BYTES = 256 * 1024  # 256 KB per note


def download_raw_blob(
    tenant_id: str,
    doc_id: str,
    filename: str,
    blob_service: Optional["BlobServiceClient"] = None,
    blob_path: Optional[str] = None,
) -> bytes:
    """Download raw document bytes from blob. Use blob_path if provided (relative to raw container)."""
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_RAW_CONTAINER)
    if blob_path:
        path = blob_path.lstrip("/")
    else:
        path = raw_blob_path(tenant_id, doc_id, filename)
    blob = container.get_blob_client(path)
    return blob.download_blob().readall()


def ensure_processed_container(blob_service: Optional["BlobServiceClient"] = None) -> None:
    """Ensure processed container exists."""
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    try:
        container.get_container_properties()
    except Exception:
        container.create_container()
        logger.info("Created container %s", Config.DOCUMENT_PROCESSED_CONTAINER)


def upload_spans(
    tenant_id: str,
    doc_id: str,
    spans: list[Span],
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload spans.jsonl to processed/{tenantId}/{docId}/spans.jsonl. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}spans.jsonl"
    content = spans_to_jsonl(spans)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s (%d spans)", path, len(spans))
    return path


def upload_meta(
    tenant_id: str,
    doc_id: str,
    meta: DocMeta,
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload meta.json to processed/{tenantId}/{docId}/meta.json. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}meta.json"
    content = json.dumps(meta.to_dict(), indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s", path)
    return path


def upload_index(
    tenant_id: str,
    doc_id: str,
    index_entries: list[dict[str, Any]],
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload index.json (list of index entries) to processed/{tenantId}/{docId}/index.json. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}index.json"
    content = json.dumps(index_entries, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s (%d entries)", path, len(index_entries))
    return path


def upload_status(
    tenant_id: str,
    doc_id: str,
    status: str,
    error_message: Optional[str] = None,
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload status.json (processing | completed | failed). Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}status.json"
    payload: dict[str, Any] = {"status": status}
    if error_message:
        payload["error"] = error_message
    content = json.dumps(payload, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    return path


def upload_assertions(
    tenant_id: str,
    doc_id: str,
    assertions: list[dict[str, Any]],
    *,
    source: str = "",
    source_url: str = "",
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload assertions.json (mined assertions, document-side only) to processed/{tenantId}/{docId}/assertions.json. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}assertions.json"
    content = json.dumps(assertions, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s (%d assertions)", path, len(assertions))
    return path


def read_assertions(
    tenant_id: str,
    doc_id: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> list[dict[str, Any]]:
    """Read assertions.json from processed/{tenantId}/{docId}/assertions.json. Returns list of assertion dicts, or [] if not found."""
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}assertions.json"
    blob = container.get_blob_client(path)
    try:
        raw = blob.download_blob().readall()
    except Exception:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def write_agent_note(
    tenant_id: str,
    doc_id: str,
    key: str,
    content: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> dict[str, Any]:
    """
    Write an agent working-memory note to blob: processed/{tenantId}/{docId}/notes/{key}.json.

    Guardrails: key must match [a-zA-Z0-9_-]{1,64}; content max 256 KB. Returns {"ok": True, "path": str}
    or {"ok": False, "error": str}.
    """
    if not key or not AGENT_NOTE_KEY_PATTERN.match(key):
        return {"ok": False, "error": "key must be 1–64 chars, alphanumeric, underscore, or hyphen only"}
    raw = content.encode("utf-8")
    if len(raw) > AGENT_NOTE_MAX_BYTES:
        return {"ok": False, "error": f"content exceeds max size ({AGENT_NOTE_MAX_BYTES} bytes)"}
    try:
        ensure_processed_container(blob_service)
        client = blob_service or get_blob_service_client()
        container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
        path = f"{processed_prefix(tenant_id, doc_id)}notes/{key}.json"
        payload = {"content": content}
        blob = container.get_blob_client(path)
        blob.upload_blob(json.dumps(payload).encode("utf-8"), overwrite=True)
        logger.debug("Wrote agent note %s (%d bytes)", path, len(raw))
        return {"ok": True, "path": path}
    except Exception as e:
        logger.warning("write_agent_note failed: %s", e)
        return {"ok": False, "error": str(e)}


def read_agent_note(
    tenant_id: str,
    doc_id: str,
    key: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> dict[str, Any]:
    """
    Read an agent working-memory note from blob: processed/{tenantId}/{docId}/notes/{key}.json.

    Guardrails: key must match [a-zA-Z0-9_-]{1,64}. Returns {"ok": True, "content": str} or
    {"ok": False, "error": str} (e.g. not found or invalid key).
    """
    if not key or not AGENT_NOTE_KEY_PATTERN.match(key):
        return {"ok": False, "error": "key must be 1–64 chars, alphanumeric, underscore, or hyphen only"}
    try:
        client = blob_service or get_blob_service_client()
        container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
        path = f"{processed_prefix(tenant_id, doc_id)}notes/{key}.json"
        blob = container.get_blob_client(path)
        raw = blob.download_blob().readall()
    except Exception:
        return {"ok": False, "error": "note not found or unreadable"}
    try:
        data = json.loads(raw.decode("utf-8"))
        content = data.get("content") if isinstance(data, dict) else None
        if content is None:
            return {"ok": False, "error": "invalid note format"}
        return {"ok": True, "content": content}
    except Exception:
        return {"ok": False, "error": "invalid note format"}


def upload_resolved_entities(
    tenant_id: str,
    doc_id: str,
    entities: list[dict[str, Any]],
    *,
    source: str = "",
    source_url: str = "",
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload resolved_entities.json (list of document entities + reconciled domain_node_id) to processed/{tenantId}/{docId}/resolved_entities.json. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}resolved_entities.json"
    payload: dict[str, Any] = {"entities": entities}
    if source:
        payload["source"] = source
    if source_url:
        payload["source_url"] = source_url
    content = json.dumps(payload, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s (%d entities)", path, len(entities))
    return path


def read_resolved_entities(
    tenant_id: str,
    doc_id: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> list[dict[str, Any]]:
    """Read resolved_entities.json from processed/{tenantId}/{docId}/resolved_entities.json. Returns list of entity dicts, or [] if not found."""
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}resolved_entities.json"
    blob = container.get_blob_client(path)
    try:
        raw = blob.download_blob().readall()
    except Exception:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    if isinstance(data, dict) and "entities" in data:
        return data["entities"] if isinstance(data["entities"], list) else []
    return data if isinstance(data, list) else []


def upload_entity_resolution(
    tenant_id: str,
    doc_id: str,
    assertions: list[dict[str, Any]],
    *,
    source: str = "",
    source_url: str = "",
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """Upload entity_resolution.json (list of assertion records) to processed/{tenantId}/{docId}/entity_resolution.json. Returns blob path."""
    ensure_processed_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = f"{processed_prefix(tenant_id, doc_id)}entity_resolution.json"
    content = json.dumps(assertions, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.debug("Uploaded %s (%d assertions)", path, len(assertions))
    return path


def read_blob(
    container_name: str,
    blob_path: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> bytes:
    """Read blob bytes (generic)."""
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(container_name)
    blob = container.get_blob_client(blob_path)
    return blob.download_blob().readall()
