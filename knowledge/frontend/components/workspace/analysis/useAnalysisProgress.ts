import { useState, useEffect, useCallback, useRef } from 'react'
import { AuthenticatedEventSource, getApiBase } from '../../../services/graphql'
import type {
  ProgressState,
  TaskProgress,
  PhaseProgress,
  AnalysisWorkflowEvent,
} from './types'

export interface UseAnalysisProgressOptions {
  onComplete?: (reportIds: string[]) => void
  onError?: (error: string) => void
  onPhaseChange?: (phase: PhaseProgress) => void
}

export interface UseAnalysisProgressReturn extends ProgressState {
  startStream: (runId: string) => void
  stopStream: () => void
  reconnect: () => void
}

const INITIAL_STATE: ProgressState = {
  phase: null,
  tasks: [],
  messages: [],
  isComplete: false,
  error: null,
  metadata: {},
}

export function useAnalysisProgress(
  options?: UseAnalysisProgressOptions
): UseAnalysisProgressReturn {
  const [progress, setProgress] = useState<ProgressState>(INITIAL_STATE)

  const eventSourceRef = useRef<AuthenticatedEventSource | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const currentRunIdRef = useRef<string | null>(null)
  const processedEventsRef = useRef<Set<string>>(new Set())

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  const handleEvent = useCallback(
    (event: AnalysisWorkflowEvent) => {
      // Create unique event ID for deduplication
      const eventId = `${event.event_type}-${JSON.stringify(event)}`
      if (processedEventsRef.current.has(eventId)) {
        return
      }
      processedEventsRef.current.add(eventId)

      // Limit set size to prevent memory issues
      if (processedEventsRef.current.size > 1000) {
        const entries = Array.from(processedEventsRef.current)
        processedEventsRef.current = new Set(entries.slice(-500))
      }

      setProgress((prev) => {
        switch (event.event_type) {
          case 'workflow_phase': {
            const metadata = event.metadata || {
              phase_index: event.phase_index!,
              phase_total: event.phase_total!,
              phase_name: event.phase_name!,
              status: event.status!,
            }
            const newPhase: PhaseProgress = {
              index: metadata.phase_index,
              total: metadata.phase_total,
              name: metadata.phase_name,
              status: metadata.status,
            }
            options?.onPhaseChange?.(newPhase)
            return {
              ...prev,
              phase: newPhase,
              messages: [...prev.messages, event.message],
            }
          }

          case 'task_progress': {
            const taskData = event.metadata || {
              task_type: event.task_type!,
              task_id: event.task_id!,
              task_index: event.task_index!,
              task_total: event.task_total!,
              title: event.title!,
              status: event.status!,
              error: event.error,
            }
            const existingTaskIndex = prev.tasks.findIndex(
              (t) => t.id === taskData.task_id
            )

            const updatedTask: TaskProgress = {
              type: taskData.task_type,
              id: taskData.task_id,
              index: taskData.task_index,
              total: taskData.task_total,
              title: taskData.title,
              status: taskData.status,
              error: taskData.error,
            }

            let newTasks: TaskProgress[]
            if (existingTaskIndex >= 0) {
              newTasks = [...prev.tasks]
              newTasks[existingTaskIndex] = updatedTask
            } else {
              newTasks = [...prev.tasks, updatedTask]
            }

            return {
              ...prev,
              tasks: newTasks,
              messages: [...prev.messages, event.message],
            }
          }

          case 'message':
          case 'status':
            return {
              ...prev,
              messages: [...prev.messages, event.message],
            }

          case 'complete': {
            const metadata = event.metadata || {}
            const reportIds = metadata.report_ids || []
            options?.onComplete?.(reportIds)
            return {
              ...prev,
              isComplete: true,
              messages: [...prev.messages, event.message],
              metadata: {
                analyses_completed: metadata.analyses_completed,
                scenarios_completed: metadata.scenarios_completed,
                reports_created: metadata.reports_created,
                report_ids: reportIds,
              },
            }
          }

          case 'error':
            options?.onError?.(event.message)
            return {
              ...prev,
              error: event.message,
              messages: [...prev.messages, event.message],
            }

          default:
            return prev
        }
      })
    },
    [options]
  )

  const startStream = useCallback(
    (runId: string) => {
      // Close existing connection
      stopStream()

      // Reset state for new stream
      setProgress(INITIAL_STATE)
      processedEventsRef.current.clear()
      currentRunIdRef.current = runId

      const apiBase = getApiBase()
      const url = `${apiBase}/runs/${runId}/events`

      const eventSource = new AuthenticatedEventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as AnalysisWorkflowEvent
          handleEvent(data)
        } catch (error) {
          // Skip non-JSON log lines
          console.debug('[useAnalysisProgress] Non-JSON event:', event.data, error)
        }
      }

      eventSource.onerror = (error) => {
        console.error('[useAnalysisProgress] SSE error:', error)
        // Check current state before attempting reconnect
        setProgress((currentProgress) => {
          if (!currentProgress.isComplete && !currentProgress.error) {
            // Attempt reconnect after 3 seconds
            reconnectTimeoutRef.current = setTimeout(() => {
              if (currentRunIdRef.current) {
                startStream(currentRunIdRef.current)
              }
            }, 3000)
          }
          return currentProgress
        })
      }
    },
    [stopStream, handleEvent]
  )

  const reconnect = useCallback(() => {
    if (currentRunIdRef.current) {
      startStream(currentRunIdRef.current)
    }
  }, [startStream])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStream()
    }
  }, [stopStream])

  return {
    ...progress,
    startStream,
    stopStream,
    reconnect,
  }
}
