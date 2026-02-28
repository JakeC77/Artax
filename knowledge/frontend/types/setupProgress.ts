/**
 * Unified Setup Progress Event Types
 *
 * These event types are used for all loading screens in the setup flow:
 * - Data Review: Staging entity data after scope confirmation
 * - Team Building: Configuring AI agents after data review
 *
 * Based on the analysis workflow pattern for consistency.
 */

// ============================================================================
// Phase Names
// ============================================================================

/** Phases during the setup loading flow */
export type SetupPhaseName =
  | 'staging_data'        // Data Review: fetching entity data from scope
  | 'building_team'       // Team Building: creating AI team configuration
  | 'configuring_agents'  // Team Building: setting up individual agents

/** Task types within a phase */
export type SetupTaskType =
  | 'entity'      // Fetching entity data (Prescription, Patient, etc.)
  | 'agent'       // Configuring an AI agent
  | 'query'       // Executing a Cypher query
  | 'validation'  // Validating data or configuration

/** Status of a task or phase */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

// ============================================================================
// SSE Event Types
// ============================================================================

/**
 * High-level phase tracking event.
 * Emitted when a phase starts or completes.
 */
export interface SetupPhaseEvent {
  event_type: 'setup_phase'
  message: string
  agent_id?: string
  timestamp?: string
  metadata: {
    phase_name: SetupPhaseName
    phase_index: number
    phase_total: number
    status: 'started' | 'completed'
  }
  // Legacy flat format support
  phase_name?: SetupPhaseName
  phase_index?: number
  phase_total?: number
  status?: 'started' | 'completed'
}

/**
 * Individual task progress event.
 * Emitted when a task starts, progresses, completes, or fails.
 */
export interface SetupTaskEvent {
  event_type: 'setup_task'
  message: string
  agent_id?: string
  timestamp?: string
  metadata: {
    task_id: string
    task_type: SetupTaskType
    title: string
    task_index: number
    task_total: number
    status: TaskStatus
    progress?: {
      current?: number
      total?: number
    }
    error?: string
  }
  // Legacy flat format support
  task_id?: string
  task_type?: SetupTaskType
  title?: string
  task_index?: number
  task_total?: number
  status?: TaskStatus
  progress?: number
  total?: number
  error?: string
}

/**
 * General status message event.
 * Used for informational messages that don't fit phase/task structure.
 */
export interface SetupStatusEvent {
  event_type: 'setup_status'
  message: string
  agent_id?: string
  timestamp?: string
}

/**
 * Flow completion event.
 * Emitted when the entire loading flow completes successfully.
 */
export interface SetupCompleteEvent {
  event_type: 'setup_complete'
  message: string
  agent_id?: string
  timestamp?: string
  metadata?: {
    phase_name?: SetupPhaseName
    summary?: {
      entities_staged?: number
      records_total?: number
      agents_configured?: number
    }
    next_stage?: string
  }
  // Legacy flat format support
  entities_staged?: number
  records_total?: number
  agents_configured?: number
  next_stage?: string
}

/**
 * Error event.
 * Emitted when an error occurs during the loading flow.
 */
export interface SetupErrorEvent {
  event_type: 'setup_error'
  message: string
  agent_id?: string
  timestamp?: string
  metadata?: {
    phase_name?: SetupPhaseName
    task_id?: string
    recoverable?: boolean
    error_code?: string
  }
  // Legacy flat format support
  error_code?: string
  recoverable?: boolean
}

/** Union of all setup progress event types */
export type SetupProgressEvent =
  | SetupPhaseEvent
  | SetupTaskEvent
  | SetupStatusEvent
  | SetupCompleteEvent
  | SetupErrorEvent

// ============================================================================
// State Types
// ============================================================================

/** Progress state for an individual task */
export interface SetupTask {
  id: string
  type: SetupTaskType
  title: string
  index: number
  total: number
  status: TaskStatus
  progress?: {
    current?: number
    total?: number
  }
  error?: string
}

/** Current phase information */
export interface SetupPhase {
  name: SetupPhaseName
  index: number
  total: number
  status: 'started' | 'completed'
}

/** Complete progress state for a loading flow */
export interface SetupProgressState {
  phase: SetupPhase | null
  tasks: SetupTask[]
  messages: string[]
  isComplete: boolean
  error: string | null
  summary: {
    entities_staged?: number
    records_total?: number
    agents_configured?: number
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/** Create initial empty progress state */
export function createInitialProgressState(): SetupProgressState {
  return {
    phase: null,
    tasks: [],
    messages: [],
    isComplete: false,
    error: null,
    summary: {},
  }
}

/** Calculate overall progress percentage (0-100) */
export function calculateSetupProgress(state: SetupProgressState): number {
  if (state.isComplete) return 100
  if (!state.phase) return 0

  const { tasks } = state

  if (tasks.length === 0) {
    // No tasks yet - show 10% if phase started
    return state.phase.status === 'started' ? 10 : 0
  }

  // Calculate based on task completion
  const completedTasks = tasks.filter((t) => t.status === 'completed').length
  const runningTasks = tasks.filter((t) => t.status === 'running').length

  // Running tasks count as 50% complete
  const effectiveComplete = completedTasks + runningTasks * 0.5
  const progress = (effectiveComplete / tasks.length) * 100

  // Reserve 10% for phase completion
  return Math.min(Math.round(progress * 0.9), 90)
}

/** Get human-readable phase display name */
export function getPhaseDisplayName(phaseName: SetupPhaseName): string {
  const displayNames: Record<SetupPhaseName, string> = {
    staging_data: 'Staging Data',
    building_team: 'Building AI Team',
    configuring_agents: 'Configuring Agents',
  }
  return displayNames[phaseName] || phaseName
}

/** Get human-readable task type label */
export function getTaskTypeLabel(taskType: SetupTaskType): string {
  const labels: Record<SetupTaskType, string> = {
    entity: 'Entity',
    agent: 'Agent',
    query: 'Query',
    validation: 'Validation',
  }
  return labels[taskType] || taskType
}

/**
 * Extract metadata from event, supporting both nested and flat formats.
 * This provides backward compatibility with older event formats.
 */
export function extractEventMetadata(
  event: SetupProgressEvent
): Record<string, unknown> {
  // If metadata object exists, prefer it
  if ('metadata' in event && event.metadata) {
    return event.metadata as Record<string, unknown>
  }

  // Fall back to extracting flat fields
  const flat: Record<string, unknown> = {}
  const metadataKeys = [
    'phase_name', 'phase_index', 'phase_total', 'status',
    'task_id', 'task_type', 'title', 'task_index', 'task_total',
    'progress', 'total', 'error', 'error_code', 'recoverable',
    'entities_staged', 'records_total', 'agents_configured', 'next_stage',
  ]

  for (const key of metadataKeys) {
    if (key in event && (event as unknown as Record<string, unknown>)[key] !== undefined) {
      flat[key] = (event as unknown as Record<string, unknown>)[key]
    }
  }

  return flat
}
