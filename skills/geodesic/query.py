#!/usr/bin/env python3
"""
Geodesic Knowledge Graph Query Helper

Usage:
    python query.py schema <workspace_id>
    python query.py cypher <workspace_id> "MATCH (n) RETURN n LIMIT 5"
    python query.py rows <workspace_id> "MATCH (n) RETURN count(n)"
"""

import json
import os
import sys
import urllib.request
import urllib.parse

def load_creds():
    """Load credentials from ~/.geodesic-creds.env"""
    creds = {}
    path = os.path.expanduser("~/.geodesic-creds.env")
    if not os.path.exists(path):
        print(f"Error: Credentials not found at {path}")
        sys.exit(1)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                creds[key] = val
    return creds

def get_token(creds):
    """Get OAuth token from Entra External ID."""
    tenant_id = creds["GRAPHQL_AUTH_TENANT_ID"]
    token_url = f"https://{tenant_id}.ciamlogin.com/{tenant_id}/oauth2/v2.0/token"
    
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": creds["GRAPHQL_AUTH_CLIENT_ID"],
        "client_secret": creds["GRAPHQL_AUTH_CLIENT_SECRET"],
        "scope": creds["GRAPHQL_AUTH_SCOPE"] + "/.default",
    }).encode()
    
    req = urllib.request.Request(token_url, data=data)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["access_token"]

def graphql(creds, token, query, variables):
    """Execute GraphQL query."""
    endpoint = creds["WORKSPACE_GRAPHQL_ENDPOINT"]
    payload = json.dumps({"query": query, "variables": variables}).encode()
    
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": creds["GRAPHQL_AUTH_TENANT_ID"],
        }
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)

def cmd_schema(creds, token, workspace_id):
    """Fetch and display schema."""
    query = """
    query($workspaceId: UUID!) {
      graphSchema(workspaceId: $workspaceId) {
        nodeTypes { label count description }
        relationshipTypes { type fromLabels toLabels }
      }
    }
    """
    result = graphql(creds, token, query, {"workspaceId": workspace_id})
    
    if "errors" in result:
        print(f"Error: {result['errors']}")
        return
    
    schema = result["data"]["graphSchema"]
    
    print("\n=== Entity Types ===")
    for nt in schema["nodeTypes"]:
        print(f"  {nt['label']} ({nt['count']} nodes)")
    
    print("\n=== Relationships ===")
    for rt in schema["relationshipTypes"]:
        froms = ", ".join(rt["fromLabels"])
        tos = ", ".join(rt["toLabels"])
        print(f"  ({froms})-[:{rt['type']}]->({tos})")

def cmd_cypher(creds, token, workspace_id, cypher_query):
    """Execute Cypher and return nodes."""
    query = """
    query($cypherQuery: String!, $workspaceId: UUID) {
      graphNodesByCypher(cypherQuery: $cypherQuery, workspaceId: $workspaceId) {
        id labels properties { key value }
      }
    }
    """
    result = graphql(creds, token, query, {"cypherQuery": cypher_query, "workspaceId": workspace_id})
    
    if "errors" in result:
        print(f"Error: {result['errors']}")
        return
    
    nodes = result["data"]["graphNodesByCypher"]
    print(f"\nReturned {len(nodes)} nodes:\n")
    for node in nodes[:20]:
        props = {p["key"]: p["value"] for p in node["properties"]}
        print(f"  [{', '.join(node['labels'])}] {json.dumps(props)[:100]}...")

def cmd_rows(creds, token, workspace_id, cypher_query):
    """Execute Cypher and return rows (for aggregations)."""
    query = """
    query($cypherQuery: String!, $workspaceIds: [String!]) {
      graphRowsByCypher(cypherQuery: $cypherQuery, workspaceIds: $workspaceIds, limit: 100) {
        columns rows rowCount truncated
      }
    }
    """
    result = graphql(creds, token, query, {"cypherQuery": cypher_query, "workspaceIds": [workspace_id]})
    
    if "errors" in result:
        print(f"Error: {result['errors']}")
        return
    
    data = result["data"]["graphRowsByCypher"]
    print(f"\nColumns: {data['columns']}")
    print(f"Rows: {data['rowCount']} (truncated: {data['truncated']})\n")
    
    for row in data["rows"][:20]:
        print(f"  {row}")

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    workspace_id = sys.argv[2]
    
    creds = load_creds()
    print("Authenticating...")
    token = get_token(creds)
    print("✓ Token acquired\n")
    
    if cmd == "schema":
        cmd_schema(creds, token, workspace_id)
    elif cmd == "cypher" and len(sys.argv) > 3:
        cmd_cypher(creds, token, workspace_id, sys.argv[3])
    elif cmd == "rows" and len(sys.argv) > 3:
        cmd_rows(creds, token, workspace_id, sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
