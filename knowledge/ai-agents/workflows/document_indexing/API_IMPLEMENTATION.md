# Document Indexing: API-Side Implementation

This document lists what the **API** (the service that receives scratchpad attachments and owns the entity surface cache and graph) must implement for the document-indexing worker to work end-to-end.

---

## 1. Upload and Trigger

When a new scratchpad attachment is created or finalized:

- **Write the file to Azure Blob** at path:  
  `raw/{tenantId}/{docId}/final/{filename}`  
  (same storage account/containers the worker uses; `docId` can be `scratchpadAttachmentId`).  
  Set blob metadata/tags: `tenantId`, `docId`, `contentType`, `uploadedBy`, `uploadedAt` (and optionally `workspaceId`, `scratchpadAttachmentId`).

- **Enqueue a message to Azure Service Bus** (same queue the worker listens to). Body = JSON-serialized **WorkflowEvent** with:
  - `workflowId`: `"document-indexing"`
  - `tenantId`, `workspaceId`, `scenarioId`, `runId` (as you already use)
  - `inputs`: JSON string containing at least:  
    `docId`, `tenantId`, `workspaceId`, `scratchpadAttachmentId`, `blobPath` (e.g. `raw/{tenantId}/{docId}/final/{filename}`), `contentType`, `filename`, and optionally `uploadedBy`, `uploadedAt`

The worker expects the same auth and queue as your existing workflow events.

---

## 2. GET Entity Surface Cache

- **Route**: `GET /document-indexing/entity-surface-cache?tenantId={tenantId}`  
  (Worker default path; configurable on worker via `DOCUMENT_INDEXING_ENTITY_CACHE_PATH`.)

- **Auth**: Same as your GraphQL/workspace API (Bearer token + `X-Tenant-Id: {tenantId}`).

- **Response**: JSON that is either:
  - a **list** of entity objects, or  
  - an object with key **`entities`** or **`data`** whose value is that list.

- **Each entity object** must include (camelCase or snake_case):  
  `semanticEntityId`, `nodeLabel`, `canonicalName`, `aliases` (list of strings), `identifiers` (e.g. `{"NPI": ["..."], "NDC": ["..."]}`).  
  The worker uses these for mention detection; the API owns creating/maintaining this cache (e.g. from Neo4j).

---

## 3. POST Evidence (Graph Write-Back)

- **Route**: `POST /document-indexing/evidence`  
  (Worker default; configurable via `DOCUMENT_INDEXING_EVIDENCE_PATH`, which may include `{docId}`.)

- **Auth**: Same as above (Bearer + `X-Tenant-Id`).

- **Request body** (JSON):
  - **`document`**: `{ docId, tenantId, contentType, spanCount, blobUri?, uploadedBy?, uploadedAt? }`
  - **`spansSummary`**: list of `{ spanId, locator, textHash }`
  - **`index`**: list of index entries:  
    `{ entityId, entityType, displayName, mentionCount, references }`  
    where `references` is a list of `{ spanId, locator, surface }`

- **Your implementation**: Persist to your graph (e.g. Neo4j): create/update Document (and optionally Span) nodes and create MENTIONED_IN / MENTIONED_AT relationships from the `document` and `index` payload. Return 2xx and optional JSON body.

---

## 4. Optional: Serving the Index

- **Optional routes** (if you want to serve index/evidence from the API):  
  `GET /documents/{docId}/index`,  
  `GET /entities/{entityId}/mentions?docId=...`,  
  `GET /documents/{docId}/spans/{spanId}`  
  (The worker does not call these; they are for your frontend or other consumers.)

---

## Summary

| Responsibility | API action |
|----------------|-----------|
| **Upload + trigger** | On new scratchpad attachment: write file to blob at `raw/{tenantId}/{docId}/final/{filename}` and enqueue a `document-indexing` WorkflowEvent with the required `inputs`. |
| **Entity surface cache** | Implement GET entity-surface-cache by tenant; return list of entities with `semanticEntityId`, `nodeLabel`, `canonicalName`, `aliases`, `identifiers`. |
| **Evidence write-back** | Implement POST evidence; parse payload and perform graph write-back (Document, Span, MENTIONED_IN, MENTIONED_AT). |
| **Auth** | Use the same auth (and base URL if the worker uses your GraphQL base) as your existing workspace/GraphQL API. |
