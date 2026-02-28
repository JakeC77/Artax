# Intent Collaboration: Overview & Vision

## Document Purpose

This document captures cross-repo decisions, rationale, and shared contracts for enabling real-time collaboration between the User (frontend) and AI Team (backend) on workspace intent.

**Related Specs:**
- [02_AI_SPEC.md](./02_AI_SPEC.md) - Backend implementation details
- [03_APP_SPEC.md](./03_APP_SPEC.md) - Frontend implementation details

---

## Problem Statement

Currently, the User and AI Team can both edit intent, but they operate in isolation:

1. **User** edits intent via the DraftView editor → saves to `workspace.intent`
2. **AI (Theo)** updates intent via conversation → emits events with `intent_package`
3. **No synchronization** → either side can overwrite the other without visibility
4. **Duplicate fields** → `workspace.intent` (markdown/JSON text) vs `workspace.setupIntentPackage` (structured object) can diverge

### Current Data Flow (Broken)

```
┌─────────────────┐          ┌─────────────────┐
│   USER WORLD    │          │    AI WORLD     │
│                 │          │                 │
│  TiptapEditor   │    ??    │   TheoState     │
│       ↓         │◄── ?? ──►│       ↓         │
│ workspace.intent│          │ intent_package  │
│  (markdown/JSON)│          │   (in-memory)   │
└─────────────────┘          └─────────────────┘
         │                           │
         └───────── NO SYNC ─────────┘
```

### Bugs This Causes

1. **State Overwrite** - User edits in editor, asks Theo to refine via chat, Theo overwrites user's edits because it doesn't see them
2. **Metadata Loss** - Full intent package (team_guidance, complexity) from Theo isn't persisted; only markdown paragraph saved to `intent` field

---

## Solution Overview

### Core Principle

**Pass intent state back and forth on every chat message.** The AI observes what changed and respects user edits unless explicitly asked to modify them.

### Target Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    BIDIRECTIONAL SYNC                           │
└─────────────────────────────────────────────────────────────────┘

User sends chat message:
┌──────────────┐                      ┌──────────────┐
│   Frontend   │ ──── user_message ──►│   Backend    │
│              │      + current       │              │
│  Structured  │      intent_package  │    Theo      │
│   Editor     │                      │              │
└──────────────┘                      └──────────────┘

AI responds with updates:
┌──────────────┐                      ┌──────────────┐
│   Frontend   │ ◄── intent_updated ──│   Backend    │
│              │     + full package   │              │
│  Structured  │     + update_summary │    Theo      │
│   Editor     │                      │              │
└──────────────┘                      └──────────────┘
```

---

## Key Decisions

### Decision 1: Single Source of Truth

**Use `setupIntentPackage` as the canonical representation. Deprecate `workspace.intent`.**

| Before | After |
|--------|-------|
| `workspace.intent` (text) | Deprecated |
| `workspace.setupIntentPackage` (JSON) | **Source of truth** |

**Rationale:**
- Structured JSON contains all metadata (team_guidance, complexity) that was being lost
- AI already produces this structure
- User edits map cleanly to specific fields
- Eliminates sync issues between two representations

**Migration:**
- Existing `intent` field data should be migrated to `setupIntentPackage` where possible
- New workspaces only write to `setupIntentPackage`
- Read logic falls back to `intent` if `setupIntentPackage` is null (transition period)

---

### Decision 2: Schema Versioning

**Add `schema_version` field to IntentPackage for future-proofing.**

```python
class IntentPackage(BaseModel):
    schema_version: int = 1  # Increment on breaking changes
    # ... rest of fields
