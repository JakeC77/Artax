import { Box, Typography, Link, Chip } from '@mui/material'
import type { Source } from '../../../types/reports'

interface SourceCitationProps {
  source: Source
  index: number
}

function isWebUrl(uri: string | null): boolean {
  if (!uri) return false
  return uri.startsWith('http://') || uri.startsWith('https://')
}

function formatSourceType(sourceType: string): string {
  // Convert snake_case or camelCase to Title Case with spaces
  return sourceType
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function SourceCitation({ source, index }: SourceCitationProps) {
  const isLink = isWebUrl(source.uri)

  return (
    <Box
      id={`source-${source.sourceId}`}
      sx={{
        display: 'flex',
        gap: 1.5,
        py: 1.5,
        '&:not(:last-child)': {
          borderBottom: '1px solid',
          borderColor: 'divider',
        },
      }}
    >
      {/* Citation number */}
      <Typography
        component="span"
        sx={{
          fontWeight: 600,
          color: 'text.secondary',
          minWidth: 28,
          flexShrink: 0,
        }}
      >
        [{index}]
      </Typography>

      {/* Citation content */}
      <Box sx={{ flex: 1 }}>
        {/* Source type chip + title */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            label={formatSourceType(source.sourceType)}
            size="small"
            sx={{
              height: 20,
              fontSize: '0.7rem',
              fontWeight: 500,
              bgcolor: 'action.selected',
            }}
          />
          {isLink && source.uri ? (
            <Link
              href={source.uri}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                fontWeight: 500,
                textDecoration: 'none',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {source.title}
            </Link>
          ) : (
            <Typography component="span" sx={{ fontWeight: 500 }}>
              {source.title}
            </Typography>
          )}
        </Box>

        {/* Description */}
        {source.description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5, pl: 0.5 }}
          >
            {source.description}
          </Typography>
        )}

        {/* Show URI if not a web link (e.g., for query identifiers) */}
        {!isLink && source.uri && (
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ mt: 0.25, pl: 0.5, display: 'block', fontFamily: 'monospace' }}
          >
            {source.uri}
          </Typography>
        )}
      </Box>
    </Box>
  )
}
