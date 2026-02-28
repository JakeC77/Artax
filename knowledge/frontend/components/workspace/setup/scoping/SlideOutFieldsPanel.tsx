/**
 * SlideOutFieldsPanel Component
 *
 * Inline field selection form that slides out on the right side of a card.
 * Used for selecting/editing fields of interest - mirrors SlideOutFilterPanel pattern.
 *
 * Features:
 * - Checkbox list of all available fields
 * - Selected fields shown checked
 * - Batches changes into single message on submit
 * - Compact design that fits within card height
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import {
  Box,
  Typography,
  Button,
  IconButton,
  Checkbox,
  FormControlLabel,
  CircularProgress,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import CloseIcon from '@mui/icons-material/Close'

import { useReducedMotion } from '../../../../hooks/useReducedMotion'
import type { FieldMetadata } from '../../../../hooks/useEntityFieldMetadata'

// ============================================================================
// Types
// ============================================================================

export interface SlideOutFieldsPanelProps {
  entityType: string
  /** Currently selected field names */
  selectedFields: string[]
  /** Available fields from schema */
  availableFields: FieldMetadata[]
  /** Whether fields are loading */
  loading?: boolean
  /** Called when user submits field changes */
  onSubmit: (chatMessage: string) => void
  /** Called when user cancels */
  onCancel: () => void
}

// ============================================================================
// Helper Functions
// ============================================================================

function formatFieldName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ============================================================================
// Main Component
// ============================================================================

export default function SlideOutFieldsPanel({
  entityType,
  selectedFields,
  availableFields,
  loading = false,
  onSubmit,
  onCancel,
}: SlideOutFieldsPanelProps) {
  const theme = useTheme()
  const prefersReducedMotion = useReducedMotion()

  // Local state for pending changes
  const [pendingSelection, setPendingSelection] = useState<Set<string>>(() => new Set(selectedFields))

  // Reset pending selection when selectedFields changes (e.g., panel reopened)
  useEffect(() => {
    setPendingSelection(new Set(selectedFields))
  }, [selectedFields])

  // Calculate changes
  const changes = useMemo(() => {
    const added = [...pendingSelection].filter((f) => !selectedFields.includes(f))
    const removed = selectedFields.filter((f) => !pendingSelection.has(f))
    return { added, removed }
  }, [pendingSelection, selectedFields])

  const hasChanges = changes.added.length > 0 || changes.removed.length > 0

  const handleToggleField = useCallback((fieldName: string) => {
    setPendingSelection((prev) => {
      const next = new Set(prev)
      if (next.has(fieldName)) {
        next.delete(fieldName)
      } else {
        next.add(fieldName)
      }
      return next
    })
  }, [])

  // Generate chat message and submit
  const handleSubmit = useCallback(() => {
    if (!hasChanges) {
      onCancel()
      return
    }

    const parts: string[] = []

    if (changes.added.length > 0) {
      const addedFormatted = changes.added.map((f) => `"${f}"`).join(', ')
      parts.push(`add ${addedFormatted}`)
    }

    if (changes.removed.length > 0) {
      const removedFormatted = changes.removed.map((f) => `"${f}"`).join(', ')
      parts.push(`remove ${removedFormatted}`)
    }

    const message = `Update fields of interest on ${entityType}: ${parts.join(' and ')}`
    onSubmit(message)
  }, [hasChanges, changes, entityType, onSubmit, onCancel])

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
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
            Fields of Interest
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Select which fields to include
          </Typography>
        </Box>
        <IconButton size="small" onClick={onCancel} sx={{ ml: 1 }}>
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </Box>

      {/* Content - Field list */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, pb: 2 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : availableFields.length === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', py: 2 }}>
            No fields available
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            {availableFields.map((field) => {
              const isSelected = pendingSelection.has(field.name)
              const isNewlyAdded = isSelected && !selectedFields.includes(field.name)
              const isMarkedForRemoval = !isSelected && selectedFields.includes(field.name)

              return (
                <FormControlLabel
                  key={field.name}
                  control={
                    <Checkbox
                      size="small"
                      checked={isSelected}
                      onChange={() => handleToggleField(field.name)}
                      sx={{ py: 0.25 }}
                    />
                  }
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontSize: '0.85rem',
                          color: isMarkedForRemoval
                            ? theme.palette.error.main
                            : isNewlyAdded
                              ? theme.palette.success.main
                              : 'text.primary',
                          textDecoration: isMarkedForRemoval ? 'line-through' : 'none',
                        }}
                      >
                        {formatFieldName(field.name)}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ color: 'text.disabled', fontSize: '0.7rem' }}
                      >
                        {field.dataType}
                      </Typography>
                    </Box>
                  }
                  sx={{
                    mx: 0,
                    px: 1,
                    py: 0.25,
                    borderRadius: 0.5,
                    bgcolor: isNewlyAdded
                      ? alpha(theme.palette.success.main, 0.05)
                      : isMarkedForRemoval
                        ? alpha(theme.palette.error.main, 0.05)
                        : 'transparent',
                    '&:hover': {
                      bgcolor: isNewlyAdded
                        ? alpha(theme.palette.success.main, 0.1)
                        : isMarkedForRemoval
                          ? alpha(theme.palette.error.main, 0.1)
                          : alpha(theme.palette.primary.main, 0.04),
                    },
                  }}
                />
              )
            })}
          </Box>
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
        <Button
          size="small"
          variant="contained"
          onClick={handleSubmit}
          disabled={!hasChanges}
        >
          Apply
        </Button>
      </Box>
    </Box>
  )
}
