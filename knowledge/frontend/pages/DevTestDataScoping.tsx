/**
 * DevTestDataScoping Page
 *
 * Development/testing page for the DataScopingView components.
 * Allows testing UI, layout, and functionality without running AI workflows.
 * Includes SSE sequence simulator for testing real-time update flows.
 *
 * Access at: /dev/data-scoping
 */

import { useState, useCallback, useRef } from 'react'
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Paper,
  Divider,
  Button,
  Stack,
  Alert,
  Chip,
  LinearProgress,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'

import DataScopingView from '../components/workspace/setup/scoping/DataScopingView'
import { type EntityUpdate } from '../components/workspace/setup/scoping/EntityCard'
import {
  mockScopeState,
  mockScopeStateLoading,
  mockScopeStateLowConfidence,
  mockScopeStateMinimal,
  mockIntentPackage,
  mockAvailableEntities,
} from '../components/workspace/setup/scoping/__mocks__/mockScopeState'
import type { ScopeState, Filter } from '../types/scopeState'
import type { ClarificationQuestion, ClarificationAnswer } from '../components/workspace/chat/ClarificationPanel'

// ============================================================================
// Types for SSE Simulation
// ============================================================================

interface ScopeUpdateEvent {
  event_type: string
  message?: string
  update_summary?: string
  changed_entities?: string[]
}

// ============================================================================
// Mock Clarification Questions
// ============================================================================

const mockClarifications: ClarificationQuestion[] = [
  {
    question_id: 'q1',
    question: 'Should we include historical claims from before 2024?',
    context: 'Including historical data would increase the dataset size significantly.',
    options: [
      { label: 'Yes, include 2023 data', description: 'Adds approximately 2M more claims' },
      { label: 'No, keep 2024 only', description: 'Maintains focused, current-year analysis' },
      { label: 'Include last 6 months of 2023', description: 'Balanced approach with recent history' },
    ],
  },
  {
    question_id: 'q2',
    question: 'How should we handle members with multiple plans?',
    context: 'Some members switch plans mid-year or have concurrent coverage.',
    options: [
      { label: 'Include all plan associations', description: 'Complete picture but may double-count' },
      { label: 'Primary plan only', description: 'Cleaner analysis but may miss nuances' },
    ],
  },
]

// ============================================================================
// SSE Event Sequences (for simulating real-time updates)
// ============================================================================

interface SSEStep {
  delay: number // ms before executing this step
  event: Partial<ScopeUpdateEvent> & {
    is_new_entity?: boolean
    added_filter_ids?: string[]
    changed_filter_ids?: string[]
    added_field_names?: string[]
    changed_field_names?: string[]
  }
  scopeStateTransform?: (prev: ScopeState) => ScopeState
}

interface SSESequence {
  name: string
  description: string
  steps: SSEStep[]
}

// Helper to add a filter to an entity
function addFilterToEntity(state: ScopeState, entityType: string, filter: Filter): ScopeState {
  return {
    ...state,
    entities: state.entities.map((e) =>
      e.entity_type === entityType
        ? { ...e, filters: [...e.filters, filter] }
        : e
    ),
  }
}

// Helper to remove a filter from an entity
function removeFilterFromEntity(state: ScopeState, entityType: string, filterId: string): ScopeState {
  return {
    ...state,
    entities: state.entities.map((e) =>
      e.entity_type === entityType
        ? { ...e, filters: e.filters.filter((f) => f.id !== filterId) }
        : e
    ),
  }
}

// Helper to add an entity
function addEntityToState(state: ScopeState, entityType: string): ScopeState {
  const newEntity = {
    entity_type: entityType,
    relevance_level: 'related' as const,
    reasoning: `${entityType} added to support the analysis.`,
    enabled: true,
    filters: [],
    fields_of_interest: [
      { field: `${entityType.toLowerCase()}_id`, justification: 'Primary identifier' },
    ],
    estimated_count: Math.floor(Math.random() * 10000) + 1000,
  }
  return {
    ...state,
    entities: [...state.entities, newEntity],
    counts: { ...state.counts, [entityType]: newEntity.estimated_count },
  }
}

