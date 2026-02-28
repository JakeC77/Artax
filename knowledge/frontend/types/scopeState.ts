/**
 * ScopeState Types for Unified Data Scoping
 *
 * These types define the structure for the merged Data Scoping + Data Review experience.
 * The ScopeState represents the complete state of a data scope query including entities,
 * filters, relationships, and preview data.
 */

// ============================================================================
// Core Filter Types
// ============================================================================

export type FilterOperator =
  | 'equals'
  | 'not_equals'
  | 'greater_than'
  | 'greater_than_or_equal'
  | 'less_than'
  | 'less_than_or_equal'
  | 'between'
  | 'in'
  | 'not_in'
  | 'contains'
  | 'starts_with'
  | 'ends_with'

export interface Filter {
  id: string
  property: string
  operator: FilterOperator | string
  value: string | string[] | number | number[] | boolean | null
  display_text: string // Human-readable, e.g., "state = CA"
  reasoning?: string // Why this filter exists
}

// ============================================================================
// Field of Interest Types
// ============================================================================

export interface FieldOfInterest {
  field: string
  justification: string
}

// ============================================================================
// Relationship Types
// ============================================================================

export interface Relationship {
  from_entity: string
  to_entity: string
  relationship_type: string // Graph relationship type, e.g., "HAS_MEMBER"
  display_label: string // Human-readable, e.g., "has member"
  reasoning?: string
}

// ============================================================================
// Entity Types
// ============================================================================

export type RelevanceLevel = 'primary' | 'related' | 'contextual'

export interface ScopeEntity {
  entity_type: string
  relevance_level: RelevanceLevel
  reasoning: string // "What is this?" explanation
  enabled: boolean // Whether entity is included (primary always true)
  filters: Filter[]
  fields_of_interest: FieldOfInterest[]
  estimated_count: number | null // null = not yet calculated, 0 = actual zero records
  query?: string // Cypher query for fetching this entity's data
}

// ============================================================================
// Tab State
// ============================================================================

export type ScopeTab = 'build_query' | 'preview_data'

// ============================================================================
// Main ScopeState Type
// ============================================================================

export interface ScopeState {
  // === Query Structure ===
  primary_entity: string // Cannot be changed by user
  entities: ScopeEntity[] // All entities in scope
  relationships: Relationship[] // How entities connect

  // === Execution Results ===
  counts: Record<string, number> // Entity → record count
  samples: Record<string, Record<string, unknown>[]> // Entity → sample records (10-20)
  full_data: Record<string, Record<string, unknown>[]> | null // Entity → all records (loaded on Preview tab)

  // === Metadata ===
  natural_language_summary: string // AI-generated description
  confidence: 'low' | 'medium' | 'high'
  last_updated?: string // ISO timestamp
  last_update_summary?: string // "Added Zoloft to medication filter"

  // === UI State ===
  active_tab: ScopeTab
  preview_loading: boolean
  selected_preview_entity: string // Which entity tab is selected in preview
}

// ============================================================================
// Helper Types for UI Interactions
// ============================================================================

/**
 * Represents a pending scope change awaiting AI confirmation.
 * Used to show optimistic UI updates while AI processes the request.
 */
export interface PendingScopeChange {
  id: string
  change_type: 'add_entity' | 'remove_entity' | 'add_filter' | 'edit_filter' | 'remove_filter'
  description: string // Natural language description of the change
  timestamp: number
}

/**
 * Props for chat message generation from UI interactions.
 * Each UI action generates a structured message for the AI.
 */
export interface ScopeChangeMessage {
  action: 'add_entity' | 'remove_entity' | 'toggle_entity' | 'add_filter' | 'edit_filter' | 'remove_filter'
  entity_type?: string
  filter?: Partial<Filter>
  justification?: string // Required for adding entities
  natural_language: string // The message to send to chat
}

// ============================================================================
// Type Guards
// ============================================================================

export function isValidRelevanceLevel(value: unknown): value is RelevanceLevel {
  return value === 'primary' || value === 'related' || value === 'contextual'
}

export function isValidScopeTab(value: unknown): value is ScopeTab {
  return value === 'build_query' || value === 'preview_data'
}

export function isPrimaryEntity(entity: ScopeEntity): boolean {
  return entity.relevance_level === 'primary'
}

// ============================================================================
// Default/Empty State Factories
// ============================================================================

export function createEmptyScopeState(primaryEntity: string): ScopeState {
  return {
    primary_entity: primaryEntity,
    entities: [],
    relationships: [],
    counts: {},
    samples: {},
    full_data: null,
    natural_language_summary: '',
    confidence: 'low',
    active_tab: 'build_query',
    preview_loading: false,
    selected_preview_entity: primaryEntity,
  }
}

export function createEmptyFilter(): Filter {
  return {
    id: crypto.randomUUID(),
    property: '',
    operator: 'equals',
    value: '',
    display_text: '',
  }
}
