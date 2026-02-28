"""Azure Blob Storage client for ontology drafts."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime

from app.config import Config
from app.workflows.ontology_creation.models import OntologyPackage

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
            "azure-storage-blob is required for ontology creation. "
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
        "Ontology creation requires Azure Blob: set AZURE_STORAGE_CONNECTION_STRING "
        "or AZURE_STORAGE_ACCOUNT_NAME (with azure-identity)."
    )


def ontology_draft_path(tenant_id: str, ontology_id: str) -> str:
    """Path for ontology draft: ontology-drafts/{tenantId}/{ontologyId}/draft.json."""
    return f"ontology-drafts/{tenant_id}/{ontology_id}/draft.json"


def conversation_summary_path(
    tenant_id: str,
    run_id: Optional[str] = None,
    ontology_id: Optional[str] = None,
) -> str:
    """Path for conversation summary blob. Key by run_id or ontology_id (one required)."""
    if run_id:
        return f"ontology-conversations/{tenant_id}/{run_id}/summary.json"
    if ontology_id:
        return f"ontology-drafts/{tenant_id}/{ontology_id}/conversation_summary.json"
    raise ValueError("conversation_summary_path requires run_id or ontology_id")


def ensure_ontology_container(blob_service: Optional["BlobServiceClient"] = None) -> None:
    """Ensure ontology drafts container exists."""
    client = blob_service or get_blob_service_client()
    container_name = Config.DOCUMENT_PROCESSED_CONTAINER  # Reuse same container as document indexing
    container = client.get_container_client(container_name)
    try:
        container.get_container_properties()
    except Exception:
        container.create_container()
        logger.info("Created container %s", container_name)


def save_ontology_draft(
    tenant_id: str,
    ontology_id: str,
    package: OntologyPackage,
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """
    Save ontology draft to blob storage.
    
    Args:
        tenant_id: Tenant ID
        ontology_id: Ontology ID (UUID)
        package: OntologyPackage to save
        blob_service: Optional blob service client
    
    Returns:
        Blob path where draft was saved
    """
    ensure_ontology_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = ontology_draft_path(tenant_id, ontology_id)
    
    # Convert package to dict and serialize
    content = json.dumps(package.to_dict(), indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    
    logger.info("Saved ontology draft: %s (version %s)", path, package.semantic_version)
    return path


def load_ontology_draft(
    tenant_id: str,
    ontology_id: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> Optional[OntologyPackage]:
    """
    Load ontology draft from blob storage.
    
    Args:
        tenant_id: Tenant ID
        ontology_id: Ontology ID (UUID)
        blob_service: Optional blob service client
    
    Returns:
        OntologyPackage if found, None otherwise
    """
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = ontology_draft_path(tenant_id, ontology_id)
    
    try:
        blob = container.get_blob_client(path)
        raw = blob.download_blob().readall()
        data = json.loads(raw.decode("utf-8"))
        
        # Parse datetime strings back to datetime objects
        if isinstance(data, dict):
            if "created_at" in data and isinstance(data["created_at"], str):
                data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            if "updated_at" in data and isinstance(data["updated_at"], str):
                data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            
            # Parse iteration history timestamps
            if "iteration_history" in data:
                for record in data["iteration_history"]:
                    if "timestamp" in record and isinstance(record["timestamp"], str):
                        record["timestamp"] = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
        
        package = OntologyPackage(**data)
        logger.info("Loaded ontology draft: %s (version %s)", path, package.semantic_version)
        return package
    except Exception as e:
        logger.warning("Failed to load ontology draft %s: %s", path, e)
        return None


def list_ontology_drafts(
    tenant_id: str,
    blob_service: Optional["BlobServiceClient"] = None,
) -> List[Dict[str, Any]]:
    """
    List all ontology drafts for a tenant.
    
    Args:
        tenant_id: Tenant ID
        blob_service: Optional blob service client
    
    Returns:
        List of draft metadata dicts with ontology_id, title, semantic_version, updated_at, finalized
    """
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    prefix = f"ontology-drafts/{tenant_id}/"
    
    drafts = []
    try:
        blobs = container.list_blobs(name_starts_with=prefix)
        for blob in blobs:
            if blob.name.endswith("/draft.json"):
                # Extract ontology_id from path
                parts = blob.name.split("/")
                if len(parts) >= 3:
                    ontology_id = parts[2]
                    
                    # Try to load the draft to get metadata
                    try:
                        package = load_ontology_draft(tenant_id, ontology_id, blob_service)
                        if package:
                            drafts.append({
                                "ontology_id": ontology_id,
                                "title": package.title,
                                "semantic_version": package.semantic_version,
                                "updated_at": package.updated_at.isoformat(),
                                "finalized": package.finalized,
                                "entity_count": len(package.entities),
                                "relationship_count": len(package.relationships)
                            })
                    except Exception as e:
                        logger.warning("Failed to load draft metadata for %s: %s", ontology_id, e)
                        # Fallback to blob metadata
                        drafts.append({
                            "ontology_id": ontology_id,
                            "title": "Unknown",
                            "semantic_version": "0.0.0",
                            "updated_at": blob.last_modified.isoformat() if blob.last_modified else "",
                            "finalized": False,
                            "entity_count": 0,
                            "relationship_count": 0
                        })
    except Exception as e:
        logger.warning("Failed to list ontology drafts: %s", e)
    
    # Sort by updated_at descending
    drafts.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return drafts


def save_conversation_summary(
    tenant_id: str,
    summary: str,
    message_count_at_summary: int,
    run_id: Optional[str] = None,
    ontology_id: Optional[str] = None,
    blob_service: Optional["BlobServiceClient"] = None,
) -> str:
    """
    Save conversation summary for ontology conversation resume (experimental).

    Args:
        tenant_id: Tenant ID
        summary: Narrative summary text
        message_count_at_summary: Number of messages when summary was generated
        run_id: Run ID to key by (use run_id or ontology_id, not both)
        ontology_id: Ontology ID to key by (alternative to run_id)
        blob_service: Optional blob service client

    Returns:
        Blob path where summary was saved
    """
    ensure_ontology_container(blob_service)
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = conversation_summary_path(tenant_id=tenant_id, run_id=run_id, ontology_id=ontology_id)
    now = datetime.utcnow()
    payload = {
        "summary": summary,
        "updated_at": now.isoformat() + "Z",
        "message_count_at_summary": message_count_at_summary,
    }
    content = json.dumps(payload, indent=2)
    blob = container.get_blob_client(path)
    blob.upload_blob(content.encode("utf-8"), overwrite=True)
    logger.info("Saved conversation summary: %s", path)
    return path


def load_conversation_summary(
    tenant_id: str,
    run_id: Optional[str] = None,
    ontology_id: Optional[str] = None,
    blob_service: Optional["BlobServiceClient"] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load conversation summary for ontology conversation resume (experimental).

    Args:
        tenant_id: Tenant ID
        run_id: Run ID to key by (use run_id or ontology_id, not both)
        ontology_id: Ontology ID to key by (alternative to run_id)
        blob_service: Optional blob service client

    Returns:
        Dict with summary, updated_at, message_count_at_summary or None if not found
    """
    client = blob_service or get_blob_service_client()
    container = client.get_container_client(Config.DOCUMENT_PROCESSED_CONTAINER)
    path = conversation_summary_path(tenant_id=tenant_id, run_id=run_id, ontology_id=ontology_id)
    try:
        blob = container.get_blob_client(path)
        raw = blob.download_blob().readall()
        data = json.loads(raw.decode("utf-8"))
        return data
    except Exception as e:
        logger.debug("No conversation summary at %s: %s", path, e)
        return None
