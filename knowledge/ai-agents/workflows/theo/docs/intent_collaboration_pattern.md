# Intent Collaboration Pattern: Bidirectional State Sync

## Overview

This document describes the **bidirectional intent collaboration pattern** implemented between the Theo backend (AI agent) and the frontend structured editor. This pattern enables real-time collaborative editing where both the user and AI can modify shared state without overwriting each other's changes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  Chat Panel     │    │ Structured Editor │    │  Event Stream     │  │
│  │                 │    │ (Intent Fields)   │    │  Client           │  │
│  │  - User input   │    │                   │    │                   │  │
│  │  - AI messages  │    │  - Title          │    │  - Send events    │  │
│  │                 │    │  - Objective      │    │  - Receive events │  │
│  │                 │    │  - Why            │    │                   │  │
│  │                 │    │  - Success        │    │                   │  │
│  └─────────────────┘    └──────────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            user_message    intent_updated    end_intent
            (with current   (from backend)    (with final
             intent state)                     intent state)
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  IntentBuilder  │───▶│   TheoState      │◀───│  Theo Agent       │  │
│  │                 │    │                   │    │  (AI)             │  │
│  │  - Sync state   │    │  - intent_package │    │                   │  │
│  │  - Merge edits  │    │  - broadcast flag │    │  - Tools          │  │
│  │  - Emit events  │    │                   │    │  - Prompts        │  │
│  └─────────────────┘    └──────────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Event Types

### Frontend → Backend

| Event Type | Payload | Purpose |
|------------|---------|---------|
| `user_message` | `{ message, current_intent_package?, user_edited_fields? }` | User sends chat message with current editor state and list of edited fields |
| `end_intent` | `{ final_intent_package? }` | User clicks Continue button to finalize |

#### user_edited_fields

The frontend tracks which fields the user edited since the last AI update. This allows Theo to acknowledge user changes naturally.

```python
{
  "event_type": "user_message",
  "message": "Can you make the success criteria more specific?",
  "current_intent_package": {...},
  "user_edited_fields": ["mission.objective", "mission.why"]  # Fields user touched
}
```

If no fields were edited, send empty list or omit the field entirely.

### Backend → Frontend

| Event Type | Payload | Purpose |
|------------|---------|---------|
| `intent_updated` | `{ intent_package, update_summary? }` | AI modified intent fields via tools |
| `intent_proposed` | `{ intent_package, ready: true }` | AI has drafted complete intent, ready for review |
| `intent_finalized` | `{ intent_package, intent_text }` | Intent confirmed, proceeding to next stage |
| `agent_message` | `{ message }` | AI's conversational response |

---

## Data Model

### IntentPackage Schema (v1)

```typescript
interface IntentPackage {
  // Schema versioning
  schema_version: number;  // Currently 1

  // User-editable fields (synced bidirectionally)
  title: string;
  description: string;
  summary: string;
  mission: {
    objective: string;
    why: string;
    success_looks_like: string;
  };

  // AI-managed metadata (preserved on merge, not shown in editor)
  team_guidance: {
    expertise_needed: string[];
    capabilities_needed: string[];
    complexity_level: "Simple" | "Moderate" | "Complex";
    complexity_notes: string;
    collaboration_pattern: "Solo" | "Coordinated" | "Orchestrated";
    human_ai_handshake_points: string[];
    workflow_pattern: "OneTime" | "Recurring" | "Exploratory";
  };
  conversation_transcript: string | null;
  iteration_history: IterationRecord[];
  current_version: number;
  created_at: string;  // ISO timestamp
  confirmed: boolean;
}
```

### Field Ownership

| Field Category | Owner | Sync Behavior |
|----------------|-------|---------------|
| User-facing fields (title, summary, mission.*) | **User authoritative** | Frontend → Backend on each message |
| AI metadata (team_guidance.*) | **AI authoritative** | Backend → Frontend, preserved on merge |
| Version tracking | **System** | Incremented on any edit |

---

## Sync Protocol

### 1. User Sends Message

```
Frontend                                    Backend
   │                                           │
   │  user_message                             │
   │  {                                        │
   │    message: "Make it more specific",      │
   │    current_intent_package: { ... }        │
   │  }                                        │
   │  ─────────────────────────────────────▶   │
   │                                           │
   │                          _sync_intent_from_user()
   │                          _merge_user_edits()
   │                                           │
   │                          Process with Theo agent
   │                                           │
```

### 2. AI Updates Intent

```
Frontend                                    Backend
   │                                           │
   │                          Theo calls update_intent_package()
   │                          Sets intent_needs_broadcast = true
   │                                           │
   │                          After agent response:
   │                          _emit_intent_updated()
   │                                           │
   │  intent_updated                           │
   │  {                                        │
   │    intent_package: { ... },               │
   │    update_summary: "Updated: objective"   │
   │  }                                        │
   │  ◀─────────────────────────────────────   │
   │                                           │
   │  Update editor fields                     │
   │                                           │
```

### 3. User Confirms Intent

