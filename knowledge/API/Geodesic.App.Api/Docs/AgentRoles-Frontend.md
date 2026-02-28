# Agent Roles – Frontend API Guide

This guide describes how to use the GraphQL API to manage **Agent Roles**: profiles that define what incoming agents are allowed to do in the API. Each role has a name, description, an optional read ontology, an optional write ontology, and a set of intents the agent is allowed to execute. You can generate **access keys** against a role; each key’s secret is shown only once at generation time.

**Base:** All operations are `POST` to the GraphQL endpoint (e.g. `/gql`).  
**Headers:** `Content-Type: application/json`.  
**Auth:** Send your auth header (e.g. `Authorization: Bearer <token>`) when the API requires it. Management of roles and keys is typically done by authenticated (e.g. JWT) users.

---

## Flow overview

1. **List roles** → `agentRoles` (optionally filter by `tenantId`).
2. **Get one role** (e.g. for edit/detail) → `agentRoleById(agentRoleId)`; request `readOntology`, `writeOntology`, `intents`, `accessKeys` as needed.
3. **Create** → `createAgentRole(...)` → returns new `agentRoleId`.
4. **Update** → `updateAgentRole(agentRoleId, ...)` with only the fields you want to change.
5. **Set allowed intents** → `setAgentRoleIntents(agentRoleId, intentIds)` (replaces the role’s intent list).
6. **Generate access key** → `generateAgentRoleAccessKey(agentRoleId, ...)` → returns **secretKey once**; client must store it.
7. **List access keys** → `agentRoleAccessKeys(agentRoleId)` or `agentRoleById` with `accessKeys` (metadata only; no secret).
8. **Revoke key** → `revokeAgentRoleAccessKey(accessKeyId)`.

Agent roles are **tenant-scoped**. Name is unique per tenant. The **secret** for an access key is never stored and is returned only in the `generateAgentRoleAccessKey` response; if the user loses it, they must revoke and generate a new key.

---

## 1. List agent roles

**Query:** `agentRoles`  
Returns a list of all agent roles. Supports HotChocolate filtering and sorting (e.g. by `tenantId`).

**Example – all roles:**

```json
{
  "query": "query { agentRoles { agentRoleId tenantId name description readOntologyId writeOntologyId createdOn lastEdit } }"
}
```

**Example – filter by tenant:**

