# Intent Management – Frontend API Guide

This guide describes how to use the GraphQL API to manage **Intents**: operations that third-party agents can perform on behalf of the system. Each intent defines what information the agent must collect, when to execute, and what the response looks like (input/output schema and grounding).

**Base:** All operations are `POST` to the GraphQL endpoint (e.g. `/gql`).  
**Headers:** `Content-Type: application/json`.  
**Auth:** Send your auth header (e.g. `Authorization: Bearer <token>`) when the API requires it.

---

## Flow overview

1. **List intents** → `intents` (optionally filter by `tenantId` via HotChocolate filtering).
2. **Get one intent** (e.g. for edit page) → `intentById(intentId)`.
3. **Create** → `createIntent(...)` → returns new `intentId`; redirect to list or edit.
4. **Update** → `updateIntent(intentId, ...)` with only the fields you want to change.
5. **Delete** → `deleteIntent(intentId)`.

Intents are **tenant-scoped**. `opId` must be unique per tenant. An intent can optionally belong to one **ontology** (one ontology has many intents); set `ontologyId` on create/update and query `ontology` when loading an intent.

---

## 1. List intents

**Query:** `intents`  
Returns a list of all intents. Supports HotChocolate filtering and sorting (e.g. by `tenantId`, `opId`, `intentName`).

**Example – all intents:**

```json
{
  "query": "query { intents { intentId tenantId ontologyId opId intentName route description dataSource createdOn lastEdit } }"
}
```

**Example – filter by tenant:**