```
Frontend                                    Backend
   │                                           │
   │  end_intent                               │
   │  {                                        │
   │    final_intent_package: { ... }          │
   │  }                                        │
   │  ─────────────────────────────────────▶   │
   │                                           │
   │                          _sync_intent_from_user()
   │                          Mark finalized
   │                                           │
   │  intent_finalized                         │
   │  {                                        │
   │    intent_package: { ... }                │
   │  }                                        │
   │  ◀─────────────────────────────────────   │
   │                                           │
```

---

## Merge Strategy

When the backend receives `current_intent_package` from the frontend:

```python
def _merge_user_edits(existing: IntentPackage, user_edited: IntentPackage) -> IntentPackage:
    return IntentPackage(
        schema_version=existing.schema_version,

        # User-editable fields: TAKE FROM USER
        title=user_edited.title,
        description=user_edited.description,
        summary=user_edited.summary,
        mission=Mission(
            objective=user_edited.mission.objective,
            why=user_edited.mission.why,
            success_looks_like=user_edited.mission.success_looks_like
        ),

        # AI metadata: PRESERVE EXISTING
        team_guidance=existing.team_guidance,
        conversation_transcript=existing.conversation_transcript,
        iteration_history=existing.iteration_history,
        current_version=existing.current_version + 1,
        created_at=existing.created_at,
        confirmed=existing.confirmed,
    )
```

---

## AI Awareness of User Edits

The AI (Theo) is made aware of user edits through dynamic prompt injection:

```python
@agent.instructions
def inject_current_intent_state(ctx: RunContext[TheoState]) -> str:
    if ctx.deps.mode == "intent" and ctx.deps.intent_package is not None:
        pkg = ctx.deps.intent_package
        return f"""
## CURRENT INTENT STATE (LIVE FROM USER'S EDITOR)

CURRENT VALUES:
- Title: {pkg.title}
- Objective: {pkg.mission.objective}
- Why: {pkg.mission.why}
- Success Looks Like: {pkg.mission.success_looks_like}
"""
    return ""
```

Additionally, the frontend sends `user_edited_fields` with each message, which is injected into Theo's context:

```python
@agent.instructions
def inject_user_edit_awareness(ctx: RunContext[TheoState]) -> str:
    """Inject user edited fields so Theo knows what the user changed."""
    if ctx.deps.mode == "intent" and ctx.deps.user_edited_fields:
        fields_list = ", ".join(ctx.deps.user_edited_fields)
        return f"""
## USER EDITS

The user has edited the following fields since your last update: {fields_list}

Acknowledge briefly if relevant. Do not overwrite these unless explicitly asked.
"""
    return ""
```

When Theo calls `update_intent_package`, the `user_edited_fields` list is cleared since the AI has now made an update.

---

## Error Handling

### Malformed Package

```python
try:
    user_package = IntentPackage(**user_package_data)
except ValidationError as e:
    logfire.warning("Failed to parse user intent package", error=str(e))
    # Continue with existing state - don't crash
```

### Missing Package (Backward Compatibility)

```python
# Frontend without this feature sends no current_intent_package
if event_metadata and event_type == "user_message":
    user_intent_package = event_metadata.get("current_intent_package")
    if user_intent_package:  # Only sync if present
        self._sync_intent_from_user(user_intent_package)
```

---

## Frontend Implementation Requirements

### Sending Messages

```typescript
// When user sends a chat message
eventStream.send({
  event_type: "user_message",
  message: userInput,
  current_intent_package: getCurrentIntentState()  // Serialize editor state
});
```

### Receiving Updates

```typescript
// When backend sends intent_updated
eventStream.on("intent_updated", (event) => {
  const { intent_package, update_summary } = event.metadata;
  updateEditorFields(intent_package);
  // Optionally show toast: "AI updated: {update_summary}"
});
```

### Confirming Intent

```typescript
// When user clicks Continue
eventStream.send({
  event_type: "end_intent",
  data: {
    intent_package: JSON.stringify(getCurrentIntentState())
  }
});
```

---

## Key Design Decisions

1. **User edits are authoritative** for user-facing fields - the frontend is the source of truth for what the user typed.

2. **AI metadata is preserved** - team_guidance and other backend-only fields are never overwritten by frontend sync.

3. **Graceful degradation** - missing or malformed packages don't crash the workflow; we log and continue.

4. **Version incrementing** - every edit (user or AI) bumps `current_version` for tracking.

5. **No content duplication** - AI doesn't repeat intent content in chat since it's visible in the editor.

---

## Files Involved

| File | Purpose |
|------|---------|
| `models.py` | `IntentPackage` schema with `schema_version` and migration validator |
| `theo_agent.py` | `TheoState` with broadcast signals, dynamic prompt injection |
| `intent_builder.py` | `_sync_intent_from_user()`, `_merge_user_edits()`, `_emit_intent_updated()` |
| `tools.py` | `update_intent_package` sets broadcast flag, `propose_intent` validation |
| `theo_intent_instructions.md` | AI instructions for respecting user edits |

---

## Future Considerations

1. **Field-level change tracking** - Currently we sync entire package; could optimize to send only changed fields.

2. **Conflict resolution UI** - If AI and user edit the same field simultaneously, show diff and let user choose.

3. **Schema migrations** - `@model_validator` is ready for v2+ migrations when schema evolves.

4. **Undo/redo** - `iteration_history` could be extended to support rollback.
