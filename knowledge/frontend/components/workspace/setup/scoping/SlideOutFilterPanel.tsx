/**
 * SlideOutFilterPanel Component
 *
 * Inline filter edit form that slides out on the right side of a card.
 * Used for both editing existing filters and adding new ones.
 *
 * Features:
 * - Chip-based field selection (matches AddEntityCard pattern)
 * - Type-aware value inputs
 * - Natural language fallback option
 * - Compact design that fits within card height
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import {
  Box,
  Typography,
  TextField,
  Button,
  IconButton,
  FormControl,
  FormControlLabel,
  MenuItem,
  Menu,
  Radio,
  RadioGroup,
  Select,
  Chip,
  Stack,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import CloseIcon from '@mui/icons-material/Close'

import { useReducedMotion } from '../../../../hooks/useReducedMotion'
import type { Filter } from '../../../../types/scopeState'
import type { FieldMetadata } from '../../../../hooks/useEntityFieldMetadata'

// ============================================================================
// Types
// ============================================================================

export interface SlideOutFilterPanelProps {
  entityType: string
  /** Existing filter to edit, or null for adding new */
  filter?: Filter | null
  /** Available fields for this entity type */
  availableFields: FieldMetadata[]
  /** Called when user submits the filter edit */
  onSubmit: (chatMessage: string) => void
  /** Called when user cancels */
  onCancel: () => void
}

interface NumberFilterState {
  operator: string
  value: number | ''
  value2?: number | ''
}

interface DateFilterState {
  operator: string
  value: string // ISO date string YYYY-MM-DD
  value2?: string // For 'between' operator
}

const NUMERIC_OPERATORS = [
  { value: 'equals', label: '=' },
  { value: 'not_equals', label: '≠' },
  { value: 'greater_than', label: '>' },
  { value: 'greater_than_or_equal', label: '≥' },
  { value: 'less_than', label: '<' },
  { value: 'less_than_or_equal', label: '≤' },
  { value: 'between', label: 'between' },
]

const DATE_OPERATORS = [
  { value: 'equals', label: 'on' },
  { value: 'greater_than', label: 'after' },
  { value: 'less_than', label: 'before' },
  { value: 'between', label: 'between' },
]

// ============================================================================
// Helper Functions
// ============================================================================

function detectFilterDataType(filter: Filter): FieldMetadata['dataType'] {
  const value = filter.value

  if (filter.operator === 'between') {
    if (Array.isArray(value) && value.length > 0) {
      const first = value[0]
      if (typeof first === 'string' && /^\d{4}-\d{2}-\d{2}/.test(first)) {
        return 'date'
      }
      if (typeof first === 'number') {
        return 'number'
      }
    }
  }

  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'

  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    return 'date'
  }

  if (Array.isArray(value) && value.length > 0) {
    const first = value[0]
    if (typeof first === 'number') return 'number'
    if (typeof first === 'string' && /^\d{4}-\d{2}-\d{2}/.test(first)) return 'date'
  }

  return 'string'
}

function formatFieldName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ============================================================================
// FieldSelectorChip Component
// ============================================================================

interface FieldSelectorChipProps {
  availableFields: FieldMetadata[]
  onSelect: (fieldName: string) => void
}

