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
  FormControl,
  InputLabel,
  Select,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import { useTheme } from '@mui/material/styles'
import { useNavigate, useParams } from 'react-router-dom'
import { Chat, ArrowLeft } from '@carbon/icons-react'
import Button from '../components/common/Button'
import ChatDock from '../components/workspace/ChatDock'
import { DataLoadingOverlay } from '../components/common/DataLoadingOverlay'
import {
  createWorkspace as gqlCreateWorkspace,
  updateWorkspace as gqlUpdateWorkspace,
  fetchWorkspaces,
  fetchWorkspaceById,
  createScratchpadAttachment,
  createScenario,
  triggerWorkflow,
  fetchUsers,
  fetchTenants,
  setTenantId,
  getTenantId,
  listCompanies,
  fetchOntologies,
  type Company,
  type Ontology,
} from '../services/graphql'
import { useWorkspace } from '../contexts/WorkspaceContext'

export default function NewWorkspacePage() {
  const theme = useTheme()
  const navigate = useNavigate()
  const { workspaceId } = useParams()
  const { setCurrentWorkspace, chatOpen, setChatOpen } = useWorkspace()

  const isEdit = Boolean(workspaceId) // For /workspaces/:workspaceId/edit route

  const [loading, setLoading] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [intent, setIntent] = useState('')
  const [visibility, setVisibility] = useState('private')
  const [setupRunId, setSetupRunId] = useState<string | null>(null)
  // Mocks for now
  const [aiTeam, setAiTeam] = useState<string>('')
  const [communicationStyle, setCommunicationStyle] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [isEditingIntent, setIsEditingIntent] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [companyId, setCompanyId] = useState<string>('')
  const [ontologyId, setOntologyId] = useState<string>('')

  // Load workspace data if workspaceId exists (new flow or edit mode)
  useEffect(() => {
    if (!workspaceId) return
    let mounted = true
    async function load() {
      setLoading(true)
      try {
        const ws = await fetchWorkspaceById(workspaceId!)
        if (!mounted) return
        if (ws) {
          setName(ws.name)
          setDescription(ws.description || '')
          setIntent(ws.intent || '')
          setVisibility(ws.visibility || 'private')
          setSetupRunId(ws.setupRunId || null)
          // Auto-open chat if setupRunId exists
          if (ws.setupRunId) {
            setChatOpen(true)
          }
          // In a real app, we'd load AI team / comms style here too
        }
      } catch (e) {
        console.error('Failed to load workspace', e)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [workspaceId, setChatOpen])

  // Load companies and ontologies when in create mode (no workspaceId)
  useEffect(() => {
    if (workspaceId) return
    let mounted = true
    async function load() {
      try {
        const [companiesData, ontologiesData] = await Promise.all([listCompanies(), fetchOntologies()])
        if (!mounted) return
        setCompanies(companiesData)
        setOntologies(ontologiesData)
      } catch (e) {
        console.error('Failed to load companies/ontologies', e)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [workspaceId])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    // Need workspaceId to upload - if we don't have one yet, create workspace first
    let targetWorkspaceId = workspaceId
    if (!targetWorkspaceId) {
      // Create a minimal workspace first if we don't have one
      if (!name.trim()) {
        alert('Please enter a workspace title before uploading documents')
        return
      }
      try {
        setUploading(true)
        targetWorkspaceId = await gqlCreateWorkspace({
          name: name.trim() || 'Untitled Workspace',
          companyId: companyId || null,
          ontologyId: ontologyId || null,
        })
        // Update local state
        const ws = await fetchWorkspaceById(targetWorkspaceId)
        if (ws) {
          setName(ws.name)
          setDescription(ws.description || '')
          setIntent(ws.intent || '')
          setVisibility(ws.visibility || 'private')
          setSetupRunId(ws.setupRunId || null)
        }
      } catch (error: any) {
        alert(error?.message || 'Failed to create workspace for upload')
        setUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
        return
      }
    }
    
    if (!targetWorkspaceId) {
      alert('Unable to determine workspace for upload')
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    
    try {
      setUploading(true)
      const derivedTitle = file.name.replace(/\.[^.]+$/, '')
      await createScratchpadAttachment({
        workspaceId: targetWorkspaceId,
        title: derivedTitle,
        description: null,
        file: file,
      })
      alert('Document uploaded successfully!')
    } catch (error: any) {
      alert(error?.message || 'Failed to upload document')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      alert('Please enter a workspace title')
      return
    }
    try {
      setSaving(true)

      let targetId = workspaceId

      // In new flow (workspaceId exists), always update
      // In old flow (no workspaceId), create new
      if (workspaceId) {
        // New flow: always update existing workspace
        await gqlUpdateWorkspace({
          workspaceId,
          name: name.trim(),
          description: description.trim() || null,
          intent: intent.trim() || null,
          visibility, // keep passing visibility if supported
        })
      } else {
        // Old flow: create new workspace (backward compatibility)
        targetId = await gqlCreateWorkspace({
          name: name.trim(),
          companyId: companyId || null,
          ontologyId: ontologyId || null,
        })

        // Trigger theo workflow for new workspace setup
        if (targetId) {
          let tid = getTenantId() || ''
          if (!tid) {
            const tenants = await fetchTenants()
            if (tenants.length > 0) {
              tid = tenants[0].tenantId
              setTenantId(tid)
            }
          }

          const users = await fetchUsers()
          if (users.length > 0) {
            const createdBy = users[0].userId
            const scenarioName = `Workspace Setup - ${new Date().toISOString()}`
            const scenarioId = await createScenario({ workspaceId: targetId, name: scenarioName, createdBy })
            const { run_id } = await triggerWorkflow({
              tenantId: tid,
              workspaceId: targetId,
              scenarioId,
              inputs: {
                name: name.trim(),
                description: description.trim() || null,
                intent: intent.trim() || null,
              },
              engine: 'ai:theo',
            })
            setSetupRunId(run_id)
            setChatOpen(true)
          }
        }
      }

      // Refresh list and select
      const data = await fetchWorkspaces()
      
      if (targetId) {
        const newWs = data.find((w) => w.workspaceId === targetId)
        if (newWs) {
          setCurrentWorkspace(newWs)
          navigate('/workspace')
          return
        }
      }
      // If we updated, navigate to workspace
      if (workspaceId) {
        const updatedWs = data.find((w) => w.workspaceId === workspaceId)
        if (updatedWs) {
          setCurrentWorkspace(updatedWs)
          navigate('/workspace')
          return
        }
      }
      navigate('/workspaces')

    } catch (e: any) {
      alert(e?.message || `Failed to ${workspaceId ? 'update' : 'create'} workspace`)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', position: 'relative', height: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>
      {saving && <DataLoadingOverlay message={workspaceId ? 'Updating workspace...' : 'Creating workspace...'} />}
      <Box
        sx={{
          flexGrow: 1,
          height: '100%',
          overflowY: 'auto',
          py: 3,
          px: 0,
          mr: { xs: 0, sm: chatOpen ? '360px' : 0, md: chatOpen ? '420px' : 0 },
          transition: theme.transitions.create('margin', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Container maxWidth={false} disableGutters>
          <Box sx={{ px: 4, mb: 2, mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                color: 'text.secondary',
                '&:hover': { color: 'text.primary' }
              }}
              onClick={() => navigate(-1)}
            >
              <ArrowLeft size={16} />
              <Typography variant="body2" sx={{ fontWeight: 700 }}>Go back</Typography>
            </Box>
            <Box>
              {!chatOpen && (
                <Tooltip title="Open chat">
                  <IconButton
                    onClick={() => setChatOpen(true)}
                    sx={{ color: 'secondary.main' }}
                  >
                    <Chat size={24} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
          </Box>

          {/* Header */}
          <Box sx={{ px: 4, mb: 4 }}>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {isEdit ? 'Edit Workspace' : 'New Workspace'}
            </Typography>
          </Box>

          <Box sx={{ px: 4, display: 'flex', gap: 4 }}>
            {/* Left Column: Form */}
            <Box sx={{ flex: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Title */}
              <TextField
                label="Workspace Title"
                placeholder="Generated workspace title"
                fullWidth
                value={name}
                onChange={(e) => setName(e.target.value)}
                size="small"
              />
              
              {/* Description */}
               <TextField
                label="Description"
                placeholder="Short description"
                fullWidth
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                size="small"
              />

              {!workspaceId && (
                <>
                  <FormControl size="small" fullWidth>
                    <InputLabel id="new-workspace-company-label">Company (optional)</InputLabel>
                    <Select
                      labelId="new-workspace-company-label"
                      value={companyId}
                      label="Company (optional)"
                      onChange={(e) => setCompanyId(e.target.value)}
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {companies.map((c) => (
                        <MenuItem key={c.companyId} value={c.companyId}>
                          {c.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" fullWidth>
                    <InputLabel id="new-workspace-ontology-label">Ontology (optional)</InputLabel>
                    <Select
                      labelId="new-workspace-ontology-label"
                      value={ontologyId}
                      label="Ontology (optional)"
                      onChange={(e) => setOntologyId(e.target.value)}
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {ontologies.map((o) => (
                        <MenuItem key={o.ontologyId} value={o.ontologyId}>
                          {o.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </>
              )}

              {/* Upload / Paste */}
              <Box sx={{ display: 'flex', gap: 2 }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                  accept="*/*"
                />
                <Button
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? 'Uploading...' : 'Upload Document'}
                </Button>
                <Button size="sm" variant="outline">
                  Paste Text
                </Button>
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

              {/* Intent 1-pager (editable) */}
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    Workspace Intent (1-pager)
                  </Typography>
                  {isEditingIntent ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setIsEditingIntent(false)}
                    >
                      Done
                    </Button>
                  ) : intent ? (
                    <Tooltip title="Edit intent">
                      <IconButton
                        size="small"
                        onClick={() => setIsEditingIntent(true)}
                        sx={{ color: 'text.secondary' }}
                      >
                        <EditIcon fontSize="small" />
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
                      onChange={(value) => setIntent(value || '')}
                      preview="live"
                      visibleDragbar={false}
                      data-color-mode="light"
                      height={400}
                      textareaProps={{
                        placeholder: 'Describe the intent of this workspace (this view is only editable during workspace creation/editing).',
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
                      data-color-mode="light"
                      height={400}
                      textareaProps={{
                        placeholder: 'Describe the intent of this workspace (this view is only editable during workspace creation/editing).',
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

              {/* Save Button */}
              <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="md"
                  onClick={handleSave}
                  disabled={saving || !name.trim()}
                >
                  {saving 
                    ? (workspaceId ? 'Updating…' : 'Creating…') 
                    : (workspaceId ? 'Update Workspace' : 'Create Workspace')}
                </Button>
              </Box>
            </Box>
          </Box>
        </Container>
      </Box>
      
      <ChatDock
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        workspaceId={workspaceId}
        setupRunId={setupRunId || undefined}
        onSubmit={(value) => {
          // Handle chat submit if needed
          console.log('Chat submit:', value)
        }}
        onIntentUpdated={(intent) => {
          // Update local intent state when Theo sends intent events
          setIntent(intent)
        }}
      />
    </Box>
  )
}
