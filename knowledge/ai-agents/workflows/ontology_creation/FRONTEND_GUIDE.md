# Ontology Creation Workflow - Frontend Integration Guide

## Overview

The Ontology Creation Workflow is an interactive chat-based experience that guides users through creating domain ontologies. Similar to how Theo helps users create intents, this workflow helps users define:

- **Entities**: Core concepts in their domain (e.g., Patient, Claim, Provider)
- **Fields**: Properties of entities with data types, nullable flags, and identifier markers
- **Relationships**: Connections between entities with semantic descriptions

The workflow supports:
- **Resumable sessions**: Users can pause and resume ontology creation days/weeks later
- **Iterative refinement**: Users can edit the ontology directly or via chat
- **Semantic versioning**: Ontologies are versioned (MAJOR.MINOR.PATCH) to track changes

## Workflow Flow

1. **User starts workflow** → Sends `WorkflowEvent` with `workflow_id="ontology-creation"`
2. **Workflow initializes** → Agent begins conversation
3. **Agent asks questions** → Streams questions via `agent_message` events
4. **User responds** → Sends `user_message` events
5. **Agent proposes ontology** → Emits `ontology_proposed` event with full structure
6. **Frontend displays ontology** → Shows entities, fields, relationships in structured UI
7. **User provides feedback** → Sends `user_message` with edits/feedback
8. **Agent updates ontology** → Emits `ontology_updated` events
9. **User confirms** → Sends `finalize_ontology` event
10. **Workflow finalizes** → Emits `ontology_finalized` event

## Event Types

### 1. `workflow_started`

**When**: Workflow begins execution

**Payload**:
```json
{
  "event_type": "workflow_started",
  "message": "Ontology Creation Workflow Started",
  "metadata": {
    "workspace_id": "uuid",
    "run_id": "uuid",
    "stage": "ontology_creation"
  },
  "agent_id": "ontology_agent"
}
```

**Frontend Action**: 
- Show loading state
- Initialize ontology editor UI
- Display welcome message

---

### 2. `agent_message`

**When**: Agent sends a message to the user (questions, responses, confirmations)

**Payload**:
```json
{
  "event_type": "agent_message",
  "message": "What domain are we modeling with this ontology?",
  "agent_id": "ontology_agent",
  "metadata": {
    "message_id": "uuid",
    "completed": true,
    "buffered": true
  }
}
```

**Frontend Action**:
- Display message in chat interface
- Show typing indicator while `completed: false`
- Scroll chat to latest message

---

### 3. `ontology_proposed`

**When**: Agent proposes an initial ontology structure (first time or after major changes)

**Payload**:
```json
{
  "event_type": "ontology_proposed",
  "message": "Ontology proposed for review",
  "metadata": {
    "ontology_package": {
      "schema_version": 1,
      "ontology_id": "uuid",
      "semantic_version": "0.1.0",
      "title": "Healthcare Domain",
      "description": "Ontology for healthcare claims processing",
      "entities": [
        {
          "entity_id": "ent_abc123",
          "name": "Patient",
          "description": "A patient in the healthcare system",
          "fields": [
            {
              "name": "patient_id",
              "data_type": "string",
              "nullable": false,
              "is_identifier": true,
              "description": "Unique patient identifier"
            },
            {
              "name": "name",
              "data_type": "string",
              "nullable": false,
              "is_identifier": false,
              "description": "Patient's full name"
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
          "description": "A patient can have multiple claims",
          "cardinality": "one-to-many"
        }
      ],
      "current_version": 1,
      "created_at": "2026-02-07T12:00:00Z",
      "updated_at": "2026-02-07T12:05:00Z",
      "finalized": false
    },
    "ready": true
  },
  "agent_id": "ontology_agent"
}
```

**Frontend Action**:
- **Display ontology structure** in a structured editor/viewer:
  - Show entities in a list or tree view
  - For each entity, show:
    - Name (editable)
    - Description (editable)
    - Fields table with columns: Name, Data Type, Nullable, Is ID, Description (all editable)
  - Show relationships in a graph or list view:
    - Display as: `Entity1 --[RELATIONSHIP_TYPE]--> Entity2`
    - Show description and cardinality
- **Enable editing**: Allow users to edit any field directly
- **Show version**: Display semantic version prominently
- **Enable "Finalize" button**: Allow user to mark ontology as complete

---

### 4. `ontology_updated`

**When**: Agent updates the ontology based on user feedback or conversation

**Payload**:
```json
{
  "event_type": "ontology_updated",
  "message": "Ontology package updated",
  "metadata": {
    "ontology_package": {
      // Same structure as ontology_proposed
      "semantic_version": "0.2.0",  // Version incremented
      // ... updated fields
    },
    "update_summary": "Added entity: Provider"
  },
  "agent_id": "ontology_agent"
}
```

**Frontend Action**:
- **Update ontology display** with new structure
- **Highlight changes**: Show what changed (e.g., new entity, updated field)
- **Show update summary**: Display `update_summary` in a notification or chat
- **Preserve user edits**: If user was editing a field, preserve their changes unless the update conflicts

