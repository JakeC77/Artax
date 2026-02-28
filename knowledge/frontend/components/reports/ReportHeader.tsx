import { useState } from 'react'
import { Box, TextField, MenuItem, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import Button from '../common/Button'
import VisibilityIcon from '@mui/icons-material/Visibility'
import type { Report } from '../../types/reports'

interface ReportHeaderProps {
  report: Report
  onUpdate?: () => Promise<void>
}

export default function ReportHeader({ report, onUpdate }: ReportHeaderProps) {
  const navigate = useNavigate()
  const [title, setTitle] = useState(report.title)
  const [status, setStatus] = useState(report.status)
  const [saving, setSaving] = useState(false)

  const handleTitleChange = async (newTitle: string) => {
    setTitle(newTitle)
    if (onUpdate) {
      try {
        setSaving(true)
        await onUpdate()
      } finally {
        setSaving(false)
      }
    }
  }

  const handleStatusChange = async (newStatus: string) => {
    setStatus(newStatus)
    if (onUpdate) {
      try {
        setSaving(true)
        await onUpdate()
      } finally {
        setSaving(false)
      }
    }
  }

  return (
    <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 2 }}>
        <TextField
          label="Report Title"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          fullWidth
          disabled={saving}
        />
        <TextField
          label="Status"
          value={status}
          onChange={(e) => handleStatusChange(e.target.value)}
          fullWidth
          select
          disabled={saving}
        >
          <MenuItem value="draft">Draft</MenuItem>
          <MenuItem value="in_progress">In Progress</MenuItem>
          <MenuItem value="completed">Completed</MenuItem>
        </TextField>
      </Box>
      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {report.templateId && report.templateVersion !== null && (
            <Typography variant="caption" color="text.secondary">
              Template: {report.templateId} (v{report.templateVersion})
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            Type: {report.type}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <VisibilityIcon sx={{ fontSize: 18 }} />
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/reports/${report.reportId}/preview`)}
          >
            Preview
          </Button>
        </Box>
      </Box>
    </Box>
  )
}


