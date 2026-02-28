# Data Loading Workflow - API Requirements

This document outlines what the **API layer** needs to implement to support the Data Loading Workflow. The workflow is already implemented in the backend worker; this document specifies the API endpoints and behaviors required for full integration.

---

## Overview

The Data Loading Workflow is a conversational, interactive workflow that allows users to load CSV data into the graph database. The workflow:

- Analyzes CSV structure and infers data types
- Maps CSV columns to ontology entities and fields intelligently
- Validates mappings before insertion
- Creates nodes and relationships in the graph database
- Provides progress updates during insertion
- Handles errors gracefully through conversation

---

## 1. Workflow Triggering

### Endpoint: POST to Azure Service Bus Queue

**When**: User initiates data loading (uploads CSV + provides instructions)

**Message Format**: Standard `WorkflowEvent` JSON

```json
{
  "workflowId": "data-loading",
  "tenantId": "uuid",
  "workspaceId": "uuid",
  "scenarioId": "uuid",
  "runId": "uuid",
  "inputs": "{\"csv_path\": \"data-loading/{tenantId}/{runId}/input.csv\", \"ontology_id\": \"uuid\", \"initial_instructions\": \"Load all customers from last week\"}",
  "status": "running",
  "requestedAt": "2026-02-07T12:00:00Z"
}
```

**Input Fields**:
- `csv_path` (optional): Path to CSV file in blob storage (e.g., `data-loading/{tenantId}/{runId}/input.csv`)
- `csv_content` (optional): CSV content as base64-encoded string (alternative to csv_path)
- `ontology_id` (optional): UUID of ontology to use for mapping (uses workspace default if not provided)
- `initial_instructions` (optional): User's instructions (e.g., "Load all customers from last week")

**Implementation Notes**:
- ✅ **Already supported** - Uses the same workflow triggering mechanism as other workflows
- The API should enqueue this message to Azure Service Bus when user uploads CSV and clicks "Load Data"
- CSV should be uploaded to blob storage first (path: `data-loading/{tenantId}/{runId}/input.csv`)
- Generate `runId` if not provided by frontend

---

## 2. Server-Sent Events (SSE) Endpoint

### Endpoint: `GET /runs/{runId}/events?tid={tenantId}`

**Purpose**: 
- **Read**: Frontend connects to receive workflow events (agent messages, progress updates)
- **Write**: Frontend sends user messages and control events (`user_message`, `confirm_mapping`, `confirm_insertion`)

**Authentication**:
- Bearer token in `Authorization` header
- `X-Tenant-Id` header with tenant UUID

**Response Format**: Server-Sent Events (text/event-stream)

**Event Format**:
```
id: {eventId}
event: message
data: {"event_type":"agent_message","message":"Analyzing CSV...","agent_id":"data_loader_agent",...}
```

### 2.1 Reading Events (Frontend → API)

The frontend connects to this endpoint to receive events from the workflow.

**Event Types Received**:
- `workflow_started` - Workflow initialization
- `csv_analyzed` - CSV structure analyzed
- `agent_message` - Agent chat messages (questions, responses, confirmations)
- `mapping_proposed` - Agent proposes column mapping
- `mapping_validated` - Validation results
- `insertion_preview` - Preview of what will be inserted
- `nodes_created` - Progress: X nodes created
- `relationships_created` - Progress: X relationships created
- `workflow_complete` - Loading finished successfully
- `workflow_error` - Error occurred

**Implementation Requirements**:
- ✅ **Already supported** - The `EventStreamReader` expects this endpoint
- Must support long-lived connections (workflow can run for minutes)
- Must handle reconnection gracefully (frontend may disconnect/reconnect)
- Must include event IDs to prevent duplicate processing
- Must filter events by `runId` and `tenantId`

### 2.2 Sending Events (Frontend → API → Worker)

The frontend sends user messages and control events through a POST endpoint.

**Event Types Sent**:
- `user_message` - User chat message or feedback
- `confirm_mapping` - User confirms proposed mapping
- `confirm_insertion` - User confirms insertion should proceed
- `reject_mapping` - User rejects mapping, provides feedback

**Endpoint**: `POST /runs/{runId}/events`

**Request Body**:
```json
{
  "event_type": "user_message",
  "message": "Yes, that mapping looks correct",
  "metadata": {
    "feedback": "Optional feedback text"
  }
}
```

**Response**: `204 No Content` or `200 OK` with event ID