function FieldSelectorChip({ availableFields, onSelect }: FieldSelectorChipProps) {
  const theme = useTheme()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const open = Boolean(anchorEl)

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleSelect = (fieldName: string) => {
    onSelect(fieldName)
    handleClose()
  }

  return (
    <>
      <Chip
        label="Select a field"
        size="small"
        onClick={handleClick}
        sx={{
          bgcolor: 'transparent',
          border: '1px dashed',
          borderColor: 'divider',
          color: 'text.secondary',
          cursor: 'pointer',
          '&:hover': {
            borderColor: 'primary.main',
            color: 'primary.main',
            bgcolor: alpha(theme.palette.primary.main, 0.04),
          },
        }}
      />
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          paper: {
            sx: { maxHeight: 240, minWidth: 180 },
          },
        }}
      >
        {availableFields.map((field) => (
          <MenuItem key={field.name} onClick={() => handleSelect(field.name)}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', gap: 2 }}>
              <span>{formatFieldName(field.name)}</span>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {field.dataType}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export default function SlideOutFilterPanel({
  entityType,
  filter,
  availableFields,
  onSubmit,
  onCancel,
}: SlideOutFilterPanelProps) {
  const theme = useTheme()
  const prefersReducedMotion = useReducedMotion()

  const isEditing = !!filter

  // Determine data type
  const dataType = useMemo(() => {
    if (filter) {
      return detectFilterDataType(filter)
    }
    return 'string' // Default for new filters until field is selected
  }, [filter])

  // State for field selection (new filter only)
  const [selectedField, setSelectedField] = useState<string>(filter?.property || '')
  const [selectedFieldType, setSelectedFieldType] = useState<FieldMetadata['dataType']>(dataType)

  // State for different filter types (current and original for before→after)
  const [stringValue, setStringValue] = useState('')
  const [originalStringValue, setOriginalStringValue] = useState('')
  const [numberState, setNumberState] = useState<NumberFilterState>({
    operator: 'equals',
    value: '',
  })
  const [originalNumberState, setOriginalNumberState] = useState<NumberFilterState>({
    operator: 'equals',
    value: '',
  })
  const [dateState, setDateState] = useState<DateFilterState>({
    operator: 'equals',
    value: '',
  })
  const [originalDateState, setOriginalDateState] = useState<DateFilterState>({
    operator: 'equals',
    value: '',
  })
  const [booleanValue, setBooleanValue] = useState(true)
  const [originalBooleanValue, setOriginalBooleanValue] = useState(true)

  // Natural language fallback
  const [useNaturalLanguage, setUseNaturalLanguage] = useState(false)
  const [naturalLanguageValue, setNaturalLanguageValue] = useState('')

  // Initialize state from existing filter
  useEffect(() => {
    if (!filter) return

    setSelectedField(filter.property)

    switch (dataType) {
      case 'string': {
        const val = Array.isArray(filter.value)
          ? (filter.value as string[]).join(', ')
          : String(filter.value || '')
        setStringValue(val)
        setOriginalStringValue(val)
        break
      }

      case 'number': {
        let numState: NumberFilterState
        if (filter.operator === 'between' && Array.isArray(filter.value)) {
          numState = {
            operator: 'between',
            value: (filter.value as number[])[0] ?? '',
            value2: (filter.value as number[])[1] ?? '',
          }
        } else {
          numState = {
            operator: filter.operator,
            value: typeof filter.value === 'number' ? filter.value : '',
          }
        }
        setNumberState(numState)
        setOriginalNumberState(numState)
        break
      }

      case 'date': {
        let dateStateVal: DateFilterState
        if (filter.operator === 'between' && Array.isArray(filter.value)) {
          dateStateVal = {
            operator: 'between',
            value: (filter.value as string[])[0] ?? '',
            value2: (filter.value as string[])[1] ?? '',
          }
        } else {
          dateStateVal = {
            operator: filter.operator,
            value: typeof filter.value === 'string' ? filter.value : '',
          }
        }
        setDateState(dateStateVal)
        setOriginalDateState(dateStateVal)
        break
      }

      case 'boolean': {
        const boolVal = filter.value === true || filter.value === 'true'
        setBooleanValue(boolVal)
        setOriginalBooleanValue(boolVal)
        break
      }
        break
    }
  }, [filter, dataType])

  // Update field type when field selection changes
  useEffect(() => {
    if (!selectedField) return
    const fieldMeta = availableFields.find((f) => f.name === selectedField)
    if (fieldMeta) {
      setSelectedFieldType(fieldMeta.dataType)
    }
  }, [selectedField, availableFields])

  // Helper to format number state as string
  const formatNumberValue = useCallback((state: NumberFilterState): string => {
    const opSymbol = NUMERIC_OPERATORS.find((o) => o.value === state.operator)?.label || state.operator
    if (state.operator === 'between') {
      return `${state.value} to ${state.value2}`
    }
    return `${opSymbol} ${state.value}`
  }, [])

  // Helper to format date for display (YYYY-MM-DD → readable)
  const formatDateDisplay = useCallback((isoDate: string): string => {
    if (!isoDate) return ''
    try {
      const date = new Date(isoDate + 'T00:00:00') // Avoid timezone issues
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch {
      return isoDate
    }
  }, [])

  // Helper to format date state as string
  const formatDateValue = useCallback((state: DateFilterState): string => {
    const opLabel = DATE_OPERATORS.find((o) => o.value === state.operator)?.label || state.operator
    if (state.operator === 'between') {
      return `${formatDateDisplay(state.value)} to ${formatDateDisplay(state.value2 || '')}`
    }
    return `${opLabel} ${formatDateDisplay(state.value)}`
  }, [formatDateDisplay])

  // Generate chat message
  const generateChatMessage = useCallback((): string => {
    const fieldName = selectedField || filter?.property

    // Natural language mode - doesn't require a field selection
    if (useNaturalLanguage && naturalLanguageValue.trim()) {
      if (isEditing && fieldName) {
        return `Change the ${fieldName} filter on ${entityType}: ${naturalLanguageValue.trim()}`
      }
      return `Add filter to ${entityType}: ${naturalLanguageValue.trim()}`
    }

    // Structured mode requires a field
    if (!fieldName) return ''

    const effectiveType = isEditing ? dataType : selectedFieldType

    switch (effectiveType) {
      case 'string':
        if (isEditing) {
          return `Edit ${fieldName} filter on ${entityType}: "${originalStringValue}" → "${stringValue}"`
        }
        return `Add filter to ${entityType}: ${fieldName} = "${stringValue}"`

      case 'number': {
        if (isEditing) {
          const before = formatNumberValue(originalNumberState)
          const after = formatNumberValue(numberState)
          return `Edit ${fieldName} filter on ${entityType}: ${before} → ${after}`
        }
        const opSymbol = NUMERIC_OPERATORS.find((o) => o.value === numberState.operator)?.label || numberState.operator
        if (numberState.operator === 'between') {
          return `Add filter to ${entityType}: ${fieldName} between ${numberState.value} and ${numberState.value2}`
        }
        return `Add filter to ${entityType}: ${fieldName} ${opSymbol} ${numberState.value}`
      }

      case 'date': {
        if (!dateState.value) return ''
        const opLabel = DATE_OPERATORS.find((o) => o.value === dateState.operator)?.label || dateState.operator
        if (isEditing) {
          const before = formatDateValue(originalDateState)
          const after = formatDateValue(dateState)
          return `Edit ${fieldName} filter on ${entityType}: ${before} → ${after}`
        }
        if (dateState.operator === 'between') {
          return `Add filter to ${entityType}: ${fieldName} between ${formatDateDisplay(dateState.value)} and ${formatDateDisplay(dateState.value2 || '')}`
        }
        return `Add filter to ${entityType}: ${fieldName} ${opLabel} ${formatDateDisplay(dateState.value)}`
      }

      case 'boolean':
        if (isEditing) {
          const before = originalBooleanValue ? 'Yes' : 'No'
          const after = booleanValue ? 'Yes' : 'No'
          return `Edit ${fieldName} filter on ${entityType}: ${before} → ${after}`
        }
        return `Add filter to ${entityType}: ${fieldName} = ${booleanValue ? 'Yes' : 'No'}`

      default:
        return ''
    }
  }, [
    entityType,
    filter,
    selectedField,
    isEditing,
    dataType,
    selectedFieldType,
    stringValue,
    originalStringValue,
    numberState,
    originalNumberState,
    formatNumberValue,
    dateState,
    originalDateState,
    formatDateValue,
    formatDateDisplay,
    booleanValue,
    originalBooleanValue,
    useNaturalLanguage,
    naturalLanguageValue,
  ])

  const chatMessage = generateChatMessage()
  // Natural language mode doesn't require a field selection
  const isValid = chatMessage.length > 0 && (isEditing || selectedField || useNaturalLanguage)

  const handleSubmit = useCallback(() => {
    if (isValid) {
      onSubmit(chatMessage)
      onCancel() // Close the panel after submitting
    }
  }, [isValid, chatMessage, onSubmit, onCancel])

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onCancel])

  const transitionDuration = prefersReducedMotion ? '0s' : '0.35s'
  const effectiveType = isEditing ? dataType : selectedFieldType

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        animation: prefersReducedMotion ? 'none' : `slideIn ${transitionDuration} cubic-bezier(0.34, 1.3, 0.64, 1)`,
        '@keyframes slideIn': {
          '0%': { opacity: 0, transform: 'translateX(20px)' },
          '100%': { opacity: 1, transform: 'translateX(0)' },
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
          {isEditing ? 'Edit Filter' : 'Add Filter'}
        </Typography>
        <IconButton size="small" onClick={onCancel} sx={{ ml: 1 }}>
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, pb: 2 }}>
        {/* ===== NATURAL LANGUAGE VIEW ===== */}
        {useNaturalLanguage ? (
          <>
            <TextField
              fullWidth
              size="small"
              variant="standard"
              value={naturalLanguageValue}
              onChange={(e) => setNaturalLanguageValue(e.target.value)}
              placeholder="e.g., only active members, amount over 1000"
              autoFocus
              multiline
              minRows={2}
            />
            <Typography
              component="button"
              variant="caption"
              onClick={() => setUseNaturalLanguage(false)}
              sx={{
                mt: 2,
                display: 'block',
                color: 'text.secondary',
                cursor: 'pointer',
                background: 'none',
                border: 'none',
                p: 0,
                textAlign: 'left',
                '&:hover': { color: 'primary.main' },
              }}
            >
              ← use field picker
            </Typography>
          </>
        ) : (
          /* ===== STRUCTURED VIEW ===== */
          <>
            {/* Field selection for new filters */}
            {!isEditing && (
              <Box sx={{ mb: 2 }}>
                {selectedField ? (
                  // Field selected: show as chip with change button
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label={formatFieldName(selectedField)}
                      size="small"
                      sx={{
                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                        color: theme.palette.primary.dark,
                        fontWeight: 600,
                      }}
                    />
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {selectedFieldType}
                    </Typography>
                    <Button
                      size="small"
                      variant="text"
                      onClick={() => setSelectedField('')}
                      sx={{
                        ml: 'auto',
                        minWidth: 'auto',
                        px: 1,
                        py: 0.25,
                        fontSize: '0.7rem',
                        color: 'text.secondary',
                        textTransform: 'none',
                      }}
                    >
                      change
                    </Button>
                  </Box>
                ) : (
                  // No field selected: show "Select a field" chip that opens dropdown
                  <FieldSelectorChip
                    availableFields={availableFields}
                    onSelect={setSelectedField}
                  />
                )}
              </Box>
            )}

            {/* Editing existing filter: show field as chip (not changeable) */}
            {isEditing && filter && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Chip
                  label={formatFieldName(filter.property)}
                  size="small"
                  sx={{
                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                    color: theme.palette.primary.dark,
                    fontWeight: 600,
                  }}
                />
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {dataType}
                </Typography>
              </Box>
            )}

            {/* Value input - only show when field is selected */}
            {(isEditing || selectedField) && (
              <>
                {/* String filter */}
                {effectiveType === 'string' && (
                  <TextField
                    fullWidth
                    size="small"
                    variant="standard"
                    value={stringValue}
                    onChange={(e) => setStringValue(e.target.value)}
                    placeholder="enter value..."
                    autoFocus
                  />
                )}

                {/* Number filter */}
                {effectiveType === 'number' && (
                  <Stack direction="row" spacing={1} alignItems="flex-end">
                    <FormControl size="small" variant="standard" sx={{ minWidth: 70 }}>
                      <Select
                        value={numberState.operator}
                        onChange={(e) =>
                          setNumberState((prev) => ({ ...prev, operator: e.target.value }))
                        }
                      >
                        {NUMERIC_OPERATORS.map((op) => (
                          <MenuItem key={op.value} value={op.value}>
                            {op.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>

                    <TextField
                      type="number"
                      size="small"
                      variant="standard"
                      value={numberState.value}
                      onChange={(e) =>
                        setNumberState((prev) => ({
                          ...prev,
                          value: e.target.value === '' ? '' : Number(e.target.value),
                        }))
                      }
                      placeholder="value"
                      sx={{ flex: 1 }}
                      autoFocus
                    />

                    {numberState.operator === 'between' && (
                      <>
                        <Typography variant="caption" sx={{ color: 'text.secondary', px: 0.5 }}>
                          and
                        </Typography>
                        <TextField
                          type="number"
                          size="small"
                          variant="standard"
                          value={numberState.value2 ?? ''}
                          onChange={(e) =>
                            setNumberState((prev) => ({
                              ...prev,
                              value2: e.target.value === '' ? '' : Number(e.target.value),
                            }))
                          }
                          placeholder="value"
                          sx={{ flex: 1 }}
                        />
                      </>
                    )}
                  </Stack>
                )}

                {/* Date filter */}
                {effectiveType === 'date' && (
                  <Stack spacing={1.5}>
                    <FormControl size="small" variant="standard" sx={{ minWidth: 100 }}>
                      <Select
                        value={dateState.operator}
                        onChange={(e) =>
                          setDateState((prev) => ({ ...prev, operator: e.target.value }))
                        }
                      >
                        {DATE_OPERATORS.map((op) => (
                          <MenuItem key={op.value} value={op.value}>
                            {op.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>

                    <Stack direction="row" spacing={1} alignItems="center">
                      <TextField
                        type="date"
                        size="small"
                        variant="standard"
                        value={dateState.value}
                        onChange={(e) =>
                          setDateState((prev) => ({ ...prev, value: e.target.value }))
                        }
                        sx={{ flex: 1 }}
                        autoFocus
                        slotProps={{
                          inputLabel: { shrink: true },
                        }}
                      />

                      {dateState.operator === 'between' && (
                        <>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            and
                          </Typography>
                          <TextField
                            type="date"
                            size="small"
                            variant="standard"
                            value={dateState.value2 ?? ''}
                            onChange={(e) =>
                              setDateState((prev) => ({ ...prev, value2: e.target.value }))
                            }
                            sx={{ flex: 1 }}
                            slotProps={{
                              inputLabel: { shrink: true },
                            }}
                          />
                        </>
                      )}
                    </Stack>
                  </Stack>
                )}

                {/* Boolean filter */}
                {effectiveType === 'boolean' && (
                  <RadioGroup
                    row
                    value={booleanValue ? 'true' : 'false'}
                    onChange={(e) => setBooleanValue(e.target.value === 'true')}
                  >
                    <FormControlLabel value="true" control={<Radio size="small" />} label="Yes" />
                    <FormControlLabel value="false" control={<Radio size="small" />} label="No" />
                  </RadioGroup>
                )}
              </>
            )}

            {/* Toggle to natural language */}
            <Typography
              component="button"
              variant="caption"
              onClick={() => setUseNaturalLanguage(true)}
              sx={{
                mt: 2,
                display: 'block',
                color: 'text.secondary',
                cursor: 'pointer',
                background: 'none',
                border: 'none',
                p: 0,
                textAlign: 'left',
                '&:hover': { color: 'primary.main' },
              }}
            >
              or just tell me what you want →
            </Typography>
          </>
        )}
      </Box>

      {/* Actions */}
      <Box
        sx={{
          display: 'flex',
          gap: 1,
          justifyContent: 'flex-end',
          px: 2,
          py: 1.5,
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Button size="small" onClick={onCancel} sx={{ color: 'text.secondary' }}>
          Cancel
        </Button>
        <Button size="small" variant="contained" onClick={handleSubmit} disabled={!isValid}>
          {isEditing ? 'Update' : 'Add'}
        </Button>
      </Box>
    </Box>
  )
}
