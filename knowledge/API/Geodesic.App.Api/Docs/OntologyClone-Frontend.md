# Ontology Clone – Frontend API Guide

This guide describes how to use the GraphQL API to **clone an ontology**: create a new ontology that copies the source ontology’s metadata and draft JSON. Use this to duplicate an ontology within the same tenant (e.g. to create a variant or backup).

**Base:** All operations are `POST` to the GraphQL endpoint (e.g. `/gql`).  
**Headers:** `Content-Type: application/json`.  
**Auth:** Send your auth header (e.g. `Authorization: Bearer <token>`) when the API requires it.

---

## Mutation

**Name:** `cloneOntology`  
**Location:** On `Mutation` (same root as other entity mutations).

**Signature:**

```graphql
cloneOntology(sourceOntologyId: UUID!, name: String, tenantId: UUID!): UUID!
```

**Behavior:** Creates a new ontology by copying the source ontology’s DB row and its draft JSON blob. Returns the **new ontology’s UUID**. Neo4j connection is **not** copied; the clone uses the app default Neo4j until you call `setOntologyNeo4jConnection` for it.

---

## Parameters

| Parameter            | Type     | Required | Description |
|----------------------|----------|----------|-------------|
| `sourceOntologyId`   | `UUID!`  | Yes      | Ontology to clone. Must belong to the given tenant. |
| `tenantId`           | `UUID!`  | Yes      | Tenant the source belongs to (and that will own the clone). |
| `name`               | `String` | No       | Name for the new ontology. If null/empty, backend uses `"Copy of {source.Name}"`. |

---

## Return value

- **Success:** `UUID` – the new ontology’s `ontologyId`. Use it to navigate to the new ontology or refetch the ontology list.
- **Error:** GraphQL error, e.g. `"Ontology not found or tenant mismatch."` if the source doesn’t exist or isn’t in the given tenant.

---

## Example request (GraphQL)

```graphql
mutation CloneOntology($sourceOntologyId: UUID!, $tenantId: UUID!, $name: String) {
  cloneOntology(sourceOntologyId: $sourceOntologyId, tenantId: $tenantId, name: $name)
}
```

**Variables (with custom name):**

```json
{
  "sourceOntologyId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tenantId": "00000000-0000-0000-0000-000000000001",
  "name": "My cloned ontology"
}
```

**Variables (default “Copy of …” name):**

```json
{
  "sourceOntologyId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tenantId": "00000000-0000-0000-0000-000000000001"
}
```

---

## Example response

**Success:**

```json
{
  "data": {
    "cloneOntology": "f7e8d9c0-b1a2-3456-7890-abcdef123456"
  }
}
```

Use that UUID as the new `ontologyId` (e.g. open ontology detail, refresh list, or run `ontologyById(ontologyId: $newId)`).

---

## Front-end checklist

1. **Auth:** Use the same auth (e.g. tenant-scoped user/token) as for other entity mutations; the API enforces tenant match.
2. **Tenant:** Pass the current tenant’s ID (e.g. from app context or workspace).
3. **After clone:** Either redirect to the new ontology using the returned UUID, or refetch the ontology list (or add the new ontology to the list using `ontologyById`).
4. **Neo4j:** If the source had a per-ontology Neo4j connection, the clone does not; the user must set it again on the new ontology if needed.
5. **Intents:** Intents are not copied; they stay tied to the source ontology. The new ontology has no intents until the user creates or assigns them.
