import { useState, useEffect } from 'react'
import { Box, CircularProgress, Typography, useTheme } from '@mui/material'
import MDEditor from '@uiw/react-md-editor'
import '@uiw/react-md-editor/markdown-editor.css'
import { upsertRichText, fetchBlockContent } from '../../../services/graphql'

interface RichTextEditorProps {
  reportBlockId: string
  onSave?: () => void
}

export default function RichTextEditor({ reportBlockId, onSave }: RichTextEditorProps) {
  const theme = useTheme()
  const [content, setContent] = useState('')
  const [initialContent, setInitialContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchBlockContent(reportBlockId, 'rich_text')
        if (!active) return
        if (data && 'content' in data) {
          setContent(data.content)
          setInitialContent(data.content)
        } else {
          setInitialContent('')
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load content')
        setInitialContent('')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [reportBlockId])

  const handleSave = async (value: string, skipCallback = false) => {
    try {
      setSaving(true)
      setError(null)
      await upsertRichText({
        reportBlockId,
        content: value || '',
      })
      if (!skipCallback) {
        onSave?.()
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to save content')
    } finally {
      setSaving(false)
    }
  }

  // Debounced auto-save - only save if content has changed from initial load
  useEffect(() => {
    if (!loading && initialContent !== null && content !== initialContent) {
      const timer = setTimeout(() => {
        handleSave(content, true) // Skip callback to prevent reload loop
      }, 500)
      return () => clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content, loading, initialContent])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  const isDark = theme.palette.mode === 'dark'

  return (
    <Box>
      <Box
        sx={{
          '& .w-md-editor': {
            bgcolor: 'background.paper',
            borderColor: 'divider',
          },
          '& .w-md-editor-text': {
            bgcolor: 'background.paper',
            color: 'text.primary',
          },
          '& .w-md-editor-text-textarea': {
            bgcolor: 'background.paper',
            color: 'text.primary',
          },
          '& .w-md-editor-preview': {
            bgcolor: 'background.paper',
            color: 'text.primary',
          },
          '& .w-md-editor-preview p': {
            color: 'text.primary',
          },
          '& .w-md-editor-preview h1, & .w-md-editor-preview h2, & .w-md-editor-preview h3, & .w-md-editor-preview h4, & .w-md-editor-preview h5, & .w-md-editor-preview h6': {
            color: 'text.primary',
          },
          '& .w-md-editor-preview code': {
            bgcolor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
            color: 'text.primary',
          },
          '& .w-md-editor-preview pre': {
            bgcolor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
            color: 'text.primary',
          },
          '& .w-md-editor-preview blockquote': {
            borderLeftColor: 'divider',
            color: 'text.secondary',
          },
          '& .w-md-editor-preview a': {
            color: 'primary.main',
          },
          '& .w-md-editor-preview table': {
            borderColor: 'divider',
          },
          '& .w-md-editor-preview th, & .w-md-editor-preview td': {
            borderColor: 'divider',
          },
        }}
      >
        <MDEditor
          value={content}
          onChange={(value) => setContent(value || '')}
        />
      </Box>
      {saving && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
          <CircularProgress size={16} />
          <Typography variant="body2" color="text.secondary">
            Saving...
          </Typography>
        </Box>
      )}
      {error && (
        <Box sx={{ mt: 1, p: 1, bgcolor: 'error.light', borderRadius: 1 }}>
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        </Box>
      )}
    </Box>
  )
}

