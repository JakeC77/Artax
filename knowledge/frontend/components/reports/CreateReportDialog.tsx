import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Box,
  Typography,
  CircularProgress,
  MenuItem,
} from '@mui/material'
import Button from '../common/Button'
import TemplateSelector from './TemplateSelector'
import TemplateViewer from './TemplateViewer'
import {
  createReport,
  createReportSection,
  createReportBlock,
} from '../../services/graphql'
import type { ReportTemplate } from '../../types/reports'

interface CreateReportDialogProps {
  open: boolean
  onClose: () => void
  onSuccess: (reportId: string) => void
  workspaceAnalysisId?: string | null
  scenarioId?: string | null
}

export default function CreateReportDialog({
  open,
  onClose,
  onSuccess,
  workspaceAnalysisId,
  scenarioId,
}: CreateReportDialogProps) {
  const [title, setTitle] = useState('')
  const [status, setStatus] = useState('draft')
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      // Reset state when dialog closes
      setTitle('')
      setStatus('draft')
      setSelectedTemplate(null)
      setError(null)
    }
  }, [open])

  const handleCreate = async () => {
    if (!selectedTemplate || !title.trim()) {
      setError('Please select a template and enter a title')
      return
    }

    try {
      setCreating(true)
      setError(null)

      // Create the report
      // TODO: Remove hardcoded scenario ID - this is for testing only
      const TEST_SCENARIO_ID = '85dca23d-ca25-4f49-8719-e2b8a20bd329'
      const reportId = await createReport({
        templateId: selectedTemplate.templateId,
        templateVersion: selectedTemplate.version,
        workspaceAnalysisId: workspaceAnalysisId || null,
        scenarioId: scenarioId || TEST_SCENARIO_ID,
        type: workspaceAnalysisId ? 'analysis' : 'scenario',
        title: title.trim(),
        status,
        metadata: null,
      })

      // Create all sections from template
      const sectionPromises = selectedTemplate.sections.map((templateSection) =>
        createReportSection({
          reportId,
          templateSectionId: templateSection.templateSectionId,
          sectionType: templateSection.sectionType,
          header: templateSection.header,
          order: templateSection.order,
        })
      )

      const sectionIds = await Promise.all(sectionPromises)

      // Create all blocks from template
      const blockPromises: Promise<string>[] = []
      for (let i = 0; i < selectedTemplate.sections.length; i++) {
        const templateSection = selectedTemplate.sections[i]
        const reportSectionId = sectionIds[i]

        for (const templateBlock of templateSection.blocks) {
          blockPromises.push(
            createReportBlock({
              reportSectionId,
              templateBlockId: templateBlock.templateBlockId,
              blockType: templateBlock.blockType,
              order: templateBlock.order,
              layoutHints: templateBlock.layoutHints,
              sourceRefs: null,
              provenance: null,
            })
          )
        }
      }

      await Promise.all(blockPromises)

      onSuccess(reportId)
      onClose()
    } catch (e: any) {
      setError(e?.message || 'Failed to create report')
    } finally {
      setCreating(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Create New Report
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <TextField
              label="Report Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              fullWidth
              required
              disabled={creating}
            />
            <TextField
              label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              fullWidth
              select
              disabled={creating}
            >
              <MenuItem value="draft">Draft</MenuItem>
              <MenuItem value="in_progress">In Progress</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
            </TextField>
          </Box>

          {!selectedTemplate ? (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                Select a Template
              </Typography>
              <TemplateSelector
                onSelectTemplate={(template) => setSelectedTemplate(template)}
                selectedTemplateId={undefined}
              />
            </Box>
          ) : (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  Selected Template: {selectedTemplate.name}
                </Typography>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedTemplate(null)}
                  disabled={creating}
                >
                  Change Template
                </Button>
              </Box>
              <Box sx={{ maxHeight: 400, overflowY: 'auto' }}>
                <TemplateViewer template={selectedTemplate} />
              </Box>
            </Box>
          )}

          {error && (
            <Box sx={{ p: 1.5, bgcolor: 'error.light', borderRadius: 1 }}>
              <Typography color="error">{error}</Typography>
            </Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button variant="outline" size="sm" onClick={onClose} disabled={creating}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={handleCreate}
          disabled={creating || !selectedTemplate || !title.trim()}
        >
          {creating ? <CircularProgress size={16} /> : 'Create Report'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