const sseSequences: SSESequence[] = [
  {
    name: 'Add Filter Flow',
    description: 'Simulates user requesting "Add filter: diagnosis = diabetes on Member"',
    steps: [
      {
        delay: 0,
        event: {
          event_type: 'scope_update',
          message: 'Adding diagnosis filter to Member entity...',
        },
      },
      {
        delay: 1500,
        event: {
          event_type: 'scope_updated',
          update_summary: 'Added diagnosis = diabetes filter',
          changed_entities: ['Member'],
          added_filter_ids: ['filter-new-1'],
        },
        scopeStateTransform: (prev) => addFilterToEntity(prev, 'Member', {
          id: 'filter-new-1',
          property: 'diagnosis',
          operator: 'equals',
          value: 'diabetes',
          display_text: 'diagnosis = diabetes',
          reasoning: 'Focusing on diabetic members as requested',
        }),
      },
      {
        delay: 500,
        event: {
          event_type: 'scope_ready',
          message: 'Scope updated successfully',
        },
      },
    ],
  },
  {
    name: 'Add Entity Flow',
    description: 'Simulates user requesting "Add Diagnosis to the scope"',
    steps: [
      {
        delay: 0,
        event: {
          event_type: 'scope_update',
          message: 'Analyzing Diagnosis entity and its relationships...',
        },
      },
      {
        delay: 2000,
        event: {
          event_type: 'scope_updated',
          update_summary: 'Added Diagnosis entity with relevant fields',
          changed_entities: ['Diagnosis'],
          is_new_entity: true,
          // All fields on a new entity should be highlighted
          added_field_names: ['diagnosis_id'],
        },
        scopeStateTransform: (prev) => addEntityToState(prev, 'Diagnosis'),
      },
      {
        delay: 500,
        event: {
          event_type: 'scope_ready',
          message: 'Scope updated successfully',
        },
      },
    ],
  },
  {
    name: 'Add Fields Flow',
    description: 'Simulates user requesting "Add gender and zip_code fields to Member"',
    steps: [
      {
        delay: 0,
        event: {
          event_type: 'scope_update',
          message: 'Adding fields to Member entity...',
        },
      },
      {
        delay: 1200,
        event: {
          event_type: 'scope_updated',
          update_summary: 'Added gender and zip_code fields',
          changed_entities: ['Member'],
          added_field_names: ['gender', 'zip_code'],
        },
        scopeStateTransform: (prev) => ({
          ...prev,
          entities: prev.entities.map((e) =>
            e.entity_type === 'Member'
              ? {
                  ...e,
                  fields_of_interest: [
                    ...e.fields_of_interest,
                    { field: 'gender', justification: 'Demographic segmentation' },
                    { field: 'zip_code', justification: 'Geographic analysis' },
                  ],
                }
              : e
          ),
        }),
      },
      {
        delay: 500,
        event: {
          event_type: 'scope_ready',
          message: 'Scope updated successfully',
        },
      },
    ],
  },
  {
    name: 'Remove Filter Flow',
    description: 'Simulates user requesting "Remove the state filter from Plan"',
    steps: [
      {
        delay: 0,
        event: {
          event_type: 'scope_update',
          message: 'Removing state filter from Plan...',
        },
      },
      {
        delay: 800,
        event: {
          event_type: 'scope_updated',
          update_summary: 'Removed state filter from Plan',
          changed_entities: ['Plan'],
        },
        scopeStateTransform: (prev) => removeFilterFromEntity(prev, 'Plan', 'filter-1'),
      },
      {
        delay: 300,
        event: {
          event_type: 'scope_ready',
          message: 'Scope updated successfully',
        },
      },
    ],
  },
  {
    name: 'Multi-Entity Update',
    description: 'Simulates a complex update affecting multiple entities',
    steps: [
      {
        delay: 0,
        event: {
          event_type: 'scope_update',
          message: 'Processing complex scope changes...',
        },
      },
      {
        delay: 1000,
        event: {
          event_type: 'scope_update',
          message: 'Updating Member filters...',
        },
      },
      {
        delay: 1500,
        event: {
          event_type: 'scope_updated',
          update_summary: 'Updated age filter and added medication filter',
          changed_entities: ['Member', 'Claim'],
          added_filter_ids: ['filter-multi-1', 'filter-multi-2'],
        },
        scopeStateTransform: (prev) => {
          let newState = addFilterToEntity(prev, 'Member', {
            id: 'filter-multi-1',
            property: 'has_chronic_condition',
            operator: 'equals',
            value: true,
            display_text: 'has chronic condition = true',
            reasoning: 'Focusing on members with chronic conditions',
          })
          newState = addFilterToEntity(newState, 'Claim', {
            id: 'filter-multi-2',
            property: 'claim_type',
            operator: 'equals',
            value: 'pharmacy',
            display_text: 'claim type = pharmacy',
            reasoning: 'Filtering to pharmacy claims',
          })
          return newState
        },
      },
      {
        delay: 500,
        event: {
          event_type: 'scope_ready',
          message: 'All updates complete',
        },
      },
    ],
  },
]

