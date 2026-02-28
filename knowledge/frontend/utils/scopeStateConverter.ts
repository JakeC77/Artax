/**
 * ScopeState Converter Utility
 *
 * Provides backward compatibility by converting legacy DataScope format
 * to the new unified ScopeState format.
 */

import type { DataScope, DataScopeEntity, ExecutionResult } from '../services/graphql'
import type {
  ScopeState,
  ScopeEntity,
  Relationship,
  Filter,
  FieldOfInterest,
  RelevanceLevel,
} from '../types/scopeState'

/**
 * Convert a legacy DataScope to the new ScopeState format.
 * Used when receiving scope_ready events with data_scope instead of scope_state.
 */
export function convertDataScopeToScopeState(dataScope: DataScope): ScopeState {
  // Guard: If dataScope or scopes is null/undefined, return empty state
  if (!dataScope || !dataScope.scopes || !Array.isArray(dataScope.scopes)) {
    return {
      primary_entity: '',
      entities: [],
      relationships: [],
      counts: {},
      samples: {},
      full_data: null,
      natural_language_summary: '',
      confidence: 'medium',
      active_tab: 'build_query',
      preview_loading: false,
      selected_preview_entity: '',
    }
  }

  // Find the primary entity (first one with relevance_level === 'primary', or fallback to first entity)
  const primaryEntity =
    dataScope.scopes.find((s) => s.relevance_level === 'primary')?.entity_type ||
    dataScope.scopes[0]?.entity_type ||
    ''

  // Convert entities
  const entities: ScopeEntity[] = dataScope.scopes.map((scope) =>
    convertDataScopeEntityToScopeEntity(scope)
  )

  // Convert relationships
  const relationships: Relationship[] = (dataScope.relationships || []).map((rel) => ({
    from_entity: rel.from_entity,
    to_entity: rel.to_entity,
    relationship_type: rel.relationship_type,
    display_label: humanizeRelationshipType(rel.relationship_type),
    reasoning: rel.reasoning,
  }))

  // Build counts map from estimated_count
  const counts: Record<string, number> = {}
  for (const scope of dataScope.scopes) {
    counts[scope.entity_type] = scope.estimated_count
  }

  // Handle both confidence and confidence_level from backend
  const rawConfidence = dataScope.confidence || (dataScope as Record<string, unknown>).confidence_level
  const confidence = (rawConfidence === 'low' || rawConfidence === 'medium' || rawConfidence === 'high')
    ? rawConfidence
    : 'medium'

  return {
    primary_entity: primaryEntity,
    entities,
    relationships,
    counts,
    samples: {},
    full_data: null,
    natural_language_summary: dataScope.summary || '',
    confidence,
    active_tab: 'build_query',
    preview_loading: false,
    selected_preview_entity: primaryEntity,
  }
}

/**
 * Convert a single DataScopeEntity to ScopeEntity format.
 */
function convertDataScopeEntityToScopeEntity(entity: DataScopeEntity): ScopeEntity {
  // Handle both reasoning and rationale from backend
  const reasoning = entity.reasoning || (entity as Record<string, unknown>).rationale as string || ''

  return {
    entity_type: entity.entity_type,
    relevance_level: validateRelevanceLevel(entity.relevance_level),
    reasoning,
    enabled: true, // All entities from DataScope are enabled
    filters: convertFilters(entity.filters),
    fields_of_interest: convertFieldsOfInterest(entity.fields_of_interest),
    estimated_count: entity.estimated_count,
    query: entity.query, // Preserve Cypher query if provided by AI
  }
}

/**
 * Convert legacy filter format to new Filter format.
 * Legacy filters can be objects with property/operator/value or plain strings.
 */
function convertFilters(filters: unknown[]): Filter[] {
  if (!Array.isArray(filters)) return []

  return filters.map((filter, index) => {
    if (typeof filter === 'string') {
      // Plain string filter
      return {
        id: `filter-${index}-${Date.now()}`,
        property: '',
        operator: 'equals',
        value: filter,
        display_text: filter,
      }
    }

    if (typeof filter === 'object' && filter !== null) {
      const f = filter as Record<string, unknown>
      const property = String(f.property || f.field || '')
      const operator = String(f.operator || 'equals')
      const value = f.value
      const reasoning = f.reasoning ? String(f.reasoning) : undefined
      // Use backend-provided id if available, otherwise generate one
      const id = f.id ? String(f.id) : `filter-${index}-${Date.now()}`
      // Use backend-provided display_text if available
      const displayText = f.display_text ? String(f.display_text) : formatFilterDisplayText(property, operator, value)

      return {
        id,
        property,
        operator,
        value: value as Filter['value'],
        display_text: displayText,
        reasoning,
      }
    }

    // Fallback for unknown format
    return {
      id: `filter-${index}-${Date.now()}`,
      property: '',
      operator: 'equals',
      value: String(filter),
      display_text: String(filter),
    }
  })
}

