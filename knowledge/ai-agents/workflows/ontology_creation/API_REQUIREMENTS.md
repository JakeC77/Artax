# Ontology Creation Workflow - API Requirements

This document outlines what the **API layer** needs to implement to support the Ontology Creation Workflow. The workflow is already implemented in the backend worker; this document specifies the API endpoints and behaviors required for full integration.

---

## Overview

The Ontology Creation Workflow is a conversational, interactive workflow that allows users to create domain ontologies through a chat interface. The workflow:

- Reads user messages from an event stream (Server-Sent Events)
- Publishes agent messages and ontology updates via GraphQL mutations
- Supports resumable sessions using `ontology_id`
- Emits structured events for frontend consumption

---

## 1. Workflow Triggering

### Endpoint: POST to Azure Service Bus Queue

**When**: User initiates ontology creation (new or resume)

**Message Format**: Standard `WorkflowEvent` JSON

```json
{
  "workflowId": "ontology-creation",
  "tenantId": "uuid",
  "workspaceId": "uuid",
  "scenarioId": "uuid",
  "runId": "uuid",
  "inputs": "{\"initial_context\": \"I want to create an ontology for healthcare\", \"ontology_id\": \"uuid\"}",
  "status": "running",
  "requestedAt": "2026-02-07T12:00:00Z"
}
```

**Input Fields**:
- `initial_context` (optional): Initial user prompt/context for new ontology
- `ontology_id` (optional): UUID to resume an existing ontology session

**Implementation Notes**:
- ✅ **Already supported** - Uses the same workflow triggering mechanism as other workflows
- The API should enqueue this message to Azure Service Bus when user clicks "Create Ontology" or "Resume Ontology"
- Generate `runId` if not provided by frontend

---

## 2. Server-Sent Events (SSE) Endpoint

### Endpoint: `GET /runs/{runId}/events?tid={tenantId}`

**Purpose**: 
- **Read**: Frontend connects to receive workflow events (agent messages, ontology updates)
- **Write**: Frontend sends user messages and control events (`user_message`, `finalize_ontology`)

**Authentication**:
- Bearer token in `Authorization` header
- `X-Tenant-Id` header with tenant UUID

**Response Format**: Server-Sent Events (text/event-stream)

**Event Format**:
```
id: {eventId}
event: message
data: {"event_type":"agent_message","message":"Hello","agent_id":"ontology_agent",...}
```

### 2.1 Reading Events (Frontend → API)

The frontend connects to this endpoint to receive events from the workflow.

**Event Types Received**:
- `workflow_started` - Workflow initialization
- `agent_message` - Agent chat messages (streaming)
- `ontology_proposed` - Initial ontology structure proposed
- `ontology_updated` - Ontology structure updated
- `ontology_finalized` - Ontology marked as complete
- `ontology_ready` - Ontology package ready (alternative to finalized)
- `workflow_complete` - Workflow finished successfully
- `workflow_error` - Error occurred

**Implementation Requirements**:
- ✅ **Already supported** - The `EventStreamReader` expects this endpoint
- Must support long-lived connections (workflow can run for minutes/hours)
- Must handle reconnection gracefully (frontend may disconnect/reconnect)
- Must include event IDs to prevent duplicate processing
- Must filter events by `runId` and `tenantId`

### 2.2 Sending Events (Frontend → API → Worker)

The frontend sends user messages and control events through the same SSE connection or via a separate POST endpoint.

**Event Types Sent**:
- `user_message` - User chat message
- `finalize_ontology` - User confirms ontology is complete

**Option A: POST Endpoint (Recommended)**

Create a dedicated endpoint for sending events:

**Endpoint**: `POST /runs/{runId}/events`

**Request Body**:
```json
{
  "event_type": "user_message",
  "message": "Can you add a Provider entity?",
  "metadata": {
    "current_ontology_package": {
      "ontology_id": "uuid",
      "semantic_version": "0.1.0",
      "title": "Healthcare Domain",
      "entities": [...],
      "relationships": [...]
    }
  }
}
```

**Response**: `204 No Content` or `200 OK` with event ID

