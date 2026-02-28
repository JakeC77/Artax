import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography, Paper } from '@mui/material'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'
import { fetchBlockContent } from '../../../services/graphql'
import type { SingleMetricContent, Source } from '../../../types/reports'
import SourceRefIndicator from './SourceRefIndicator'

interface SingleMetricBlockProps {
  reportBlockId: string
  sourceRefs?: string[]
  sources?: Source[]
}

export default function SingleMetricBlock({ reportBlockId, sourceRefs = [], sources = [] }: SingleMetricBlockProps) {
  const [content, setContent] = useState<SingleMetricContent | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await fetchBlockContent(reportBlockId, 'single_metric')
        if (!active) return
        if (data && 'label' in data) {
          setContent(data as SingleMetricContent)
        }
      } catch (e: any) {
        console.error('Failed to load single metric content:', e)
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

  if (!content || !content.value) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        No content
      </Typography>
    )
  }

  const TrendIcon = content.trend === 'up' ? TrendingUpIcon : content.trend === 'down' ? TrendingDownIcon : TrendingFlatIcon
  const trendColor = content.trend === 'up' ? 'success.main' : content.trend === 'down' ? 'error.main' : 'text.secondary'

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: 'background.paper',
        position: 'relative',
      }}
    >
      {sourceRefs.length > 0 && (
        <Box sx={{ position: 'absolute', top: 8, right: 12 }}>
          <SourceRefIndicator sourceRefs={sourceRefs} sources={sources} />
        </Box>
      )}
      {content.label && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {content.label}
        </Typography>
      )}
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          {content.value}
        </Typography>
        {content.unit && (
          <Typography variant="h6" color="text.secondary">
            {content.unit}
          </Typography>
        )}
        {content.trend && (
          <TrendIcon sx={{ color: trendColor, fontSize: 28 }} />
        )}
      </Box>
    </Paper>
  )
}