```json
{
  "query": "query ListIntents($tenantId: UUID!) { intents(where: { tenantId: { eq: $tenantId } }) { intentId ontologyId opId intentName route description dataSource createdOn lastEdit } }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

**Example – filter by ontology:**

```json
{
  "query": "query ListIntentsByOntology($ontologyId: UUID!) { intents(where: { ontologyId: { eq: $ontologyId } }) { intentId opId intentName ontology { ontologyId name } } }",
  "variables": {
    "ontologyId": "523e4567-e89b-12d3-a456-426614174004"
  }
}
```

**Response:**

```json
{
  "data": {
    "intents": [
      {
        "intentId": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
        "tenantId": "123e4567-e89b-12d3-a456-426614174000",
        "ontologyId": "523e4567-e89b-12d3-a456-426614174004",
        "opId": "memberAuthentication",
        "intentName": "member.authentication",
        "route": "POST /api/intents/route",
        "description": "Authenticate a member based on demographic criteria.",
        "dataSource": "Patient-Match",
        "createdOn": "2026-02-14T17:00:00Z",
        "lastEdit": null
      }
    ]
  }
}
```

To include the JSON fields (e.g. for an edit form), request them in the selection set:

- `inputSchema` – JSON string (input JSON Schema)
- `outputSchema` – JSON string (output JSON Schema)
- `grounding` – Cypher query template (plain text)

---

## 2. Get one intent (by ID)

**Query:** `intentById(intentId: UUID!): Intent`  
Use this to load an intent for the edit page.

| Argument  | Type | Required | Description        |
|-----------|------|----------|--------------------|
| intentId  | UUID | Yes      | Intent to fetch.   |

**Example:**

```json
{
  "query": "query GetIntent($intentId: UUID!) { intentById(intentId: $intentId) { intentId tenantId ontologyId opId intentName route description dataSource inputSchema outputSchema grounding createdOn lastEdit ontology { ontologyId name } } }",
  "variables": {
    "intentId": "f7e8d9c0-b1a2-3456-7890-abcdef123456"
  }
}
```

**Response:** `intentById` is either the `Intent` object or `null` if not found.

---

## 3. Create intent

**Mutation:** `createIntent(tenantId: UUID!, opId: String!, intentName: String!, route: String, description: String, dataSource: String, inputSchema: String, outputSchema: String, grounding: String, ontologyId: UUID): UUID!`

| Argument    | Type   | Required | Description |
|-------------|--------|----------|-------------|
| tenantId    | UUID   | Yes      | Tenant that owns the intent. |
| opId        | String | Yes      | Operation id (e.g. `memberAuthentication`). Must be unique per tenant. |
| intentName  | String | Yes      | Intent identifier (e.g. `member.authentication`). |
| route       | String | No       | e.g. `POST /api/intents/route`. |
| description | String | No       | Human-readable description. |
| dataSource  | String | No       | e.g. `Patient-Match`, `GraphQL`. |
| inputSchema | String | No       | JSON string: input JSON Schema. |
| outputSchema| String | No       | JSON string: output JSON Schema. |
| grounding   | String | No       | Cypher query template for grounding (plain text). |
| ontologyId  | UUID   | No       | Ontology this intent belongs to. One ontology has many intents. |

**Returns:** The new intent’s `intentId` (UUID).

**Example:**

```json
{
  "query": "mutation CreateIntent($tenantId: UUID!, $opId: String!, $intentName: String!, $route: String, $description: String, $dataSource: String, $inputSchema: String, $outputSchema: String, $grounding: String, $ontologyId: UUID) { createIntent(tenantId: $tenantId, opId: $opId, intentName: $intentName, route: $route, description: $description, dataSource: $dataSource, inputSchema: $inputSchema, outputSchema: $outputSchema, grounding: $grounding, ontologyId: $ontologyId) }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000",
    "opId": "memberAuthentication",
    "intentName": "member.authentication",
    "route": "POST /api/intents/route",
    "description": "Authenticate a member based on demographic criteria.",
    "dataSource": "Patient-Match",
    "inputSchema": "{\"type\":\"object\",\"required\":[\"intentName\",\"parameters\"],\"properties\":{}}",
    "outputSchema": "{\"type\":\"object\",\"properties\":{\"patientId\":{\"type\":\"string\"}}}",
    "grounding": "MATCH (m:Member) WHERE m.firstName = $firstName AND m.lastName = $lastName AND m.dateOfBirth = $dateOfBirth RETURN m LIMIT 1",
    "ontologyId": "523e4567-e89b-12d3-a456-426614174004"
  }
}
```

**Success response:**

```json
{
  "data": {
    "createIntent": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

Use that UUID to navigate to the edit page or refresh the list.

---

## 4. Update intent

**Mutation:** `updateIntent(intentId: UUID!, opId: String, intentName: String, route: String, description: String, dataSource: String, inputSchema: String, outputSchema: String, grounding: String, ontologyId: UUID): Boolean!`

| Argument    | Type   | Required | Description |
|-------------|--------|----------|-------------|
| intentId    | UUID   | Yes      | Intent to update. |
| opId        | String | No       | New operation id; if provided, replaces current. |
| intentName  | String | No       | New intent name; if provided, replaces current. |
| route       | String | No       | Pass `null` to clear. |
| description | String | No       | Pass `null` to clear. |
| dataSource  | String | No       | Pass `null` to clear. |
| inputSchema | String | No       | Pass `null` to clear. |
| outputSchema| String | No       | Pass `null` to clear. |
| grounding   | String | No       | Pass `null` to clear. |
| ontologyId  | UUID   | No       | Set or clear the intent’s ontology; pass `null` to clear. |

Only include variables for fields you want to change. Omitted fields are left unchanged.

**Returns:** `true` if the intent was found and updated; `false` if the intent was not found.

**Example (update description, outputSchema, and ontology only):**

```json
{
  "query": "mutation UpdateIntent($intentId: UUID!, $description: String, $outputSchema: String, $ontologyId: UUID) { updateIntent(intentId: $intentId, description: $description, outputSchema: $outputSchema, ontologyId: $ontologyId) }",
  "variables": {
    "intentId": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
    "description": "Updated description.",
    "outputSchema": "{\"type\":\"object\",\"properties\":{\"patientId\":{\"type\":\"string\"},\"matched\":{\"type\":\"boolean\"}}}",
    "ontologyId": "523e4567-e89b-12d3-a456-426614174004"
  }
}
```

---

## 5. Delete intent

**Mutation:** `deleteIntent(intentId: UUID!): Boolean!`

| Argument | Type | Required | Description     |
|----------|------|----------|-----------------|
| intentId | UUID | Yes      | Intent to delete. |

**Returns:** `true` if the intent was found and deleted; `false` if the intent was not found.

**Example:**

```json
{
  "query": "mutation DeleteIntent($intentId: UUID!) { deleteIntent(intentId: $intentId) }",
  "variables": {
    "intentId": "f7e8d9c0-b1a2-3456-7890-abcdef123456"
  }
}
```

---

## Intent type (reference)

| Field         | Type     | Description |
|---------------|----------|-------------|
| intentId      | UUID!    | Unique id. |
| tenantId      | UUID!    | Tenant that owns the intent. |
| ontologyId    | UUID     | When set, this intent belongs to this ontology (one ontology has many intents). |
| opId          | String!  | Operation id (unique per tenant). |
| intentName    | String!  | Intent identifier. |
| route         | String   | e.g. route path. |
| description   | String   | Human-readable description. |
| dataSource    | String   | e.g. Patient-Match, GraphQL. |
| inputSchema   | String   | JSON string (input JSON Schema). |
| outputSchema  | String   | JSON string (output JSON Schema). |
| grounding     | String   | Cypher query template for grounding (plain text). |
| createdOn     | DateTime!| When the intent was created. |
| lastEdit      | DateTime | When the intent was last updated. |
| ontology      | Ontology | Resolved ontology when ontologyId is set; otherwise null. |

---

## Suggested UI flows

- **List page:** Query `intents` (optionally filtered by `tenantId`). Table columns: OpId, Intent Name, Route, Data Source, Description (truncated). Actions: Add (navigate to create), Edit (navigate to edit with `intentId`), Delete (call `deleteIntent`, then refresh list).
- **Create page:** Form with required Tenant (e.g. dropdown), OpId, Intent Name; optional Ontology (dropdown), Route, Description, Data Source; text areas or JSON editors for Input Schema and Output Schema; and a text area for Grounding (Cypher query template). Submit via `createIntent`; redirect to list or to edit page with the returned `intentId`.
- **Edit page:** Load `intentById(intentId)`, same form pre-filled; submit via `updateIntent(intentId, ...)` with only changed fields.