/**
 * Convert fields_of_interest from DataScopeEntity format.
 */
function convertFieldsOfInterest(
  fields: DataScopeEntity['fields_of_interest']
): FieldOfInterest[] {
  if (!Array.isArray(fields)) return []

  return fields.map((field) => {
    if (typeof field === 'string') {
      return { field, justification: '' }
    }
    return {
      field: field.field || '',
      justification: field.justification || '',
    }
  })
}

/**
 * Validate and normalize relevance level.
 */
function validateRelevanceLevel(level: unknown): RelevanceLevel {
  if (level === 'primary' || level === 'related' || level === 'contextual') {
    return level
  }
  return 'related' // Default to related if not specified
}

/**
 * Convert relationship type from SCREAMING_SNAKE_CASE to human-readable format.
 * e.g., "HAS_MEMBER" → "has member"
 */
function humanizeRelationshipType(relationshipType: string): string {
  return relationshipType
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char) // Keep lowercase
}

/**
 * Format a filter into a human-readable display string.
 */
function formatFilterDisplayText(property: string, operator: string, value: unknown): string {
  if (!property) {
    return String(value)
  }

  const operatorSymbols: Record<string, string> = {
    equals: '=',
    not_equals: '≠',
    greater_than: '>',
    greater_than_or_equal: '≥',
    less_than: '<',
    less_than_or_equal: '≤',
    between: 'between',
    in: 'IN',
    not_in: 'NOT IN',
    contains: 'contains',
    starts_with: 'starts with',
    ends_with: 'ends with',
  }

  const opSymbol = operatorSymbols[operator] || operator

  if (Array.isArray(value)) {
    if (operator === 'between' && value.length === 2) {
      return `${property} ${opSymbol} ${value[0]} and ${value[1]}`
    }
    return `${property} ${opSymbol} [${value.join(', ')}]`
  }

  return `${property} ${opSymbol} ${value}`
}

/**
 * Merge execution results into an existing ScopeState.
 * Updates counts and samples from the execution results.
 */
export function mergeExecutionResultsIntoScopeState(
  scopeState: ScopeState,
  executionResults: ExecutionResult[]
): ScopeState {
  const newCounts = { ...scopeState.counts }
  const newSamples = { ...scopeState.samples }

  for (const result of executionResults) {
    newCounts[result.entity_type] = result.total_count
    newSamples[result.entity_type] = result.sample_data || []
  }

  return {
    ...scopeState,
    counts: newCounts,
    samples: newSamples,
  }
}

/**
 * Update a single entity's enabled status in the ScopeState.
 * Returns a new ScopeState with the updated entity.
 */
export function updateEntityEnabled(
  scopeState: ScopeState,
  entityType: string,
  enabled: boolean
): ScopeState {
  return {
    ...scopeState,
    entities: scopeState.entities.map((entity) =>
      entity.entity_type === entityType ? { ...entity, enabled } : entity
    ),
  }
}

/**
 * Get all enabled entities from a ScopeState.
 */
export function getEnabledEntities(scopeState: ScopeState): ScopeEntity[] {
  return scopeState.entities.filter((entity) => entity.enabled)
}

/**
 * Get the primary entity from a ScopeState.
 */
export function getPrimaryEntity(scopeState: ScopeState): ScopeEntity | undefined {
  return scopeState.entities.find((entity) => entity.relevance_level === 'primary')
}

/**
 * Count total filters across all entities.
 */
export function getTotalFilterCount(scopeState: ScopeState): number {
  return scopeState.entities.reduce((total, entity) => total + entity.filters.length, 0)
}

/**
 * Count total fields of interest across all entities.
 */
export function getTotalFieldsOfInterestCount(scopeState: ScopeState): number {
  return scopeState.entities.reduce(
    (total, entity) => total + entity.fields_of_interest.length,
    0
  )
}
