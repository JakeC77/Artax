import { useState, useEffect, useCallback } from 'react'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  IconButton,
  Typography,
  Alert,
} from '@mui/material'
import { CloseOutline } from '@carbon/icons-react'
import { alpha, useTheme } from '@mui/material/styles'
import MDEditor from '@uiw/react-md-editor'
import '@uiw/react-md-editor/markdown-editor.css'
import { updateOntology, type Ontology } from '../../services/graphql'
import Button from '../common/Button'

export type DomainExamplesModalProps = {
  open: boolean
  onClose: () => void
  ontology: Ontology | null
  onSuccess?: () => void
}

export default function DomainExamplesModal({
  open,
  onClose,
  ontology,
  onSuccess,
}: DomainExamplesModalProps) {
  const theme = useTheme()
  const [domainExamples, setDomainExamples] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open && ontology) {
      setDomainExamples(ontology.domainExamples ?? '')
      setError(null)
    }
  }, [open, ontology])

  const handleClose = useCallback(() => {
    if (!saving) {
      onClose()
      setError(null)
    }
  }, [saving, onClose])

  const handleSave = useCallback(async () => {
    if (!ontology) return
    setSaving(true)
    setError(null)
    try {
      await updateOntology(
        ontology.ontologyId,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        domainExamples || null
      )
      onSuccess?.()
      handleClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save domain examples')
    } finally {
      setSaving(false)
    }
  }, [ontology, domainExamples, onSuccess, handleClose])

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          boxShadow: `0 8px 24px ${alpha(theme.palette.common.black, 0.15)}`,
          minHeight: '60vh',
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Domain examples {ontology ? `— ${ontology.name}` : ''}
        </Typography>
        <IconButton onClick={handleClose} aria-label="Close" size="small" disabled={saving}>
          <CloseOutline size={24} />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Markdown content used as examples in AI workflows for this ontology.
        </Typography>
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        <Box
          sx={{
            flex: 1,
            minHeight: 360,
            '& .w-md-editor': {
              minHeight: 340,
            },
            '& .w-md-editor-toolbar': {
              bgcolor: 'action.hover',
              borderBottom: '1px solid',
              borderColor: 'divider',
            },
            '& .w-md-editor-toolbar button': {
              color: 'text.secondary',
            },
            '& .w-md-editor-text-input': {
              fontFamily: theme.typography.fontFamily,
              fontSize: '0.875rem',
            },
            '& .w-md-editor-preview': {
              boxSizing: 'border-box',
              p: 1.5,
            },
          }}
        >
          <MDEditor
            value={domainExamples}
            onChange={(value) => setDomainExamples(value ?? '')}
            preview="live"
            visibleDragbar={false}
            height={340}
            textareaProps={{
              placeholder: 'Enter markdown examples for the AI workflow...',
              style: {
                fontFamily: theme.typography.fontFamily,
                fontSize: '0.875rem',
              },
            }}
          />
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button size="sm" variant="outline" onClick={handleClose} disabled={saving}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
