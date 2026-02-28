import { useState, useEffect } from 'react'
import { Box, TextField, MenuItem, CircularProgress } from '@mui/material'
import { upsertInsightCard, fetchBlockContent } from '../../../services/graphql'

interface InsightCardEditorProps {
  reportBlockId: string
  onSave?: () => void
}

export default function InsightCardEditor({ reportBlockId, onSave }: InsightCardEditorProps) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [badge, setBadge] = useState('')
  const [severity, setSeverity] = useState<'info' | 'warning' | 'critical' | null>(null)
  const [initialState, setInitialState] = useState<{ title: string; body: string; badge: string; severity: typeof severity } | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchBlockContent(reportBlockId, 'insight_card')
        if (!active) return
        if (data && 'title' in data) {
          setTitle(data.title)
          setBody(data.body)
          setBadge(data.badge || '')
          setSeverity(data.severity)
          setInitialState({ title: data.title, body: data.body, badge: data.badge || '', severity: data.severity })
        } else {
          setInitialState({ title: '', body: '', badge: '', severity: null })
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load content')
        setInitialState({ title: '', body: '', badge: '', severity: null })
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [reportBlockId])

  const handleSave = async (skipCallback = false) => {
    if (!title.trim() || !body.trim()) {
      setError('Title and body are required')
      return
    }

    try {
      setSaving(true)
      setError(null)
      await upsertInsightCard({
        reportBlockId,
        title: title.trim(),
        body: body.trim(),
        badge: badge.trim() || null,
        severity: severity || null,
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

  // Debounced auto-save - only save if values have changed from initial load
  useEffect(() => {
    if (!loading && initialState !== null) {
      const hasChanged = 
        title !== initialState.title ||
        body !== initialState.body ||
        badge !== initialState.badge ||
        severity !== initialState.severity
      
      if (hasChanged && title.trim() && body.trim()) {
        const timer = setTimeout(() => {
          handleSave(true) // Skip callback to prevent reload loop
        }, 500)
        return () => clearTimeout(timer)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, body, badge, severity, loading, initialState])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <TextField
        label="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        fullWidth
        required
        disabled={saving}
      />
      <TextField
        label="Body"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        fullWidth
        multiline
        rows={4}
        required
        disabled={saving}
      />
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <TextField
          label="Badge"
          value={badge}
          onChange={(e) => setBadge(e.target.value)}
          fullWidth
          disabled={saving}
        />
        <TextField
          label="Severity"
          value={severity || ''}
          onChange={(e) => setSeverity((e.target.value || null) as typeof severity)}
          fullWidth
          select
          disabled={saving}
        >
          <MenuItem value="">None</MenuItem>
          <MenuItem value="info">Info</MenuItem>
          <MenuItem value="warning">Warning</MenuItem>
          <MenuItem value="critical">Critical</MenuItem>
        </TextField>
      </Box>
      {saving && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={16} />
          <span style={{ fontSize: '0.875rem', color: '#666' }}>Saving...</span>
        </Box>
      )}
      {error && (
        <Box sx={{ p: 1, bgcolor: 'error.light', borderRadius: 1 }}>
          <span style={{ fontSize: '0.875rem', color: '#d32f2f' }}>{error}</span>
        </Box>
      )}
    </Box>
  )
}

