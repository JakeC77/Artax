# Data Loading Workflow – Frontend API Guide

This guide describes how to use the GraphQL API for the **data loading** workflow: uploading CSVs against an ontology, starting the chat/load run, and revisiting runs via the stored `runId`.

**Base:** All operations are `POST` to the GraphQL endpoint (e.g. `/gql`).  
**Headers:** `Content-Type: application/json` for normal queries/mutations; for file upload use `Content-Type: multipart/form-data` (see below).  
**Auth:** Send your auth header (e.g. `Authorization: Bearer <token>`) when the API requires it.

---

## Flow overview

1. **Upload CSV** → `createDataLoadingAttachment` → get `attachmentId`.
2. **Start workflow** (when user is ready) → `startDataLoadingPipeline` → get `runId` and optionally subscribe to the run’s event stream.
3. **Revisit a run** → use `dataLoadingAttachmentById(attachmentId)` and read `runId` (and `status`) to reconnect to the same stream.

The API stores `runId` on the attachment when the pipeline is started, so the UI can always show “open stream” using that `runId`.

---

## 1. Upload a CSV (create attachment)

**Purpose:** Upload a CSV file for a given tenant and ontology. The file is stored in cloud storage and a record is created. You get back an `attachmentId` to use when starting the workflow or listing attachments.

**Mutation:** `createDataLoadingAttachment(tenantId: UUID!, ontologyId: UUID!, file: Upload!, fileName: String): UUID!`

| Argument   | Type   | Required | Description |
|-----------|--------|----------|-------------|
| tenantId  | UUID   | Yes      | Tenant the ontology belongs to. |
| ontologyId| UUID   | Yes      | Ontology this CSV is for. |
| file      | Upload | Yes      | The CSV file (GraphQL `Upload`). |
| fileName  | String | No       | Display name for the file; if omitted, derived from the uploaded file. |

**Returns:** The new attachment’s `attachmentId` (UUID).  
**Errors:** If the ontology is not found or the tenant does not match the ontology’s tenant, the API returns a GraphQL error.

**Request (multipart/form-data for file upload):**

GraphQL multipart request spec is used. Example structure:

- **operations:** JSON string of the GraphQL operation and variables (with the file variable set to `null`).
- **map:** JSON object mapping file(s) to variable paths.
- **0:** The actual file (binary).

Example `operations`:

```json
{
  "query": "mutation CreateDataLoadingAttachment($tenantId: UUID!, $ontologyId: UUID!, $file: Upload!, $fileName: String) { createDataLoadingAttachment(tenantId: $tenantId, ontologyId: $ontologyId, file: $file, fileName: $fileName) }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000",
    "ontologyId": "523e4567-e89b-12d3-a456-426614174004",
    "file": null,
    "fileName": "customers.csv"
  }
}
```

Example `map`:

```json
{ "0": ["variables.file"] }
```

Then in the form, the file part is named `0` and contains the CSV binary.

**Success response:**

