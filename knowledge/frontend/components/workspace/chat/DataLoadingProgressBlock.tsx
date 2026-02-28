import { Box, Typography, LinearProgress, Chip, alpha } from '@mui/material'
import { AccountTree, Link as LinkIcon } from '@mui/icons-material'
import type { ChatMessage } from './ChatMessages'

type DataLoadingProgressBlockProps = {
  message: ChatMessage
}

export default function DataLoadingProgressBlock({ message }: DataLoadingProgressBlockProps) {
  if (!message.dataLoadingProgress) {
    return null
  }

  const { type, created, total } = message.dataLoadingProgress
  const isNodes = type === 'nodes_created'
  const progress = total ? (created / total) * 100 : undefined

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        bgcolor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'light' ? 0.08 : 0.2),
        border: '1px solid',
        borderColor: 'primary.main',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {isNodes ? (
          <AccountTree sx={{ color: 'primary.main', fontSize: 20 }} />
        ) : (
          <LinkIcon sx={{ color: 'primary.main', fontSize: 20 }} />
        )}
        <Typography variant="body2" fontWeight={600} sx={{ color: 'primary.main' }}>
          {isNodes ? 'Nodes Created' : 'Relationships Created'}
        </Typography>
        <Chip
          label={`${created}${total ? ` / ${total}` : ''}`}
          size="small"
          sx={{
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            fontWeight: 600,
            ml: 'auto',
          }}
        />
      </Box>

      {progress !== undefined && (
        <Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 8,
              borderRadius: 1,
              bgcolor: (theme) => theme.palette.mode === 'light' ? 'action.hover' : 'action.selected',
              '& .MuiLinearProgress-bar': {
                bgcolor: 'primary.main',
              },
            }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            {Math.round(progress)}% complete
          </Typography>
        </Box>
      )}

      {message.content && (
        <Typography variant="body2" sx={{ color: 'text.primary', mt: 0.5 }}>
          {message.content}
        </Typography>
      )}
    </Box>
  )
}
