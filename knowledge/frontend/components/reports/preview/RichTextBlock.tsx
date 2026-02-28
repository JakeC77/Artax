import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography, useTheme } from '@mui/material'
import MDEditor from '@uiw/react-md-editor'
import '@uiw/react-md-editor/markdown-editor.css'
import { fetchBlockContent } from '../../../services/graphql'
import type { Source } from '../../../types/reports'
import SourceRefIndicator from './SourceRefIndicator'

interface RichTextBlockProps {
  reportBlockId: string
  sourceRefs?: string[]
  sources?: Source[]
}

export default function RichTextBlock({ reportBlockId, sourceRefs = [], sources = [] }: RichTextBlockProps) {
  const theme = useTheme()
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await fetchBlockContent(reportBlockId, 'rich_text')
        if (!active) return
        if (data && 'content' in data) {
          setContent(data.content)
        }
      } catch (e: any) {
        console.error('Failed to load rich text content:', e)
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

  if (!content) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        No content
      </Typography>
    )
  }

  const isDark = theme.palette.mode === 'dark'

  return (
    <Box
      sx={{
        position: 'relative',
        '& .w-md-editor': {
          boxShadow: 'none',
          bgcolor: 'transparent',
        },
        '& .w-md-editor-text': {
          bgcolor: 'transparent',
        },
        '& .wmde-markdown': {
          bgcolor: 'transparent',
          color: 'text.primary',
        },
        '& .wmde-markdown p': {
          color: 'text.primary',
        },
        '& .wmde-markdown h1, & .wmde-markdown h2, & .wmde-markdown h3, & .wmde-markdown h4, & .wmde-markdown h5, & .wmde-markdown h6': {
          color: 'text.primary',
        },
        '& .wmde-markdown code': {
          bgcolor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
          color: 'text.primary',
        },
        '& .wmde-markdown pre': {
          bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
          color: 'text.primary',
        },
        '& .wmde-markdown blockquote': {
          borderLeftColor: 'divider',
          color: 'text.secondary',
        },
        '& .wmde-markdown a': {
          color: 'primary.main',
        },
        '& .wmde-markdown table': {
          borderColor: 'divider',
        },
        '& .wmde-markdown th, & .wmde-markdown td': {
          borderColor: 'divider',
        },
      }}
    >
      <MDEditor.Markdown source={content} />
      {sourceRefs.length > 0 && (
        <Box sx={{ mt: 1, textAlign: 'right' }}>
          <SourceRefIndicator sourceRefs={sourceRefs} sources={sources} />
        </Box>
      )}
    </Box>
  )
}

