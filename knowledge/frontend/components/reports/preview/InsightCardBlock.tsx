import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography, Paper, Chip } from '@mui/material'
import InfoIcon from '@mui/icons-material/Info'
import WarningIcon from '@mui/icons-material/Warning'
import ErrorIcon from '@mui/icons-material/Error'
import { fetchBlockContent } from '../../../services/graphql'
import type { InsightCardContent, Source } from '../../../types/reports'
import SourceRefIndicator from './SourceRefIndicator'

interface InsightCardBlockProps {
  reportBlockId: string
  sourceRefs?: string[]
  sources?: Source[]
}

export default function InsightCardBlock({ reportBlockId, sourceRefs = [], sources = [] }: InsightCardBlockProps) {
  const [content, setContent] = useState<InsightCardContent | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await fetchBlockContent(reportBlockId, 'insight_card')
        if (!active) return
        if (data && 'title' in data) {
          setContent(data as InsightCardContent)
        }
      } catch (e: any) {
        console.error('Failed to load insight card content:', e)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [reportBlockId])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  if (!content || (!content.title && !content.body)) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        No content
      </Typography>
    )
  }

  const getSeverityColor = (severity: string | null) => {
    switch (severity) {
      case 'critical':
        return 'error'
      case 'warning':
        return 'warning'
      case 'info':
      default:
        return 'info'
    }
  }

  const getSeverityIcon = (severity: string | null) => {
    switch (severity) {
      case 'critical':
        return <ErrorIcon />
      case 'warning':
        return <WarningIcon />
      case 'info':
      default:
        return <InfoIcon />
    }
  }

  const severityColor = getSeverityColor(content.severity)

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: 'background.paper',
        borderLeft: content.severity ? `4px solid` : undefined,
        borderLeftColor: content.severity ? `${severityColor}.main` : undefined,
        position: 'relative',
      }}
    >
      {sourceRefs.length > 0 && (
        <Box sx={{ position: 'absolute', top: 8, right: 12 }}>
          <SourceRefIndicator sourceRefs={sourceRefs} sources={sources} />
        </Box>
      )}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 2 }}>
        {content.severity && (
          <Box sx={{ color: `${severityColor}.main`, display: 'flex', alignItems: 'center' }}>
            {getSeverityIcon(content.severity)}
          </Box>
        )}
        <Box sx={{ flex: 1 }}>
          {content.badge && (
            <Chip
              label={content.badge}
              size="small"
              sx={{ mb: 1 }}
              color={severityColor as 'info' | 'warning' | 'error'}
              variant="outlined"
            />
          )}
          {content.title && (
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
              {content.title}
            </Typography>
          )}
          {content.body && (
            <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
              {content.body}
            </Typography>
          )}
        </Box>
      </Box>
    </Paper>
  )
}