---

### 5. `ontology_finalized`

**When**: User confirms the ontology is complete (via `finalize_ontology` event)

**Payload**:
```json
{
  "event_type": "ontology_finalized",
  "message": "Ontology finalized: Healthcare Domain",
  "metadata": {
    "ontology_package": {
      // Full ontology structure
      "semantic_version": "1.0.0",  // Promoted to 1.0.0 if was 0.x.x
      "finalized": true
    },
    "ontology_text": "# Healthcare Domain\n\n...",  // Formatted markdown
    "title": "Healthcare Domain",
    "semantic_version": "1.0.0"
  },
  "agent_id": "ontology_agent"
}
```

**Frontend Action**:
- **Show completion state**: Display success message
- **Disable editing**: Make ontology read-only (or show "Edit" option to create new version)
- **Show final version**: Display semantic version prominently
- **Enable export**: Allow user to export ontology (JSON, GraphQL schema, etc.)
- **Show next steps**: Suggest actions (e.g., "Use this ontology", "Create another")

---

### 6. `workflow_complete`

**When**: Workflow finishes successfully

**Payload**:
```json
{
  "event_type": "workflow_complete",
  "message": "Ontology 'Healthcare Domain' finalized successfully",
  "agent_id": "ontology_agent"
}
```

**Frontend Action**:
- Hide loading indicators
- Show completion summary
- Enable navigation away from workflow

---

### 7. `workflow_error`

**When**: An error occurs during workflow execution

**Payload**:
```json
{
  "event_type": "workflow_error",
  "message": "Error: Failed to save ontology draft",
  "agent_id": "ontology_agent"
}
```

**Frontend Action**:
- Display error message to user
- Allow retry or cancellation
- Save draft state if possible

---

## User Actions → Events

### Starting a New Ontology

**Frontend sends**:
```json
{
  "workflow_id": "ontology-creation",
  "inputs": {
    "initial_context": "I want to create an ontology for healthcare claims"  // Optional
  }
}
```

### Resuming an Existing Ontology

**Frontend sends**:
```json
{
  "workflow_id": "ontology-creation",
  "inputs": {
    "ontology_id": "existing-uuid-here"  // Required for resume
  }
}
```

### Sending a User Message

**Frontend sends**:
```json
{
  "event_type": "user_message",
  "message": "Can you add a Provider entity?",
  "metadata": {
    "current_ontology_package": {
      // Current state of ontology (include user's edits)
      // This ensures agent sees user's direct edits
    }
  }
}
```

**Important**: Always include `current_ontology_package` in metadata to sync user edits.

### Finalizing Ontology

**Frontend sends**:
```json
{
  "event_type": "finalize_ontology",
  "metadata": {
    "final_ontology_package": {
      // Final state including any last-minute edits
    }
  }
}
```

---

## UI/UX Recommendations

### Chat Interface

- **Display agent messages** in chat bubbles
- **Show typing indicator** while agent is processing
- **Allow user to type** and send messages
- **Display ontology updates** inline or in a sidebar

### Ontology Editor

**Entity View**:
```
┌─────────────────────────────────────┐
│ Patient                              │
│ A patient in the healthcare system   │
│                                      │
│ Fields:                              │
│ ┌─────────────┬───────────┬────────┐│
│ │ Name        │ Type      │ ID?    ││
│ ├─────────────┼───────────┼────────┤│
│ │ patient_id  │ string    │ ✓      ││
│ │ name        │ string    │        ││
│ │ dob         │ date      │        ││
│ └─────────────┴───────────┴────────┘│
└─────────────────────────────────────┘
```

**Relationship View**:
```
Patient --[HAS_CLAIM (one-to-many)]--> Claim
  └─ A patient can have multiple claims

Claim --[SERVICED_BY (many-to-one)]--> Provider
  └─ Each claim is serviced by one provider
```

### State Management

1. **Maintain local state** of `ontology_package` from events
2. **Track user edits** separately from agent updates
3. **Merge strategy**: 
   - Agent updates overwrite agent-set fields
   - User edits take precedence over agent updates
   - When sending `user_message`, include merged state

### Visual Indicators

- **Version badge**: Show semantic version (e.g., "v0.1.0")
- **Change indicators**: Highlight new/modified entities/fields
- **Status**: Show "Draft", "Proposed", "Finalized"
- **Save indicator**: Show "Saving..." / "Saved" / "Unsaved changes"

### Error Handling

- **Network errors**: Retry sending events
- **Validation errors**: Show field-level errors
- **Workflow errors**: Display error message, allow retry

---

## Example Integration