**Implementation**:
- Validate `runId` and `tenantId` (from auth context)
- Append event to scenario run log via GraphQL `appendScenarioRunLog` mutation
- Format as JSON matching the structure expected by `EventStreamReader`
- Return immediately (don't wait for workflow processing)

---

## 3. GraphQL Mutations

### 3.1 Append Scenario Run Log

**Mutation**: `appendScenarioRunLog`

**Purpose**: Workflow publishes events to this mutation, which appear in the SSE stream

**GraphQL Schema**:
```graphql
mutation AppendScenarioRunLog($runId: UUID!, $content: String!) {
  appendScenarioRunLog(runId: $runId, content: $content)
}
```

**Content Format**: JSON string (single event or newline-separated events)

**Example**:
```json
{"event_type":"agent_message","message":"I've analyzed your CSV with 150 rows","agent_id":"data_loader_agent"}
```

**Implementation Requirements**:
- ✅ **Already supported** - Used by `ScenarioRunLogger`
- Must append content to scenario run log
- Must be queryable via SSE endpoint (`/runs/{runId}/events`)
- Must support event IDs for deduplication
- Must handle large payloads

### 3.2 Graph Database Operations (Cypher)

**Note**: The workflow executes Cypher queries directly against Neo4j instead of using GraphQL mutations.

**Connection Details**:
- Uses existing Neo4j connection configuration (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- Same connection pool as other workflows (document indexing, etc.)

**Operations**:
- **Node Creation**: Uses `CREATE (n:Label {...})` Cypher statements
- **Relationship Creation**: Uses `CREATE (from)-[r:REL_TYPE]->(to)` Cypher statements
- **Batch Operations**: Uses `UNWIND` for efficient batch creation

**Implementation Requirements**:
- ✅ **Already implemented** - Workflow uses Neo4j driver directly
- No API changes needed for graph operations
- Uses existing Neo4j connection from `Config.NEO4J_URI`, `Config.NEO4J_USER`, `Config.NEO4J_PASSWORD`
- All operations run in write transactions
- Batch operations use UNWIND for performance

---

## 4. CSV Upload

### Blob Storage Path

**Path Pattern**: `data-loading/{tenantId}/{runId}/input.csv`

**Container**: Same as document indexing (`DOCUMENT_PROCESSED_CONTAINER`)

**Implementation**:
- Upload CSV file to blob storage when user selects file
- Set blob metadata: `tenantId`, `runId`, `workspaceId`, `uploadedAt`
- Pass blob path in workflow inputs

**Alternative**: CSV content can be passed directly in workflow inputs as base64-encoded string (for small files)

---

## 5. Event Schema Reference

### CSV Analyzed Event (Received)

**Event Type**: `csv_analyzed`

**Payload**:
```json
{
  "event_type": "csv_analyzed",
  "message": "CSV structure analyzed",
  "metadata": {
    "columns": [
      {
        "name": "customer_id",
        "data_type": "string",
        "sample_values": ["C001", "C002"],
        "nullable": false
      }
    ],
    "row_count": 150,
    "has_headers": true
  },
  "agent_id": "data_loader_agent"
}
```

### Mapping Proposed Event (Received)

**Event Type**: `mapping_proposed`

**Payload**:
```json
{
  "event_type": "mapping_proposed",
  "message": "I'm proposing this mapping—does it look correct?",
  "metadata": {
    "entity_mappings": [
      {
        "entity_name": "Customer",
        "csv_columns": ["customer_id", "name", "email"],
        "field_mappings": [
          {
            "csv_column": "customer_id",
            "field_name": "customer_id",
            "is_identifier": true
          }
        ]
      }
    ],
    "relationship_mappings": [
      {
        "relationship_type": "MADE_PURCHASE",
        "from_entity": "Customer",
        "to_entity": "Order",
        "csv_columns": ["customer_id", "order_id"]
      }
    ],
    "unmapped_columns": []
  },
  "agent_id": "data_loader_agent"
}
```

### Mapping Validated Event (Received)

**Event Type**: `mapping_validated`

**Payload**:
```json
{
  "event_type": "mapping_validated",
  "message": "Validation passed: 0 errors, 2 warnings",
  "metadata": {
    "is_valid": true,
    "errors": [],
    "warnings": [
      {
        "type": "type_mismatch",
        "message": "CSV column 'amount' is string, but field expects float",
        "column": "amount"
      }
    ],
    "summary": "Validation passed: 0 errors, 2 warnings"
  },
  "agent_id": "data_loader_agent"
}
```

### Insertion Preview Event (Received)

**Event Type**: `insertion_preview`

**Payload**:
```json
{
  "event_type": "insertion_preview",
  "message": "Preview of what will be inserted",
  "metadata": {
    "nodes_to_create": {
      "Customer": 150,
      "Order": 150
    },
    "relationships_to_create": {
      "MADE_PURCHASE": 150
    },
    "sample_nodes": {
      "Customer": [
        {"customer_id": "C001", "name": "John Doe", "email": "john@example.com"}
      ]
    },
    "sample_relationships": [
      {"from": "C001", "to": "O001", "type": "MADE_PURCHASE"}
    ],
    "total_rows": 150
  },
  "agent_id": "data_loader_agent"
}
```

### Nodes Created Event (Received)

**Event Type**: `nodes_created`

**Payload**:
```json
{
  "event_type": "nodes_created",
  "message": "Created 150 Customer nodes",
  "metadata": {
    "entity_name": "Customer",
    "created": 150,
    "total": 150,
    "errors": []
  },
  "agent_id": "data_loader_agent"
}
```

### Relationships Created Event (Received)

**Event Type**: `relationships_created`

**Payload**:
```json
{
  "event_type": "relationships_created",
  "message": "Created 150 relationships",
  "metadata": {
    "created": 150,
    "total": 150,
    "errors": []
  },
  "agent_id": "data_loader_agent"
}
```

### User Message Event (Sent)

**Event Type**: `user_message`

**Payload**:
```json
{
  "event_type": "user_message",
  "message": "Yes, that mapping looks correct. Please proceed.",
  "metadata": {
    "feedback": "Optional feedback"
  }
}
```

### Confirm Mapping Event (Sent)

**Event Type**: `confirm_mapping`

**Payload**:
```json
{
  "event_type": "confirm_mapping",
  "metadata": {}
}
```

### Confirm Insertion Event (Sent)

**Event Type**: `confirm_insertion`

**Payload**:
```json
{
  "event_type": "confirm_insertion",
  "metadata": {}
}
```

### Reject Mapping Event (Sent)

**Event Type**: `reject_mapping`

**Payload**:
```json
{
  "event_type": "reject_mapping",
  "metadata": {
    "feedback": "The customer_id column should map to the id field, not customer_id"
  }
}
```

---

## 6. Implementation Checklist

### Required Endpoints

- [x] **Workflow Triggering** - POST to Service Bus (already exists)
- [x] **SSE Event Stream** - `GET /runs/{runId}/events?tid={tenantId}` (already exists)
- [ ] **Send User Event** - `POST /runs/{runId}/events` (NEW - see section 2.2)
- [x] **GraphQL Mutation** - `appendScenarioRunLog` (already exists)
- [x] **Neo4j Connection** - Direct Cypher execution (uses existing connection)

### Required Behaviors

- [x] **Event Deduplication** - Use event IDs to prevent processing duplicates
- [x] **Long-lived Connections** - SSE endpoint must support connections lasting minutes
- [x] **Reconnection Support** - Frontend may disconnect/reconnect; must resume from last event
- [ ] **Event Validation** - Validate `user_message`, `confirm_mapping`, etc. event structure
- [ ] **Error Handling** - Return appropriate HTTP status codes for invalid requests
- [ ] **Graph Node Creation** - Create nodes with labels and properties
- [ ] **Graph Relationship Creation** - Create relationships between nodes
- [ ] **Batch Operations** - Support batch creation for performance
- [ ] **Workspace Scoping** - All graph operations must be scoped to workspace
- [ ] **Tenant Isolation** - All operations must respect tenant boundaries

### Optional Enhancements

- [ ] **CSV Upload API** - Dedicated endpoint for CSV upload (if not using blob storage directly)
- [ ] **Progress Tracking** - `GET /runs/{runId}/progress` endpoint for loading status
- [ ] **Error Recovery** - Save failed rows for retry
- [ ] **Incremental Loading** - Update existing nodes instead of creating new ones
- [ ] **Conflict Resolution** - Handle duplicate identifiers intelligently

---

## 7. Testing Recommendations

### Test Scenarios

1. **Basic CSV Loading**
   - Upload CSV with customer data
   - Verify CSV analysis event received
   - Verify mapping proposed
   - Confirm mapping
   - Verify nodes and relationships created

2. **Mapping Validation**
   - Upload CSV with type mismatches
   - Verify validation errors reported
   - Fix mapping based on feedback
   - Verify validation passes

3. **Large CSV Loading**
   - Upload CSV with 1000+ rows
   - Verify batch operations used
   - Verify progress events received
   - Verify all data loaded correctly

4. **Error Handling**
   - Upload CSV with missing required fields
   - Verify errors reported clearly
   - Verify user can retry or fix

5. **Relationship Creation**
   - Upload CSV with multiple entities
   - Verify nodes created first
   - Verify relationships created after nodes
   - Verify relationships link correct nodes

6. **Edge Cases**
   - CSV with no headers
   - CSV with special characters
   - CSV with missing values
   - CSV with duplicate identifiers

---

## 8. Integration Example

### Frontend Flow

```typescript
// 1. Upload CSV
const csvFile = // ... file from input
const blobPath = await uploadToBlobStorage(csvFile, `data-loading/${tenantId}/${runId}/input.csv`);

// 2. Start workflow
const response = await fetch('/api/workflows/data-loading/trigger', {
  method: 'POST',
  body: JSON.stringify({
    tenant_id: tenantId,
    workspace_id: workspaceId,
    scenario_id: scenarioId,
    inputs: {
      csv_path: blobPath,
      initial_instructions: "Load all customers from last week"
    }
  })
});

const { run_id, sse_url } = await response.json();

// 3. Connect to SSE stream
const eventSource = new EventSource(`${sse_url}`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Tenant-Id': tenantId
  }
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  handleWorkflowEvent(data);
};

// 4. Handle events
function handleWorkflowEvent(event) {
  switch (event.event_type) {
    case 'csv_analyzed':
      displayCSVStructure(event.metadata);
      break;
    case 'mapping_proposed':
      displayMappingProposal(event.metadata);
      showConfirmButton();
      break;
    case 'mapping_validated':
      displayValidationResults(event.metadata);
      break;
    case 'insertion_preview':
      displayPreview(event.metadata);
      showConfirmInsertionButton();
      break;
    case 'nodes_created':
      updateProgress(event.metadata);
      break;
    case 'workflow_complete':
      showCompletionMessage(event);
      break;
  }
}

// 5. Send user messages
async function confirmMapping() {
  await fetch(`/runs/${runId}/events`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-Id': tenantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      event_type: 'confirm_mapping'
    })
  });
}

async function confirmInsertion() {
  await fetch(`/runs/${runId}/events`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-Id': tenantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      event_type: 'confirm_insertion'
    })
  });
}
```

---

## 9. Summary

### What Already Exists

✅ Workflow triggering (Service Bus)  
✅ SSE event stream endpoint (`GET /runs/{runId}/events`)  
✅ GraphQL `appendScenarioRunLog` mutation  
✅ Event deduplication via event IDs  
✅ Long-lived connection support  

### What Needs to Be Added

🔨 **POST endpoint for sending user events** (`POST /runs/{runId}/events`)  
- Accept `user_message`, `confirm_mapping`, `confirm_insertion`, `reject_mapping` events
- Validate event structure
- Append to scenario run log via GraphQL mutation

✅ **Graph database operations**  
- Uses existing Neo4j connection (no API changes needed)
- Executes Cypher queries directly via Neo4j driver
- Batch operations use UNWIND for performance

🔨 **CSV upload handling**  
- Upload CSV to blob storage at `data-loading/{tenantId}/{runId}/input.csv`
- Or accept CSV content directly in workflow inputs

### Implementation Priority

1. **High Priority**: POST endpoint for user events (required for workflow to function)
2. ✅ **Complete**: Graph database operations (uses existing Neo4j connection, no API changes needed)
3. **Low Priority**: Progress tracking API, error recovery, incremental loading

---

## 10. Related Documentation

- **Frontend Guide**: `app/workflows/data_loading/FRONTEND_GUIDE.md` (to be created)
- **Workflow Implementation**: `app/workflows/data_loading/data_loading_workflow.py`
- **Event Stream Reader**: `app/core/event_stream_reader.py`
- **GraphQL Logger**: `app/core/graphql_logger.py`
- **Ontology Creation**: `app/workflows/ontology_creation/API_REQUIREMENTS.md` (similar pattern)

---

## Questions or Issues?

Contact the backend team or refer to the workflow implementation in `app/workflows/data_loading/`.
