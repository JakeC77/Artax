/**
 * useSetupProgress Hook
 *
 * Processes SSE events for setup loading screens (Data Review, Team Building).
 * Based on the useAnalysisProgress pattern for consistency.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { AuthenticatedEventSource } from '../services/graphql'
import {
  type SetupProgressState,
  type SetupProgressEvent,
  type SetupTask,
  type SetupPhase,
  createInitialProgressState,
  extractEventMetadata,
} from '../types/setupProgress'

// ============================================================================
// Types
// ============================================================================

export interface UseSetupProgressOptions {
  /** Called when the loading flow completes successfully */
  onComplete?: (summary: SetupProgressState['summary']) => void
  /** Called when an error occurs */
  onError?: (error: string) => void
  /** Called when a phase changes */
  onPhaseChange?: (phase: SetupPhase) => void
  /** Called on each task update */
  onTaskUpdate?: (task: SetupTask) => void
}

export interface UseSetupProgressReturn extends SetupProgressState {
  /** Start listening to SSE stream for a run */
  startStream: (runId: string) => void
  /** Stop listening to SSE stream */
  stopStream: () => void
  /** Reconnect to the stream */
  reconnect: () => void
  /** Process a single event (for testing or manual event injection) */
  processEvent: (event: SetupProgressEvent) => void
  /** Reset progress state */
  reset: () => void
  /** Whether stream is currently connected */
  isConnected: boolean
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useSetupProgress(options: UseSetupProgressOptions = {}): UseSetupProgressReturn {
  const { onComplete, onError, onPhaseChange, onTaskUpdate } = options

  // State
  const [state, setState] = useState<SetupProgressState>(createInitialProgressState())
  const [isConnected, setIsConnected] = useState(false)

  // Refs
  const eventSourceRef = useRef<AuthenticatedEventSource | null>(null)
  const runIdRef = useRef<string | null>(null)
  const seenEventsRef = useRef<Set<string>>(new Set())

  // ============================================================================
  // Event Processing
  // ============================================================================

  const processEvent = useCallback(
    (event: SetupProgressEvent) => {
      // Deduplicate events using JSON hash
      const eventKey = JSON.stringify(event)
      if (seenEventsRef.current.has(eventKey)) {
        return
      }
      seenEventsRef.current.add(eventKey)

      // Rotate seen events set if it gets too large
      if (seenEventsRef.current.size > 1000) {
        const entries = Array.from(seenEventsRef.current)
        seenEventsRef.current = new Set(entries.slice(500))
      }

      const eventType = event.event_type

      switch (eventType) {
        case 'setup_phase': {
          const meta = extractEventMetadata(event)
          const phase: SetupPhase = {
            name: meta.phase_name as SetupPhase['name'],
            index: (meta.phase_index as number) ?? 1,
            total: (meta.phase_total as number) ?? 1,
            status: (meta.status as SetupPhase['status']) ?? 'started',
          }

          setState((prev) => ({
            ...prev,
            phase,
            messages: [...prev.messages, event.message],
          }))

          onPhaseChange?.(phase)
          break
        }

        case 'setup_task': {
          const meta = extractEventMetadata(event)
          const taskId = (meta.task_id as string) || `task-${meta.task_index}`

          const task: SetupTask = {
            id: taskId as string,
            type: (meta.task_type as SetupTask['type']) || 'entity',
            title: (meta.title as string) || taskId,
            index: (meta.task_index as number) ?? 0,
            total: (meta.task_total as number) ?? 1,
            status: (meta.status as SetupTask['status']) || 'pending',
            progress: meta.progress as SetupTask['progress'],
            error: meta.error as string | undefined,
          }

          setState((prev) => {
            // Update existing task or add new one
            const existingIndex = prev.tasks.findIndex((t) => t.id === task.id)
            const newTasks =
              existingIndex >= 0
                ? prev.tasks.map((t, i) => (i === existingIndex ? task : t))
                : [...prev.tasks, task]

            return {
              ...prev,
              tasks: newTasks,
              messages: [...prev.messages, event.message],
            }
          })

          onTaskUpdate?.(task)
          break
        }

        case 'setup_status': {
          setState((prev) => ({
            ...prev,
            messages: [...prev.messages, event.message],
          }))
          break
        }

        case 'setup_complete': {
          const meta = extractEventMetadata(event) || {}
          const summary = meta.summary || {
            entities_staged: meta.entities_staged,
            records_total: meta.records_total,
            agents_configured: meta.agents_configured,
          }

          setState((prev) => ({
            ...prev,
            isComplete: true,
            summary,
            messages: [...prev.messages, event.message],
          }))

          onComplete?.(summary)
          break
        }

        case 'setup_error': {
          const errorMessage = event.message

          setState((prev) => ({
            ...prev,
            error: errorMessage,
            messages: [...prev.messages, errorMessage],
          }))

          onError?.(errorMessage)
          break
        }

        default:
          // Unknown event type - log but don't crash
          console.warn('[useSetupProgress] Unknown event type:', eventType)
      }
    },
    [onComplete, onError, onPhaseChange, onTaskUpdate]
  )

  // ============================================================================
  // Legacy Event Mapping
  // ============================================================================

  /**
   * Map legacy event types to unified setup events.
   * This provides backward compatibility with existing backend events.
   */
  const mapLegacyEvent = useCallback((rawEvent: Record<string, unknown>): SetupProgressEvent | null => {
    const eventType = rawEvent.event_type as string

    // Already a setup event - pass through
    if (eventType?.startsWith('setup_')) {
      return rawEvent as unknown as SetupProgressEvent
    }

    // Map legacy data staging events
    switch (eventType) {
      case 'staging_started':
      case 'execution_started':
        return {
          event_type: 'setup_phase',
          message: (rawEvent.message as string) || 'Starting data staging...',
          agent_id: rawEvent.agent_id as string,
          metadata: {
            phase_name: 'staging_data',
            phase_index: 1,
            phase_total: 1,
            status: 'started',
          },
        }

      case 'cypher_execution_started':
        return {
          event_type: 'setup_status',
          message: (rawEvent.message as string) || 'Executing queries...',
          agent_id: rawEvent.agent_id as string,
        }

      case 'cypher_query_generated':
      case 'cypher_query_executing':
        return {
          event_type: 'setup_status',
          message: (rawEvent.message as string) || 'Query in progress...',
          agent_id: rawEvent.agent_id as string,
        }

      case 'entity_complete': {
        const entityType = rawEvent.entity_type as string
        const totalCount = rawEvent.total_count as number
        return {
          event_type: 'setup_task',
          message: `Fetched ${totalCount} ${entityType} records`,
          agent_id: rawEvent.agent_id as string,
          metadata: {
            task_id: `entity_${entityType?.toLowerCase()}`,
            task_type: 'entity',
            title: entityType || 'Entity',
            task_index: 0, // Will be updated by state merge
            task_total: 1, // Will be updated by state merge
            status: 'completed',
            progress: {
              current: totalCount,
              total: totalCount,
            },
          },
        }
      }

      case 'execution_complete':
      case 'cypher_execution_completed':
        return {
          event_type: 'setup_complete',
          message: (rawEvent.message as string) || 'Data staging complete!',
          agent_id: rawEvent.agent_id as string,
          metadata: {
            phase_name: 'staging_data',
            summary: {
              records_total: rawEvent.total_matches as number,
            },
          },
        }

      case 'staging_error':
      case 'workspace_staging_error':
        return {
          event_type: 'setup_error',
          message: (rawEvent.message as string) || 'Data staging failed',
          agent_id: rawEvent.agent_id as string,
        }

      // Map legacy team building events
      case 'team_building_started':
        return {
          event_type: 'setup_phase',
          message: (rawEvent.message as string) || 'Building AI team...',
          agent_id: rawEvent.agent_id as string,
          metadata: {
            phase_name: 'building_team',
            phase_index: 1,
            phase_total: 1,
            status: 'started',
          },
        }

      case 'agent_configured': {
        const agentName = rawEvent.agent_name as string
        return {
          event_type: 'setup_task',
          message: `${agentName} configured`,
          agent_id: rawEvent.agent_id as string,
          metadata: {
            task_id: `agent_${agentName?.toLowerCase().replace(/\s+/g, '_')}`,
            task_type: 'agent',
            title: agentName || 'Agent',
            task_index: 0,
            task_total: 1,
            status: 'completed',
          },
        }
      }

      case 'team_complete':
        return {
          event_type: 'setup_complete',
          message: (rawEvent.message as string) || 'AI team ready!',
          agent_id: rawEvent.agent_id as string,
          metadata: {
            phase_name: 'building_team',
            summary: {
              agents_configured: rawEvent.agent_count as number,
            },
          },
        }

      case 'team_building_error':
        return {
          event_type: 'setup_error',
          message: (rawEvent.message as string) || 'Team building failed',
          agent_id: rawEvent.agent_id as string,
        }

      default:
        // Not a setup-related event - ignore
        return null
    }
  }, [])

  // ============================================================================
  // Stream Management
  // ============================================================================

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsConnected(false)
  }, [])

  const startStream = useCallback(
    (runId: string) => {
      // Clean up existing stream
      stopStream()

      runIdRef.current = runId
      seenEventsRef.current.clear()

      const baseUrl = import.meta.env.VITE_GRAPHQL_URL?.replace('/gql', '') || ''
      const eventUrl = `${baseUrl}/runs/${runId}/events`

      const eventSource = new AuthenticatedEventSource(eventUrl)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Map legacy events to unified format
          const mappedEvent = mapLegacyEvent(data)
          if (mappedEvent) {
            processEvent(mappedEvent)
          }
        } catch (err) {
          console.error('[useSetupProgress] Failed to parse event:', err)
        }
      }

      eventSource.onerror = (err) => {
        console.error('[useSetupProgress] SSE error:', err)
        setIsConnected(false)

        // Auto-reconnect after 3 seconds if we have a run ID
        if (runIdRef.current) {
          setTimeout(() => {
            if (runIdRef.current) {
              startStream(runIdRef.current)
            }
          }, 3000)
        }
      }
    },
    [stopStream, processEvent, mapLegacyEvent]
  )

  const reconnect = useCallback(() => {
    if (runIdRef.current) {
      startStream(runIdRef.current)
    }
  }, [startStream])

  const reset = useCallback(() => {
    stopStream()
    setState(createInitialProgressState())
    seenEventsRef.current.clear()
    runIdRef.current = null
  }, [stopStream])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStream()
    }
  }, [stopStream])

  // ============================================================================
  // Return
  // ============================================================================

  return {
    ...state,
    startStream,
    stopStream,
    reconnect,
    processEvent,
    reset,
    isConnected,
  }
}

export default useSetupProgress