```

**Rationale:**
- JSON blobs are harder to migrate than normalized tables
- Version field enables graceful schema evolution
- Pydantic validators can handle migrations on read

**Rules:**
- Prefer additive changes (new fields with defaults) over breaking changes
- Never rename or remove fields; add new ones and deprecate old
- Increment `schema_version` only for structural changes requiring migration logic

---

### Decision 3: Conflict Resolution Strategy

**User edits are authoritative. AI adapts.**

No locking. No merge UI. No conflict dialogs.

| Scenario | Behavior |
|----------|----------|
| User edits objective, then asks Theo to refine | Theo sees user's version, refines from there |
| User edits while Theo is generating | User's edit wins; Theo's next response sees updated state |
| Theo proposes changes user doesn't like | User edits directly; Theo respects on next message |

**Rationale:**
- Simplest mental model for users
- AI can always regenerate; user edits represent deliberate intent
- No blocking UX for "resolving conflicts"

**Implementation:**
- Frontend sends `current_intent_package` with every chat message
- Backend replaces its in-memory state with user's version before processing
- Theo's prompt instructs it to observe diffs and respect user edits

---

### Decision 4: No Explicit Save

**All edits are "live." Persistence happens on Continue.**

| Action | Result |
|--------|--------|
| User types in editor | Local state updates immediately |
| User sends chat message | Current state sent to AI |
| AI responds | Editor updates with AI's changes |
| User clicks Continue | Full package persisted to database |

**Rationale:**
- Removes cognitive overhead of "did I save?"
- Matches modern collaborative editing patterns (Google Docs, Notion)
- Simplifies state management (no dirty/clean distinction)

---

### Decision 5: Change Tracking is Optional

**Backend does not track which fields changed. Frontend can diff client-side if needed.**

**What backend sends:**
```typescript
{
  event_type: "intent_updated",
  intent_package: IntentPackage,
  update_summary?: string  // Natural language: "I refined the objective to focus on..."
}
```

**What backend does NOT send:**
```typescript
{
  changes: ["objective", "summary"]  // ❌ Not needed
}
```

**Rationale:**
- AI naturally explains changes in conversational form
- Frontend can diff `previousPackage` vs `newPackage` for UI badges if desired
- Reduces backend complexity

**Frontend option (not required):**
```typescript
// If you want "Updated" badges on sections
const changedFields = diffPackages(previousPackage, newPackage)
// Returns ['objective', 'summary'] if those changed
```

---

## Shared Data Contract

### IntentPackage Schema (v1)

This is the canonical structure both repos must agree on:

```typescript
interface IntentPackage {
  // Versioning
  schema_version: number  // Currently: 1
  
  // User-editable fields (rendered in structured editor)
  title: string
  description: string           // 100-200 char UI card display
  summary: string               // 2-4 sentence mission summary
  
  mission: {
    objective: string           // What user wants to accomplish
    why: string                 // Deeper motivation
    success_looks_like: string  // Success criteria
  }
  
  // AI metadata (not rendered to user, but persisted)
  team_guidance: {
    expertise_needed: string[]
    capabilities_needed: string[]
    complexity_level: "Simple" | "Moderate" | "Complex"
    complexity_notes: string
    collaboration_pattern: "Solo" | "Coordinated" | "Orchestrated"
    human_ai_handshake_points: string[]
    workflow_pattern: "OneTime" | "Recurring" | "Exploratory"
  }
  
  // Tracking
  conversation_transcript?: string
  iteration_history: IterationRecord[]
  current_version: number
  created_at: string  // ISO datetime
  confirmed: boolean
}
```

**User-editable fields:** `title`, `description`, `summary`, `mission.*`

**AI-only fields:** `team_guidance.*`, `conversation_transcript`, `iteration_history`, `current_version`, `created_at`, `confirmed`

---

## Event Contracts

### Frontend → Backend

**On every chat message:**

```typescript
{
  event_type: "user_message",
  content: string,                           // User's chat text
  current_intent_package: IntentPackage | null  // Full package with user edits
}
```

**On stage transition (Continue button):**

```typescript
{
  event_type: "end_intent",
  metadata: {
    final_intent_package: IntentPackage  // Package to persist
  }
}
```

### Backend → Frontend

**When Theo updates intent:**

```typescript
{
  event_type: "intent_updated",
  intent_package: IntentPackage,    // Full package with all metadata
  update_summary?: string           // Optional: natural language description of changes
}
```

**When intent is ready for review:**

```typescript
{
  event_type: "intent_proposed",
  intent_package: IntentPackage,
  ready: boolean
}
```

**When stage completes:**

```typescript
{
  event_type: "intent_finalized",
  intent_package: IntentPackage
}
```

---

## Migration Path

### Phase 1: Backend Changes
1. Add `schema_version` to IntentPackage model
2. Update event reader to accept `current_intent_package` in user messages
3. Update Theo's prompt to observe user edits
4. Emit `intent_updated` events with full package

### Phase 2: Frontend Changes
1. Build structured Tiptap editor with fixed sections
2. Update `useChatStream` to send `current_intent_package` with messages
3. Handle `intent_updated` events to refresh editor
4. Migrate reads from `intent` to `setupIntentPackage`

### Phase 3: Cleanup
1. Deprecate `workspace.intent` field
2. Migration script for existing workspaces (optional, can lazy-migrate on read)
3. Remove old markdown conversion logic

---

## Open Questions

1. **Offline/reconnection** - If user loses connection while AI is updating, how do we reconcile? (Suggest: user's local state wins on reconnect)

2. **Undo/redo** - Should the structured editor support undo across AI updates? (Suggest: yes, treat AI updates as undoable edits)

3. **Concurrent sessions** - What if user has two tabs open? (Suggest: out of scope for v1, last-write-wins)

---

## Success Criteria

- [ ] User can edit intent in structured editor
- [ ] User can ask Theo to refine intent via chat
- [ ] Theo sees user's edits and incorporates them
- [ ] User's edits are never silently overwritten
- [ ] Full intent package (including team_guidance) persists to workspace
- [ ] No duplicate/conflicting data between `intent` and `setupIntentPackage`