```json
{
  "data": {
    "createDataLoadingAttachment": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

Use that UUID as `attachmentId` for the next steps.

---

## 2. List attachments (query)

**Purpose:** List data-loading attachments, e.g. for a given tenant or ontology.

**Query:** `dataLoadingAttachments` (with optional filters via HotChocolate filtering).

**Example – all attachments:**

```json
{
  "query": "query { dataLoadingAttachments { attachmentId tenantId ontologyId fileName blobPath uri createdOn runId status } }"
}
```

**Example – filter by tenant and ontology:**

```json
{
  "query": "query ListAttachments($tenantId: UUID!, $ontologyId: UUID!) { dataLoadingAttachments(where: { tenantId: { eq: $tenantId }, ontologyId: { eq: $ontologyId } }) { attachmentId fileName createdOn runId status } }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000",
    "ontologyId": "523e4567-e89b-12d3-a456-426614174004"
  }
}
```

**Response:**

```json
{
  "data": {
    "dataLoadingAttachments": [
      {
        "attachmentId": "a1b2c3d4-e5f6-7890-abcd-111111111111",
        "tenantId": "123e4567-e89b-12d3-a456-426614174000",
        "ontologyId": "523e4567-e89b-12d3-a456-426614174004",
        "fileName": "customers.csv",
        "blobPath": "data-loading/123e4567.../a1b2c3d4.../customers.csv",
        "uri": "https://...",
        "createdOn": "2026-01-29T14:00:00Z",
        "runId": "423e4567-e89b-12d3-a456-426614174003",
        "status": "running"
      }
    ]
  }
}
```

- **runId** is `null` until the user has started the pipeline for this attachment; after that, use it to subscribe to the run’s stream.
- **status** values: e.g. `uploaded`, `running`, `completed`, `failed` (backend may use others).

---

## 3. Get one attachment by ID (query)

**Purpose:** Load a single attachment (e.g. to show details or to get `runId` for reconnecting to a stream).

**Query:** `dataLoadingAttachmentById(attachmentId: UUID!): DataLoadingAttachment`

**Request:**

```json
{
  "query": "query GetAttachment($attachmentId: UUID!) { dataLoadingAttachmentById(attachmentId: $attachmentId) { attachmentId tenantId ontologyId fileName blobPath uri createdOn createdBy runId status } }",
  "variables": {
    "attachmentId": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

**Response:** The `DataLoadingAttachment` object or `null` if not found.

---

## 4. Start the data-loading workflow (mutation)

**Purpose:** Start the data-loading run for an existing attachment. The API creates a `runId`, sends the workflow event to the backend, and **saves `runId` on the attachment**. The client uses `runId` to subscribe to the run’s event stream (e.g. chat).

**Mutation:** `startDataLoadingPipeline(dataLoadingAttachmentId: UUID!, workspaceId: UUID, initialInstructions: String): StartDataLoadingResult!`

| Argument               | Type   | Required | Description |
|------------------------|--------|----------|-------------|
| dataLoadingAttachmentId| UUID   | Yes      | The attachment (from step 1 or list). |
| workspaceId            | UUID   | No       | Optional workspace context for the run; not required. |
| initialInstructions    | String | No       | Optional instructions (e.g. “Load all customers from last week”). |

**Returns:** `StartDataLoadingResult { runId: UUID, success: Boolean! }`  
- **success:** `true` if the run was accepted (queued or no Service Bus); `false` if attachment/workspace not found or send failed.  
- **runId:** Present when the run was queued; use it to connect to the run’s event stream. `null` if the run was not queued.

**Request:**

```json
{
  "query": "mutation StartDataLoading($dataLoadingAttachmentId: UUID!, $workspaceId: UUID, $initialInstructions: String) { startDataLoadingPipeline(dataLoadingAttachmentId: $dataLoadingAttachmentId, workspaceId: $workspaceId, initialInstructions: $initialInstructions) { runId success } }",
  "variables": {
    "dataLoadingAttachmentId": "a1b2c3d4-e5f6-7890-abcd-111111111111",
    "initialInstructions": "Load all customers from last week"
  }
}
```

You can omit `workspaceId` entirely. If you pass it, it is included in the workflow payload for context but the run is not scoped to a workspace.

**Success response:**

```json
{
  "data": {
    "startDataLoadingPipeline": {
      "runId": "423e4567-e89b-12d3-a456-426614174003",
      "success": true
    }
  }
}
```

**Failure (e.g. attachment not found):**

```json
{
  "data": {
    "startDataLoadingPipeline": {
      "runId": null,
      "success": false
    }
  }
}
```

**Frontend actions:**

- If `success` is `true` and `runId` is non-null → subscribe to the run’s stream using `runId` (e.g. SignalR/SSE channel keyed by `runId`).
- The attachment row is updated server-side with this `runId` and status (e.g. `running`). To “revisit” the same run later, call `dataLoadingAttachmentById(attachmentId)` and use the returned `runId` to reconnect to the stream.

---

## 5. Delete an attachment (mutation)

**Purpose:** Remove the attachment record and the stored file.

**Mutation:** `deleteDataLoadingAttachment(attachmentId: UUID!): Boolean!`

**Request:**

```json
{
  "query": "mutation DeleteAttachment($attachmentId: UUID!) { deleteDataLoadingAttachment(attachmentId: $attachmentId) }",
  "variables": {
    "attachmentId": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

**Response:** `true` if the attachment was found and deleted; `false` if not found.

---

## Quick reference

| Action           | Operation                         | Returns / Use |
|-----------------|-----------------------------------|----------------|
| Upload CSV      | `createDataLoadingAttachment(...)`| New `attachmentId` (UUID). |
| List attachments| `dataLoadingAttachments` (optional filters) | `[DataLoadingAttachment!]!` |
| Get one         | `dataLoadingAttachmentById(attachmentId)`  | `DataLoadingAttachment` or null. |
| Start workflow  | `startDataLoadingPipeline(...)`   | `{ runId, success }` → use `runId` to subscribe to stream. |
| Delete          | `deleteDataLoadingAttachment(attachmentId)` | `Boolean!` |

**Revisiting a run:** After a run has been started, the attachment’s `runId` and `status` are set. Use `dataLoadingAttachmentById(attachmentId)` (or the list query) to read `runId` and connect your client to that run’s stream (e.g. by `runId`) to “reopen” the same chat/session.
