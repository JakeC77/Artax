import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  Box,
  Alert,
  CircularProgress,
  Button as MUIButton,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Paper,
  List,
  ListItemButton,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Collapse,
} from '@mui/material'
import { Delete, CloudUpload } from '@mui/icons-material'
import ChatDock from '../components/workspace/ChatDock'
import { useChatStream } from '../components/workspace/chat/useChatStream'
import {
  appendScenarioRunLog,
  getTenantId,
  fetchOntologies,
  createDataLoadingAttachment,
  dataLoadingAttachments,
  dataLoadingAttachmentById,
  startDataLoadingPipeline,
  deleteDataLoadingAttachment,
  type Ontology,
  type DataLoadingAttachment,
} from '../services/graphql'
import { useWorkspace } from '../contexts/WorkspaceContext'
import CsvAnalysisBlock, { type CsvAnalysisData } from '../components/workspace/chat/CsvAnalysisBlock'

export default function OntologyDataLoader() {
  const navigate = useNavigate()
  const { attachmentId: attachmentIdParam } = useParams<{ attachmentId?: string }>()
  const [searchParams] = useSearchParams()
  const { currentWorkspace } = useWorkspace()

  const [selectedOntologyId, setSelectedOntologyId] = useState<string>('')
  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [attachments, setAttachments] = useState<DataLoadingAttachment[]>([])
  const [selectedAttachmentId, setSelectedAttachmentId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [isLoadingOntologies, setIsLoadingOntologies] = useState(false)
  const [isLoadingAttachments, setIsLoadingAttachments] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false)
  const [isDeleting, setIsDeleting] = useState<string | null>(null)
  const [csvAnalysisByAttachment, setCsvAnalysisByAttachment] = useState<Record<string, CsvAnalysisData>>({})
  const [expandedAttachmentId, setExpandedAttachmentId] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const activeStreamRunIdRef = useRef<string | null>(null)
  const dropRef = useRef<HTMLDivElement>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)

  // Load ontologies on mount
  useEffect(() => {
    let active = true
    async function loadOntologies() {
      setIsLoadingOntologies(true)
      try {
        const data = await fetchOntologies()
        if (!active) return
        setOntologies(data)
        
        // Check for ontologyId in URL search params
        const ontologyIdParam = searchParams.get('ontologyId')
        
        // If we have an attachmentId param, load that attachment first
        if (attachmentIdParam) {
          const attachment = await dataLoadingAttachmentById(attachmentIdParam)
          if (attachment && active) {
            setSelectedOntologyId(attachment.ontologyId)
            setSelectedAttachmentId(attachment.attachmentId)
            if (attachment.runId) {
              setRunId(attachment.runId)
            }
          }
        } else if (ontologyIdParam && active) {
          // If we have an ontologyId in query params, set it
          const ontology = data.find((o) => o.ontologyId === ontologyIdParam)
          if (ontology) {
            setSelectedOntologyId(ontologyIdParam)
          }
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load ontologies')
      } finally {
        if (active) setIsLoadingOntologies(false)
        if (active) setIsInitializing(false)
      }
    }
    loadOntologies()
    return () => {
      active = false
    }
  }, [attachmentIdParam, searchParams])

  // Load attachments when ontology changes
  useEffect(() => {
    if (!selectedOntologyId) {
      setAttachments([])
      return
    }

    let active = true
    async function loadAttachments() {
      setIsLoadingAttachments(true)
      try {
        const tenantId = getTenantId()
        const data = await dataLoadingAttachments(tenantId || undefined, selectedOntologyId)
        if (!active) return
        setAttachments(data)
      } catch (e: any) {
        if (!active) return
        console.error('[OntologyDataLoader] Failed to load attachments:', e)
        setError(e?.message || 'Failed to load attachments')
      } finally {
        if (active) setIsLoadingAttachments(false)
      }
    }
    loadAttachments()
    return () => {
      active = false
    }
  }, [selectedOntologyId])

  // Handle file selection
  const handleFileSelect = useCallback(
    async (file: File) => {
      if (!selectedOntologyId) {
        setError('Please select an ontology first')
        return
      }

      // Validate CSV
      if (!file.name.toLowerCase().endsWith('.csv')) {
        setError('Please upload a CSV file')
        return
      }

      const tenantId = getTenantId()
      if (!tenantId) {
        setError('No tenant ID found')
        return
      }

      try {
        setIsUploading(true)
        setError(null)
        const attachmentId = await createDataLoadingAttachment(tenantId, selectedOntologyId, file, file.name)
        // Reload attachments
        const data = await dataLoadingAttachments(tenantId, selectedOntologyId)
        setAttachments(data)
        setSelectedAttachmentId(attachmentId)
      } catch (e: any) {
        console.error('[OntologyDataLoader] Failed to upload file:', e)
        setError(e?.message || 'Failed to upload file')
      } finally {
        setIsUploading(false)
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    },
    [selectedOntologyId]
  )

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        handleFileSelect(file)
      }
    },
    [handleFileSelect]
  )

  // Drag and drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingOver(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDraggingOver(false)

      const file = e.dataTransfer.files?.[0]
      if (file) {
        handleFileSelect(file)
      }
    },
    [handleFileSelect]
  )

  // Start data loading workflow
  const handleStartWorkflow = useCallback(async () => {
    if (!selectedAttachmentId || !currentWorkspace?.workspaceId) {
      setError('Please select an attachment and ensure a workspace is active')
      return
    }

    try {
      setIsStartingWorkflow(true)
      setError(null)
      const result = await startDataLoadingPipeline(selectedAttachmentId, currentWorkspace.workspaceId)

      if (!result.success) {
        throw new Error('Failed to start data loading pipeline')
      }

      if (result.runId) {
        setRunId(result.runId)
        // Update attachment in list
        const tenantId = getTenantId()
        const data = await dataLoadingAttachments(tenantId || undefined, selectedOntologyId)
        setAttachments(data)
      }
    } catch (e: any) {
      console.error('[OntologyDataLoader] Failed to start workflow:', e)
      setError(e?.message || 'Failed to start data loading workflow')
    } finally {
      setIsStartingWorkflow(false)
    }
  }, [selectedAttachmentId, currentWorkspace?.workspaceId, selectedOntologyId])

  // Delete attachment
  const handleDeleteAttachment = useCallback(
    async (attachmentId: string) => {
      if (!confirm('Are you sure you want to delete this attachment?')) {
        return
      }

      try {
        setIsDeleting(attachmentId)
        setError(null)
        await deleteDataLoadingAttachment(attachmentId)
        // Reload attachments
        const tenantId = getTenantId()
        const data = await dataLoadingAttachments(tenantId || undefined, selectedOntologyId)
        setAttachments(data)
        if (selectedAttachmentId === attachmentId) {
          setSelectedAttachmentId(null)
          setRunId('')
        }
      } catch (e: any) {
        console.error('[OntologyDataLoader] Failed to delete attachment:', e)
        setError(e?.message || 'Failed to delete attachment')
      } finally {
        setIsDeleting(null)
      }
    },
    [selectedOntologyId, selectedAttachmentId]
  )

  // Use chat stream hook for SSE connection
  const chatStream = useChatStream({
    workspaceId: currentWorkspace?.workspaceId,
    currentWorkspace: currentWorkspace || undefined,
    initialMessages: [],
  })

  // Listen for CSV analysis events and store them by attachment (via runId mapping)
  useEffect(() => {
    const messages = chatStream.messages
    // Create a map of runId to attachmentId from current attachments
    const runIdToAttachmentId = new Map<string, string>()
    attachments.forEach((att) => {
      if (att.runId) {
        runIdToAttachmentId.set(att.runId, att.attachmentId)
      }
    })

    // Process messages to find CSV analysis
    // When a csv_analyzed event comes through, it's associated with the current runId
    // We map that runId to the attachmentId
    messages.forEach((message) => {
      if (message.csvAnalysis && runId && runIdToAttachmentId.has(runId)) {
        const attachmentId = runIdToAttachmentId.get(runId)!
        setCsvAnalysisByAttachment((prev) => {
          // Only update if we don't already have analysis for this attachment
          if (prev[attachmentId]) return prev
          return {
            ...prev,
            [attachmentId]: message.csvAnalysis!,
          }
        })
      }
    })
  }, [chatStream.messages, runId, attachments])

  // Connect to SSE stream when runId is available
  useEffect(() => {
    const tenantId = getTenantId()
    if (runId && tenantId && runId !== activeStreamRunIdRef.current) {
      activeStreamRunIdRef.current = runId
      chatStream.startStream(runId, tenantId)
    }
    // Cleanup on unmount
    return () => {
      if (activeStreamRunIdRef.current) {
        chatStream.stopStream()
        activeStreamRunIdRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  // Handle chat message submission
  const handleChatSubmit = useCallback(
    async (message: string) => {
      if (!runId || !message.trim()) return

      try {
        // Create user_message event
        const userMessageEvent = {
          event_type: 'user_message',
          message: message,
        }

        // Append to scenario run log (this sends the message to the workflow)
        await appendScenarioRunLog(runId, JSON.stringify(userMessageEvent))
      } catch (e: any) {
        console.error('[OntologyDataLoader] Failed to send message:', e)
        setError(e?.message || 'Failed to send message')
      }
    },
    [runId]
  )

  // Get selected attachment
  const selectedAttachment = attachments.find((a) => a.attachmentId === selectedAttachmentId)

  // Get status color for chip
  const getStatusColor = (status: string | null): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    if (!status) return 'default'
    switch (status.toLowerCase()) {
      case 'completed':
        return 'success'
      case 'running':
        return 'primary'
      case 'failed':
        return 'error'
      case 'uploaded':
        return 'default'
      default:
        return 'default'
    }
  }

  if (isInitializing) {
    return (
      <Box
        sx={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="h6">Loading data loader...</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', overflow: 'hidden', position: 'relative' }}>
      {/* Left: File Management */}
      <Box
        sx={{
          width: { xs: 0, sm: '65%' },
          display: { xs: 'none', sm: 'flex' },
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          sx={{
            p: 2,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="h6" fontWeight={600}>
            Ontology Data Loader
          </Typography>
          <MUIButton variant="outlined" onClick={() => navigate('/knowledge')}>
            Back to Knowledge
          </MUIButton>
        </Box>

        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2, overflow: 'auto', flex: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* Ontology Selector */}
          <FormControl fullWidth>
            <InputLabel id="ontology-select-label">Select Ontology</InputLabel>
            <Select
              labelId="ontology-select-label"
              id="ontology-select"
              value={selectedOntologyId}
              label="Select Ontology"
              onChange={(e) => {
                setSelectedOntologyId(e.target.value)
                setSelectedAttachmentId(null)
                setRunId('')
              }}
              disabled={isLoadingOntologies}
            >
              {isLoadingOntologies ? (
                <MenuItem disabled>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Loading...
                </MenuItem>
              ) : ontologies.length === 0 ? (
                <MenuItem disabled>No ontologies available</MenuItem>
              ) : (
                ontologies.map((ontology) => (
                  <MenuItem key={ontology.ontologyId} value={ontology.ontologyId}>
                    {ontology.name} ({ontology.semVer})
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>

          {/* File Upload Area */}
          {selectedOntologyId && (
            <>
              <Paper
                ref={dropRef}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                sx={{
                  border: '2px dashed',
                  borderColor: isDraggingOver ? 'primary.main' : 'divider',
                  borderRadius: 1,
                  p: 3,
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'border-color 0.2s',
                  bgcolor: isDraggingOver ? 'action.hover' : 'background.paper',
                }}
              >
                <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body1" sx={{ mb: 0.5 }}>
                  Drag and drop CSV file here
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  or click to browse
                </Typography>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={handleFileInputChange}
                  disabled={isUploading}
                />
              </Paper>

              {isUploading && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2">Uploading...</Typography>
                </Box>
              )}

              {/* Attachments List */}
              <Box>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
                  Uploaded Files
                </Typography>
                {isLoadingAttachments ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <CircularProgress size={24} />
                  </Box>
                ) : attachments.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No files uploaded yet
                  </Typography>
                ) : (
                  <List>
                    {attachments.map((attachment) => {
                      const csvAnalysis = csvAnalysisByAttachment[attachment.attachmentId]
                      const isExpanded = expandedAttachmentId === attachment.attachmentId
                      const hasAnalysis = !!csvAnalysis

                      return (
                        <Box key={attachment.attachmentId} sx={{ mb: 1 }}>
                          <ListItemButton
                            selected={selectedAttachmentId === attachment.attachmentId}
                            onClick={() => {
                              setSelectedAttachmentId(attachment.attachmentId)
                              if (attachment.runId) {
                                setRunId(attachment.runId)
                              } else {
                                setRunId('')
                              }
                              if (hasAnalysis) {
                                setExpandedAttachmentId(isExpanded ? null : attachment.attachmentId)
                              }
                            }}
                            sx={{
                              border: '1px solid',
                              borderColor: 'divider',
                              borderRadius: 1,
                              '&.Mui-selected': {
                                bgcolor: 'primary.light',
                                '&:hover': {
                                  bgcolor: 'primary.light',
                                },
                              },
                            }}
                          >
                            <ListItemText
                              primary={attachment.fileName}
                              secondary={
                                <Box sx={{ display: 'flex', gap: 1, mt: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                                  <Typography variant="caption" color="text.secondary">
                                    {new Date(attachment.createdOn).toLocaleDateString()}
                                  </Typography>
                                  {attachment.status && (
                                    <Chip
                                      label={attachment.status}
                                      size="small"
                                      color={getStatusColor(attachment.status)}
                                    />
                                  )}
                                  {attachment.runId && (
                                    <Chip label="Active Run" size="small" color="primary" variant="outlined" />
                                  )}
                                  {hasAnalysis && (
                                    <Chip
                                      label={`${csvAnalysis.row_count} rows, ${csvAnalysis.columns.length} columns`}
                                      size="small"
                                      color="success"
                                      variant="outlined"
                                    />
                                  )}
                                </Box>
                              }
                            />
                            <ListItemSecondaryAction>
                              {!attachment.runId && (
                                <MUIButton
                                  variant="contained"
                                  size="small"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setSelectedAttachmentId(attachment.attachmentId)
                                    handleStartWorkflow()
                                  }}
                                  disabled={isStartingWorkflow || !currentWorkspace?.workspaceId}
                                >
                                  {isStartingWorkflow && selectedAttachmentId === attachment.attachmentId
                                    ? 'Starting...'
                                    : 'Start Loader'}
                                </MUIButton>
                              )}
                              <IconButton
                                edge="end"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDeleteAttachment(attachment.attachmentId)
                                }}
                                disabled={isDeleting === attachment.attachmentId}
                                sx={{ ml: 1 }}
                              >
                                {isDeleting === attachment.attachmentId ? (
                                  <CircularProgress size={20} />
                                ) : (
                                  <Delete />
                                )}
                              </IconButton>
                            </ListItemSecondaryAction>
                          </ListItemButton>
                          {hasAnalysis && (
                            <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                              <Box sx={{ pl: 2, pr: 2, pb: 2 }}>
                                <CsvAnalysisBlock analysis={csvAnalysis} />
                              </Box>
                            </Collapse>
                          )}
                        </Box>
                      )
                    })}
                  </List>
                )}
              </Box>

              {/* Start Workflow Button for Selected Attachment */}
              {selectedAttachment && selectedAttachment.runId && (
                <Alert severity="info">
                  This attachment has an active run. The chat interface will connect to the existing workflow.
                </Alert>
              )}
            </>
          )}
        </Box>
      </Box>

      {/* Right: Chat Interface */}
      <Box
        sx={{
          width: { xs: '100%', sm: '35%' },
          borderLeft: { xs: 'none', sm: '1px solid' },
          borderColor: { xs: 'transparent', sm: 'divider' },
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          position: 'relative',
        }}
      >
        {runId ? (
          <ChatDock
            open={true}
            onClose={() => navigate('/knowledge')}
            onSubmit={handleChatSubmit}
            setupRunId={runId}
            initialMessages={chatStream.messages}
            initialIsAgentWorking={chatStream.isAgentWorking}
            inputDisabled={chatStream.isAgentWorking || chatStream.isTurnOpen}
            isSetupMode={true}
            fullScreen={true}
          />
        ) : (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: 3,
              textAlign: 'center',
            }}
          >
            <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
              Select an attachment and start the data loader
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Upload a CSV file and click "Start Loader" to begin the data loading workflow.
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  )
}
