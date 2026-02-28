import { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Chip,
} from '@mui/material'
import { fetchReportTemplates, fetchReportTemplateById } from '../../services/graphql'
import type { ReportTemplate } from '../../types/reports'

interface TemplateSelectorProps {
  onSelectTemplate: (template: ReportTemplate) => void
  selectedTemplateId?: string | null
}

export default function TemplateSelector({
  onSelectTemplate,
  selectedTemplateId,
}: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Omit<ReportTemplate, 'sections'>[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchReportTemplates()
        if (!active) return
        setTemplates(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load templates')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  const handleSelect = async (template: Omit<ReportTemplate, 'sections'>) => {
    try {
      const fullTemplate = await fetchReportTemplateById(template.templateId, template.version)
      if (fullTemplate) {
        onSelectTemplate(fullTemplate)
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load template details')
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    )
  }

  if (templates.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">No templates available</Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
        gap: 2,
      }}
    >
      {templates.map((template) => (
        <Box key={`${template.templateId}-${template.version}`}>
          <Paper
            elevation={0}
            onClick={() => handleSelect(template)}
            sx={{
              p: 2,
              border: '1px solid',
              borderColor:
                selectedTemplateId === template.templateId ? 'primary.main' : 'divider',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              '&:hover': {
                boxShadow: 2,
                borderColor: 'primary.main',
                transform: 'translateY(-2px)',
              },
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {template.name}
              </Typography>
              <Chip label={`v${template.version}`} size="small" />
            </Box>
            {template.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {template.description}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Created: {new Date(template.createdAt).toLocaleDateString()}
            </Typography>
          </Paper>
        </Box>
      ))}
    </Box>
  )
}


