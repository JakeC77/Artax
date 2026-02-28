import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AuthenticatedEventSource,
  getApiBase,
  workspaceSetupStatus,
  startWorkspaceSetup,
  confirmIntentAndStartDataScoping,
  confirmDataScopeAndStartExecution,
  confirmDataReviewAndBuildTeam,
  completeWorkspaceSetup,
  fetchAiTeamMembers,
  type SetupStage,
  type SetupStatus,
  type IntentPackage,
  type DataScope,
  type ExecutionResult,
  type TeamConfig,
  type AiTeamMember,
} from '../../../services/graphql'
import type { ScopeState } from '../../../types/scopeState'
import { convertDataScopeToScopeState, mergeExecutionResultsIntoScopeState } from '../../../utils/scopeStateConverter'

export type SetupEvent = {
  event_type: string
  [key: string]: any
}

export type UseWorkspaceSetupOptions = {
  workspaceId: string
  onStageChange?: (stage: SetupStage) => void
  onIntentReady?: (intentPackage: IntentPackage) => void
  onScopeReady?: (dataScope: DataScope) => void
  /** New: Called when scope state is ready (unified format) */
  onScopeStateReady?: (scopeState: ScopeState) => void
  /** New: Called when scope state is updated (e.g., filter change) */
  onScopeStateUpdated?: (scopeState: ScopeState, updateSummary?: string) => void
  onExecutionComplete?: (results: ExecutionResult[]) => void
  onTeamComplete?: (teamConfig: TeamConfig) => void
  onExecutionError?: (error: string) => void
  onTeamBuildingError?: (error: string) => void
  /** Generic error handler for any stage - receives error message and stage where it occurred */
  onError?: (error: string, stage?: string) => void
}

export type UseWorkspaceSetupReturn = {
  // State
  status: SetupStatus | null
  loading: boolean
  error: string | null
  isStreaming: boolean
  events: SetupEvent[]

  // Error state for specific stages
  executionError: string | null
  teamBuildingError: string | null

  // Artifacts
  intentPackage: IntentPackage | null
  dataScope: DataScope | null
  /** New: Unified scope state for the merged scoping/review experience */
  scopeState: ScopeState | null
  executionResults: ExecutionResult[] | null
  teamConfig: TeamConfig | null

  // Actions
  startSetup: (initialMessage?: string) => Promise<void>
  confirmIntent: (intentPackage: IntentPackage) => Promise<void>
  confirmScope: (dataScope: DataScope) => Promise<void>
  confirmReview: (executionResults: ExecutionResult[]) => Promise<void>
  completeSetup: (teamConfig: TeamConfig) => Promise<string | null>

  // Stream management
  connectToStage: (runId: string, tenantId: string) => void
  disconnectStream: () => void

  // Utilities
  refetchStatus: () => Promise<SetupStatus | null | undefined>
}

