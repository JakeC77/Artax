// Analysis Workflow Types
// Based on ANALYSIS_WORKFLOW_FRONTEND_IMPLEMENTATION.md

// Backend phase names from the workflow
// These match the actual SSE events emitted by the backend
export type BackendPhase =
  | 'planning_analysis'
  | 'executing_analysis'
  | 'planning_scenarios'
  | 'executing_scenarios'

// Simplified UI phase names (4 phases)
export type UIPhase = 'planning' | 'analyzing' | 'modeling' | 'scenarios'

// Map backend phases to UI phases
export const PHASE_MAPPING: Record<BackendPhase, UIPhase> = {
  planning_analysis: 'planning',
  executing_analysis: 'analyzing',
  planning_scenarios: 'modeling',
  executing_scenarios: 'scenarios',
}

export const UI_PHASE_ORDER: UIPhase[] = ['planning', 'analyzing', 'modeling', 'scenarios']

export const UI_PHASE_LABELS: Record<UIPhase, string> = {
  planning: 'Planning',
  analyzing: 'Analyzing',
  modeling: 'Modeling',
  scenarios: 'Scenarios',
}

export const UI_PHASE_DISPLAY_NAMES: Record<UIPhase, string> = {
  planning: 'Planning Analysis',
  analyzing: 'Running Analyses',
  modeling: 'Planning Scenarios',
  scenarios: 'Running Scenarios',
}

// SSE Event Types
export interface WorkflowPhaseEvent {
  event_type: 'workflow_phase'
  message: string
  agent_id?: string
  metadata?: {
    phase_index: number
    phase_total: number
    phase_name: BackendPhase
    status: 'started' | 'completed'
  }
  // Legacy format support
  phase_index?: number
  phase_total?: number
  phase_name?: BackendPhase
  status?: 'started' | 'completed'
}

export interface TaskProgressEvent {
  event_type: 'task_progress'
  message: string
  agent_id?: string
  metadata?: {
    task_type: 'analysis' | 'scenario'
    task_id: string
    task_index: number
    task_total: number
    title: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    error?: string
  }
  // Legacy format support
  task_type?: 'analysis' | 'scenario'
  task_id?: string
  task_index?: number
  task_total?: number
  title?: string
  status?: 'pending' | 'running' | 'completed' | 'failed'
  error?: string
}

export interface StatusEvent {
  event_type: 'status' | 'message'
  message: string
  agent_id?: string
}

export interface CompleteEvent {
  event_type: 'complete'
  message: string
  metadata?: {
    analyses_completed?: number
    scenarios_completed?: number
    reports_created?: number
    report_ids?: string[]
  }
}

export interface ErrorEvent {
  event_type: 'error'
  message: string
}

export type AnalysisWorkflowEvent =
  | WorkflowPhaseEvent
  | TaskProgressEvent
  | StatusEvent
  | CompleteEvent
  | ErrorEvent

// Progress State
export interface TaskProgress {
  type: 'analysis' | 'scenario'
  id: string
  index: number
  total: number
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  error?: string
}

export interface PhaseProgress {
  index: number
  total: number
  name: BackendPhase
  status: 'started' | 'completed'
}

export interface ProgressState {
  phase: PhaseProgress | null
  tasks: TaskProgress[]
  messages: string[]
  isComplete: boolean
  error: string | null
  metadata: {
    analyses_completed?: number
    scenarios_completed?: number
    reports_created?: number
    report_ids?: string[]
  }
}

// Workflow Inputs
export interface WorkflowInputs {
  intent_package: {
    objective: string
    focus_areas: string[]
    key_questions?: string[]
    constraints?: {
      timeline?: string
      budget_target?: string
      [key: string]: string | undefined
    }
  }
  data_inventory: {
    entities: string[]
    record_counts: Record<string, number>
    relationships?: string[]
    sample_data?: Record<string, unknown>
  }
}

// Report Summary for cards
export interface ReportSummary {
  id: string
  type: 'analysis' | 'scenario'
  title: string
  executiveSummary: string
  keyFindings: string[]
  status: 'draft' | 'completed'
  createdAt: string
}

// Helper functions
export function getUIPhaseIndex(backendPhase: BackendPhase): number {
  const uiPhase = PHASE_MAPPING[backendPhase]
  return UI_PHASE_ORDER.indexOf(uiPhase) + 1
}

export function getUIPhase(backendPhase: BackendPhase): UIPhase {
  return PHASE_MAPPING[backendPhase]
}

export function calculateOverallProgress(progress: ProgressState): number {
  // Weight: Planning=10%, Analyzing=40%, Modeling=10%, Scenarios=40%
  const phaseWeights: Record<UIPhase, number> = {
    planning: 10,
    analyzing: 40,
    modeling: 10,
    scenarios: 40,
  }

  if (!progress.phase) return 0

  const uiPhase = PHASE_MAPPING[progress.phase.name]
  const phaseIndex = UI_PHASE_ORDER.indexOf(uiPhase)

  // Base progress from completed phases
  let baseProgress = 0
  for (let i = 0; i < phaseIndex; i++) {
    baseProgress += phaseWeights[UI_PHASE_ORDER[i]]
  }

  // Add progress within current phase based on phase status and tasks
  if (progress.phase.status === 'completed') {
    // If phase is marked complete, add full weight
    baseProgress += phaseWeights[uiPhase]
  } else {
    // Phase is in progress - calculate based on tasks
    const tasksInPhase = progress.tasks.filter(
      (t) =>
        (uiPhase === 'analyzing' && t.type === 'analysis') ||
        (uiPhase === 'scenarios' && t.type === 'scenario')
    )

    if (tasksInPhase.length > 0) {
      const completedTasks = tasksInPhase.filter((t) => t.status === 'completed').length
      const runningTasks = tasksInPhase.filter((t) => t.status === 'running').length
      const taskProgress = (completedTasks + runningTasks * 0.5) / tasksInPhase.length
      baseProgress += phaseWeights[uiPhase] * taskProgress
    } else if (uiPhase === 'planning' || uiPhase === 'modeling') {
      // Planning phases with no tasks - show 50% progress if started
      baseProgress += phaseWeights[uiPhase] * 0.5
    }
  }

  return Math.min(baseProgress, 100)
}

export function formatTimeRemaining(seconds: number | null): string {
  if (seconds === null) return '2 minutes'
  if (seconds < 60) return `${seconds} seconds`
  const minutes = Math.ceil(seconds / 60)
  return `${minutes} minute${minutes > 1 ? 's' : ''}`
}