```typescript
// Pseudocode example

class OntologyCreationUI {
  ontologyPackage: OntologyPackage | null = null;
  chatMessages: Message[] = [];
  
  async startWorkflow(initialContext?: string, ontologyId?: string) {
    const event = {
      workflow_id: "ontology-creation",
      inputs: {
        ...(initialContext && { initial_context: initialContext }),
        ...(ontologyId && { ontology_id: ontologyId })
      }
    };
    
    await this.sendWorkflowEvent(event);
    this.subscribeToEvents();
  }
  
  subscribeToEvents() {
    eventStream.on('agent_message', (event) => {
      this.chatMessages.push({
        role: 'agent',
        content: event.message,
        timestamp: Date.now()
      });
      this.renderChat();
    });
    
    eventStream.on('ontology_proposed', (event) => {
      this.ontologyPackage = event.metadata.ontology_package;
      this.renderOntologyEditor();
      this.showNotification('Ontology proposed - review and edit as needed');
    });
    
    eventStream.on('ontology_updated', (event) => {
      this.ontologyPackage = event.metadata.ontology_package;
      this.renderOntologyEditor();
      this.highlightChanges(event.metadata.update_summary);
    });
    
    eventStream.on('ontology_finalized', (event) => {
      this.ontologyPackage = event.metadata.ontology_package;
      this.setReadOnly(true);
      this.showSuccess('Ontology finalized!');
    });
  }
  
  async sendUserMessage(message: string) {
    const event = {
      event_type: "user_message",
      message: message,
      metadata: {
        current_ontology_package: this.ontologyPackage  // Include user edits
      }
    };
    
    await this.sendEvent(event);
    this.chatMessages.push({
      role: 'user',
      content: message,
      timestamp: Date.now()
    });
    this.renderChat();
  }
  
  async finalizeOntology() {
    const event = {
      event_type: "finalize_ontology",
      metadata: {
        final_ontology_package: this.ontologyPackage  // Include final edits
      }
    };
    
    await this.sendEvent(event);
  }
  
  onUserEdit(field: string, value: any) {
    // Update local state
    this.updateOntologyPackage(field, value);
    
    // Optionally auto-sync with agent (debounced)
    this.debouncedSync();
  }
}
```

---

## Data Types Reference

### OntologyPackage Structure

```typescript
interface OntologyPackage {
  schema_version: number;           // Internal schema version
  ontology_id: string;              // UUID for resuming sessions
  semantic_version: string;         // "MAJOR.MINOR.PATCH" format
  title: string;                    // Domain name/title
  description: string;              // Domain description
  entities: EntityDefinition[];     // List of entities
  relationships: RelationshipDefinition[];  // List of relationships
  conversation_transcript?: string; // Full conversation history
  iteration_history: IterationRecord[];  // Change history
  current_version: number;           // Internal version counter
  created_at: string;               // ISO datetime
  updated_at: string;                // ISO datetime
  finalized: boolean;                // Whether user confirmed
}

interface EntityDefinition {
  entity_id: string;                // Temporary ID for references
  name: string;                      // Entity name
  description: string;               // Semantic description
  fields: FieldDefinition[];         // Entity fields
}

interface FieldDefinition {
  name: string;                      // Field name
  data_type: string;                 // "string", "integer", "float", "date", "boolean", etc.
  nullable: boolean;                 // Whether field can be null
  is_identifier: boolean;            // Whether this is an ID field
  description: string;                // Field description
}

interface RelationshipDefinition {
  relationship_id: string;           // Temporary ID
  from_entity: string;                // Source entity ID
  to_entity: string;                  // Target entity ID
  relationship_type: string;         // Relationship type name
  description: string;                // Relationship description
  cardinality?: string;               // "one-to-one", "one-to-many", "many-to-many"
}
```

---

## Semantic Versioning

The ontology uses semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** increments for breaking changes:
  - Removing an entity
  - Removing a relationship
  - Changing a field from nullable to required
  - Changing a field's data type

- **MINOR** increments for additive changes:
  - Adding a new entity
  - Adding a new relationship
  - Adding a new optional field

- **PATCH** increments for corrections:
  - Updating descriptions
  - Fixing typos
  - Minor refinements

**Display**: Show version prominently, e.g., "v1.2.3" or badge

---

## Best Practices

1. **Always sync user edits**: Include `current_ontology_package` in `user_message` events
2. **Debounce auto-save**: Don't send updates on every keystroke
3. **Show loading states**: Indicate when agent is processing
4. **Handle errors gracefully**: Allow retry, preserve state
5. **Visual feedback**: Highlight changes, show version updates
6. **Accessibility**: Ensure keyboard navigation, screen reader support
7. **Mobile responsive**: Support touch interactions for editing

---

## Testing Checklist

- [ ] Start new ontology workflow
- [ ] Resume existing ontology workflow
- [ ] Receive and display `ontology_proposed` event
- [ ] Edit ontology fields directly
- [ ] Send user messages with edits synced
- [ ] Receive and display `ontology_updated` events
- [ ] Finalize ontology
- [ ] Handle errors gracefully
- [ ] Display semantic version correctly
- [ ] Show relationship graph/visualization

---

## Support

For questions or issues, contact the backend team or refer to:
- Backend implementation: `app/workflows/ontology_creation/`
- Workflow entry point: `app/workflows/ontology_creation_workflow.py`
- Agent implementation: `app/workflows/ontology_creation/ontology_agent.py`