export function useWorkspaceSetup(options: UseWorkspaceSetupOptions): UseWorkspaceSetupReturn {
  const { workspaceId, onStageChange, onIntentReady, onScopeReady, onScopeStateReady, onScopeStateUpdated, onExecutionComplete, onTeamComplete, onExecutionError, onTeamBuildingError, onError } = options

  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<SetupEvent[]>([])

  // Artifact state
  const [intentPackage, setIntentPackage] = useState<IntentPackage | null>(null)
  const [dataScope, setDataScope] = useState<DataScope | null>(null)
  const [scopeState, setScopeState] = useState<ScopeState | null>(null)
  const [executionResults, setExecutionResults] = useState<ExecutionResult[] | null>(null)
  const [teamConfig, setTeamConfig] = useState<TeamConfig | null>(null)

  // Error state for specific stages
  const [executionError, setExecutionError] = useState<string | null>(null)
  const [teamBuildingError, setTeamBuildingError] = useState<string | null>(null)

  // Refs for SSE management
  const esRef = useRef<AuthenticatedEventSource | null>(null)
  const processedEventsRef = useRef<Set<string>>(new Set())
  const eventSequenceRef = useRef<number>(0)
  const currentWorkspaceIdRef = useRef<string>(workspaceId)

  // Reset state when workspace changes
  useEffect(() => {
    if (workspaceId !== currentWorkspaceIdRef.current) {
      // Close existing connection
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }

      // Clear all refs
      processedEventsRef.current = new Set()
      eventSequenceRef.current = 0
      currentWorkspaceIdRef.current = workspaceId

      // Clear state
      setEvents([])
      setIsStreaming(false)
      setIntentPackage(null)
      setDataScope(null)
      setScopeState(null)
      setExecutionResults(null)
      setTeamConfig(null)
      setExecutionError(null)
      setTeamBuildingError(null)
    }
  }, [workspaceId])

  // Fetch setup status
  const refetchStatus = useCallback(async () => {
    if (!workspaceId) return

    try {
      setLoading(true)
      setError(null)
      const setupStatus = await workspaceSetupStatus(workspaceId)
      setStatus(setupStatus)

      // Sync artifact state from status
      if (setupStatus.intentPackage) {
        setIntentPackage(setupStatus.intentPackage)
      }
      if (setupStatus.dataScope) {
        setDataScope(setupStatus.dataScope)
        // Also convert to ScopeState for unified experience
        const converted = convertDataScopeToScopeState(setupStatus.dataScope)
        // Merge execution results if available
        if (setupStatus.executionResults) {
          setScopeState(mergeExecutionResultsIntoScopeState(converted, setupStatus.executionResults))
        } else {
          setScopeState(converted)
        }
      }
      if (setupStatus.executionResults) {
        setExecutionResults(setupStatus.executionResults)
      }
      if (setupStatus.teamConfig) {
        setTeamConfig(setupStatus.teamConfig)
      } else if (setupStatus.stage === 'team_building' || setupStatus.stage === 'complete') {
        // Fallback: If we're in team_building/complete but teamConfig is null,
        // try to construct it from aiTeamMembers (which may be stored separately)
        try {
          const members = await fetchAiTeamMembers(workspaceId)
          if (members.length > 0) {
            // Find the conductor (if any) - usually the first member or one with 'conductor' in role
            const conductorMember = members.find((m: AiTeamMember) =>
              m.role?.toLowerCase().includes('conductor') ||
              m.role?.toLowerCase().includes('analyst') ||
              m.role?.toLowerCase().includes('strategist')
            ) || members[0]

            const constructedConfig: TeamConfig = {
              team_id: members[0]?.aiTeamId || `team-${workspaceId}`,
              team_name: 'AI Team',
              conductor: conductorMember ? {
                agent_id: conductorMember.agentId,
                name: conductorMember.name,
                role: conductorMember.role,
                capabilities: conductorMember.expertise || [],
              } : undefined,
              agents: members.map((m: AiTeamMember) => ({
                agent_id: m.agentId,
                name: m.name,
                role: m.role,
                type: m.role?.toLowerCase().includes('conductor') ? 'conductor' : 'specialist',
                capabilities: m.expertise || [],
              })),
            }
            setTeamConfig(constructedConfig)
            console.log('[useWorkspaceSetup] Constructed teamConfig from aiTeamMembers:', constructedConfig)
          }
        } catch (teamErr) {
          console.warn('[useWorkspaceSetup] Failed to fetch aiTeamMembers as fallback:', teamErr)
        }
      }

      return setupStatus

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to fetch setup status:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch setup status')
      return null
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  // Fetch status on mount
  useEffect(() => {
    refetchStatus()
  }, [refetchStatus])

  // Handle stage changes
  useEffect(() => {
    if (status?.stage && onStageChange) {
      onStageChange(status.stage)
    }
  }, [status?.stage, onStageChange])

  // Connect to SSE stream for a stage
  const connectToStage = useCallback((runId: string, tenantId: string) => {
    if (!runId || !tenantId) {
      console.warn('[useWorkspaceSetup] Cannot connect to stream: missing runId or tenantId')
      return
    }

    // Clean up existing connection
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    const url = `${getApiBase()}/runs/${runId}/events?tid=${encodeURIComponent(tenantId)}`

    const es = new AuthenticatedEventSource(url)
    esRef.current = es
    setIsStreaming(true)

    es.addEventListener('message', (event: MessageEvent) => {
      // Helper to process a single parsed event object
      const processEvent = (data: Record<string, unknown>) => {
        const eventId = `${data.event_type}-${eventSequenceRef.current++}`

        // Deduplicate events
        if (processedEventsRef.current.has(eventId)) {
          return
        }
        processedEventsRef.current.add(eventId)

        // Add to events array
        setEvents(prev => [...prev, data as SetupEvent])

        // Handle specific event types
        handleEventType(data)
      }

      try {
        // Try parsing as single JSON object first
        const data = JSON.parse(event.data)
        processEvent(data)
      } catch (singleParseError) {
        // If single parse fails, try parsing as newline-separated JSON objects
        // The backend sometimes sends multiple JSON objects separated by literal \n
        // (backslash-n) instead of actual newlines. Normalize these first.
        // Pattern: } followed by literal \n followed by { indicates JSON object boundary
        const normalized = event.data.replace(/}\s*\\n\s*{/g, '}\n{')
        const lines = normalized.split('\n').filter((line: string) => line.trim())
        let parsedAny = false

        for (const line of lines) {
          try {
            const data = JSON.parse(line)
            processEvent(data)
            parsedAny = true
          } catch {
            // Skip unparseable lines
          }
        }

        if (!parsedAny) {
          console.error('[useWorkspaceSetup] Failed to parse SSE event:', singleParseError)
          console.error('[useWorkspaceSetup] Raw event data:', event.data?.substring(0, 500))
        }
      }
    })

    // Helper function to handle event types (extracted to avoid duplication)
    const handleEventType = (data: Record<string, unknown>) => {
      switch (data.event_type) {
        case 'intent_ready':
          if (data.intent_package) {
            setIntentPackage(data.intent_package as IntentPackage)
            onIntentReady?.(data.intent_package as IntentPackage)
          }
          break

        case 'scope_ready':
          // Handle new unified scope_state format
          if (data.scope_state) {
            setScopeState(data.scope_state as ScopeState)
            onScopeStateReady?.(data.scope_state as ScopeState)
          }
          // Handle legacy data_scope format (backward compatibility)
          if (data.data_scope) {
            setDataScope(data.data_scope as DataScope)
            onScopeReady?.(data.data_scope as DataScope)
            // Also convert to ScopeState for unified experience
            if (!data.scope_state) {
              const converted = convertDataScopeToScopeState(data.data_scope as DataScope)
              setScopeState(converted)
              onScopeStateReady?.(converted)
            }
          }
          break

        case 'scope_updated':
          // Handle scope updates (e.g., filter changes via chat)
          if (data.scope_state) {
            setScopeState(data.scope_state as ScopeState)
            onScopeStateUpdated?.(data.scope_state as ScopeState, data.update_summary as string | undefined)
          } else if (data.data_scope) {
            // Backward compatibility
            setDataScope(data.data_scope as DataScope)
            const converted = convertDataScopeToScopeState(data.data_scope as DataScope)
            setScopeState(converted)
            onScopeStateUpdated?.(converted, data.update_summary as string | undefined)
          }
          break

        case 'execution_progress':
          // Handle execution progress updates
          break

        case 'execution_complete':
          if (data.results) {
            const results = data.results as ExecutionResult[]
            setExecutionResults(results)
            onExecutionComplete?.(results)
            // Merge execution results into ScopeState
            setScopeState((prev) => {
              if (prev) {
                return mergeExecutionResultsIntoScopeState(prev, results)
              }
              return prev
            })
          }
          break

        case 'execution_error': {
          const execError = (data.error || data.message || 'Execution failed') as string
          console.error('[useWorkspaceSetup] Execution error:', execError)
          setExecutionError(execError)
          onExecutionError?.(execError)
          break
        }

        case 'error': {
          // Generic error event - route to appropriate handler based on stage
          const genericError = (data.error || data.message || 'An error occurred') as string
          const errorStage = data.stage as string | undefined
          console.error('[useWorkspaceSetup] Generic error at stage:', errorStage, 'error:', genericError)

          // Route to stage-specific error state if applicable
          if (errorStage === 'data_review') {
            setExecutionError(genericError)
            onExecutionError?.(genericError)
          } else if (errorStage === 'team_building') {
            setTeamBuildingError(genericError)
            onTeamBuildingError?.(genericError)
          }

          // Also call the generic error handler
          onError?.(genericError, errorStage)
          break
        }

        case 'team_building_progress':
          // Handle team building status updates
          break

        case 'team_complete': {
          // Handle both snake_case and camelCase field names
          const teamConfigData = (data.team_config || data.teamConfig) as TeamConfig | undefined
          if (teamConfigData) {
            setTeamConfig(teamConfigData)
            onTeamComplete?.(teamConfigData)
          }
          break
        }

        case 'team_building_error': {
          const teamError = (data.error || data.message || 'Team building failed') as string
          console.error('[useWorkspaceSetup] Team building error:', teamError)
          setTeamBuildingError(teamError)
          onTeamBuildingError?.(teamError)
          break
        }

        case 'stage_update':
          if (data.stage) {
            setStatus(prev => prev ? {
              ...prev,
              stage: data.stage as SetupStage,
            } : prev)
            onStageChange?.(data.stage as SetupStage)
          }
          break

        default:
          // Unknown event type - ignore silently
          break
      }
    }

    es.addEventListener('error', (err) => {
      console.error('[useWorkspaceSetup] SSE error:', err)
      setIsStreaming(false)
    })

    es.addEventListener('open', () => {
      setIsStreaming(true)
    })

  }, [onIntentReady, onScopeReady, onExecutionComplete, onTeamComplete, onExecutionError, onTeamBuildingError, onError])

  // Disconnect stream
  const disconnectStream = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
      setIsStreaming(false)
    }
  }, [])

  // Start workspace setup (Stage 1)
  const startSetup = useCallback(async (initialMessage?: string) => {
    try {
      setLoading(true)
      setError(null)
      // Pass initialMessage to mutation - backend will include it in inputs and write to event log
      const result = await startWorkspaceSetup(workspaceId, initialMessage)

      setStatus(prev => prev ? { ...prev, stage: result.stage, runId: result.runId } : null)

      // Refetch to get updated status
      await refetchStatus()

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to start setup:', err)
      setError(err instanceof Error ? err.message : 'Failed to start setup')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, refetchStatus])

  // Confirm intent and move to Stage 2
  const confirmIntent = useCallback(async (intentPkg: IntentPackage) => {
    try {
      setLoading(true)
      setError(null)
      const result = await confirmIntentAndStartDataScoping(workspaceId, intentPkg)

      setStatus(prev => prev ? { ...prev, stage: result.stage, runId: result.runId } : null)
      setIntentPackage(intentPkg)

      // Refetch to get updated status
      await refetchStatus()

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to confirm intent:', err)
      setError(err instanceof Error ? err.message : 'Failed to confirm intent')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, refetchStatus])

  // Confirm scope and move to Stage 3
  const confirmScope = useCallback(async (scope: DataScope) => {
    try {
      setLoading(true)
      setError(null)
      const result = await confirmDataScopeAndStartExecution(workspaceId, scope)

      setStatus(prev => prev ? { ...prev, stage: result.stage, runId: result.runId } : null)
      setDataScope(scope)

      // Refetch to get updated status
      await refetchStatus()

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to confirm scope:', err)
      setError(err instanceof Error ? err.message : 'Failed to confirm scope')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, refetchStatus])

  // Confirm review and move to Stage 4
  const confirmReview = useCallback(async (execResults: ExecutionResult[]) => {
    try {
      setLoading(true)
      setError(null)
      const result = await confirmDataReviewAndBuildTeam(workspaceId, execResults)

      setStatus(prev => prev ? { ...prev, stage: result.stage, runId: result.runId } : null)

      // Refetch to get updated status
      await refetchStatus()

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to confirm review:', err)
      setError(err instanceof Error ? err.message : 'Failed to confirm review')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, refetchStatus])

  // Complete setup (Stage 5 - final)
  const completeSetup = useCallback(async (config: TeamConfig): Promise<string | null> => {
    try {
      setLoading(true)
      setError(null)
      const runId = await completeWorkspaceSetup(workspaceId, config)

      setStatus(prev => prev ? { ...prev, stage: 'complete' } : null)

      // Disconnect stream since setup is complete
      disconnectStream()

      // Refetch to get final status
      await refetchStatus()

      return runId

    } catch (err) {
      console.error('[useWorkspaceSetup] Failed to complete setup:', err)
      setError(err instanceof Error ? err.message : 'Failed to complete setup')
      throw err
    } finally {
      setLoading(false)
    }
  }, [workspaceId, refetchStatus, disconnectStream])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnectStream()
    }
  }, [disconnectStream])

  return {
    // State
    status,
    loading,
    error,
    isStreaming,
    events,

    // Error state for specific stages
    executionError,
    teamBuildingError,

    // Artifacts
    intentPackage,
    dataScope,
    scopeState,
    executionResults,
    teamConfig,

    // Actions
    startSetup,
    confirmIntent,
    confirmScope,
    confirmReview,
    completeSetup,

    // Stream management
    connectToStage,
    disconnectStream,

    // Utilities
    refetchStatus,
  }
}