**Implementation**:
- Validate `runId` and `tenantId` (from auth context)
- Append event to scenario run log via GraphQL `appendScenarioRunLog` mutation
- Format as JSON matching the structure expected by `EventStreamReader`
- Return immediately (don't wait for workflow processing)

**Option B: SSE Bidirectional (Alternative)**

If your SSE implementation supports bidirectional communication:
- Frontend sends events via the same SSE connection
- API forwards to GraphQL log mutation
- Worker reads via `EventStreamReader`

**Recommendation**: Use **Option A** (POST endpoint) for better reliability and easier debugging.

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
{"event_type":"agent_message","message":"What domain are we modeling?","agent_id":"ontology_agent","completed":false}
```

**Implementation Requirements**:
- ✅ **Already supported** - Used by `ScenarioRunLogger`
- Must append content to scenario run log
- Must be queryable via SSE endpoint (`/runs/{runId}/events`)
- Must support event IDs for deduplication
- Must handle large payloads (ontology packages can be large)

---

## 4. Event Schema Reference

### User Message Event

**Event Type**: `user_message`

**Payload**:
```json
{
  "event_type": "user_message",
  "message": "Can you add a Provider entity?",
  "metadata": {
    "current_ontology_package": {
      "ontology_id": "uuid",
      "semantic_version": "0.1.0",
      "title": "Healthcare Domain",
      "description": "...",
      "entities": [
        {
          "entity_id": "ent_abc123",
          "name": "Patient",
          "description": "...",
          "fields": [
            {
              "name": "patient_id",
              "data_type": "string",
              "nullable": false,
              "is_identifier": true,
              "description": "..."
            }
          ]
        }
      ],
      "relationships": [
        {
          "relationship_id": "rel_xyz789",
          "from_entity": "ent_abc123",
          "to_entity": "ent_def456",
          "relationship_type": "HAS_CLAIM",
          "description": "...",
          "cardinality": "one-to-many"
        }
      ],
      "current_version": 1,
      "created_at": "2026-02-07T12:00:00Z",
      "updated_at": "2026-02-07T12:05:00Z",
      "finalized": false
    }
  }
}
```

**Important**: Always include `current_ontology_package` in metadata to sync user edits.

### Finalize Ontology Event

**Event Type**: `finalize_ontology`

**Payload**:
```json
{
  "event_type": "finalize_ontology",
  "metadata": {
    "final_ontology_package": {
      // Same structure as current_ontology_package above
      "finalized": true
    }
  }
}
```

### Agent Message Event (Received)

**Event Type**: `agent_message`

**Payload**:
```json
{
  "event_type": "agent_message",
  "message": "What domain are we modeling with this ontology?",
  "agent_id": "ontology_agent",
  "message_id": "uuid",
  "completed": false,
  "buffered": true
}
```

**Fields**:
- `completed`: `false` while streaming, `true` when message complete
- `buffered`: Whether message is part of a buffered batch

### Ontology Proposed Event (Received)

**Event Type**: `ontology_proposed`

**Payload**:
```json
{
  "event_type": "ontology_proposed",
  "message": "Ontology proposed for review",
  "metadata": {
    "ontology_package": {
      // Full OntologyPackage structure (see User Message Event)
    },
    "ready": true
  },
  "agent_id": "ontology_agent"
}
```

### Ontology Updated Event (Received)

**Event Type**: `ontology_updated`

**Payload**:
```json
{
  "event_type": "ontology_updated",
  "message": "Ontology package updated",
  "metadata": {
    "ontology_package": {
      // Updated OntologyPackage structure
      "semantic_version": "0.2.0"
    },
    "update_summary": "Added entity: Provider"
  },
  "agent_id": "ontology_agent"
}
```

### Ontology Finalized Event (Received)

**Event Type**: `ontology_finalized`

**Payload**:
```json
{
  "event_type": "ontology_finalized",
  "message": "Ontology finalized: Healthcare Domain",
  "metadata": {
    "ontology_package": {
      // Final OntologyPackage structure
      "semantic_version": "1.0.0",
      "finalized": true
    },
    "ontology_text": "# Healthcare Domain\n\n...",
    "title": "Healthcare Domain",
    "semantic_version": "1.0.0"
  },
  "agent_id": "ontology_agent"
}
```

---

## 5. Implementation Checklist

### Required Endpoints

- [x] **Workflow Triggering** - POST to Service Bus (already exists)
- [x] **SSE Event Stream** - `GET /runs/{runId}/events?tid={tenantId}` (already exists)
- [ ] **Send User Event** - `POST /runs/{runId}/events` (NEW - see Option A above)
- [x] **GraphQL Mutation** - `appendScenarioRunLog` (already exists)

### Required Behaviors

- [x] **Event Deduplication** - Use event IDs to prevent processing duplicates
- [x] **Long-lived Connections** - SSE endpoint must support connections lasting minutes/hours
- [x] **Reconnection Support** - Frontend may disconnect/reconnect; must resume from last event
- [ ] **Event Validation** - Validate `user_message` and `finalize_ontology` event structure
- [ ] **Error Handling** - Return appropriate HTTP status codes for invalid requests
- [ ] **Rate Limiting** - Consider rate limits for user message events (prevent spam)

### Optional Enhancements

- [ ] **Event History API** - `GET /runs/{runId}/events/history` to fetch past events
- [ ] **Event Filtering** - Support filtering SSE stream by event type
- [ ] **Webhook Support** - Alternative to SSE for event delivery (if preferred)
- [ ] **Event Acknowledgment** - Allow frontend to acknowledge receipt of events

---

## 6. Testing Recommendations

### Test Scenarios

1. **New Ontology Creation**
   - Trigger workflow with `initial_context`
   - Verify SSE connection receives `workflow_started`
   - Send `user_message` via POST endpoint
   - Verify workflow receives message and responds
   - Verify `ontology_proposed` event received

2. **Resume Existing Ontology**
   - Trigger workflow with `ontology_id`
   - Verify workflow loads existing ontology state
   - Verify events continue from previous session

3. **User Message Flow**
   - Send `user_message` with `current_ontology_package`
   - Verify workflow processes message
   - Verify `ontology_updated` event received with changes

4. **Finalize Ontology**
   - Send `finalize_ontology` event
   - Verify `ontology_finalized` event received
   - Verify `workflow_complete` event received

5. **Error Handling**
   - Send invalid event structure → verify 400 error
   - Send event for non-existent `runId` → verify 404 error
   - Send event with wrong `tenantId` → verify 403 error
   - Disconnect SSE → verify reconnection works

6. **Edge Cases**
   - Large ontology packages (test payload size limits)
   - Rapid message sending (test rate limiting)
   - Concurrent connections (test multiple frontends)
   - Long-running sessions (test connection stability)

---

## 7. Integration Example

### Frontend Flow

```typescript
// 1. Start workflow
const response = await fetch('/api/workflows/ontology-creation/trigger', {
  method: 'POST',
  body: JSON.stringify({
    tenant_id: tenantId,
    workspace_id: workspaceId,
    scenario_id: scenarioId,
    inputs: {
      initial_context: "I want to create an ontology for healthcare"
    }
  })
});

const { run_id, sse_url } = await response.json();

// 2. Connect to SSE stream
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

// 3. Send user message
async function sendUserMessage(message: string, ontologyPackage: OntologyPackage) {
  await fetch(`/runs/${runId}/events`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-Id': tenantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      event_type: 'user_message',
      message: message,
      metadata: {
        current_ontology_package: ontologyPackage
      }
    })
  });
}

