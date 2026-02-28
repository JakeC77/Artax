import { useState, useEffect } from 'react'
import { Box, TextField, MenuItem, CircularProgress } from '@mui/material'
import { upsertSingleMetric, fetchBlockContent } from '../../../services/graphql'

interface SingleMetricEditorProps {
  reportBlockId: string
  onSave?: () => void
}

export default function SingleMetricEditor({ reportBlockId, onSave }: SingleMetricEditorProps) {
  const [label, setLabel] = useState('')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')
  const [trend, setTrend] = useState<'up' | 'down' | 'stable' | null>(null)
  const [initialState, setInitialState] = useState<{ label: string; value: string; unit: string; trend: typeof trend } | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchBlockContent(reportBlockId, 'single_metric')
        if (!active) return
        if (data && 'label' in data) {
          setLabel(data.label)
          setValue(data.value)
          setUnit(data.unit || '')
          setTrend(data.trend)
          setInitialState({ label: data.label, value: data.value, unit: data.unit || '', trend: data.trend })
        } else {
          setInitialState({ label: '', value: '', unit: '', trend: null })
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load content')
        setInitialState({ label: '', value: '', unit: '', trend: null })
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
    if (!label.trim() || !value.trim()) {
      setError('Label and value are required')
      return
    }

    try {
      setSaving(true)
      setError(null)
      await upsertSingleMetric({
        reportBlockId,
        label: label.trim(),
        value: value.trim(),
        unit: unit.trim() || null,
        trend: trend || null,
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
        label !== initialState.label ||
        value !== initialState.value ||
        unit !== initialState.unit ||
        trend !== initialState.trend
      
      if (hasChanged && label.trim() && value.trim()) {
        const timer = setTimeout(() => {
          handleSave(true) // Skip callback to prevent reload loop
        }, 500)
        return () => clearTimeout(timer)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [label, value, unit, trend, loading, initialState])

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
        label="Label"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        fullWidth
        required
        disabled={saving}
      />
      <Box sx={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 2 }}>
        <TextField
          label="Value"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          fullWidth
          required
          disabled={saving}
        />
        <TextField
          label="Unit"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          fullWidth
          disabled={saving}
        />
        <TextField
          label="Trend"
          value={trend || ''}
          onChange={(e) => setTrend((e.target.value || null) as typeof trend)}
          fullWidth
          select
          disabled={saving}
        >
          <MenuItem value="">None</MenuItem>
          <MenuItem value="up">Up</MenuItem>
          <MenuItem value="down">Down</MenuItem>
          <MenuItem value="stable">Stable</MenuItem>
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

