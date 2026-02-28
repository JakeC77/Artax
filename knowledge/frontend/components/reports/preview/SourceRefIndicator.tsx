import { Box, Link } from '@mui/material'
import type { Source } from '../../../types/reports'

interface SourceRefIndicatorProps {
  sourceRefs: string[]
  sources: Source[]
}

export default function SourceRefIndicator({ sourceRefs, sources }: SourceRefIndicatorProps) {
  if (!sourceRefs || sourceRefs.length === 0 || !sources || sources.length === 0) {
    return null
  }

  // Map sourceRefs to their index numbers (1-based)
  const refIndices = sourceRefs
    .map((refId) => {
      const idx = sources.findIndex((s) => s.sourceId === refId)
      return idx >= 0 ? idx + 1 : null
    })
    .filter((idx): idx is number => idx !== null)
    .sort((a, b) => a - b)

  if (refIndices.length === 0) {
    return null
  }

  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        gap: 0.25,
        ml: 0.5,
        verticalAlign: 'super',
        fontSize: '0.7rem',
        lineHeight: 1,
      }}
    >
      {refIndices.map((idx, i) => (
        <Link
          key={idx}
          href={`#source-${sources[idx - 1].sourceId}`}
          sx={{
            color: 'text.secondary',
            textDecoration: 'none',
            '&:hover': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          [{idx}]{i < refIndices.length - 1 ? ',' : ''}
        </Link>
      ))}
    </Box>
  )
}
