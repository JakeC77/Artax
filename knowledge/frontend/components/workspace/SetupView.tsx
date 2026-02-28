import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'
import MDEditor from '@uiw/react-md-editor'
import '@uiw/react-md-editor/markdown-editor.css'
import {
  Box,
  Container,
  TextField,
  Typography,
  MenuItem,
  CircularProgress,
  IconButton,
  Tooltip,
  Paper,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material'
import AttachFileRoundedIcon from '@mui/icons-material/AttachFileRounded'
import { useTheme } from '@mui/material/styles'
import { Edit, TrashCan, Document } from '@carbon/icons-react'
import Button from '../common/Button'
import { DataLoadingOverlay } from '../common/DataLoadingOverlay'
import {
  updateWorkspace as gqlUpdateWorkspace,
  fetchWorkspaceById,
  createScratchpadAttachment,
  fetchScratchpadAttachments,
  deleteScratchpadAttachment,
  type ScratchpadAttachment,
} from '../../services/graphql'
import { useWorkspace } from '../../contexts/WorkspaceContext'

export default function SetupView() {
  const theme = useTheme()
  const { currentWorkspace, setCurrentWorkspace, setChatOpen } = useWorkspace()

  const [name, setName] = useState('')
  const [intent, setIntent] = useState('')
  const [visibility, setVisibility] = useState('private')
  
  // Mocks for now
  const [aiTeam, setAiTeam] = useState<string>('')
  const [communicationStyle, setCommunicationStyle] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [isEditingIntent, setIsEditingIntent] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [attachments, setAttachments] = useState<ScratchpadAttachment[]>([])
  const [loadingAttachments, setLoadingAttachments] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [snackbar, setSnackbar] = useState<{
    open: boolean
    message: string
    severity: 'success' | 'error' | 'info' | 'warning'
  }>({
    open: false,
    message: '',
    severity: 'info',
  })

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    open: boolean
    attachmentId: string | null
  }>({
    open: false,
    attachmentId: null,
  })

  // Load workspace data from currentWorkspace
  useEffect(() => {
    if (!currentWorkspace) return
    setName(currentWorkspace.name)
    setIntent(currentWorkspace.intent || '')
    setVisibility(currentWorkspace.visibility || 'private')
    
    if (currentWorkspace.setupRunId) {
      setChatOpen(true)
    }
    
    loadAttachments()
  }, [currentWorkspace, setChatOpen])

  async function loadAttachments() {
    if (!currentWorkspace?.workspaceId) return
    try {
      setLoadingAttachments(true)
      const data = await fetchScratchpadAttachments(currentWorkspace.workspaceId)
      setAttachments(data)
    } catch (e) {
      console.error('Failed to load attachments', e)
    } finally {
      setLoadingAttachments(false)
    }
  }

  // Also listen for external intent updates (e.g. from ChatDock via context if we wire it up, or if currentWorkspace updates)
  // For now relying on currentWorkspace updates.

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    if (!currentWorkspace?.workspaceId) {
      setSnackbar({
        open: true,
        message: 'No active workspace to upload to',
        severity: 'error',
      })
      return
    }
    
    try {
      setUploading(true)
      const derivedTitle = file.name.replace(/\.[^.]+$/, '')
      await createScratchpadAttachment({
        workspaceId: currentWorkspace.workspaceId,
        title: derivedTitle,
        file: file,
      })
      setSnackbar({
        open: true,
        message: 'Document uploaded successfully!',
        severity: 'success',
      })
      loadAttachments()
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: error?.message || 'Failed to upload document',
        severity: 'error',
      })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      setSnackbar({
        open: true,
        message: 'Please enter a workspace title',
        severity: 'warning',
      })
      return
    }
    if (!currentWorkspace?.workspaceId) return

    try {
      setSaving(true)

      await gqlUpdateWorkspace({
        workspaceId: currentWorkspace.workspaceId,
        name: name.trim(),
        intent: intent.trim() || null,
        visibility, 
      })

      // Refresh workspace data
      const updated = await fetchWorkspaceById(currentWorkspace.workspaceId)
      if (updated) {
        setCurrentWorkspace(updated)
        setSnackbar({
          open: true,
          message: 'Workspace updated successfully',
          severity: 'success',
        })
      } else {
        // Workspace was updated but not yet available (eventual consistency, permissions, etc.)
        setSnackbar({
          open: true,
          message: 'Workspace updated but not yet available. Please refresh the page or try again in a moment.',
          severity: 'error',
        })
      }

    } catch (e: any) {
      setSnackbar({
        open: true,
        message: e?.message || 'Failed to update workspace',
        severity: 'error',
      })
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteAttachment(id: string) {
    setDeleteConfirmation({ open: true, attachmentId: id })
  }

  async function confirmDeleteAttachment() {
    const id = deleteConfirmation.attachmentId
    if (!id) return

    try {
      await deleteScratchpadAttachment(id)
      setAttachments(prev => prev.filter(a => a.scratchpadAttachmentId !== id))
      setSnackbar({
        open: true,
        message: 'Document removed successfully',
        severity: 'success',
      })
    } catch (e: any) {
      setSnackbar({
        open: true,
        message: e?.message || 'Failed to delete attachment',
        severity: 'error',
      })
    } finally {
      setDeleteConfirmation({ open: false, attachmentId: null })
    }
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto', p: 0 }}>
      {uploading && <DataLoadingOverlay message="Uploading document..." />}
      <Container maxWidth={false} disableGutters>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Workspace Setup
          </Typography>
          <Box sx={{ mr: 1 }}>
            {/* Save Button */}
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || !name.trim()}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4, pb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {/* Title */}
              <TextField
                label="Workspace Title"
                placeholder="Generated workspace title"
                fullWidth
                value={name}
                onChange={(e) => setName(e.target.value)}
                size="small"
              />
              
            </Box>

            {/* AI Team + Preferred communication style */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="Select existing AI team (optional)"
                size="small"
                fullWidth
                select
                value={aiTeam}
                onChange={(e) => setAiTeam(e.target.value)}
              >
                <MenuItem value="">None</MenuItem>
                <MenuItem value="team-a">Customer Retention Team</MenuItem>
                <MenuItem value="team-b">Cost Optimization Team</MenuItem>
              </TextField>

              <TextField
                label="Preferred Communication Style"
                size="small"
                fullWidth
                select
                value={communicationStyle}
                onChange={(e) => setCommunicationStyle(e.target.value)}
              >
                <MenuItem value="">Not set</MenuItem>
                <MenuItem value="concise">Concise & bullet points</MenuItem>
                <MenuItem value="narrative">Narrative & context first</MenuItem>
              </TextField>
            </Box>

            {/* Context Documents */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h5" sx={{ fontWeight: 600 }}>
                  Documents
                </Typography>
                
                {/* Upload btn */}
                <Box sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    onChange={handleFileSelect}
                    accept="*/*"
                  />
                  <Tooltip title="Upload Documents">
                    <IconButton
                      size="small"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                      color="primary"
                      sx={{ 
                        bgcolor: 'action.hover',
                        '&:hover': { bgcolor: 'action.selected' }
                      }}
                    >
                      <AttachFileRoundedIcon sx={{ fontSize: 20 }} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              {loadingAttachments ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : attachments.length === 0 ? (
                <Paper 
                  variant="outlined" 
                  sx={{ 
                    p: 3, 
                    textAlign: 'center', 
                    bgcolor: 'background.default',
                    borderStyle: 'dashed',
                    color: 'text.secondary'
                  }}
                >
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    No documents uploaded yet.
                  </Typography>
                  <Typography variant="body2">
                    Uploaded documents will be available in your workspace.
                  </Typography>
                </Paper>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {attachments.map((att) => (
                    <Paper
                      key={att.scratchpadAttachmentId}
                      variant="outlined"
                      sx={{
                        p: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1.5,
                        width: '40%',
                      }}
                    >
                      <Document size={20} />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" noWrap title={att.title || att.uri} sx={{ fontWeight: 600 }}>
                          {att.title || 'Untitled'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {new Date(att.createdOn).toLocaleDateString()}
                        </Typography>
                      </Box>
                      <IconButton
                        size="small"
                        className="delete-btn"
                        onClick={() => handleDeleteAttachment(att.scratchpadAttachmentId)}
                        sx={{ 
                          color: 'error.main'
                        }}
                      >
                        <TrashCan size={20} />
                      </IconButton>
                    </Paper>
                  ))}
                </Box>
              )}
            </Box>

            {/* Intent 1-pager (editable) */}
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
                  Workspace Intent
                </Typography>
                {isEditingIntent ? (
                  <Box sx={{ mr: 1 }}>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setIsEditingIntent(false)}
                    >
                      Done
                    </Button>
                  </Box>
                ) : intent ? (
                  <Tooltip title="Edit intent">
                    <IconButton
                      size="small"
                      color="primary"
                      sx={{ 
                        bgcolor: 'action.hover',
                        '&:hover': { bgcolor: 'action.selected' }
                      }}
                      onClick={() => setIsEditingIntent(true)}
                    >
                      <Edit size={20} />
                    </IconButton>
                  </Tooltip>
                ) : null}
              </Box>
              {isEditingIntent ? (
                <Box
                  sx={{
                    '& .w-md-editor': {
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                    },
                    '& .w-md-editor-text': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                      fontFamily: theme.typography.fontFamily,
                      fontSize: '0.875rem',
                    },
                    '& .w-md-editor-text-textarea': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                    },
                    '& .w-md-editor-text-pre': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                    },
                    '& .w-md-editor-preview': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                      '& p': { m: 0, mb: 1 },
                      '& ul, & ol': { pl: 3, mb: 1 },
                      '& li': { mb: 0.5 },
                      '& pre': {
                        p: 1.5,
                        borderRadius: 1,
                        overflow: 'auto',
                        bgcolor: 'action.hover',
                        border: '1px solid',
                        borderColor: 'divider',
                        mb: 1,
                      },
                      '& code': {
                        bgcolor: 'action.hover',
                        px: 0.5,
                        py: 0.25,
                        borderRadius: 0.5,
                        border: '1px solid',
                        borderColor: 'divider',
                        fontSize: '0.875rem',
                      },
                      '& h1, & h2, & h3, & h4, & h5, & h6': {
                        mt: 2,
                        mb: 1,
                        fontWeight: 700,
                        '&:first-of-type': { mt: 0 },
                      },
                      '& h1': { fontSize: '1.5rem' },
                      '& h2': { fontSize: '1.25rem' },
                      '& h3': { fontSize: '1.125rem' },
                      '& strong, & b': {
                        fontWeight: 700,
                      },
                      '& em, & i': {
                        fontStyle: 'italic',
                      },
                      '& a': {
                        color: 'primary.main',
                        textDecoration: 'underline',
                      },
                    },
                    '& .w-md-editor-toolbar': {
                      bgcolor: 'action.hover',
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                    },
                    '& .w-md-editor-toolbar button': {
                      color: 'text.secondary',
                      '&:hover': {
                        bgcolor: 'action.selected',
                      },
                    },
                  }}
                >
                  <MDEditor
                    value={intent}
                    onChange={(value) => {
                      setIntent(value || '')
                      setIsEditingIntent(true)
                    }}
                    preview="live"
                    visibleDragbar={false}
                    data-color-mode={theme.palette.mode}
                    height={400}
                    textareaProps={{
                      placeholder: 'Describe the intent of this workspace.',
                      onFocus: () => setIsEditingIntent(true),
                      style: {
                        fontSize: '0.875rem',
                        fontFamily: theme.typography.fontFamily,
                      },
                    }}
                  />
                </Box>
              ) : intent ? (
                <Paper
                  sx={{
                    p: 2,
                    minHeight: 200,
                    bgcolor: 'background.paper',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    '& p': { m: 0, mb: 1 },
                    '& ul, & ol': { pl: 3, mb: 1 },
                    '& li': { mb: 0.5 },
                    '& pre': {
                      p: 1.5,
                      borderRadius: 1,
                      overflow: 'auto',
                      bgcolor: 'action.hover',
                      border: '1px solid',
                      borderColor: 'divider',
                      mb: 1,
                    },
                    '& code': {
                      bgcolor: 'action.hover',
                      px: 0.5,
                      py: 0.25,
                      borderRadius: 0.5,
                      border: '1px solid',
                      borderColor: 'divider',
                      fontSize: '0.875rem',
                    },
                    '& h1, & h2, & h3, & h4, & h5, & h6': {
                      mt: 2,
                      mb: 1,
                      fontWeight: 700,
                      '&:first-of-type': { mt: 0 },
                    },
                    '& h1': { fontSize: '1.5rem' },
                    '& h2': { fontSize: '1.25rem' },
                    '& h3': { fontSize: '1.125rem' },
                    '& strong, & b': {
                      fontWeight: 700,
                    },
                    '& em, & i': {
                      fontStyle: 'italic',
                    },
                    '& a': {
                      color: 'primary.main',
                      textDecoration: 'underline',
                    },
                  }}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[
                      rehypeRaw,
                      [
                        rehypeSanitize,
                        {
                          tagNames: [
                            'strong',
                            'em',
                            'b',
                            'i',
                            'p',
                            'h1',
                            'h2',
                            'h3',
                            'h4',
                            'h5',
                            'h6',
                            'ul',
                            'ol',
                            'li',
                            'code',
                            'pre',
                            'a',
                          ],
                        },
                      ],
                    ]}
                  >
                    {intent}
                  </ReactMarkdown>
                </Paper>
              ) : (
                <Box
                  sx={{
                    '& .w-md-editor': {
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                    },
                    '& .w-md-editor-text': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                      fontFamily: theme.typography.fontFamily,
                      fontSize: '0.875rem',
                    },
                    '& .w-md-editor-text-textarea': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                    },
                    '& .w-md-editor-text-pre': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                    },
                    '& .w-md-editor-preview': {
                      bgcolor: 'background.paper',
                      color: 'text.primary',
                      '& p': { m: 0, mb: 1 },
                      '& ul, & ol': { pl: 3, mb: 1 },
                      '& li': { mb: 0.5 },
                      '& pre': {
                        p: 1.5,
                        borderRadius: 1,
                        overflow: 'auto',
                        bgcolor: 'action.hover',
                        border: '1px solid',
                        borderColor: 'divider',
                        mb: 1,
                      },
                      '& code': {
                        bgcolor: 'action.hover',
                        px: 0.5,
                        py: 0.25,
                        borderRadius: 0.5,
                        border: '1px solid',
                        borderColor: 'divider',
                        fontSize: '0.875rem',
                      },
                      '& h1, & h2, & h3, & h4, & h5, & h6': {
                        mt: 2,
                        mb: 1,
                        fontWeight: 700,
                        '&:first-of-type': { mt: 0 },
                      },
                      '& h1': { fontSize: '1.5rem' },
                      '& h2': { fontSize: '1.25rem' },
                      '& h3': { fontSize: '1.125rem' },
                      '& strong, & b': {
                        fontWeight: 700,
                      },
                      '& em, & i': {
                        fontStyle: 'italic',
                      },
                      '& a': {
                        color: 'primary.main',
                        textDecoration: 'underline',
                      },
                    },
                    '& .w-md-editor-toolbar': {
                      bgcolor: 'action.hover',
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                    },
                    '& .w-md-editor-toolbar button': {
                      color: 'text.secondary',
                      '&:hover': {
                        bgcolor: 'action.selected',
                      },
                    },
                  }}
                >
                  <MDEditor
                    value={intent}
                    onChange={(value) => {
                      setIntent(value || '')
                      setIsEditingIntent(true)
                    }}
                    preview="live"
                    visibleDragbar={false}
                    data-color-mode={theme.palette.mode}
                    height={400}
                    textareaProps={{
                      placeholder: 'Describe the intent of this workspace.',
                      onFocus: () => setIsEditingIntent(true),
                      style: {
                        fontSize: '0.875rem',
                        fontFamily: theme.typography.fontFamily,
                      },
                    }}
                  />
                </Box>
              )}
            </Box>

        </Box>
      </Container>

      <Dialog
        open={deleteConfirmation.open}
        onClose={() => setDeleteConfirmation({ open: false, attachmentId: null })}
      >
        <DialogTitle>Delete Document?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to remove this document? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ mb: 2, mr: 2 }}>
          <Button 
            variant="outline"
            size="sm"
            onClick={() => setDeleteConfirmation({ open: false, attachmentId: null })}
          >
            Cancel
          </Button>
          <Button 
            onClick={confirmDeleteAttachment}
            color="error"
            size="sm"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

