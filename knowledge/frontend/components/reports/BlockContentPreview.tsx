import { useEffect, useState } from 'react'
import { Box, Typography, CircularProgress } from '@mui/material'
import { fetchBlockContent } from '../../services/graphql'
import type { ReportBlock, RichTextContent, SingleMetricContent, MultiMetricContent, InsightCardContent } from '../../types/reports'

interface BlockContentPreviewProps {
  block: ReportBlock
}

export default function BlockContentPreview({ block }: BlockContentPreviewProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await fetchBlockContent(block.reportBlockId, block.blockType)
        if (!active) return

        if (!data) {
          setContent(null)
          return
        }

        switch (block.blockType) {
          case 'rich_text': {
            const richText = data as RichTextContent
            // Strip markdown and get plain text preview
            const plainText = richText.content
              .replace(/#{1,6}\s+/g, '') // Remove headers
              .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove bold
              .replace(/\*([^*]+)\*/g, '$1') // Remove italic
              .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1') // Remove links
              .replace(/`([^`]+)`/g, '$1') // Remove code
              .replace(/\n+/g, ' ') // Replace newlines with spaces
              .trim()
            setContent(plainText || 'No content')
            break
          }
          case 'single_metric': {
            const metric = data as SingleMetricContent
            const unit = metric.unit ? ` ${metric.unit}` : ''
            setContent(metric.label ? `${metric.label}: ${metric.value}${unit}` : `${metric.value}${unit}`)
            break
          }
          case 'multi_metric': {
            const multiMetric = data as MultiMetricContent
            try {
              const metrics = JSON.parse(multiMetric.metrics)
              const count = Array.isArray(metrics) ? metrics.length : 0
              setContent(count === 0 ? 'No metrics' : `${count} metric${count !== 1 ? 's' : ''}`)
            } catch {
              setContent('No metrics')
            }
            break
          }
          case 'insight_card': {
            const insight = data as InsightCardContent
            if (insight.title) {
              setContent(insight.body ? `${insight.title}: ${insight.body}` : insight.title)
            } else {
              setContent(insight.body || 'No content')
            }
            break
          }
          default:
            setContent(null)
        }
      } catch (e: any) {
        if (!active) return
        setContent(null)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [block.reportBlockId, block.blockType])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
        <CircularProgress size={12} />
      </Box>
    )
  }

  if (!content) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, fontStyle: 'italic' }}>
        No content
      </Typography>
    )
  }

  // Truncate long content
  const maxLength = 100
  const truncated = content.length > maxLength ? `${content.substring(0, maxLength)}...` : content

  return (
    <Typography
      variant="body2"
      color="text.secondary"
      sx={{
        mt: 0.5,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        lineHeight: 1.4,
      }}
    >
      {truncated}
    </Typography>
  )
}

