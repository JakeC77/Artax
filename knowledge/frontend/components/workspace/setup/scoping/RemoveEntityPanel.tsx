/**
 * RemoveEntityPanel Component
 *
 * Slide-out panel for removing entities with feedback collection.
 * Captures "why" to create feedback loops for AI learning.
 * Controlled component - parent manages open state.
 */

import { useState, useCallback, useEffect } from 'react'
import { Box, Typography, Button, IconButton, TextField } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import CloseIcon from '@mui/icons-material/Close'

import { useReducedMotion } from '../../../../hooks/useReducedMotion'
import type { ScopeState, ScopeEntity } from '../../../../types/scopeState'

// ============================================================================
// Types
// ============================================================================

export interface RemoveEntityPanelProps {
  entity: ScopeEntity
  scopeState: ScopeState | null
  /** Called with chat message including reason */
  onSubmit: (chatMessage: string) => void
  /** Called when panel is closed/cancelled */
  onCancel: () => void
}

// ============================================================================
// Main Component
// ============================================================================

export default function RemoveEntityPanel({
  entity,
  scopeState,
  onSubmit,
  onCancel,
}: RemoveEntityPanelProps) {
  const theme = useTheme()
  const prefersReducedMotion = useReducedMotion()

  const [reason, setReason] = useState('')

  // Reset reason when entity changes
  useEffect(() => {
    setReason('')
  }, [entity.entity_type])

  const handleSubmit = useCallback(() => {
    // Generate chat message with reason for AI learning
    let message = `Remove ${entity.entity_type} from the scope`
    if (reason.trim()) {
      message += `. Reason: ${reason.trim()}`
    }
    onSubmit(message)
  }, [entity.entity_type, reason, onSubmit])

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

  // Analyze impact
  const connectedEntities = scopeState
    ? scopeState.relationships
        .filter((r) => r.from_entity === entity.entity_type || r.to_entity === entity.entity_type)
        .map((r) => (r.from_entity === entity.entity_type ? r.to_entity : r.from_entity))
        .filter((e) => e !== scopeState.primary_entity)
    : []
  const uniqueConnected = [...new Set(connectedEntities)]
  const filterCount = entity.filters.length

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
        <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
          Remove {entity.entity_type}
        </Typography>
        <IconButton size="small" onClick={onCancel} sx={{ ml: 1 }}>
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, pb: 2 }}>
        {/* Impact info */}
        {(filterCount > 0 || uniqueConnected.length > 0) && (
          <Box
            sx={{
              p: 1.5,
              bgcolor: alpha(theme.palette.grey[500], 0.06),
              borderRadius: 0.5,
              mb: 2,
            }}
          >
            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.5 }}>
              {filterCount > 0 && (
                <>
                  {filterCount} filter{filterCount > 1 ? 's' : ''} will be removed.
                </>
              )}
              {uniqueConnected.length > 0 && (
                <>
                  {filterCount > 0 && <br />}
                  May affect: {uniqueConnected.join(', ')}
                </>
              )}
            </Typography>
          </Box>
        )}

        {/* Reason input - for AI feedback loop */}
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          Why are you removing this?
        </Typography>
        <TextField
          fullWidth
          size="small"
          variant="standard"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g., not relevant to this analysis"
          multiline
          minRows={2}
          autoFocus
        />

        {/* Feedback note */}
        <Typography
          variant="caption"
          sx={{
            mt: 2,
            display: 'block',
            color: 'text.disabled',
            fontStyle: 'italic',
          }}
        >
          Your feedback helps improve recommendations
        </Typography>
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
        <Button size="small" variant="contained" onClick={handleSubmit}>
          Remove
        </Button>
      </Box>
    </Box>
  )
}
