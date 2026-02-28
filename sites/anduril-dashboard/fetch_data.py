#!/usr/bin/env python3
import json, os, urllib.request, urllib.parse

creds = {}
with open(os.path.expanduser('~/.geodesic-creds.env')) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            creds[key] = val

tenant_id = creds['GRAPHQL_AUTH_TENANT_ID']
token_url = f'https://{tenant_id}.ciamlogin.com/{tenant_id}/oauth2/v2.0/token'
data = urllib.parse.urlencode({
    'grant_type': 'client_credentials',
    'client_id': creds['GRAPHQL_AUTH_CLIENT_ID'],
    'client_secret': creds['GRAPHQL_AUTH_CLIENT_SECRET'],
    'scope': creds['GRAPHQL_AUTH_SCOPE'] + '/.default',
}).encode()
req = urllib.request.Request(token_url, data=data)
with urllib.request.urlopen(req, timeout=15) as resp:
    token = json.load(resp)['access_token']
print("Got token")

endpoint = creds['WORKSPACE_GRAPHQL_ENDPOINT']
workspace_id = "6a72b532-4910-47d1-9c15-ee549bbffa4c"

def query_nodes(cypher):
    gql = """query($cypherQuery: String!, $workspaceId: UUID) {
      graphNodesByCypher(cypherQuery: $cypherQuery, workspaceId: $workspaceId) {
        id labels properties { key value }
      }
    }"""
    body = json.dumps({"query": gql, "variables": {"cypherQuery": cypher, "workspaceId": workspace_id}}).encode()
    r = urllib.request.Request(endpoint, body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(r, timeout=60) as resp:
        result = json.load(resp)
    if "errors" in result:
        print(f"  ERROR: {result['errors']}")
        return []
    nodes = result.get("data", {}).get("graphNodesByCypher", [])
    print(f"  {len(nodes)} nodes: {cypher[:60]}")
    return nodes

def to_dicts(nodes):
    results = []
    for n in nodes:
        d = {"_id": n["id"], "_labels": n["labels"]}
        for p in n.get("properties", []):
            v = p["value"]
            try: v = json.loads(v)
            except: pass
            d[p["key"]] = v
        results.append(d)
    return results

queries = {
    "segment_quarter_revenue": "MATCH (sqr:SegmentQuarterRevenue) RETURN sqr",
    "program_segments": "MATCH (ps:ProgramSegment) RETURN ps",
    "contract_quarter_revenue": "MATCH (cqr:ContractQuarterRevenue) RETURN cqr",
    "customers": "MATCH (cu:Customer) RETURN cu",
    "okrs": "MATCH (o:OKR) RETURN o",
    "contracts": "MATCH (c:Contract) RETURN c",
    "departments": "MATCH (d:Department) RETURN d",
    "department_budgets": "MATCH (db:DepartmentBudget) RETURN db",
    "department_headcount": "MATCH (dhc:DepartmentHeadcountCost) RETURN dhc",
    "employees": "MATCH (e:Employee) RETURN e LIMIT 50",
    "skill_assessments": "MATCH (sa:SkillAssessment) RETURN sa LIMIT 100",
    "skills": "MATCH (s:Skill) RETURN s",
    "time_allocation": "MATCH (wta:WeeklyTimeAllocation) RETURN wta LIMIT 200",
    "initiatives": "MATCH (i:Initiative) RETURN i",
    "vendors": "MATCH (v:Vendor) RETURN v",
    "vendor_contracts": "MATCH (vc:VendorContract) RETURN vc",
}

all_data = {}
for key, cypher in queries.items():
    print(f"Querying {key}...")
    all_data[key] = to_dicts(query_nodes(cypher))

out = os.path.join(os.path.dirname(__file__), "data.json")
with open(out, "w") as f:
    json.dump(all_data, f, indent=2)
print(f"\nSaved to {out}")
for k, v in all_data.items():
    print(f"  {k}: {len(v)}")
