import { useState, useEffect } from 'react'
import { Box, TextField, MenuItem, IconButton, CircularProgress } from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import { upsertMultiMetric, fetchBlockContent } from '../../../services/graphql'
import type { Metric } from '../../../types/reports'

interface MultiMetricEditorProps {
  reportBlockId: string
  onSave?: () => void
}

export default function MultiMetricEditor({ reportBlockId, onSave }: MultiMetricEditorProps) {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [initialMetrics, setInitialMetrics] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchBlockContent(reportBlockId, 'multi_metric')
        if (!active) return
        if (data && 'metrics' in data) {
          try {
            const parsed = JSON.parse(data.metrics) as Metric[]
            const loadedMetrics = Array.isArray(parsed) ? parsed : []
            setMetrics(loadedMetrics)
            setInitialMetrics(data.metrics)
          } catch {
            setMetrics([])
            setInitialMetrics('[]')
          }
        } else {
          setMetrics([])
          setInitialMetrics('[]')
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load content')
        setInitialMetrics('[]')
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
    try {
      setSaving(true)
      setError(null)
      const metricsJson = JSON.stringify(metrics)
      await upsertMultiMetric({
        reportBlockId,
        metrics: metricsJson,
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

  // Debounced auto-save - only save if metrics have changed from initial load
  useEffect(() => {
    if (!loading && initialMetrics !== null) {
      const currentMetricsJson = JSON.stringify(metrics)
      if (currentMetricsJson !== initialMetrics) {
        const timer = setTimeout(() => {
          handleSave(true) // Skip callback to prevent reload loop
        }, 500)
        return () => clearTimeout(timer)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metrics, loading, initialMetrics])

  const addMetric = () => {
    setMetrics([...metrics, { label: '', value: '', unit: null, trend: null }])
  }

  const removeMetric = (index: number) => {
    setMetrics(metrics.filter((_, i) => i !== index))
  }

  const updateMetric = (index: number, field: keyof Metric, value: string | null) => {
    const updated = [...metrics]
    updated[index] = { ...updated[index], [field]: value }
    setMetrics(updated)
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {metrics.map((metric, index) => (
        <Box
          key={index}
          sx={{
            p: 2,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600 }}>Metric {index + 1}</span>
            <IconButton size="small" onClick={() => removeMetric(index)} disabled={saving}>
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Box>
          <TextField
            label="Label"
            value={metric.label}
            onChange={(e) => updateMetric(index, 'label', e.target.value)}
            fullWidth
            size="small"
            disabled={saving}
          />
          <Box sx={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 2 }}>
            <TextField
              label="Value"
              value={metric.value}
              onChange={(e) => updateMetric(index, 'value', e.target.value)}
              fullWidth
              size="small"
              disabled={saving}
            />
            <TextField
              label="Unit"
              value={metric.unit || ''}
              onChange={(e) => updateMetric(index, 'unit', e.target.value || null)}
              fullWidth
              size="small"
              disabled={saving}
            />
            <TextField
              label="Trend"
              value={metric.trend || ''}
              onChange={(e) => updateMetric(index, 'trend', (e.target.value || null) as typeof metric.trend)}
              fullWidth
              size="small"
              select
              disabled={saving}
            >
              <MenuItem value="">None</MenuItem>
              <MenuItem value="up">Up</MenuItem>
              <MenuItem value="down">Down</MenuItem>
              <MenuItem value="stable">Stable</MenuItem>
            </TextField>
          </Box>
        </Box>
      ))}

      <Box>
        <IconButton onClick={addMetric} disabled={saving} sx={{ border: '1px dashed', borderColor: 'divider' }}>
          <AddIcon sx={{ fontSize: 20 }} />
        </IconButton>
        <span style={{ marginLeft: 8, fontSize: '0.875rem', color: '#666' }}>Add Metric</span>
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

