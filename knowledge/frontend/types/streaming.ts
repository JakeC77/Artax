// Streaming Event Types for SSE Communication
// These types define the structure of events received from the backend via Server-Sent Events

import type { IntentPackage, DataScope, ExecutionResult, TeamConfig } from '../services/graphql'
import type { ScopeState } from './scopeState'

// ============================================================================
// Base Types
// ============================================================================

export interface BaseStreamEvent {
  event_type: string
  agent_id?: string
  subtask_id?: string
  timestamp?: number
  message?: string
}

// ============================================================================
// Agent Message Events (Streaming Text)
// ============================================================================

export interface AgentMessageEvent extends BaseStreamEvent {
  event_type: 'agent_message'
  message: string
  message_id: string
  completed: boolean
  accumulated_length?: number
  part_index?: number
}

export interface AgentThinkingEvent extends BaseStreamEvent {
  event_type: 'agent_thinking'
}

export interface AgentCompletedEvent extends BaseStreamEvent {
  event_type: 'agent_completed'
}

export interface ToolCalledEvent extends BaseStreamEvent {
  event_type: 'tool_called'
  tool_name?: string
}

// ============================================================================
// Task/Workflow Events
// ============================================================================

export interface TaskDecomposedEvent extends BaseStreamEvent {
  event_type: 'task_decomposed'
  subtasks?: string[]
}

export interface SubtaskAssignedEvent extends BaseStreamEvent {
  event_type: 'subtask_assigned'
  subtask?: string
}

export interface TaskCompletedEvent extends BaseStreamEvent {
  event_type: 'task_completed'
  result?: string
}

export interface UserMessageEvent extends BaseStreamEvent {
  event_type: 'user_message'
  message: string
  clarification_responses?: Array<{ question_id: string }>
}

export interface WorkflowStageEvent extends BaseStreamEvent {
  event_type: 'workflow_stage'
  stage?: string
}

// ============================================================================
// Intent Events
// ============================================================================

export interface IntentProposedEvent extends BaseStreamEvent {
  event_type: 'intent_proposed'
  intent_text?: string
  intent_package?: IntentPackage | null
}

export interface IntentFinalizedEvent extends BaseStreamEvent {
  event_type: 'intent_finalized'
  intent_text?: string
  intent_package?: IntentPackage | null
}

export interface IntentUpdatedEvent extends BaseStreamEvent {
  event_type: 'intent_updated'
  intent_package: IntentPackage
  update_summary?: string
}

export interface IntentReadyEvent extends BaseStreamEvent {
  event_type: 'intent_ready'
  intent_package?: IntentPackage | null
  intent_text?: string
  title?: string
  summary?: string
  objective?: string
  why?: string
  success_looks_like?: string
  ready?: boolean
}

// ============================================================================
// Data Scope Events
// ============================================================================

export interface ScopeEntity {
  entity_type: string
  relevance_level?: 'primary' | 'related' | 'contextual'
  filters?: ScopeFilter[]
  fields_of_interest?: string[]
  reasoning?: string
  estimated_count?: number
}

export interface ScopeFilter {
  property: string
  operator: string
  value: unknown
  reasoning?: string
}

export interface ScopeRelationship {
  from_entity: string
  to_entity: string
  relationship_type: string
  reasoning?: string
}

export interface ScopeUpdateEvent extends BaseStreamEvent {
  event_type: 'scope_update' | 'scope_updated' | 'scope_ready'
  // Legacy format (backward compatibility)
  data_scope?: DataScope
  entities?: ScopeEntity[]
  relationships?: ScopeRelationship[]
  summary?: string
  confidence?: 'low' | 'medium' | 'high'
  ready?: boolean
  // New unified format
  scope_state?: ScopeState
  update_summary?: string // Human-readable change description
  changed_entities?: string[] // Which entities were affected by the update
  // Entity update metadata
  is_new_entity?: boolean
  added_filter_ids?: string[]
  changed_filter_ids?: string[]
  added_field_names?: string[]
  changed_field_names?: string[]
}

// ============================================================================
// Preview Data Events (for streaming data to preview tab)
// ============================================================================

export interface PreviewDataEvent extends BaseStreamEvent {
  event_type: 'preview_data'
  entity_type: string
  data: Record<string, unknown>[]
  total_count: number
  page?: number
  page_size?: number
  is_complete: boolean
}

// ============================================================================
// Clarification Events
// ============================================================================

export interface ClarificationOption {
  label: string
  description: string
  recommended?: boolean
}

export interface ClarificationNeededEvent extends BaseStreamEvent {
  event_type: 'clarification_needed'
  question_id: string
  question: string
  context?: string
  options: ClarificationOption[]
  affects_entities?: string[]
  stage?: string
}

// ============================================================================
// Execution Events
// ============================================================================

export interface EntityCompleteEvent extends BaseStreamEvent {
  event_type: 'entity_complete'
  entity_type?: string
  total_count?: number
}

export interface ExecutionCompleteEvent extends BaseStreamEvent {
  event_type: 'execution_complete'
  results?: ExecutionResult[]
}

// ============================================================================
// Team Building Events
// ============================================================================

export interface TeamBuildingStartedEvent extends BaseStreamEvent {
  event_type: 'team_building_started'
}

export interface TeamCompleteEvent extends BaseStreamEvent {
  event_type: 'team_complete'
  team_config?: TeamConfig
  teamConfig?: TeamConfig // Alternative camelCase field name
}

