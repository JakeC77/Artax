# Intent Execution API – REST Endpoints for Third-Party Agents

This document describes the **REST-style** endpoints intended for **third-party agents** that execute intents. These endpoints use **access-key authentication** (not JWT): the agent sends an access key that was generated for an agent role via the GraphQL API (`generateAgentRoleAccessKey`). The API validates the key and returns or performs operations scoped to that role’s allowed intents.

**Base URL:** Your API host (e.g. `https://api.example.com`).  
**Auth:** Pass the **access key** (the full secret returned once at generation) in one of these ways:

- **Authorization header:** `Authorization: Bearer <access_key>`
- **X-Api-Key header:** `X-Api-Key: <access_key>`

If the key is missing, invalid, or expired, the API returns **401 Unauthorized** with a JSON body. The same response is used in all error cases to avoid leaking key existence.

---

## GET /api/agent/intents – List intents for the agent role

Returns a JSON array of **intents** associated with the agent role identified by the access key. Use this to discover which intents the agent is allowed to execute.

**Method:** `GET`  
**Request body:** None.

**Success (200 OK)**  
Response body is a JSON array of intent objects. Each object has (camelCase):

| Field         | Type    | Description |
|---------------|---------|-------------|
| intentId      | UUID    | Unique id of the intent. |
| opId          | string  | Operation id (e.g. for routing). |
| intentName    | string  | Display name. |
| route         | string? | Optional route description. |
| description   | string? | Optional description. |
| dataSource    | string? | Optional data source label. |
| inputSchema   | string? | JSON Schema for input (JSON string). |
| outputSchema  | string? | JSON Schema for output (JSON string). |
| grounding     | string? | Cypher query template for grounding. |
| ontologyId    | UUID?   | Ontology this intent belongs to, if any. |
| createdOn     | string  | ISO 8601 datetime. |
| lastEdit      | string? | ISO 8601 datetime, if edited. |

If the role has no intents, the array is empty `[]`.

**Error (401 Unauthorized)**  
Body: `{ "error": "Missing or invalid access key" }`  
Returned when the access key is missing, invalid, or expired.

**Example – curl**

```bash
curl -X GET "https://api.example.com/api/agent/intents" \
  -H "Authorization: Bearer ge_1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef12345678"
```

Or with X-Api-Key:

```bash
curl -X GET "https://api.example.com/api/agent/intents" \
  -H "X-Api-Key: ge_1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef12345678"
```

**Example – 200 response**

```json
[
  {
    "intentId": "f7e8d9c0-b1a2-3456-7890-abcdef123456",
    "opId": "memberAuthentication",
    "intentName": "member.authentication",
    "route": "POST /api/intents/route",
    "description": "Authenticate a member based on demographic criteria.",
    "dataSource": "Patient-Match",
    "inputSchema": "{\"type\":\"object\",\"properties\":{\"firstName\":{\"type\":\"string\"},\"lastName\":{\"type\":\"string\"},\"dateOfBirth\":{\"type\":\"string\"}},\"required\":[\"firstName\",\"lastName\",\"dateOfBirth\"]}",
    "outputSchema": "{\"type\":\"object\",\"properties\":{\"memberId\":{\"type\":\"string\"}}}",
    "grounding": "MATCH (m:Member) WHERE m.firstName = $firstName AND m.lastName = $lastName AND m.dateOfBirth = $dateOfBirth RETURN m LIMIT 1",
    "ontologyId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "createdOn": "2026-02-14T17:00:00Z",
    "lastEdit": null
  }
]
```

---

## POST /api/agent/intents/execute – Execute an intent

Runs the intent’s **grounding** Cypher query with the provided parameters against the graph (resolved from the intent’s ontology). The intent must be one of the intents allowed for the agent role.

**Method:** `POST`  
**Request body (JSON):**

| Field       | Type   | Required | Description |
|-------------|--------|----------|-------------|
| opId        | string | Yes*     | Operation id of the intent (e.g. `"Member Auth"`). Use when intentId is not provided. |
| intentId    | UUID   | Yes*     | Exact intent id. When provided, takes precedence over opId. |
| parameters  | object | No       | Key-value map for the grounding Cypher. Keys must match the `$` variable names in the intent’s grounding query (without the `$`). Default: `{}`. |

\* At least one of `opId` or `intentId` is required.

**Success (200 OK)**  
Response body (camelCase):

| Field     | Type              | Description |
|-----------|-------------------|-------------|
| columns   | string[]          | Column names from the Cypher RETURN. |
| rows      | array of arrays   | Each row is an array of cell values (string, number, boolean, null; nodes/relationships serialized). |
| rowCount  | number            | Number of rows returned. |
| truncated | boolean           | True if the result was limited (e.g. cap at 10,000 rows). |

**Errors**

| Status | Body / condition |
|--------|-------------------|
| 400    | `{ "error": "Invalid request body." }` – JSON parse failure. |
| 400    | `{ "error": "Request must include opId or intentId." }` – Both missing. |
| 400    | `{ "error": "Intent has no grounding query." }` – Intent has no grounding. |
| 400    | `{ "error": "Invalid grounding query or parameters." }` – Cypher validation failed. |
| 401    | `{ "error": "Missing or invalid access key" }` – Key missing, invalid, or expired. |
| 403    | `{ "error": "Intent not allowed for this role." }` – Intent not in role’s allowed list. |
| 404    | `{ "error": "Intent not found or not allowed for this role." }` – No matching intent. |
| 502    | `{ "error": "Graph execution failed." }` – Neo4j error. |

**Parameter keys and grounding:** The grounding query uses Cypher parameters like `$patientId`, `$firstName`, `$lastName`, `$dateOfBirth`. The request `parameters` object must use the same names **without** the `$`: e.g. `{ "patientId": "123", "firstName": "Jane", "lastName": "Doe", "dateOfBirth": "1990-01-15" }`. The API runs the query in a parameterized way (no string replacement); keys are passed through to Neo4j.

**Example – curl (Member Auth by opId)**

```bash
curl -X POST "https://api.example.com/api/agent/intents/execute" \
  -H "Authorization: Bearer ge_YOUR_ACCESS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "opId": "Member Auth",
    "parameters": {
      "firstName": "Jane",
      "lastName": "Doe",
      "dateOfBirth": "1990-01-15"
    }
  }'
```

**Example – 200 response**

```json
{
  "columns": ["m"],
  "rows": [[ "node-id-or-summary" ]],
  "rowCount": 1,
  "truncated": false
}
```
