# Document Indexing: Upload and Trigger Contract

This document describes the contract between the **other API** (that receives scratchpad attachments) and this **background worker** (geodesic-ai) for document processing.

## Upload and finalization (other API)

When a new scratchpad attachment is created/finalized, the other API should:

1. **Persist the file to Azure Blob Storage** using the finalization pattern:
   - **Path**: `raw/{tenantId}/{docId}/final/{filename}`
   - **docId** may be the `scratchpadAttachmentId` or a dedicated document ID.
   - **Metadata/tags** on the blob (or sidecar): `tenantId`, `docId`, `contentType`, `uploadedBy`, `uploadedAt`, and optionally `workspaceId`, `scratchpadAttachmentId`.

2. **Kick off the processing job** by enqueueing a message to **Azure Service Bus** (same queue this worker listens to). The message body must be a JSON-serialized **WorkflowEvent** with:
   - **workflowId**: `"document-indexing"`
   - **inputs**: JSON string (or object) containing at least:
     - `docId` (string, UUID)
     - `tenantId` (string, UUID)
     - `workspaceId` (string, UUID)
     - `scratchpadAttachmentId` (string, UUID)
     - `blobPath` or `blobUri` (string): path under raw container, e.g. `raw/{tenantId}/{docId}/final/{filename}`, or full blob URL
     - `contentType` (string, e.g. `application/pdf`)
     - `uploadedBy` (string, optional)
     - `uploadedAt` (string, ISO datetime, optional)
     - `filename` (string): filename for the blob (used to download from blob)

   Other standard WorkflowEvent fields: `tenantId`, `workspaceId`, `scenarioId`, `runId` must be set as usual (e.g. from the scenario run that triggered the attachment).

## Example Service Bus message (inputs)

```json
{
  "tenantId": "<uuid>",
  "workspaceId": "<uuid>",
  "scenarioId": "<uuid>",
  "runId": "<uuid>",
  "workflowId": "document-indexing",
  "inputs": "{\"docId\":\"<uuid>\",\"tenantId\":\"<uuid>\",\"workspaceId\":\"<uuid>\",\"scratchpadAttachmentId\":\"<uuid>\",\"blobPath\":\"raw/<tenantId>/<docId>/final/document.pdf\",\"contentType\":\"application/pdf\",\"filename\":\"document.pdf\",\"uploadedBy\":\"user@example.com\",\"uploadedAt\":\"2025-01-28T12:00:00Z\"}"
}
```

## Worker behavior

- The worker reads the raw file from blob at the given path (or derives path from `blobPath`/`blobUri` and container `DOCUMENT_RAW_CONTAINER`).
- It runs: normalization → fetch entity surface cache from **your API** → mention detection → index construction → **POST evidence** to your API.
- Your API is responsible for: providing the entity surface cache (GET) and performing graph write-back when it receives the evidence (POST).

## Config (worker)

- **Azure Blob**: `AZURE_STORAGE_CONNECTION_STRING` or `AZURE_STORAGE_ACCOUNT_NAME`; `DOCUMENT_RAW_CONTAINER`, `DOCUMENT_PROCESSED_CONTAINER`.
- **Document-indexing API**: `DOCUMENT_INDEXING_API_URL` (optional; defaults to base of `WORKSPACE_GRAPHQL_ENDPOINT`); `DOCUMENT_INDEXING_ENTITY_CACHE_PATH`, `DOCUMENT_INDEXING_EVIDENCE_PATH`; auth uses same GraphQL auth (scope, client secret or managed identity).

---

## Document-graphiti workflow (experimental)

A separate pipeline builds a **knowledge graph** from documents using [Graphiti](https://help.getzep.com/graphiti/getting-started/welcome) (Zep). Same event shape as document-indexing; you choose which pipeline runs by setting **workflowId** on the Service Bus message.

- **workflowId**: `"document-graphiti"` — runs end-to-end: download blob → normalize to spans → ingest into Graphiti (Neo4j) as episodes → **entity resolution** (ontology + document subgraph + LLM agent) → write `processed/{tenantId}/{docId}/entity_resolution.json`. Requires Neo4j, GraphQL (ontology), and an LLM configured for Graphiti and for the resolution agent.
- **workflowId**: `"document-indexing"` — runs the existing index + evidence pipeline (normalize → chunk → LLM mention extraction → index → evidence POST).

Optional inputs for document-graphiti (and entity resolution): `source` / `source_url` (document name and URL for provenance), `workspaceId` / `workspace_node_ids` (for domain-graph Cypher scoping when resolving entities).

**Config (document-graphiti):** `GRAPHITI_ENABLED=true`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`. LLM: set `GOOGLE_API_KEY` or `GEMINI_API_KEY` to use Gemini (requires `graphiti-core[google-genai]`); otherwise Graphiti uses OpenAI (`OPENAI_API_KEY`). Optional: `GRAPHITI_GEMINI_MODEL`, `GRAPHITI_GEMINI_EMBEDDING_MODEL`, `GRAPHITI_GEMINI_RERANKER_MODEL`; `SEMAPHORE_LIMIT` for concurrency. Entity resolution uses the same Neo4j and GraphQL; optional `ENTITY_RESOLUTION_MODEL` or `DOCUMENT_INDEXING_LLM_MODEL` for the resolution agent.

---

## Entity-resolution workflow (standalone)

To **re-run entity resolution only** (e.g. after ontology or domain graph changes), send a message with **workflowId**: `"entity-resolution"`. Graphiti must have already run for that doc/tenant so the document subgraph exists in Neo4j.

- **inputs**: `docId`, `tenantId` (required); optional `source`, `source_url`, `workspaceId`, `workspace_node_ids`.
- **Output**: overwrites `processed/{tenantId}/{docId}/entity_resolution.json` with a JSON array of assertion records (source_entity, assertion, terminal_entity, source, source_url; domain fields null when not reconciled).