// ============================================================================
// Setup Task Events (Data Staging Progress)
// ============================================================================

export interface SetupTaskEvent extends BaseStreamEvent {
  event_type: 'setup_task'
  task_id?: string
  task_type?: 'entity' | 'agent' | string
  title?: string
  status?: 'pending' | 'running' | 'completed' | 'failed'
  task_index?: number
  task_total?: number
  progress?: { current: number; total: number }
}

// ============================================================================
// Setup Complete Events
// ============================================================================

export interface SetupCompleteEvent extends BaseStreamEvent {
  event_type: 'setup_complete'
  stage?: string
  team_name?: string
  team_size?: number
  entity_count?: number
  total_matches?: number
  execution_success?: boolean
  intent_title?: string
  intent_summary?: string
  scope_summary?: string
  selected_node_count?: number
}

export interface WorkflowCompleteEvent extends BaseStreamEvent {
  event_type: 'workflow_complete'
  stage?: string
  team_name?: string
  team_size?: number
}

// ============================================================================
// Error Events
// ============================================================================

export interface ErrorEvent extends BaseStreamEvent {
  event_type: 'error'
  error?: string
  stage?: string
}

export interface WorkflowErrorEvent extends BaseStreamEvent {
  event_type: 'workflow_error'
  error?: string
  stage?: string
}

// ============================================================================
// Ontology workflow events
// ============================================================================

export interface OntologyProposedEvent extends BaseStreamEvent {
  event_type: 'ontology_proposed'
  ontology_package?: unknown
  metadata?: { ontology_package?: unknown }
}

export interface OntologyUpdatedEvent extends BaseStreamEvent {
  event_type: 'ontology_updated'
  ontology_package?: unknown
  update_summary?: string
  metadata?: { ontology_package?: unknown; update_summary?: string }
}

export interface OntologyFinalizedEvent extends BaseStreamEvent {
  event_type: 'ontology_finalized'
  ontology_package?: unknown
  metadata?: { ontology_package?: unknown }
}

export interface WorkflowStartedEvent extends BaseStreamEvent {
  event_type: 'workflow_started'
}

// ============================================================================
// Data loading / CSV events
// ============================================================================

export interface NodesCreatedEvent extends BaseStreamEvent {
  event_type: 'nodes_created'
  created?: number
  total?: number
  message?: string
}

export interface RelationshipsCreatedEvent extends BaseStreamEvent {
  event_type: 'relationships_created'
  created?: number
  total?: number
  message?: string
}

export interface CsvAnalyzedEvent extends BaseStreamEvent {
  event_type: 'csv_analyzed'
  message?: string
  columns?: unknown[]
  row_count?: number
  has_headers?: boolean
}

// ============================================================================
// Union Types
// ============================================================================

export type StreamEvent =
  | AgentMessageEvent
  | AgentThinkingEvent
  | AgentCompletedEvent
  | ToolCalledEvent
  | TaskDecomposedEvent
  | SubtaskAssignedEvent
  | TaskCompletedEvent
  | UserMessageEvent
  | WorkflowStageEvent
  | IntentProposedEvent
  | IntentFinalizedEvent
  | IntentUpdatedEvent
  | IntentReadyEvent
  | ScopeUpdateEvent
  | PreviewDataEvent
  | ClarificationNeededEvent
  | EntityCompleteEvent
  | ExecutionCompleteEvent
  | SetupTaskEvent
  | SetupCompleteEvent
  | WorkflowCompleteEvent
  | TeamBuildingStartedEvent
  | TeamCompleteEvent
  | ErrorEvent
  | WorkflowErrorEvent
  | OntologyProposedEvent
  | OntologyUpdatedEvent
  | OntologyFinalizedEvent
  | WorkflowStartedEvent
  | NodesCreatedEvent
  | RelationshipsCreatedEvent
  | CsvAnalyzedEvent

// ============================================================================
// Type Guards
// ============================================================================

export function isAgentMessageEvent(event: StreamEvent): event is AgentMessageEvent {
  return event.event_type === 'agent_message'
}

export function isClarificationNeededEvent(event: StreamEvent): event is ClarificationNeededEvent {
  return event.event_type === 'clarification_needed'
}

export function isIntentProposedEvent(event: StreamEvent): event is IntentProposedEvent {
  return event.event_type === 'intent_proposed'
}

export function isIntentUpdatedEvent(event: StreamEvent): event is IntentUpdatedEvent {
  return event.event_type === 'intent_updated'
}

export function isScopeUpdateEvent(event: StreamEvent): event is ScopeUpdateEvent {
  return event.event_type === 'scope_update' || event.event_type === 'scope_updated' || event.event_type === 'scope_ready'
}

export function isErrorEvent(event: StreamEvent): event is ErrorEvent {
  return event.event_type === 'error'
}

export function isTaskCompletedEvent(event: StreamEvent): event is TaskCompletedEvent {
  return event.event_type === 'task_completed'
}

export function isTeamCompleteEvent(event: StreamEvent): event is TeamCompleteEvent {
  return event.event_type === 'team_complete'
}

export function isPreviewDataEvent(event: StreamEvent): event is PreviewDataEvent {
  return event.event_type === 'preview_data'
}

export function isExecutionCompleteEvent(event: StreamEvent): event is ExecutionCompleteEvent {
  return event.event_type === 'execution_complete'
}
