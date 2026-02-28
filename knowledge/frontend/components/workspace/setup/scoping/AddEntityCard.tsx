/**
 * AddEntityCard Component
 *
 * Card-based form for adding new entities to scope.
 * Styled to match EntityCard exactly - feels like building a card the same way AI would.
 *
 * States:
 * 1. Selecting: Shows entity chips to pick from (default state)
 * 2. Editing: Full form matching EntityCard layout
 *
 * Action Panel Pattern (integrated split view):
 * - When action panel opens, card splits into two halves
 * - Left side: Minimal header (entity name + badges) for context
 * - Right side: Full action panel
 * - Integrated feel, part of the card
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import {
  Box,
  Typography,
  Chip,
  TextField,
  Button,
  Collapse,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import AddIcon from '@mui/icons-material/Add'
import CheckIcon from '@mui/icons-material/Check'
import CloseIcon from '@mui/icons-material/Close'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'

import SlideOutFilterPanel from './SlideOutFilterPanel'
import SlideOutFieldsPanel from './SlideOutFieldsPanel'
import { useReducedMotion } from '../../../../hooks/useReducedMotion'
import { useEntityFieldMetadata } from '../../../../hooks/useEntityFieldMetadata'
import type { ScopeState } from '../../../../types/scopeState'

// ============================================================================
// Types
// ============================================================================

export interface AddEntityCardProps {
  scopeState: ScopeState | null
  availableEntities: string[]
  onSubmit: (chatMessage: string) => void
  disabled?: boolean
}

type CardState = 'selecting' | 'editing'

// ============================================================================
// Main Component
// ============================================================================

export default function AddEntityCard({
  scopeState,
  availableEntities,
  onSubmit,
  disabled = false,
}: AddEntityCardProps) {
  const theme = useTheme()
  const prefersReducedMotion = useReducedMotion()
  const isDarkMode = theme.palette.mode === 'dark'
  const formRef = useRef<HTMLDivElement>(null)
  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([])
  const whyDataCalloutSx = {
    bgcolor: isDarkMode
      ? 'background.default'
      : alpha(theme.palette.secondary.main, 0.16),
    borderLeft: '3px solid',
    borderColor: isDarkMode
      ? 'divider'
      : alpha(theme.palette.secondary.dark, 0.7),
    borderRadius: 0.5,
    p: 1.5,
  }

  // Card state - starts with selecting (no collapsed state)
  const [cardState, setCardState] = useState<CardState>('selecting')

  // Form state
  const [selectedEntity, setSelectedEntity] = useState('')
  const [justification, setJustification] = useState('')
  const [confirming, setConfirming] = useState(false)

  // Filter state
  const [pendingFilters, setPendingFilters] = useState<Array<{ text: string; id: string }>>([])
  const [isAddingFilter, setIsAddingFilter] = useState(false)
  const [filtersExpanded, setFiltersExpanded] = useState(true)

  // Fields of interest state
  const [selectedFields, setSelectedFields] = useState<string[]>([])
  const [isEditingFields, setIsEditingFields] = useState(false)
  const [fieldsExpanded, setFieldsExpanded] = useState(true)

  // Fetch available fields for selected entity type
  const { fields: availableFields, loading: fieldsLoading } = useEntityFieldMetadata(
    selectedEntity || null
  )

  // Cleanup all timeouts on unmount
  useEffect(() => {
    return () => {
      timeoutRefs.current.forEach(clearTimeout)
      timeoutRefs.current = []
    }
  }, [])

  // Filter out entities already in scope
  const entitiesNotInScope = useMemo(() => {
    if (!scopeState) return availableEntities
    const inScopeTypes = new Set(scopeState.entities.map((e) => e.entity_type))
    return availableEntities.filter((type) => !inScopeTypes.has(type))
  }, [scopeState, availableEntities])

  const isFormValid = selectedEntity && justification.trim().length >= 10
  const isEditing = cardState === 'editing'
  const isSelecting = cardState === 'selecting'
  const isActionPanelOpen = isAddingFilter || isEditingFields

  // Select an entity and move to editing
  const handleEntitySelect = useCallback((entityType: string) => {
    setSelectedEntity(entityType)
    setSelectedFields([])
    setPendingFilters([])
    setCardState('editing')
  }, [])

  const handleCancel = useCallback(() => {
    if (confirming) return
    setSelectedEntity('')
    setJustification('')
    setPendingFilters([])
    setSelectedFields([])
    setIsAddingFilter(false)
    setIsEditingFields(false)
    setFiltersExpanded(true)
    setFieldsExpanded(true)
    setCardState('selecting')
  }, [confirming])

  const handleSubmit = useCallback(() => {
    if (!isFormValid) return

    setConfirming(true)

    // Build the chat message
    let message = `Add ${selectedEntity} to the scope because ${justification.trim()}`

    if (pendingFilters.length > 0) {
      const filterDescriptions = pendingFilters.map((f) => f.text).join(', ')
      message += `. Apply filters: ${filterDescriptions}`
    }

    if (selectedFields.length > 0) {
      message += `. Include fields: ${selectedFields.join(', ')}`
    }

    const successDuration = prefersReducedMotion ? 300 : 700
    const t1 = setTimeout(() => {
      onSubmit(message)

      // Reset form
      setSelectedEntity('')
      setJustification('')
      setPendingFilters([])
      setSelectedFields([])
      setIsAddingFilter(false)
      setIsEditingFields(false)
      setCardState('selecting')

      const t2 = setTimeout(
        () => {
          setConfirming(false)
        },
        prefersReducedMotion ? 100 : 300
      )
      timeoutRefs.current.push(t2)
    }, successDuration)
    timeoutRefs.current.push(t1)
  }, [isFormValid, selectedEntity, justification, pendingFilters, selectedFields, onSubmit, prefersReducedMotion])

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isAddingFilter) {
          setIsAddingFilter(false)
        } else if (isEditingFields) {
          setIsEditingFields(false)
        } else if (isEditing) {
          handleCancel()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isEditing, isAddingFilter, isEditingFields, handleCancel])

  const handleCloseActionPanel = useCallback(() => {
    setIsAddingFilter(false)
    setIsEditingFields(false)
  }, [])


  const handleFilterPanelSubmit = useCallback((filterText: string) => {
    const id = `pending-${Date.now()}`
    setPendingFilters((prev) => [...prev, { text: filterText, id }])
    setIsAddingFilter(false)
  }, [])

  const handleRemovePendingFilter = useCallback((filterId: string) => {
    setPendingFilters((prev) => prev.filter((f) => f.id !== filterId))
  }, [])

  const handleFieldsUpdate = useCallback((chatMessage: string) => {
    const allFields = chatMessage.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, '')) || []
    const hasAdd = chatMessage.includes(': add ')
    const hasRemove = chatMessage.includes(' remove ')

    if (hasAdd && hasRemove) {
      const [addPart, removePart] = chatMessage.split(' and remove ')
      const addedFields = addPart.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, '')) || []
      const removedFields = removePart.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, '')) || []

      setSelectedFields((prev) => {
        const afterRemove = prev.filter((f) => !removedFields.includes(f))
        return [...afterRemove, ...addedFields.filter((f) => !afterRemove.includes(f))]
      })
    } else if (hasAdd) {
      setSelectedFields((prev) => [...prev, ...allFields.filter((f) => !prev.includes(f))])
    } else if (hasRemove) {
      setSelectedFields((prev) => prev.filter((f) => !allFields.includes(f)))
    }
    setIsEditingFields(false)
  }, [])

  const handleRemoveSelectedField = useCallback((fieldName: string) => {
    setSelectedFields((prev) => prev.filter((f) => f !== fieldName))
  }, [])

  const toggleFilters = useCallback(() => {
    setFiltersExpanded((prev) => !prev)
  }, [])

  const toggleFields = useCallback(() => {
    setFieldsExpanded((prev) => !prev)
  }, [])

  const transitionDuration = prefersReducedMotion ? '0s' : '0.35s'

  // Don't render if no entities available
  if (entitiesNotInScope.length === 0 && !isEditing) {
    return null
  }

  return (
    <Box
      ref={formRef}
      sx={{
        border: '1px dashed',
        borderColor: isEditing ? 'primary.main' : 'divider',
        borderRadius: 0.5,
        bgcolor: isDarkMode ? 'background.paper' : 'background.default',
        position: 'relative',
        overflow: 'hidden',
        opacity: disabled ? 0.6 : 1,
        transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease',
      }}
    >
      {/* Success overlay */}
      <Box
        role="status"
        aria-live="polite"
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 1,
          bgcolor: 'background.paper',
          borderRadius: 0.5,
          zIndex: confirming ? 20 : -1,
          opacity: confirming ? 1 : 0,
          transition: prefersReducedMotion ? 'none' : 'opacity 0.2s ease',
        }}
      >
        <CheckIcon sx={{ fontSize: 24, color: 'success.main' }} />
        <Typography variant="body1" sx={{ fontWeight: 500, color: 'success.main' }}>
          Entity Added
        </Typography>
      </Box>

      {/* Main layout - flex split when action panel is open */}
      <Box
        sx={{
          display: 'flex',
          minHeight: isActionPanelOpen ? 280 : 'auto',
          opacity: confirming ? 0 : 1,
          transition: 'opacity 0.15s ease',
        }}
      >
        {/* Left side: Full content when closed, minimal header when panel open */}
        <Box
          sx={{
            flex: isActionPanelOpen ? '0 0 50%' : '1 1 auto',
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            transition: prefersReducedMotion ? 'none' : 'flex 0.2s ease',
          }}
        >
          {/* === SELECTING STATE === */}
          {isSelecting && (
            <>
              {/* Header */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <AddIcon sx={{ fontSize: 22, color: 'primary.main' }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Add New Entity
                </Typography>
              </Box>

              {/* Entity selection chips */}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {entitiesNotInScope.map((entityType) => (
                  <Chip
                    key={entityType}
                    label={entityType}
                    onClick={() => handleEntitySelect(entityType)}
                    disabled={disabled}
                    sx={{
                      bgcolor: alpha(theme.palette.primary.main, 0.08),
                      color: theme.palette.primary.dark,
                      fontWeight: 500,
                      fontSize: '0.85rem',
                      py: 2,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: 'transparent',
                      transition: prefersReducedMotion ? 'none' : 'all 0.15s ease',
                      '&:hover': {
                        bgcolor: alpha(theme.palette.primary.main, 0.15),
                        borderColor: theme.palette.primary.main,
                      },
                    }}
                  />
                ))}
              </Box>
            </>
          )}

          {/* === EDITING STATE (matches EntityCard layout) === */}
          {isEditing && (
            <>
              {/* Header: Entity name + "New" badge - always visible */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: isActionPanelOpen ? 2 : 1, pr: isActionPanelOpen ? 0 : 6 }}>
                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.25rem' }}>
                  {selectedEntity}
                </Typography>
                <Chip
                  label="New"
                  size="small"
                  sx={{
                    bgcolor: alpha(theme.palette.success.main, 0.15),
                    color: theme.palette.success.dark,
                    fontWeight: 600,
                    fontSize: '0.7rem',
                    height: 22,
                  }}
                />
                {/* Change entity button - only when panel closed */}
                {!isActionPanelOpen && (
                  <Button
                    size="small"
                    variant="text"
                    onClick={() => setCardState('selecting')}
                    sx={{
                      ml: 'auto',
                      minWidth: 'auto',
                      px: 1,
                      py: 0.25,
                      fontSize: '0.75rem',
                      color: 'text.secondary',
                      textTransform: 'none',
                    }}
                  >
                    Change
                  </Button>
                )}
              </Box>

              {/* Contextual content when action panel is open */}
              {isActionPanelOpen && (
                <Box sx={{ flex: 1 }}>
                  {/* Editing filters: show current filters */}
                  {isAddingFilter && (
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 500, mb: 1, color: 'text.secondary' }}>
                        Current Filters
                      </Typography>
                      {pendingFilters.length === 0 ? (
                        <Typography variant="body2" sx={{ color: 'text.disabled', fontStyle: 'italic' }}>
                          No filters applied yet
                        </Typography>
                      ) : (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {pendingFilters.map((filter) => (
                            <Chip
                              key={filter.id}
                              label={filter.text.length > 30 ? `${filter.text.slice(0, 30)}...` : filter.text}
                              size="small"
                              onDelete={() => handleRemovePendingFilter(filter.id)}
                              deleteIcon={<CloseIcon sx={{ fontSize: '14px !important' }} />}
                              sx={{
                                bgcolor: alpha(theme.palette.success.main, 0.1),
                                color: theme.palette.success.dark,
                                border: '1px dashed',
                                borderColor: theme.palette.success.main,
                                fontWeight: 500,
                                fontSize: '0.8rem',
                              }}
                            />
                          ))}
                        </Box>
                      )}
                    </Box>
                  )}

                  {/* Editing fields: show current fields */}
                  {isEditingFields && (
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 500, mb: 1, color: 'text.secondary' }}>
                        Selected Fields
                      </Typography>
                      {selectedFields.length === 0 ? (
                        <Typography variant="body2" sx={{ color: 'text.disabled', fontStyle: 'italic' }}>
                          No fields selected yet
                        </Typography>
                      ) : (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selectedFields.map((fieldName) => (
                            <Chip
                              key={fieldName}
                              label={fieldName}
                              size="small"
                              onDelete={() => handleRemoveSelectedField(fieldName)}
                              deleteIcon={<CloseIcon sx={{ fontSize: '12px !important' }} />}
                              sx={{
                                bgcolor: alpha(theme.palette.success.main, 0.1),
                                color: theme.palette.success.dark,
                                fontSize: '0.75rem',
                                border: '1px dashed',
                                borderColor: theme.palette.success.main,
                              }}
                            />
                          ))}
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              )}

              {/* Full content when action panel is closed */}
              {!isActionPanelOpen && (
                <>
              {/* Rationale section (matches EntityCard beige box) */}
              <Box
                sx={{
                  ...whyDataCalloutSx,
                  mb: 2,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    display: 'block',
                    mb: 0.5,
                    fontSize: '0.75rem',
                  }}
                >
                  Why this data?
                </Typography>
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  minRows={2}
                  maxRows={4}
                  placeholder="e.g., I need to analyze prescribing patterns by provider specialty"
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  error={justification.length > 0 && justification.length < 10}
                  helperText={
                    justification.length < 10
                      ? `${10 - justification.length} more characters needed`
                      : ''
                  }
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      bgcolor: 'background.paper',
                      fontSize: '0.875rem',
                    },
                  }}
                />
              </Box>

              {/* Filters section */}
              <Box sx={{ mb: 2 }}>
                <Box
                  component="button"
                  type="button"
                  onClick={toggleFilters}
                  aria-expanded={filtersExpanded}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    userSelect: 'none',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    font: 'inherit',
                    color: 'inherit',
                    '&:hover': { color: 'primary.main' },
                  }}
                >
                  {filtersExpanded ? (
                    <ExpandLessIcon sx={{ fontSize: 18, mr: 0.5 }} />
                  ) : (
                    <ExpandMoreIcon sx={{ fontSize: 18, mr: 0.5 }} />
                  )}
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Filters ({pendingFilters.length} applied)
                  </Typography>
                </Box>

                <Collapse in={filtersExpanded}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.75, mt: 1, pl: 3 }}>
                    {/* Pending filter chips */}
                    {pendingFilters.map((filter) => (
                      <Chip
                        key={filter.id}
                        label={filter.text.length > 30 ? `${filter.text.slice(0, 30)}...` : filter.text}
                        size="small"
                        onDelete={() => handleRemovePendingFilter(filter.id)}
                        deleteIcon={<CloseIcon sx={{ fontSize: '14px !important' }} />}
                        sx={{
                          bgcolor: alpha(theme.palette.success.main, 0.1),
                          color: theme.palette.success.dark,
                          border: '1px dashed',
                          borderColor: theme.palette.success.main,
                          fontWeight: 500,
                          fontSize: '0.8rem',
                          height: 32,
                        }}
                      />
                    ))}

                    {/* Add filter button */}
                    <Chip
                      icon={
                        <AddIcon
                          sx={{
                            fontSize: '14px !important',
                            transition: prefersReducedMotion ? 'none' : `transform ${transitionDuration} ease`,
                            transform: isAddingFilter ? 'rotate(135deg)' : 'rotate(0deg)',
                          }}
                        />
                      }
                      label={isAddingFilter ? 'Close' : 'Filter'}
                      size="small"
                      onClick={isAddingFilter ? handleCloseActionPanel : () => setIsAddingFilter(true)}
                      sx={{
                        bgcolor: isAddingFilter ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                        border: '1px dashed',
                        borderColor: isAddingFilter ? 'primary.main' : 'divider',
                        color: isAddingFilter ? 'primary.main' : 'text.secondary',
                        fontWeight: 500,
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        transition: prefersReducedMotion ? 'none' : 'all 0.15s ease',
                        '&:hover': {
                          bgcolor: alpha(theme.palette.primary.main, 0.04),
                          borderColor: 'primary.main',
                          color: 'primary.main',
                        },
                      }}
                    />
                  </Box>
                </Collapse>
              </Box>

              {/* Fields of Interest section */}
              <Box>
                <Box
                  component="button"
                  type="button"
                  onClick={toggleFields}
                  aria-expanded={fieldsExpanded}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    userSelect: 'none',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    font: 'inherit',
                    color: 'inherit',
                    '&:hover': { color: 'primary.main' },
                  }}
                >
                  {fieldsExpanded ? (
                    <ExpandLessIcon sx={{ fontSize: 18, mr: 0.5 }} />
                  ) : (
                    <ExpandMoreIcon sx={{ fontSize: 18, mr: 0.5 }} />
                  )}
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Fields of Interest ({selectedFields.length} fields)
                  </Typography>
                </Box>

                <Collapse in={fieldsExpanded}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.5, mt: 1, pl: 3 }}>
                    {/* Selected field chips */}
                    {selectedFields.map((fieldName) => (
                      <Chip
                        key={fieldName}
                        label={fieldName}
                        size="small"
                        onDelete={() => handleRemoveSelectedField(fieldName)}
                        deleteIcon={<CloseIcon sx={{ fontSize: '12px !important' }} />}
                        sx={{
                          bgcolor: alpha(theme.palette.success.main, 0.1),
                          color: theme.palette.success.dark,
                          fontSize: '0.75rem',
                          height: 26,
                          border: '1px dashed',
                          borderColor: theme.palette.success.main,
                        }}
                      />
                    ))}

                    {/* Add field button */}
                    <Chip
                      icon={
                        <AddIcon
                          sx={{
                            fontSize: '14px !important',
                            transition: prefersReducedMotion ? 'none' : `transform ${transitionDuration} ease`,
                            transform: isEditingFields ? 'rotate(135deg)' : 'rotate(0deg)',
                          }}
                        />
                      }
                      label={isEditingFields ? 'Close' : 'Field'}
                      size="small"
                      onClick={isEditingFields ? handleCloseActionPanel : () => setIsEditingFields(true)}
                      sx={{
                        bgcolor: isEditingFields ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                        border: '1px dashed',
                        borderColor: isEditingFields ? 'primary.main' : 'divider',
                        color: isEditingFields ? 'primary.main' : 'text.secondary',
                        fontWeight: 500,
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        transition: prefersReducedMotion ? 'none' : 'all 0.15s ease',
                        '&:hover': {
                          bgcolor: alpha(theme.palette.primary.main, 0.04),
                          borderColor: 'primary.main',
                          color: 'primary.main',
                        },
                      }}
                    />
                  </Box>
                </Collapse>
              </Box>

              {/* Footer: Action buttons (matches EntityCard edit mode footer) */}
              <Box
                sx={{
                  mt: 2,
                  pt: 1.5,
                  borderTop: '1px solid',
                  borderColor: 'divider',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: 1,
                }}
              >
                <Button
                  size="small"
                  onClick={handleCancel}
                  sx={{ color: 'text.secondary', textTransform: 'none' }}
                >
                  Cancel
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleSubmit}
                  disabled={!isFormValid}
                  sx={{ textTransform: 'none' }}
                >
                  Add to Scope
                </Button>
              </Box>
                </>
              )}
            </>
          )}
        </Box>

        {/* Right side: Action Panel - integrated into the card */}
        {isActionPanelOpen && (
          <Box
            sx={{
              flex: '0 0 50%',
              borderLeft: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {isEditingFields ? (
              <SlideOutFieldsPanel
                entityType={selectedEntity}
                selectedFields={selectedFields}
                availableFields={availableFields}
                loading={fieldsLoading}
                onSubmit={handleFieldsUpdate}
                onCancel={handleCloseActionPanel}
              />
            ) : (
              <SlideOutFilterPanel
                entityType={selectedEntity}
                filter={null}
                availableFields={availableFields}
                onSubmit={handleFilterPanelSubmit}
                onCancel={handleCloseActionPanel}
              />
            )}
          </Box>
        )}
      </Box>
    </Box>
  )
}
