import { useState } from 'react'
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Collapse,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import BlockList from './BlockList'
import { updateReportSection, deleteReportSection } from '../../services/graphql'
import type { ReportSection, ReportTemplateSection } from '../../types/reports'
import Button from '../common/Button'

interface SectionItemProps {
  section: ReportSection
  templateSection: ReportTemplateSection | null
  onSectionChange: () => void
}

export default function SectionItem({
  section,
  templateSection,
  onSectionChange,
}: SectionItemProps) {
  const [expanded, setExpanded] = useState(true)
  const [editingHeader, setEditingHeader] = useState(false)
  const [header, setHeader] = useState(section.header)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSaveHeader = async () => {
    try {
      setSaving(true)
      await updateReportSection({
        reportSectionId: section.reportSectionId,
        header: header.trim(),
      })
      setEditingHeader(false)
      onSectionChange()
    } catch (error) {
      console.error('Failed to update section header:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      setSaving(true)
      await deleteReportSection(section.reportSectionId)
      setDeleteDialogOpen(false)
      onSectionChange()
    } catch (error) {
      console.error('Failed to delete section:', error)
    } finally {
      setSaving(false)
    }
  }

  const templateBlocks = templateSection?.blocks || []

  return (
    <>
      <Paper
        elevation={0}
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          mb: 2,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            p: 2,
          }}
        >
          <Box sx={{ flex: 1 }}>
            {editingHeader ? (
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <TextField
                  value={header}
                  onChange={(e) => setHeader(e.target.value)}
                  size="small"
                  fullWidth
                  autoFocus
                  disabled={saving}
                  onBlur={handleSaveHeader}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSaveHeader()
                    } else if (e.key === 'Escape') {
                      setHeader(section.header)
                      setEditingHeader(false)
                    }
                  }}
                />
              </Box>
            ) : (
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {section.header}
              </Typography>
            )}
            <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
              <Chip label={section.sectionType} size="small" variant="outlined" />
              <Typography variant="caption" color="text.secondary">
                {section.blocks.length} block{section.blocks.length !== 1 ? 's' : ''}
              </Typography>
            </Box>
          </Box>
          <IconButton size="small" onClick={() => setEditingHeader(true)} disabled={saving}>
            <EditIcon sx={{ fontSize: 18 }} />
          </IconButton>
          <IconButton size="small" onClick={() => setDeleteDialogOpen(true)} disabled={saving} color="error">
            <DeleteIcon sx={{ fontSize: 18 }} />
          </IconButton>
          <IconButton size="small" onClick={() => setExpanded(!expanded)}>
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Box>
        <Collapse in={expanded}>
          <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            <BlockList
              blocks={section.blocks}
              reportSectionId={section.reportSectionId}
              templateBlocks={templateBlocks}
              onBlocksChange={onSectionChange}
            />
          </Box>
        </Collapse>
      </Paper>

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Section</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete section "{section.header}"? This will also delete all blocks in this section.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button size="sm" variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button size="sm" color="error" onClick={handleDelete} disabled={saving}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