// 4. Finalize ontology
async function finalizeOntology(ontologyPackage: OntologyPackage) {
  await fetch(`/runs/${runId}/events`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-Id': tenantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      event_type: 'finalize_ontology',
      metadata: {
        final_ontology_package: ontologyPackage
      }
    })
  });
}
```

---

## 8. Summary

### What Already Exists

✅ Workflow triggering (Service Bus)  
✅ SSE event stream endpoint (`GET /runs/{runId}/events`)  
✅ GraphQL `appendScenarioRunLog` mutation  
✅ Event deduplication via event IDs  
✅ Long-lived connection support  

### What Needs to Be Added

🔨 **POST endpoint for sending user events** (`POST /runs/{runId}/events`)  
- Accept `user_message` and `finalize_ontology` events
- Validate event structure
- Append to scenario run log via GraphQL mutation
- Return appropriate HTTP status codes

### Implementation Priority

1. **High Priority**: POST endpoint for user events (required for workflow to function)
2. **Medium Priority**: Event validation and error handling
3. **Low Priority**: Rate limiting, event history API, webhook support

---

## 9. Related Documentation

- **Frontend Guide**: `app/workflows/ontology_creation/FRONTEND_GUIDE.md`
- **Workflow Implementation**: `app/workflows/ontology_creation_workflow.py`
- **Event Stream Reader**: `app/core/event_stream_reader.py`
- **GraphQL Logger**: `app/core/graphql_logger.py`

---

## Questions or Issues?

Contact the backend team or refer to the workflow implementation in `app/workflows/ontology_creation/`.
