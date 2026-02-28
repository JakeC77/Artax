import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AuthenticatedEventSource,
  getApiBase,
  updateWorkspace,
  fetchWorkspaceById,
  type Workspace,
  type IntentPackage,
  type DataScope,
  type ExecutionResult,
  type TeamConfig,
} from '../../../services/graphql'
import { type ChatMessage, type AttachedEvent } from './ChatMessages'
import type { CsvAnalysisData } from './CsvAnalysisBlock'
import { type ClarificationQuestion } from './ClarificationPanel'
import type { OntologyPackage } from '../../../types/ontology'
import type { StreamEvent, PreviewDataEvent } from '../../../types/streaming'
import type { ScopeState } from '../../../types/scopeState'
import { convertDataScopeToScopeState } from '../../../utils/scopeStateConverter'

// Helper function to parse multiple JSON objects from a string
const parseJSONEvents = (text: string): Array<{ json: any; start: number; end: number }> => {
  const events: Array<{ json: any; start: number; end: number }> = []
  let i = 0
  let braceCount = 0
  let start = -1
  let inString = false
  let escapeNext = false

  while (i < text.length) {
    const char = text[i]

    if (escapeNext) {
      escapeNext = false
      i++
      continue
    }

    if (char === '\\' && inString) {
      escapeNext = true
      i++
      continue
    }

    if (char === '"' && !escapeNext) {
      inString = !inString
      i++
      continue
    }

    if (!inString) {
      if (char === '{') {
        if (braceCount === 0) {
          start = i
        }
        braceCount++
      } else if (char === '}') {
        braceCount--
        if (braceCount === 0 && start !== -1) {
          try {
            const jsonStr = text.substring(start, i + 1)
            const json = JSON.parse(jsonStr)
            events.push({ json, start, end: i + 1 })
          } catch (e) {
            console.warn('Failed to parse JSON:', text.substring(start, Math.min(i + 1, start + 200)), e)
          }
          start = -1
        }
      }
    }

    i++
  }

  return events
}

const parseNdjsonWithRemainder = (text: string): { events: any[]; remainder: string } => {
  const normalized = text.replace(/}\s*{/g, '}\n{')
  const lines = normalized
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length < 1) {
    return { events: [], remainder: '' }
  }

  const events: any[] = []
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    if (!line.startsWith('{') || !line.endsWith('}')) {
      return { events, remainder: lines.slice(i).join('\n') }
    }
    try {
      events.push(JSON.parse(line))
    } catch (e) {
      return { events, remainder: lines.slice(i).join('\n') }
    }
  }

  return { events, remainder: '' }
}

const parseJSONEventsWithRemainder = (text: string): { events: any[]; remainder: string } => {
  const parsed = parseJSONEvents(text)
  if (parsed.length === 0) {
    return { events: [], remainder: text }
  }

  const lastEnd = parsed[parsed.length - 1]?.end ?? 0
  const remainder = lastEnd > 0 ? text.slice(lastEnd) : text
  return { events: parsed.map((event) => event.json), remainder }
}