```json
{
  "query": "query ListAgentRoles($tenantId: UUID!) { agentRoles(where: { tenantId: { eq: $tenantId } }) { agentRoleId name description readOntology { name } writeOntology { name } } }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

---

## 2. Get one agent role (by ID)

**Query:** `agentRoleById(agentRoleId: UUID!): AgentRole`  
Use this to load a role for the edit/detail page, including read/write ontologies, intents, and access keys (metadata only).

| Argument    | Type | Required | Description     |
|-------------|------|----------|-----------------|
| agentRoleId | UUID | Yes      | Role to fetch.  |

**Example:**

```json
{
  "query": "query GetAgentRole($agentRoleId: UUID!) { agentRoleById(agentRoleId: $agentRoleId) { agentRoleId tenantId name description readOntologyId writeOntologyId createdOn lastEdit readOntology { ontologyId name } writeOntology { ontologyId name } intents { intentId opId intentName } accessKeys { accessKeyId keyPrefix name createdOn expiresAt } } }",
  "variables": {
    "agentRoleId": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

**Response:** `agentRoleById` is either the `AgentRole` object or `null` if not found.

---

## 3. List access keys for a role

**Query:** `agentRoleAccessKeys(agentRoleId: UUID!): [AgentRoleAccessKey!]!`  
Returns metadata for all access keys belonging to the role. The secret is **never** returned.

| Argument    | Type | Required | Description     |
|-------------|------|----------|-----------------|
| agentRoleId | UUID | Yes      | Role whose keys to list. |

**Example:**

```json
{
  "query": "query ListAccessKeys($agentRoleId: UUID!) { agentRoleAccessKeys(agentRoleId: $agentRoleId) { accessKeyId keyPrefix name createdOn expiresAt } }",
  "variables": {
    "agentRoleId": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

---

## 4. Create agent role

**Mutation:** `createAgentRole(tenantId: UUID!, name: String!, description: String, readOntologyId: UUID, writeOntologyId: UUID): UUID!`

| Argument       | Type   | Required | Description |
|----------------|--------|----------|-------------|
| tenantId       | UUID   | Yes      | Tenant that owns the role. |
| name           | String | Yes      | Display name; unique per tenant. |
| description    | String | No       | Optional description. |
| readOntologyId | UUID   | No       | Ontology the agent can read from. |
| writeOntologyId| UUID   | No       | Ontology the agent can write to. |

**Returns:** The new role’s `agentRoleId` (UUID).

**Example:**

```json
{
  "query": "mutation CreateAgentRole($tenantId: UUID!, $name: String!, $description: String, $readOntologyId: UUID, $writeOntologyId: UUID) { createAgentRole(tenantId: $tenantId, name: $name, description: $description, readOntologyId: $readOntologyId, writeOntologyId: $writeOntologyId) }",
  "variables": {
    "tenantId": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Integration Agent",
    "description": "Read-only access to member ontology; can run member auth and prescription lookup.",
    "readOntologyId": "523e4567-e89b-12d3-a456-426614174004",
    "writeOntologyId": null
  }
}
```

**Success response:**

```json
{
  "data": {
    "createAgentRole": "a1b2c3d4-e5f6-7890-abcd-111111111111"
  }
}
```

---

## 5. Update agent role

**Mutation:** `updateAgentRole(agentRoleId: UUID!, name: String, description: String, readOntologyId: UUID, writeOntologyId: UUID): Boolean!`

| Argument       | Type   | Required | Description |
|----------------|--------|----------|-------------|
| agentRoleId    | UUID   | Yes      | Role to update. |
| name           | String | No       | New name. |
| description    | String | No       | Pass `null` to clear. |
| readOntologyId | UUID   | No       | Pass `null` to clear. |
| writeOntologyId| UUID   | No       | Pass `null` to clear. |

Only include variables for fields you want to change. Omitted fields are left unchanged.

**Returns:** `true` if the role was found and updated; `false` if not found.

---

## 6. Delete agent role

**Mutation:** `deleteAgentRole(agentRoleId: UUID!): Boolean!`

| Argument    | Type | Required | Description     |
|-------------|------|----------|-----------------|
| agentRoleId | UUID | Yes      | Role to delete. |

**Returns:** `true` if the role was found and deleted; `false` if not found. Associated access keys and intent links are removed (cascade).

---

## 7. Set allowed intents

**Mutation:** `setAgentRoleIntents(agentRoleId: UUID!, intentIds: [UUID!]!): Boolean!`  
Replaces the role’s allowed intents with the given list. Intents that do not exist or belong to a different tenant are skipped.

| Argument    | Type    | Required | Description |
|-------------|---------|----------|-------------|
| agentRoleId | UUID    | Yes      | Role to update. |
| intentIds   | [UUID!]!| Yes      | Full list of intent IDs the role may execute. |

**Returns:** `true` if the role was found and the list was set; `false` if the role was not found.

**Example:**

```json
{
  "query": "mutation SetAgentRoleIntents($agentRoleId: UUID!, $intentIds: [UUID!]!) { setAgentRoleIntents(agentRoleId: $agentRoleId, intentIds: $intentIds) }",
  "variables": {
    "agentRoleId": "a1b2c3d4-e5f6-7890-abcd-111111111111",
    "intentIds": ["f7e8d9c0-b1a2-3456-7890-abcdef123456", "b2c3d4e5-f6a7-8901-bcde-222222222222"]
  }
}
```

---

## 8. Generate access key

**Mutation:** `generateAgentRoleAccessKey(agentRoleId: UUID!, name: String, expiresAt: DateTime): GenerateAgentRoleAccessKeyResult!`  
Creates a new access key for the role. The **secretKey** is returned only in this response; the client must store it. It is never stored or returned again.

| Argument    | Type   | Required | Description |
|-------------|--------|----------|-------------|
| agentRoleId | UUID   | Yes      | Role to generate the key for. |
| name        | String | No       | Optional label for the key. |
| expiresAt   | DateTime | No     | Optional expiry (e.g. ISO 8601). |

**Returns:** `GenerateAgentRoleAccessKeyResult { accessKeyId, secretKey, keyPrefix, expiresAt }`.

**Example:**

```json
{
  "query": "mutation GenerateKey($agentRoleId: UUID!, $name: String, $expiresAt: DateTime) { generateAgentRoleAccessKey(agentRoleId: $agentRoleId, name: $name, expiresAt: $expiresAt) { accessKeyId secretKey keyPrefix expiresAt } }",
  "variables": {
    "agentRoleId": "a1b2c3d4-e5f6-7890-abcd-111111111111",
    "name": "Production API key",
    "expiresAt": null
  }
}
```

**Success response:**

```json
{
  "data": {
    "generateAgentRoleAccessKey": {
      "accessKeyId": "c3d4e5f6-a7b8-9012-cdef-333333333333",
      "secretKey": "ge_1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef12345678",
      "keyPrefix": "ge_1a2b3c4d",
      "expiresAt": null
    }
  }
}
```

**Important:** Show the user the `secretKey` once (e.g. in a modal or copy-to-clipboard) and instruct them to store it securely. If they lose it, they must revoke this key and generate a new one.

---

## 9. Revoke access key

**Mutation:** `revokeAgentRoleAccessKey(accessKeyId: UUID!): Boolean!`

| Argument   | Type | Required | Description     |
|------------|------|----------|-----------------|
| accessKeyId| UUID | Yes      | Key to revoke (delete). |

**Returns:** `true` if the key was found and revoked; `false` if not found.

**Example:**

```json
{
  "query": "mutation RevokeKey($accessKeyId: UUID!) { revokeAgentRoleAccessKey(accessKeyId: $accessKeyId) }",
  "variables": {
    "accessKeyId": "c3d4e5f6-a7b8-9012-cdef-333333333333"
  }
}
```

---

## Types (reference)

**AgentRole**

| Field          | Type     | Description |
|----------------|----------|-------------|
| agentRoleId    | UUID!    | Unique id. |
| tenantId       | UUID!    | Tenant that owns the role. |
| name           | String!  | Display name (unique per tenant). |
| description    | String   | Optional description. |
| readOntologyId | UUID     | Ontology the agent can read from. |
| writeOntologyId| UUID     | Ontology the agent can write to. |
| createdOn      | DateTime!| When the role was created. |
| lastEdit       | DateTime | When the role was last updated. |
| readOntology   | Ontology | Resolved read ontology; null if not set. |
| writeOntology  | Ontology | Resolved write ontology; null if not set. |
| intents        | [Intent!]! | Intents this role may execute. |
| accessKeys     | [AgentRoleAccessKey!]! | Access keys (metadata only). |

**AgentRoleAccessKey** (metadata only; no secret)

| Field       | Type     | Description |
|-------------|----------|-------------|
| accessKeyId | UUID!    | Unique id. |
| agentRoleId | UUID!    | Role this key belongs to. |
| keyPrefix   | String!  | Short prefix for display (e.g. ge_1a2b3c4d). |
| name        | String   | Optional label. |
| createdOn   | DateTime!| When the key was created. |
| expiresAt   | DateTime | Optional expiry. |

**GenerateAgentRoleAccessKeyResult** (returned only from generate mutation)

| Field       | Type     | Description |
|-------------|----------|-------------|
| accessKeyId | UUID!    | Id of the new key. |
| secretKey   | String!  | Full secret; **returned only once**. Client must store it. |
| keyPrefix   | String!  | Prefix for display. |
| expiresAt   | DateTime | Optional expiry. |

---

## Suggested UI flows

- **List page:** Query `agentRoles` (optionally filter by tenant). Table: Name, Description, Read ontology, Write ontology, Created. Actions: Add, Edit, Delete, Manage intents, Manage keys.
- **Create/Edit role:** Form: Tenant (create only), Name, Description, Read ontology (dropdown), Write ontology (dropdown). Submit: `createAgentRole` or `updateAgentRole`. On edit, load role with `agentRoleById`.
- **Set intents:** From role detail, show multi-select of intents (from `intents` filtered by same tenant). Submit: `setAgentRoleIntents(agentRoleId, intentIds)`.
- **Access keys:** List keys via `agentRoleAccessKeys(agentRoleId)` or `agentRoleById { accessKeys }`. Show keyPrefix, name, createdOn, expiresAt. Actions: Generate key (call `generateAgentRoleAccessKey`, then show result in a modal with **secretKey** and a “Copy” / “I have stored this” flow), Revoke (call `revokeAgentRoleAccessKey`).

---

## Security note

- **Storing the secret:** The client is responsible for storing the generated `secretKey`; the API does not persist or return it again.
- **Revoke if compromised:** If a key is leaked, revoke it with `revokeAgentRoleAccessKey` and generate a new one.
- **Key-based auth:** This API only stores and manages roles and keys. Using these keys to authenticate incoming requests (e.g. `Authorization: Bearer <secretKey>`) and to enforce read/write ontology and allowed intents is a separate integration (e.g. custom middleware) and is not covered in this doc.
