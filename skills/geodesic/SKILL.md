# Geodesic Knowledge Graph Skill

Query enterprise knowledge graphs via the Geodesic GraphQL API.

## Capabilities

- **Schema Discovery**: Fetch entity types, relationships, and suggested patterns
- **Cypher Queries**: Execute read-only Cypher against Neo4j graphs
- **Aggregations**: COUNT, SUM, AVG, etc. via `graphRowsByCypher`
- **Dashboard Generation**: Create Chart.js visualizations from query results

## Configuration

Credentials stored in `~/.geodesic-creds.env` (outside workspace, not in git):

```
GRAPHQL_AUTH_SCOPE=api://...
GRAPHQL_AUTH_CLIENT_ID=...
GRAPHQL_AUTH_CLIENT_SECRET=...
GRAPHQL_AUTH_TENANT_ID=...
WORKSPACE_GRAPHQL_ENDPOINT=https://...
```

## Usage

### 1. Get Auth Token

```python
import urllib.request, urllib.parse, json, os

# Load creds from ~/.geodesic-creds.env
tenant_id = os.environ["GRAPHQL_AUTH_TENANT_ID"]
token_url = f"https://{tenant_id}.ciamlogin.com/{tenant_id}/oauth2/v2.0/token"

data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": os.environ["GRAPHQL_AUTH_CLIENT_ID"],
    "client_secret": os.environ["GRAPHQL_AUTH_CLIENT_SECRET"],
    "scope": os.environ["GRAPHQL_AUTH_SCOPE"] + "/.default",
}).encode()

req = urllib.request.Request(token_url, data=data)
with urllib.request.urlopen(req, timeout=15) as resp:
    token = json.load(resp)["access_token"]
```

### 2. Query Schema

```graphql
query GetSchema($workspaceId: UUID!) {
  graphSchema(workspaceId: $workspaceId) {
    nodeTypes { label count description properties { name dataType } }
    relationshipTypes { type fromLabels toLabels }
    suggestedPatterns { name cypherPattern }
  }
}
```

### 3. Execute Cypher (Nodes)

```graphql
query RunCypher($cypherQuery: String!, $workspaceId: UUID) {
  graphNodesByCypher(cypherQuery: $cypherQuery, workspaceId: $workspaceId) {
    id labels properties { key value }
  }
}
```

### 4. Execute Cypher (Rows/Aggregations)

```graphql
query RunRows($cypherQuery: String!, $workspaceIds: [String!]) {
  graphRowsByCypher(cypherQuery: $cypherQuery, workspaceIds: $workspaceIds, limit: 1000) {
    columns rows rowCount truncated
  }
}
```

## Known Workspaces

| Name | ID | Description |
|------|-----|-------------|
| Q1 Prescription Drug Cost Optimization | `b06be363-f2d0-419a-acca-73ba84b3f64e` | PBM healthcare data |

## Example Queries

**Prescriptions by drug class:**
```cypher
MATCH (rx:Prescription)-[:PRESCRIPTION_TO_MEDICATION]->(m:Medication)-[:MEDICATION_TO_DRUGCLASS]->(dc:DrugClass)
RETURN dc.name as drug_class, count(rx) as rx_count
ORDER BY rx_count DESC LIMIT 10
```

**AWP by drug class:**
```cypher
MATCH (m:Medication)-[:MEDICATION_TO_DRUGCLASS]->(dc:DrugClass)
MATCH (m)-[:MEDICATION_TO_PRICINGDATA]->(p:PricingData)
RETURN dc.name as drug_class, avg(toFloat(p.awp)) as avg_awp
ORDER BY avg_awp DESC
```

**Monthly trends:**
```cypher
MATCH (rx:Prescription)
RETURN substring(rx.writtenDate, 0, 7) as month, count(rx) as count
ORDER BY month
```

## Headers Required

```
Authorization: Bearer {token}
X-Tenant-Id: {tenant_id}
Content-Type: application/json
```

## Limitations

- Read-only access (no mutations)
- Results capped at 1000 rows by default
- Token expires (refresh as needed)