// Format event_type to display label: "scope_updated" -> "Scope Updated"
const formatEventTypeLabel = (eventType: string): string => {
  return eventType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Entity update info from scope events (for "Theo Updated" badges)
export type ScopeEntityUpdateInfo = {
  changedEntities: string[]
  updateSummary: string
  isNewEntity?: boolean
  addedFilterIds?: string[]
  changedFilterIds?: string[]
  addedFieldNames?: string[]
  changedFieldNames?: string[]
}

// Setup task info from SSE events (for loading screen progress)
export type SetupTaskInfo = {
  taskId: string
  taskType: 'entity' | 'agent' | 'other'
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  taskIndex: number
  taskTotal: number
  progress?: { current: number; total: number }
  message?: string
}

export type UseChatStreamOptions = {
  workspaceId?: string
  initialMessages?: ChatMessage[]
  onIntentUpdated?: (intent: string) => void
  onIntentProposed?: (intentPackage: IntentPackage | null) => void
  // NEW: Intent package updated event (bidirectional sync)
  onIntentPackageUpdated?: (intentPackage: IntentPackage, updateSummary?: string) => void
  // Data scope callbacks (for scoping phase)
  onScopeUpdated?: (dataScope: DataScope, ready: boolean) => void
  onScopeReady?: (dataScope: DataScope) => void
  // NEW: Unified ScopeState callbacks for merged scoping/review
  // entityUpdateInfo contains changed_entities, added_filter_ids, etc. from the SSE event
  onScopeStateUpdated?: (scopeState: ScopeState, entityUpdateInfo?: ScopeEntityUpdateInfo) => void
  onScopeStateReady?: (scopeState: ScopeState) => void
  // Preview data callback (for streaming data to preview tab)
  onPreviewData?: (entityType: string, data: Record<string, unknown>[], totalCount: number) => void
  // Clarification callback (for data scoping stage)
  onClarificationNeeded?: (question: ClarificationQuestion) => void
  // Execution callbacks (for loading/review phases)
  onExecutionProgress?: (entityType: string, progress: number, total: number) => void
  onExecutionComplete?: (results: ExecutionResult[]) => void
  // Setup task callbacks (for data staging loading screen)
  onSetupTask?: (task: SetupTaskInfo) => void
  // Team building callbacks (for aiTeam phase)
  onTeamBuildingStatus?: (message: string) => void
  onTeamComplete?: (teamConfig: TeamConfig) => void
  // Ontology creation callbacks
  onOntologyProposed?: (ontologyPackage: OntologyPackage) => void
  onOntologyUpdated?: (ontologyPackage: OntologyPackage, updateSummary?: string) => void
  onOntologyFinalized?: (ontologyPackage: OntologyPackage) => void
  currentWorkspace?: Workspace | null
  setCurrentWorkspace?: (ws: Workspace) => void
}

export type UseChatStreamReturn = {
  messages: ChatMessage[]
  isAgentWorking: boolean
  setIsAgentWorking: (working: boolean) => void
  isTurnOpen: boolean
  setIsTurnOpen: (open: boolean) => void
  runId: string
  lastEventType: string | null
  startStream: (runId: string, tenantId: string, options?: { initialMessage?: string; showThinking?: boolean }) => void
  stopStream: () => void
  pendingClarifications: ClarificationQuestion[]
  clearClarifications: () => void
  addOptimisticMessage: (msg: { role: 'user' | 'assistant'; content: string }) => void
  workflowError: string | null
  clearWorkflowError: () => void
}

export function useChatStream(options: UseChatStreamOptions): UseChatStreamReturn {
  const {
    workspaceId,
    initialMessages,
    onIntentUpdated,
    onIntentProposed,
    onIntentPackageUpdated,
    onScopeUpdated,
    onScopeReady,
    onScopeStateUpdated,
    onScopeStateReady,
    onPreviewData,
    onClarificationNeeded,
    onExecutionProgress,
    onExecutionComplete,
    onSetupTask,
    onTeamBuildingStatus,
    onTeamComplete,
    onOntologyProposed,
    onOntologyUpdated,
    onOntologyFinalized,
    currentWorkspace,
    setCurrentWorkspace,
  } = options

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    // Initialize with sorted messages if provided
    if (initialMessages && initialMessages.length > 0) {
      return [...initialMessages].sort((a, b) => a.timestamp - b.timestamp)
    }
    return []
  })
  const [isAgentWorking, setIsAgentWorking] = useState(false)
  const [isTurnOpen, setIsTurnOpen] = useState(false)
  const [runId, setRunId] = useState<string>('')
  const [lastEventType, setLastEventType] = useState<string | null>(null)
  const [pendingClarifications, setPendingClarifications] = useState<ClarificationQuestion[]>([])
  const [workflowError, setWorkflowError] = useState<string | null>(null)

  // Track answered clarification IDs to avoid re-showing on stream replay
  const answeredClarificationIdsRef = useRef<Set<string>>(new Set())

  const clearClarifications = useCallback(() => {
    setPendingClarifications([])
  }, [])

  const clearWorkflowError = useCallback(() => {
    setWorkflowError(null)
  }, [])

  // Add a message optimistically (shown immediately before server confirms)
  const addOptimisticMessage = useCallback((msg: { role: 'user' | 'assistant'; content: string }) => {
    const optimisticId = `optimistic-${Date.now()}`
    setMessages((prev) => {
      const newMessages = [
        ...prev,
        {
          id: optimisticId,
          role: msg.role,
          content: msg.content,
          timestamp: Date.now(),
        },
      ]
      return newMessages.sort((a, b) => a.timestamp - b.timestamp)
    })
  }, [])

  const lastEventIdRef = useRef<string | null>(null)
  const esRef = useRef<AuthenticatedEventSource | null>(null)
  const processedEventsRef = useRef<Set<string>>(new Set())
  const activeAgentsRef = useRef<Set<string>>(new Set())
  const eventSequenceRef = useRef<number>(0)
  const processedIntentEventsRef = useRef<Set<string>>(new Set())
  const isUpdatingIntentRef = useRef<boolean>(false)
  const currentWorkspaceIdRef = useRef<string>(workspaceId || '')
  const closedMessageIdsRef = useRef<Set<string>>(new Set())
  const openMessageIdsRef = useRef<Set<string>>(new Set())
  const ndjsonRemainderRef = useRef<string>('')

  // Batching refs for smooth streaming - collect events and process once per frame
  const pendingAgentMessagesRef = useRef<Map<string, { content: string; accumulatedLength: number | null; isComplete: boolean; timestamp: number }>>(new Map())
  const batchScheduledRef = useRef<number | null>(null)

  // Process all batched agent messages in a single state update
  const processBatchedAgentMessages = useCallback(() => {
    const pendingMessages = pendingAgentMessagesRef.current
    if (pendingMessages.size === 0) {
      batchScheduledRef.current = null
      return
    }

    // Clone and clear the pending map
    const messagesToProcess = new Map(pendingMessages)
    pendingMessages.clear()
    batchScheduledRef.current = null

    setMessages((prev) => {
      let updated = [...prev]
      let hasChanges = false

      messagesToProcess.forEach((data, messageId) => {
        const { content: newContent, accumulatedLength, isComplete, timestamp } = data

        // Check if message is already closed
        if (closedMessageIdsRef.current.has(messageId) && !isComplete) {
          return
        }

        openMessageIdsRef.current.add(messageId)

        const existingIndex = updated.findIndex((m) => m.id === messageId)
        if (existingIndex >= 0) {
          // Append to existing message, honoring accumulated_length when provided
          const existingContent = updated[existingIndex].content
          let nextContent = existingContent
          if (accumulatedLength != null) {
            if (newContent.length >= accumulatedLength) {
              nextContent = newContent
            } else if (existingContent.length >= accumulatedLength) {
              nextContent = existingContent
            } else if (existingContent.length + newContent.length > accumulatedLength) {
              const remaining = Math.max(0, accumulatedLength - existingContent.length)
              nextContent = existingContent + newContent.slice(0, remaining)
            } else {
              nextContent = existingContent + newContent
            }
          } else {
            nextContent = existingContent + newContent
          }

          if (nextContent !== updated[existingIndex].content || isComplete !== updated[existingIndex].isComplete) {
            updated[existingIndex] = {
              ...updated[existingIndex],
              content: nextContent,
              isComplete: updated[existingIndex].isComplete || isComplete,
            }
            hasChanges = true
          }

          if (isComplete) {
            closedMessageIdsRef.current.add(messageId)
            openMessageIdsRef.current.delete(messageId)
          }
        } else {
          // Create new message
          if (updated.some((m) => m.id === messageId)) return

          if (isComplete) {
            closedMessageIdsRef.current.add(messageId)
            openMessageIdsRef.current.delete(messageId)
          }

          // If the only chunk we received is a completion marker with no content,
          // don't create an empty assistant message.
          if (isComplete && !newContent && (accumulatedLength == null || accumulatedLength <= 0)) {
            return
          }

          const initialContent =
            accumulatedLength != null && newContent.length > accumulatedLength
              ? newContent.slice(0, accumulatedLength)
              : newContent

          updated.push({
            id: messageId,
            role: 'assistant' as const,
            content: initialContent,
            timestamp,
            isComplete,
          })
          hasChanges = true
        }
      })

      // Update turn open state
      // If there are no active agents and no open messages, reset turn state
      // This handles cases where agent_completed events aren't sent
      const hasOpenMessages = openMessageIdsRef.current.size > 0
      const hasActiveAgents = activeAgentsRef.current.size > 0
      
      if (!hasOpenMessages && !hasActiveAgents) {
        setIsTurnOpen(false)
      } else {
        setIsTurnOpen(hasOpenMessages)
      }

      if (!hasChanges) return prev
      return updated.sort((a, b) => a.timestamp - b.timestamp)
    })
  }, [])

  // Queue an agent message event for batched processing
  const queueAgentMessage = useCallback((messageId: string, content: string, accumulatedLength: number | null, isComplete: boolean, timestamp: number) => {
    const pending = pendingAgentMessagesRef.current.get(messageId)

    if (pending) {
      // Merge with existing pending data - accumulate content
      let mergedContent = pending.content
      if (accumulatedLength != null) {
        if (content.length >= accumulatedLength) {
          mergedContent = content
        } else if (pending.content.length >= accumulatedLength) {
          mergedContent = pending.content
        } else if (pending.content.length + content.length > accumulatedLength) {
          const remaining = Math.max(0, accumulatedLength - pending.content.length)
          mergedContent = pending.content + content.slice(0, remaining)
        } else {
          mergedContent = pending.content + content
        }
      } else {
        mergedContent = pending.content + content
      }

      pendingAgentMessagesRef.current.set(messageId, {
        content: mergedContent,
        accumulatedLength: accumulatedLength ?? pending.accumulatedLength,
        isComplete: pending.isComplete || isComplete,
        timestamp: pending.timestamp,
      })
    } else {
      pendingAgentMessagesRef.current.set(messageId, {
        content,
        accumulatedLength,
        isComplete,
        timestamp,
      })
    }

    // Schedule processing if not already scheduled
    if (batchScheduledRef.current === null) {
      batchScheduledRef.current = requestAnimationFrame(processBatchedAgentMessages)
    }
  }, [processBatchedAgentMessages])

  // Reset state when workspace changes
  useEffect(() => {
    if (workspaceId && workspaceId !== currentWorkspaceIdRef.current) {
      console.log('[useChatStream] Workspace changed, resetting state. Old:', currentWorkspaceIdRef.current, 'New:', workspaceId)

      // Close existing connection
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }

      // Clear all refs
      lastEventIdRef.current = null
      processedEventsRef.current = new Set()
      activeAgentsRef.current = new Set()
      eventSequenceRef.current = 0
      processedIntentEventsRef.current = new Set()
      isUpdatingIntentRef.current = false
      currentWorkspaceIdRef.current = workspaceId

      // Clear state
      setMessages([])
      setIsAgentWorking(false)
      setRunId('')
      setLastEventType(null)
      setWorkflowError(null)
    }
  }, [workspaceId])

  const stopStream = useCallback(() => {
    console.log('[useChatStream] Stopping stream')
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  const startStream = useCallback(
    (rid: string, tenantId: string, options?: { initialMessage?: string; showThinking?: boolean }) => {
      console.log('[useChatStream] Starting stream for workspaceId:', workspaceId, 'runId:', rid, 'options:', options)

      if (esRef.current) {
        console.log('[useChatStream] Closing existing connection before opening new one')
        esRef.current.close()
        esRef.current = null
      }
      lastEventIdRef.current = null
      processedEventsRef.current = new Set()
      processedIntentEventsRef.current = new Set()
      eventSequenceRef.current = 0
      closedMessageIdsRef.current = new Set()
      openMessageIdsRef.current = new Set()
      setIsTurnOpen(false)
      ndjsonRemainderRef.current = ''
      setWorkflowError(null)

      // If an initial message string is provided, seed the messages array with it; otherwise clear messages
      if (options?.initialMessage) {
        const optimisticId = `optimistic-${Date.now()}`
        setMessages([{
          id: optimisticId,
          role: 'user',
          content: options.initialMessage,
          timestamp: Date.now(),
        }])
        setIsTurnOpen(true)
      } else {
        setMessages([])
      }

      // Set thinking indicator if requested
      if (options?.showThinking) {
        setIsAgentWorking(true)
      } else {
        setIsAgentWorking(false)
      }

      activeAgentsRef.current = new Set()
      isUpdatingIntentRef.current = false
      closedMessageIdsRef.current = new Set()
      openMessageIdsRef.current = new Set()
      ndjsonRemainderRef.current = ''
      setRunId(rid)

      const apiBase = getApiBase().replace(/\/$/, '')
      const url = `${apiBase}/runs/${rid}/events?tid=${encodeURIComponent(tenantId)}`
      console.log('[useChatStream] Connecting to SSE:', url)
      const es = new AuthenticatedEventSource(url)

      es.onmessage = (evt) => {
        if (evt.lastEventId && evt.lastEventId === lastEventIdRef.current) return
        lastEventIdRef.current = evt.lastEventId || lastEventIdRef.current
        const text = evt.data ?? ''
        if (!text) return

        const timestamp = Date.now()
        const combinedText = `${ndjsonRemainderRef.current}${text}`
        const { events: jsonEvents, remainder } = parseJSONEventsWithRemainder(combinedText)
        if (jsonEvents.length > 0) {
          ndjsonRemainderRef.current = remainder
        } else {
          const ndjson = parseNdjsonWithRemainder(combinedText)
          ndjsonRemainderRef.current = ndjson.remainder
          if (ndjson.events.length > 0) {
            ndjson.events.forEach((jsonData, index) => processEvent(jsonData, index))
            return
          }
        }

        function processEvent(jsonData: StreamEvent, index: number) {
          if (!jsonData.event_type) {
            console.warn('JSON event missing event_type:', jsonData)
            return
          }

          const eventType = jsonData.event_type
          eventSequenceRef.current += 1
          const sequence = eventSequenceRef.current
          const eventId = `${eventType}-${jsonData.agent_id || 'unknown'}-${jsonData.subtask_id || 'main'}-${timestamp}-${index}-${sequence}`

          if (processedEventsRef.current.has(eventId)) {
            return
          }
          processedEventsRef.current.add(eventId)

          const eventTimestamp = timestamp + sequence / 1000000
          setLastEventType(eventType)

          console.log('[useChatStream] Processing event for workspaceId:', workspaceId, 'runId:', rid, 'eventType:', eventType)

          // Handle different event types
          if (
            eventType === 'task_decomposed' ||
            eventType === 'subtask_assigned' ||
            eventType === 'task_completed' ||
            eventType === 'user_message' ||
            eventType === 'workflow_stage'
          ) {
            if (eventType === 'user_message') {
              setIsTurnOpen(true)

              // Track answered clarification IDs from clarification_responses
              const clarificationResponses = jsonData.clarification_responses as Array<{ question_id: string }> | undefined
              if (clarificationResponses && Array.isArray(clarificationResponses)) {
                for (const response of clarificationResponses) {
                  if (response.question_id) {
                    answeredClarificationIdsRef.current.add(response.question_id)
                    // Also remove from pending if somehow still there
                    setPendingClarifications((prev) =>
                      prev.filter((q) => q.question_id !== response.question_id)
                    )
                  }
                }
              }
            }
            setMessages((prev) => {
              const messageId = `event-${eventId}`
              if (prev.some((m) => m.id === messageId)) return prev

              let content = jsonData.message || ''
              if (eventType === 'task_completed') {
                content = jsonData.result || jsonData.message || 'Task completed'
              }

              const role: 'user' | 'assistant' = eventType === 'user_message' ? 'user' : 'assistant'

              // For user_message events, skip if we already have this message (optimistic update)
              // Use normalized comparison to handle whitespace differences
              if (eventType === 'user_message') {
                const normalizedContent = content.trim()
                const alreadyExists = prev.some(
                  (m) => m.role === 'user' && m.content.trim() === normalizedContent
                )
                if (alreadyExists) {
                  return prev
                }
              }

              return [
                ...prev,
                {
                  id: messageId,
                  role,
                  content,
                  timestamp: eventTimestamp,
                },
              ].sort((a, b) => a.timestamp - b.timestamp)
            })

            if (eventType === 'task_completed') {
              activeAgentsRef.current.clear()
              setIsAgentWorking(false)
            }
          } else if (eventType === 'agent_message') {
            // Handle multipart agent messages - queue for batched processing
            const serverMessageId = jsonData.message_id
            const newContent = jsonData.message || ''
            const accumulatedLength =
              typeof jsonData.accumulated_length === 'number' ? jsonData.accumulated_length : null
            const isComplete = jsonData.completed === true
            // Use message_id from server if available, otherwise fallback to eventId for backward compatibility
            const messageId = serverMessageId ? `agent-message-${serverMessageId}` : `event-${eventId}`

            // Skip empty completion markers
            if (isComplete && !newContent && (accumulatedLength == null || accumulatedLength <= 0)) {
              return
            }

            // Queue for batched processing (single state update per animation frame)
            queueAgentMessage(messageId, newContent, accumulatedLength, isComplete, eventTimestamp)

            // Turn off thinking indicator when agent message arrives
            // (agent is responding, no longer "thinking")
            setIsAgentWorking(false)
            
            // If there are no active agents, assume the agent is done and reset turn state
            // This handles cases where agent_completed events aren't sent
            if (activeAgentsRef.current.size === 0) {
              // Schedule reset after batched processing completes
              setTimeout(() => {
                // If still no active agents, reset turn state
                if (activeAgentsRef.current.size === 0) {
                  setIsTurnOpen(false)
                  // Mark any open messages as closed since agent is done
                  openMessageIdsRef.current.forEach((msgId) => {
                    closedMessageIdsRef.current.add(msgId)
                  })
                  openMessageIdsRef.current.clear()
                }
              }, 200)
            }
          } else if (eventType === 'agent_thinking' || eventType === 'tool_called' || eventType === 'agent_completed') {
            const agentId = jsonData.agent_id || 'unknown'

            if (eventType === 'agent_thinking' || eventType === 'tool_called') {
              activeAgentsRef.current.add(agentId)
              setIsAgentWorking(true)
            } else if (eventType === 'agent_completed') {
              activeAgentsRef.current.delete(agentId)
              if (activeAgentsRef.current.size === 0) {
                setIsAgentWorking(false)
                // Reset turn open state when agent completes - allows user to respond
                setIsTurnOpen(false)
                openMessageIdsRef.current.clear()
              }
            }
          } else if (eventType === 'intent_proposed' || eventType === 'intent_finalized' || eventType === 'intent_ready') {
            // Notify about intent_proposed for phase transition, passing intent_package
            if (eventType === 'intent_proposed' && onIntentProposed) {
              onIntentProposed(jsonData.intent_package || null)
            }

            // For intent_finalized and intent_ready, update the intent package state
            // These events contain the finalized intent with all user edits incorporated
            if ((eventType === 'intent_finalized' || eventType === 'intent_ready') && jsonData.intent_package && onIntentPackageUpdated) {
              console.log('[useChatStream] Intent finalized/ready, updating package:', eventType)
              onIntentPackageUpdated(jsonData.intent_package as IntentPackage, `${eventType}`)
            }

            // After intent_finalized, the agent will start working on the next phase
            // Show thinking indicator until the next agent_message arrives
            if (eventType === 'intent_finalized') {
              setIsAgentWorking(true)
            }

            // Handle intent update
            if (jsonData.agent_id === 'theo' && jsonData.intent_text && workspaceId) {
              const intentHash = `${eventType}-${jsonData.intent_text.substring(0, 50)}-${timestamp}`

              if (processedIntentEventsRef.current.has(intentHash)) {
                return
              }

              if (isUpdatingIntentRef.current) {
                return
              }

              const currentIntent = currentWorkspace?.intent || ''
              const intentText = jsonData.intent_text

              if (currentIntent.trim() === intentText.trim()) {
                processedIntentEventsRef.current.add(intentHash)
                return
              }

              isUpdatingIntentRef.current = true
              processedIntentEventsRef.current.add(intentHash)

              updateWorkspace({
                workspaceId,
                intent: intentText,
              })
                .then(() => fetchWorkspaceById(workspaceId))
                .then((updatedWorkspace) => {
                  if (updatedWorkspace && setCurrentWorkspace) {
                    if (updatedWorkspace.intent !== currentIntent) {
                      setCurrentWorkspace(updatedWorkspace)
                      if (onIntentUpdated) {
                        onIntentUpdated(intentText)
                      }
                    }
                  }
                })
                .catch((error) => {
                  console.error('Failed to update workspace intent:', error)
                  processedIntentEventsRef.current.delete(intentHash)
                })
                .finally(() => {
                  isUpdatingIntentRef.current = false
                })

              // NOTE: Do NOT add intent_proposed/finalized message to chat - the conversational
              // text comes through agent_message events. The intent event is for state management.
            }
          } else if (eventType === 'intent_updated') {
            // Handle intent_updated event (bidirectional sync)
            // This is sent by AI when it updates the intent package
            console.log('[useChatStream] Intent updated event:', jsonData)

            if (jsonData.intent_package && onIntentPackageUpdated) {
              const intentPackage = jsonData.intent_package as IntentPackage
              const updateSummary = jsonData.update_summary as string | undefined
              onIntentPackageUpdated(intentPackage, updateSummary)
            }

            // NOTE: Do NOT add intent_updated message to chat - the conversational
            // text comes through agent_message events. The intent_updated event is for
            // structured data synchronization between frontend and backend.
          } else if (eventType === 'scope_updated' || eventType === 'scope_ready' || eventType === 'scope_update') {
            // Handle data scope events (for scoping phase)
            // Supports both legacy format (data_scope) and new format (entities array)
            console.log('[useChatStream] Scope event:', eventType, jsonData)

            let dataScope: DataScope | undefined = jsonData.data_scope as DataScope | undefined

            // If no data_scope but entities array exists, transform to DataScope format
            if (!dataScope && jsonData.entities && Array.isArray(jsonData.entities)) {
              dataScope = {
                scopes: jsonData.entities.map((entity: any) => ({
                  entity_type: entity.entity_type,
                  reasoning: entity.reasoning || '',
                  filters: entity.filters || [],
                  // Preserve null/undefined - don't convert to 0 here so UI can distinguish
                  // between "no count yet" vs "actual zero records"
                  estimated_count: entity.estimated_count ?? entity.count ?? null,
                  // Preserve additional fields for richer display
                  relevance_level: entity.relevance_level,
                  fields_of_interest: entity.fields_of_interest,
                })),
                // Preserve relationships and metadata from the event
                relationships: jsonData.relationships,
                summary: jsonData.summary,
                confidence: jsonData.confidence,
              }
              console.log('[useChatStream] Transformed entities to DataScope:', dataScope)
            }

            if (dataScope) {
              // Determine if scope is ready based on:
              // 1. ready flag on the event (new pattern, replaces scope_finalized)
              // 2. scope_ready event type (legacy)
              // 3. high confidence level (legacy fallback)
              const isReady = jsonData.ready === true || eventType === 'scope_ready' || jsonData.confidence === 'high'

              if ((eventType === 'scope_update' || eventType === 'scope_updated') && onScopeUpdated) {
                // scope_update/scope_updated - check ready flag from event
                onScopeUpdated(dataScope, isReady)
                if (isReady && onScopeReady) {
                  onScopeReady(dataScope)
                }
              } else if (eventType === 'scope_ready' && onScopeReady) {
                // scope_ready means scope is finalized and ready for confirmation
                onScopeReady(dataScope)
                // Also call onScopeUpdated with ready=true for components that use that pattern
                if (onScopeUpdated) {
                  onScopeUpdated(dataScope, true)
                }
              }

              // Extract entity update info from the event (for "Theo Updated" badges)
              const changedEntities = jsonData.changed_entities as string[] | undefined
              const entityUpdateInfo: ScopeEntityUpdateInfo | undefined =
                changedEntities && changedEntities.length > 0
                  ? {
                      changedEntities,
                      updateSummary: (jsonData.update_summary as string) || 'Updated scope',
                      isNewEntity: jsonData.is_new_entity as boolean | undefined,
                      addedFilterIds: jsonData.added_filter_ids as string[] | undefined,
                      changedFilterIds: jsonData.changed_filter_ids as string[] | undefined,
                      addedFieldNames: jsonData.added_field_names as string[] | undefined,
                      changedFieldNames: jsonData.changed_field_names as string[] | undefined,
                    }
                  : undefined

              // NEW: Also call ScopeState callbacks for unified experience
              // Check if we have new scope_state format first
              if (jsonData.scope_state) {
                const scopeState = jsonData.scope_state as ScopeState
                if (eventType === 'scope_ready' && onScopeStateReady) {
                  onScopeStateReady(scopeState)
                } else if ((eventType === 'scope_update' || eventType === 'scope_updated') && onScopeStateUpdated) {
                  onScopeStateUpdated(scopeState, entityUpdateInfo)
                }
              } else {
                // Convert DataScope to ScopeState for backward compatibility
                const scopeState = convertDataScopeToScopeState(dataScope)
                if (eventType === 'scope_ready' && onScopeStateReady) {
                  onScopeStateReady(scopeState)
                } else if ((eventType === 'scope_update' || eventType === 'scope_updated') && onScopeStateUpdated) {
                  onScopeStateUpdated(scopeState, entityUpdateInfo)
                }
              }

              // Attach scope events to the last assistant message for collapsible display
              if (jsonData.message) {
                const attachedEvent: AttachedEvent = {
                  eventType,
                  displayLabel: formatEventTypeLabel(eventType),
                  message: jsonData.message as string,
                  timestamp: eventTimestamp,
                }

                setMessages((prev) => {
                  // Find the last assistant message
                  const lastAssistantIdx = [...prev].reverse().findIndex((m) => m.role === 'assistant')
                  if (lastAssistantIdx === -1) return prev

                  const actualIdx = prev.length - 1 - lastAssistantIdx
                  const updated = [...prev]
                  updated[actualIdx] = {
                    ...updated[actualIdx],
                    attachedEvents: [...(updated[actualIdx].attachedEvents || []), attachedEvent],
                  }
                  return updated
                })
              }
            }
          } else if (eventType === 'preview_data') {
            // Handle preview data streaming for the preview tab
            console.log('[useChatStream] Preview data event:', jsonData)
            const previewEvent = jsonData as PreviewDataEvent
            if (onPreviewData && previewEvent.entity_type && previewEvent.data) {
              onPreviewData(previewEvent.entity_type, previewEvent.data, previewEvent.total_count || 0)
            }

            // NOTE: Do NOT add scope_update message to chat - the conversational text
            // comes through agent_message events. The scope_update.message is a technical
            // summary for the scope panel, not for the chat UI.
          } else if (eventType === 'clarification_needed') {
            // Handle clarification_needed event (data scoping stage)
            console.log('[useChatStream] Clarification needed:', jsonData)

            const questionId = jsonData.question_id || `clarification-${eventTimestamp}`

            // Skip if this clarification was already answered (happens on stream replay)
            if (answeredClarificationIdsRef.current.has(questionId)) {
              console.log('[useChatStream] Skipping already-answered clarification:', questionId)
              return
            }

            // Turn off agent working indicator while waiting for user input
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
            openMessageIdsRef.current.clear()
            setIsTurnOpen(false)

            // Build the clarification question from the event
            const clarificationQuestion: ClarificationQuestion = {
              question_id: questionId,
              question: jsonData.question || jsonData.message || 'Please clarify',
              context: jsonData.context,
              options: jsonData.options || [],
              affects_entities: jsonData.affects_entities,
              agent_id: jsonData.agent_id,
              stage: jsonData.stage,
            }

            // Add to pending clarifications (queue multiple questions)
            setPendingClarifications((prev) => {
              // Avoid duplicate questions
              if (prev.some((q) => q.question_id === clarificationQuestion.question_id)) {
                return prev
              }
              return [...prev, clarificationQuestion]
            })

            // Notify callback if provided
            if (onClarificationNeeded) {
              onClarificationNeeded(clarificationQuestion)
            }

            // Add message to chat showing the clarification request
            if (jsonData.message) {
              const clarificationMessage = jsonData.message
              setMessages((prev) => {
                const messageId = `event-${eventId}`
                if (prev.some((m) => m.id === messageId)) return prev

                return [
                  ...prev,
                  {
                    id: messageId,
                    role: 'assistant' as const,
                    content: clarificationMessage,
                    timestamp: eventTimestamp,
                  },
                ].sort((a, b) => a.timestamp - b.timestamp)
              })
            }
          } else if (eventType === 'entity_complete') {
            // Handle entity_complete event (data execution stage)
            console.log('[useChatStream] Entity complete:', jsonData)
            if (onExecutionProgress && jsonData.entity_type) {
              onExecutionProgress(jsonData.entity_type, jsonData.total_count || 0, jsonData.total_count || 0)
            }
          } else if (eventType === 'execution_complete') {
            // Handle execution_complete event (data execution stage)
            console.log('[useChatStream] Execution complete:', jsonData)
            if (onExecutionComplete && jsonData.results) {
              onExecutionComplete(jsonData.results)
            }
          } else if (eventType === 'setup_task') {
            // Handle setup_task events (data staging progress)
            console.log('[useChatStream] Setup task:', jsonData)
            if (onSetupTask) {
              const taskInfo: SetupTaskInfo = {
                taskId: jsonData.task_id || `task-${eventTimestamp}`,
                taskType: jsonData.task_type === 'entity' ? 'entity' : jsonData.task_type === 'agent' ? 'agent' : 'other',
                title: jsonData.title || jsonData.message || 'Task',
                status: jsonData.status === 'completed' ? 'completed' : jsonData.status === 'running' ? 'running' : jsonData.status === 'failed' ? 'failed' : 'pending',
                taskIndex: jsonData.task_index ?? 0,
                taskTotal: jsonData.task_total ?? 1,
                progress: jsonData.progress,
                message: jsonData.message,
              }
              onSetupTask(taskInfo)
            }
          } else if (eventType === 'team_building_started') {
            // Handle team_building_started event
            console.log('[useChatStream] Team building started:', jsonData)
            if (onTeamBuildingStatus) {
              onTeamBuildingStatus(jsonData.message || 'Building your AI team...')
            }
          } else if (eventType === 'team_complete') {
            // Handle team_complete event
            console.log('[useChatStream] Team complete:', jsonData)
            // Handle both snake_case and camelCase field names
            const teamConfigData = jsonData.team_config || jsonData.teamConfig
            if (onTeamComplete && teamConfigData) {
              onTeamComplete(teamConfigData)
            }
          } else if (eventType === 'ontology_proposed') {
            // Handle ontology_proposed event
            console.log('[useChatStream] Ontology proposed:', jsonData)
            // ontology_package can be at top level or in metadata
            const ontologyPackage = (jsonData.ontology_package || jsonData.metadata?.ontology_package) as OntologyPackage | undefined
            if (onOntologyProposed && ontologyPackage) {
              onOntologyProposed(ontologyPackage)
            }
            // Turn off agent working indicator when ontology is proposed
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
            // Reset turn open state - agent has finished responding
            setIsTurnOpen(false)
            openMessageIdsRef.current.clear()
          } else if (eventType === 'ontology_updated') {
            // Handle ontology_updated event
            console.log('[useChatStream] Ontology updated:', jsonData)
            // ontology_package can be at top level or in metadata
            const ontologyPackage = (jsonData.ontology_package || jsonData.metadata?.ontology_package) as OntologyPackage | undefined
            const updateSummary = (jsonData.update_summary || jsonData.metadata?.update_summary) as string | undefined
            if (onOntologyUpdated && ontologyPackage) {
              onOntologyUpdated(ontologyPackage, updateSummary)
            }
            // Reset turn open state - agent has finished responding
            setIsTurnOpen(false)
            openMessageIdsRef.current.clear()
          } else if (eventType === 'ontology_finalized') {
            // Handle ontology_finalized event
            console.log('[useChatStream] Ontology finalized:', jsonData)
            // ontology_package can be at top level or in metadata
            const ontologyPackage = (jsonData.ontology_package || jsonData.metadata?.ontology_package) as OntologyPackage | undefined
            if (onOntologyFinalized && ontologyPackage) {
              onOntologyFinalized(ontologyPackage)
            }
            // Turn off agent working indicator
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
            // Reset turn open state - agent has finished responding
            setIsTurnOpen(false)
            openMessageIdsRef.current.clear()
          } else if (eventType === 'workflow_started') {
            // Handle workflow_started event (for ontology creation workflow)
            console.log('[useChatStream] Workflow started:', jsonData)
            setIsAgentWorking(true)
          } else if (eventType === 'workflow_complete') {
            // Handle workflow_complete event
            console.log('[useChatStream] Workflow complete:', jsonData)
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
          } else if (eventType === 'workflow_error') {
            // Handle workflow_error event
            console.error('[useChatStream] Workflow error:', jsonData)
            const errorMessage = jsonData.message || jsonData.error || 'An error occurred in the workflow'
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
            setIsTurnOpen(false)
            // Add error message to chat
            setMessages((prev) => {
              const messageId = `workflow-error-${eventId}`
              if (prev.some((m) => m.id === messageId)) return prev
              return [
                ...prev,
                {
                  id: messageId,
                  role: 'assistant' as const,
                  content: `**Error:** ${errorMessage}`,
                  timestamp: eventTimestamp,
                },
              ].sort((a, b) => a.timestamp - b.timestamp)
            })
          } else if (eventType === 'nodes_created' || eventType === 'relationships_created') {
            // Handle data loading progress events
            console.log('[useChatStream] Data loading progress:', eventType, jsonData)
            const created = typeof jsonData.created === 'number' ? jsonData.created : 0
            const total = typeof jsonData.total === 'number' ? jsonData.total : undefined
            const message = jsonData.message || (eventType === 'nodes_created' ? `Created ${created} nodes` : `Created ${created} relationships`)

            setMessages((prev) => {
              const messageId = `data-loading-${eventType}-${eventId}`
              if (prev.some((m) => m.id === messageId)) return prev

              return [
                ...prev,
                {
                  id: messageId,
                  role: 'assistant' as const,
                  content: message,
                  timestamp: eventTimestamp,
                  dataLoadingProgress: {
                    type: eventType as 'nodes_created' | 'relationships_created',
                    created,
                    total,
                  },
                },
              ].sort((a, b) => a.timestamp - b.timestamp)
            })
          } else if (eventType === 'csv_analyzed') {
            // Handle CSV analysis events
            console.log('[useChatStream] CSV analyzed:', jsonData)
            const message = jsonData.message || 'CSV structure analyzed'
            const csvAnalysis: CsvAnalysisData | undefined = jsonData.columns && jsonData.row_count !== undefined
              ? {
                  columns: jsonData.columns as CsvAnalysisData['columns'],
                  row_count: jsonData.row_count,
                  has_headers: jsonData.has_headers !== undefined ? jsonData.has_headers : true,
                }
              : undefined

            setMessages((prev) => {
              const messageId = `csv-analyzed-${eventId}`
              if (prev.some((m) => m.id === messageId)) return prev

              return [
                ...prev,
                {
                  id: messageId,
                  role: 'assistant' as const,
                  content: message,
                  timestamp: eventTimestamp,
                  csvAnalysis,
                },
              ].sort((a, b) => a.timestamp - b.timestamp)
            })
          } else if (eventType === 'error') {
            // Handle generic error event - display as error message in chat
          } else if (eventType === 'setup_complete') {
            // Handle setup_complete event (final completion signal for entire setup flow)
            const data = jsonData as { stage?: string; team_name?: string }
            console.log('[useChatStream] Setup complete:', jsonData)

            // If stage is 'completed', this is the team building completion
            // The backend doesn't always send team_complete separately - setup_complete with stage=completed
            // serves as the signal that team building is done
            const stage = data.stage
            const teamName = data.team_name

            if (stage === 'completed' && onTeamComplete) {
              // Construct a minimal team config from setup_complete event data
              // The actual team config should already be set from setup_task events
              // This just signals completion so the loading screen can transition
              const minimalTeamConfig: TeamConfig = {
                team_id: teamName || `team-${workspaceId}`,
                team_name: teamName || 'AI Team',
                agents: [], // The actual agents are already tracked via setup_task events
              }
              onTeamComplete(minimalTeamConfig)
            }
          } else if (eventType === 'workflow_complete') {
            // Handle workflow_complete event (alternative completion signal)
            const workflowData = jsonData as { team_name?: string }
            console.log('[useChatStream] Workflow complete:', jsonData)

            if (onTeamComplete) {
              const teamName = workflowData.team_name
              const minimalTeamConfig: TeamConfig = {
                team_id: teamName || `team-${workspaceId}`,
                team_name: teamName || 'AI Team',
                agents: [],
              }
              onTeamComplete(minimalTeamConfig)
            }
          } else if (eventType === 'error' || eventType === 'workflow_error') {
            // Handle generic error and workflow_error events - display as error message in chat
            const errData = jsonData as { error?: string; message?: string; stage?: string }
            console.error('[useChatStream] Error event:', jsonData)
            const errorMessage = errData.error || errData.message || 'An error occurred'
            const errorStage = errData.stage

            // Turn off agent working indicator and reset turn state
            activeAgentsRef.current.clear()
            setIsAgentWorking(false)
            openMessageIdsRef.current.clear()
            setIsTurnOpen(false)

            // Set workflow error state for components to display
            setWorkflowError(errorMessage)

            // Add error message to chat
            setMessages((prev) => {
              const messageId = `error-${eventId}`
              if (prev.some((m) => m.id === messageId)) return prev

              return [
                ...prev,
                {
                  id: messageId,
                  role: 'assistant' as const,
                  content: `**Error${errorStage ? ` during ${errorStage}` : ''}:** ${errorMessage}`,
                  timestamp: eventTimestamp,
                  isError: true,
                },
              ].sort((a, b) => a.timestamp - b.timestamp)
            })
          }
        }

        if (jsonEvents.length > 0) {
          jsonEvents.forEach((jsonData, index) => {
            processEvent(jsonData, index)
          })
        } else {
          try {
            const singleJson = JSON.parse(text)
            if (singleJson.event_type) {
              processEvent(singleJson, 0)
            }
          } catch (e) {
            // Not JSON
          }
        }
      }

      es.onerror = () => {}
      esRef.current = es
    },
    [workspaceId, currentWorkspace, setCurrentWorkspace, onIntentUpdated, onIntentProposed, onIntentPackageUpdated, onScopeUpdated, onScopeReady, onScopeStateUpdated, onScopeStateReady, onPreviewData, onClarificationNeeded, onExecutionProgress, onExecutionComplete, onSetupTask, onTeamBuildingStatus, onTeamComplete, queueAgentMessage]
  )

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
    }
  }, [])

  return {
    messages,
    isAgentWorking,
    setIsAgentWorking,
    isTurnOpen,
    setIsTurnOpen,
    runId,
    lastEventType,
    startStream,
    stopStream,
    pendingClarifications,
    clearClarifications,
    addOptimisticMessage,
    workflowError,
    clearWorkflowError,
  }
}