// ============================================================================
// State Presets
// ============================================================================

type StatePreset = 'full' | 'loading' | 'lowConfidence' | 'minimal' | 'empty'

const statePresets: Record<StatePreset, { label: string; state: ScopeState | null }> = {
  full: { label: 'Full State (5 entities, filters)', state: mockScopeState },
  loading: { label: 'Loading State', state: mockScopeStateLoading },
  lowConfidence: { label: 'Low Confidence', state: mockScopeStateLowConfidence },
  minimal: { label: 'Minimal (1 entity)', state: mockScopeStateMinimal },
  empty: { label: 'Empty / Null', state: null },
}

// ============================================================================
// Main Component
// ============================================================================

export default function DevTestDataScoping() {
  const theme = useTheme()

  // State management
  const [statePreset, setStatePreset] = useState<StatePreset>('full')
  const [isScopeReady, setIsScopeReady] = useState(true)
  const [chatDisabled, setChatDisabled] = useState(false)
  const [showClarifications, setShowClarifications] = useState(false)
  const [showIntent, setShowIntent] = useState(true)
  const [chatLog, setChatLog] = useState<string[]>([])

  // SSE Simulation state
  const [selectedSequence, setSelectedSequence] = useState<number>(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentStepIndex, setCurrentStepIndex] = useState(-1)
  const [simulatedScopeState, setSimulatedScopeState] = useState<ScopeState | null>(null)
  const [entityUpdates, setEntityUpdates] = useState<Record<string, EntityUpdate>>({})
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Get current scope state - use simulated if playing, otherwise preset
  const currentScopeState = simulatedScopeState ?? statePresets[statePreset].state

  // Handlers
  const handleChatSubmit = useCallback((message: string) => {
    setChatLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] User: ${message}`])
    // Simulate AI response after a delay
    setTimeout(() => {
      setChatLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] AI: Received your message about "${message.slice(0, 50)}..."`])
    }, 500)
  }, [])

  const handleStageData = useCallback(() => {
    setChatLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] System: Stage Data clicked!`])
    alert('Stage Data clicked! In production, this would start team building.')
  }, [])

  const handleClarificationSubmit = useCallback((answers: ClarificationAnswer[]) => {
    setChatLog((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] Clarification answers:`,
      ...answers.map((a) => `  - ${a.question}: ${a.selected_option}`),
    ])
    setShowClarifications(false)
  }, [])

  const clearChatLog = useCallback(() => {
    setChatLog([])
  }, [])

  // SSE Sequence Playback
  const playSequence = useCallback(() => {
    const sequence = sseSequences[selectedSequence]
    if (!sequence) return

    // Initialize with current preset state
    const initialState = statePresets[statePreset].state
    if (!initialState) {
      setChatLog((prev) => [...prev, `[SSE] Cannot play sequence - no initial state`])
      return
    }

    setSimulatedScopeState(initialState)
    setIsPlaying(true)
    setCurrentStepIndex(0)
    setEntityUpdates({})
    setChatLog((prev) => [...prev, `[SSE] Starting sequence: ${sequence.name}`])

    let stepIndex = 0
    let currentState = initialState

    const executeStep = () => {
      if (stepIndex >= sequence.steps.length) {
        setIsPlaying(false)
        setCurrentStepIndex(-1)
        setChatLog((prev) => [...prev, `[SSE] Sequence complete`])
        return
      }

      const step = sequence.steps[stepIndex]
      setCurrentStepIndex(stepIndex)

      // Log the event
      setChatLog((prev) => [
        ...prev,
        `[SSE] Event: ${step.event.event_type}${step.event.message ? ` - ${step.event.message}` : ''}`,
      ])

      // Apply state transform if present
      if (step.scopeStateTransform) {
        currentState = step.scopeStateTransform(currentState)
        setSimulatedScopeState(currentState)
      }

      // Update entity notifications if changed_entities is present
      if (step.event.changed_entities && step.event.update_summary) {
        const timestamp = Date.now()
        // Extract specific change details
        const isNewEntity = step.event.is_new_entity ?? false
        const addedFilterIds = step.event.added_filter_ids ?? []
        const changedFilterIds = step.event.changed_filter_ids ?? []
        const addedFieldNames = step.event.added_field_names ?? []
        const changedFieldNames = step.event.changed_field_names ?? []

        const newUpdates: Record<string, EntityUpdate> = {}
        for (const entityType of step.event.changed_entities) {
          newUpdates[entityType] = {
            summary: step.event.update_summary,
            changedFields: isNewEntity ? ['entity', 'fields'] : ['filters'],
            timestamp,
            isNew: isNewEntity,
            addedFilterIds,
            changedFilterIds,
            addedFieldNames,
            changedFieldNames,
          }
        }
        setEntityUpdates((prev) => ({ ...prev, ...newUpdates }))
      }

      stepIndex++

      // Schedule next step
      if (stepIndex < sequence.steps.length) {
        timeoutRef.current = setTimeout(executeStep, sequence.steps[stepIndex].delay)
      } else {
        timeoutRef.current = setTimeout(() => {
          setIsPlaying(false)
          setCurrentStepIndex(-1)
          setChatLog((prev) => [...prev, `[SSE] Sequence complete`])
        }, 500)
      }
    }

    // Start with initial delay
    timeoutRef.current = setTimeout(executeStep, sequence.steps[0].delay)
  }, [selectedSequence, statePreset])

  const stopSequence = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setIsPlaying(false)
    setCurrentStepIndex(-1)
    setChatLog((prev) => [...prev, `[SSE] Sequence stopped`])
  }, [])

  const resetSimulation = useCallback(() => {
    stopSequence()
    setSimulatedScopeState(null)
    setEntityUpdates({})
    setChatLog((prev) => [...prev, `[SSE] Simulation reset`])
  }, [stopSequence])

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Control Panel (Left Side) */}
      <Paper
        elevation={0}
        sx={{
          width: 320,
          flexShrink: 0,
          borderRight: '1px solid',
          borderColor: 'divider',
          overflow: 'auto',
          p: 2,
        }}
      >
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Dev Test Controls
        </Typography>

        <Alert severity="info" sx={{ mb: 2 }}>
          This page tests DataScopingView without AI workflows.
        </Alert>

        {/* State Preset Selector */}
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>State Preset</InputLabel>
          <Select
            value={statePreset}
            label="State Preset"
            onChange={(e) => setStatePreset(e.target.value as StatePreset)}
          >
            {Object.entries(statePresets).map(([key, { label }]) => (
              <MenuItem key={key} value={key}>
                {label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Divider sx={{ my: 2 }} />

        {/* Toggle Controls */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          Behavior Toggles
        </Typography>

        <Stack spacing={1}>
          <FormControlLabel
            control={
              <Switch
                checked={isScopeReady}
                onChange={(e) => setIsScopeReady(e.target.checked)}
              />
            }
            label="Scope Ready"
          />
          <FormControlLabel
            control={
              <Switch
                checked={chatDisabled}
                onChange={(e) => setChatDisabled(e.target.checked)}
              />
            }
            label="Chat Disabled"
          />
          <FormControlLabel
            control={
              <Switch
                checked={showClarifications}
                onChange={(e) => setShowClarifications(e.target.checked)}
              />
            }
            label="Show Clarifications"
          />
          <FormControlLabel
            control={
              <Switch
                checked={showIntent}
                onChange={(e) => setShowIntent(e.target.checked)}
              />
            }
            label="Show Intent Package"
          />
        </Stack>

        <Divider sx={{ my: 2 }} />

        {/* Current State Info */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          Current State Info
        </Typography>

        {currentScopeState ? (
          <Box sx={{ fontSize: 12 }}>
            <Box sx={{ mb: 0.5 }}>
              <strong>Primary:</strong> {currentScopeState.primary_entity}
            </Box>
            <Box sx={{ mb: 0.5 }}>
              <strong>Entities:</strong> {currentScopeState.entities.length}
            </Box>
            <Box sx={{ mb: 0.5 }}>
              <strong>Enabled:</strong>{' '}
              {currentScopeState.entities.filter((e) => e.enabled).length}
            </Box>
            <Box sx={{ mb: 0.5 }}>
              <strong>Confidence:</strong>{' '}
              <Chip
                label={currentScopeState.confidence}
                size="small"
                sx={{
                  height: 18,
                  fontSize: 10,
                  bgcolor:
                    currentScopeState.confidence === 'high'
                      ? alpha(theme.palette.success.main, 0.1)
                      : currentScopeState.confidence === 'medium'
                        ? alpha(theme.palette.warning.main, 0.1)
                        : alpha(theme.palette.error.main, 0.1),
                }}
              />
            </Box>
            <Box sx={{ mb: 0.5 }}>
              <strong>Loading:</strong> {currentScopeState.preview_loading ? 'Yes' : 'No'}
            </Box>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No scope state (null)
          </Typography>
        )}

        <Divider sx={{ my: 2 }} />

        {/* SSE Sequence Simulator */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          SSE Event Simulator
        </Typography>

        <Alert severity="info" sx={{ mb: 1.5, py: 0.5 }}>
          <Typography variant="caption">
            Simulate real-time Theo updates to test the event stream flow.
          </Typography>
        </Alert>

        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel>Event Sequence</InputLabel>
          <Select
            value={selectedSequence}
            label="Event Sequence"
            onChange={(e) => setSelectedSequence(e.target.value as number)}
            disabled={isPlaying}
          >
            {sseSequences.map((seq, idx) => (
              <MenuItem key={idx} value={idx}>
                {seq.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Typography variant="caption" sx={{ display: 'block', mb: 1.5, color: 'text.secondary' }}>
          {sseSequences[selectedSequence]?.description}
        </Typography>

        <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
          {!isPlaying ? (
            <Button
              variant="contained"
              size="small"
              startIcon={<PlayArrowIcon />}
              onClick={playSequence}
              disabled={!statePresets[statePreset].state}
              fullWidth
            >
              Play Sequence
            </Button>
          ) : (
            <Button
              variant="outlined"
              size="small"
              startIcon={<StopIcon />}
              onClick={stopSequence}
              color="error"
              fullWidth
            >
              Stop
            </Button>
          )}
        </Stack>

        {isPlaying && (
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Step {currentStepIndex + 1} of {sseSequences[selectedSequence]?.steps.length}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={((currentStepIndex + 1) / (sseSequences[selectedSequence]?.steps.length || 1)) * 100}
              sx={{ mt: 0.5 }}
            />
          </Box>
        )}

        {simulatedScopeState && (
          <Button
            variant="text"
            size="small"
            onClick={resetSimulation}
            sx={{ mb: 1, color: 'text.secondary' }}
          >
            Reset to Preset
          </Button>
        )}

        {/* Entity Updates Display */}
        {Object.keys(entityUpdates).length > 0 && (
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
              Active Entity Updates:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
              {Object.entries(entityUpdates).map(([entityType, update]) => (
                <Chip
                  key={entityType}
                  label={`${entityType}: ${update.changedFields.join(', ')}`}
                  size="small"
                  onDelete={() => {
                    setEntityUpdates((prev) => {
                      const newUpdates = { ...prev }
                      delete newUpdates[entityType]
                      return newUpdates
                    })
                  }}
                  sx={{
                    height: 20,
                    fontSize: 10,
                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                  }}
                />
              ))}
            </Box>
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Chat Log */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" sx={{ color: 'text.secondary' }}>
            Event Log
          </Typography>
          <Button size="small" onClick={clearChatLog}>
            Clear
          </Button>
        </Box>

        <Box
          sx={{
            bgcolor: alpha(theme.palette.grey[500], 0.05),
            borderRadius: 1,
            p: 1,
            maxHeight: 200,
            overflow: 'auto',
            fontSize: 11,
            fontFamily: 'monospace',
          }}
        >
          {chatLog.length === 0 ? (
            <Typography variant="caption" color="text.secondary">
              No messages yet. Interact with the UI to see chat messages.
            </Typography>
          ) : (
            chatLog.map((msg, i) => (
              <Box key={i} sx={{ mb: 0.5 }}>
                {msg}
              </Box>
            ))
          )}
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Quick Actions */}
        <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
          Quick Actions
        </Typography>

        <Stack spacing={1}>
          <Button
            variant="outlined"
            size="small"
            fullWidth
            onClick={() => {
              setStatePreset('full')
              setIsScopeReady(true)
              setChatDisabled(false)
              setShowClarifications(false)
            }}
          >
            Reset to Default
          </Button>
          <Button
            variant="outlined"
            size="small"
            fullWidth
            onClick={() => {
              setStatePreset('loading')
              setIsScopeReady(false)
            }}
          >
            Simulate Loading
          </Button>
          <Button
            variant="outlined"
            size="small"
            fullWidth
            onClick={() => setShowClarifications(true)}
          >
            Trigger Clarification
          </Button>
        </Stack>
      </Paper>

      {/* DataScopingView (Main Area) */}
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        <DataScopingView
          workspaceId="dev-test-workspace"
          workspaceName="Dev Test Workspace"
          scopeState={currentScopeState}
          isScopeReady={isScopeReady}
          onStageData={handleStageData}
          currentStep={2}
          totalSteps={3}
          setupRunId="dev-test-run-123"
          onChatSubmit={handleChatSubmit}
          chatDisabled={chatDisabled}
          pendingClarifications={showClarifications ? mockClarifications : []}
          onClarificationSubmit={handleClarificationSubmit}
          intentPackage={showIntent ? mockIntentPackage : null}
          availableEntities={mockAvailableEntities}
          entityUpdates={entityUpdates}
        />
      </Box>
    </Box>
  )
}
