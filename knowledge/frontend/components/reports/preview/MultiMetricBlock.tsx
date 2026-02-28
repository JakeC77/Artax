import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography, Paper } from '@mui/material'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat'
import { fetchBlockContent } from '../../../services/graphql'
import type { Metric, Source } from '../../../types/reports'
import SourceRefIndicator from './SourceRefIndicator'

interface MultiMetricBlockProps {
  reportBlockId: string
  sourceRefs?: string[]
  sources?: Source[]
}

export default function MultiMetricBlock({ reportBlockId, sourceRefs = [], sources = [] }: MultiMetricBlockProps) {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await fetchBlockContent(reportBlockId, 'multi_metric')
        if (!active) return
        if (data && 'metrics' in data) {
          try {
            const parsed = JSON.parse(data.metrics) as Metric[]
            setMetrics(Array.isArray(parsed) ? parsed : [])
          } catch {
            setMetrics([])
          }
        }
      } catch (e: any) {
        console.error('Failed to load multi metric content:', e)
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

  if (metrics.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        No metrics
      </Typography>
    )
  }

  return (
    <Box sx={{ position: 'relative' }}>
      {sourceRefs.length > 0 && (
        <Box sx={{ position: 'absolute', top: -4, right: 0, zIndex: 1 }}>
          <SourceRefIndicator sourceRefs={sourceRefs} sources={sources} />
        </Box>
      )}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
          gap: 2,
        }}
      >
      {metrics.map((metric, index) => {
        const TrendIcon = metric.trend === 'up' ? TrendingUpIcon : metric.trend === 'down' ? TrendingDownIcon : TrendingFlatIcon
        const trendColor = metric.trend === 'up' ? 'success.main' : metric.trend === 'down' ? 'error.main' : 'text.secondary'

        return (
          <Paper
            key={index}
            elevation={0}
            sx={{
              p: 2,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              bgcolor: 'background.paper',
            }}
          >
            {metric.label && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {metric.label}
              </Typography>
            )}
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {metric.value}
              </Typography>
              {metric.unit && (
                <Typography variant="body2" color="text.secondary">
                  {metric.unit}
                </Typography>
              )}
              {metric.trend && (
                <TrendIcon sx={{ color: trendColor, fontSize: 20 }} />
              )}
            </Box>
          </Paper>
        )
      })}
      </Box>
    </Box>
  )
}

