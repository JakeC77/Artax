import { Box, Typography, Divider } from '@mui/material'
import type { Source } from '../../../types/reports'
import SourceCitation from './SourceCitation'

interface SourcesListProps {
  sources: Source[]
}

export default function SourcesList({ sources }: SourcesListProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  return (
    <Box sx={{ mt: 6 }}>
      <Divider sx={{ mb: 3 }} />
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
        Sources
      </Typography>
      <Box>
        {sources.map((source, idx) => (
          <SourceCitation key={source.sourceId} source={source} index={idx + 1} />
        ))}
      </Box>
    </Box>
  )
}
