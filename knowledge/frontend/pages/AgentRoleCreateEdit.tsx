import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Box,
  Alert,
  CircularProgress,
  TextField,
  Typography,
  Paper,
  Stack,
  FormControl,
  FormLabel,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  InputAdornment,
  OutlinedInput,
  Checkbox,
} from '@mui/material'
import { ArrowLeft } from '@carbon/icons-react'
import ContentCopy from '@mui/icons-material/ContentCopy'
import DeleteOutline from '@mui/icons-material/DeleteOutline'
import Button from '../components/common/Button'
import {
  fetchAgentRoleById,
  createAgentRole,
  updateAgentRole,
  setAgentRoleIntents,
  generateAgentRoleAccessKey,
  revokeAgentRoleAccessKey,
  getTenantId,
  fetchOntologies,
  fetchIntents,
  type AgentRoleDetail,
  type AgentRoleAccessKey,
  type GenerateAgentRoleAccessKeyResult,
} from '../services/graphql'
import type { Ontology } from '../services/graphql'
import type { Intent } from '../services/graphql'
import { formatDateTime } from '../utils/formatUtils'

export default function AgentRoleCreateEdit() {
  const navigate = useNavigate()
  const { agentRoleId } = useParams<{ agentRoleId?: string }>()
  const isCreate = !agentRoleId || agentRoleId === 'create'

  const [loading, setLoading] = useState(!isCreate)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [readOntologyId, setReadOntologyId] = useState<string>('')
  const [writeOntologyId, setWriteOntologyId] = useState<string>('')
  const [selectedIntentIds, setSelectedIntentIds] = useState<Set<string>>(new Set())

  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [intents, setIntents] = useState<Intent[]>([])
  const [role, setRole] = useState<AgentRoleDetail | null>(null)

  // When createAgentRole succeeds but setAgentRoleIntents fails, we keep the new ID here
  // so a retry only updates intents (and basic fields) instead of creating a duplicate role.
  const pendingCreatedRoleIdRef = useRef<string | null>(null)

  // Generate key modal
  const [generateModalOpen, setGenerateModalOpen] = useState(false)
  const [generateName, setGenerateName] = useState('')
  const [generateExpiresAt, setGenerateExpiresAt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generatedResult, setGeneratedResult] = useState<GenerateAgentRoleAccessKeyResult | null>(null)
  const [secretCopied, setSecretCopied] = useState(false)

  // Revoke key
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false)
  const [keyToRevoke, setKeyToRevoke] = useState<AgentRoleAccessKey | null>(null)
  const [revoking, setRevoking] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [ontList, intentsList] = await Promise.all([fetchOntologies(), fetchIntents()])
        if (!active) return
        setOntologies(ontList)
        setIntents(intentsList)
      } catch {
        if (!active) return
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (isCreate) return
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAgentRoleById(agentRoleId!)
        if (!active) return
        if (!data) {
          setError('Agent role not found')
          setLoading(false)
          return
        }
        setRole(data)
        setName(data.name)
        setDescription(data.description ?? '')
        setReadOntologyId(data.readOntologyId ?? '')
        setWriteOntologyId(data.writeOntologyId ?? '')
        setSelectedIntentIds(new Set(data.intents.map((i) => i.intentId)))
      } catch (e: unknown) {
        if (!active) return
        setError(e instanceof Error ? e.message : 'Failed to load agent role')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [agentRoleId, isCreate])

  const handleSave = useCallback(async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const tenantId = getTenantId()
      if (!tenantId) {
        setError('Tenant ID is required')
        setSaving(false)
        return
      }

      const readId = readOntologyId.trim() || null
      const writeId = writeOntologyId.trim() || null
      const intentIds = Array.from(selectedIntentIds)

      if (isCreate) {
        const existingId = pendingCreatedRoleIdRef.current
        if (existingId) {
          // Role was already created in a previous attempt; only update and set intents.
          await updateAgentRole({
            agentRoleId: existingId,
            name: name.trim(),
            description: description.trim() || null,
            readOntologyId: readId,
            writeOntologyId: writeId,
          })
          await setAgentRoleIntents(existingId, intentIds)
          pendingCreatedRoleIdRef.current = null
          navigate('/agent-roles')
        } else {
          const newId = await createAgentRole({
            tenantId,
            name: name.trim(),
            description: description.trim() || null,
            readOntologyId: readId,
            writeOntologyId: writeId,
          })
          pendingCreatedRoleIdRef.current = newId
          await setAgentRoleIntents(newId, intentIds)
          pendingCreatedRoleIdRef.current = null
          navigate('/agent-roles')
        }
      } else {
        await updateAgentRole({
          agentRoleId: agentRoleId!,
          name: name.trim(),
          description: description.trim() || null,
          readOntologyId: readId,
          writeOntologyId: writeId,
        })
        await setAgentRoleIntents(agentRoleId!, intentIds)
        navigate('/agent-roles')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save agent role')
      // If the role was created but setAgentRoleIntents failed, switch to edit URL
      // so retry uses update + setIntents and the UI shows edit mode.
      if (isCreate && pendingCreatedRoleIdRef.current) {
        navigate(`/agent-role/${pendingCreatedRoleIdRef.current}`, { replace: true })
      }
    } finally {
      setSaving(false)
    }
  }, [
    isCreate,
    agentRoleId,
    name,
    description,
    readOntologyId,
    writeOntologyId,
    selectedIntentIds,
    navigate,
  ])

  const handleCancel = useCallback(() => navigate('/agent-roles'), [navigate])

  const toggleIntent = useCallback((intentId: string) => {
    setSelectedIntentIds((prev) => {
      const next = new Set(prev)
      if (next.has(intentId)) next.delete(intentId)
      else next.add(intentId)
      return next
    })
  }, [])

  const openGenerateModal = useCallback(() => {
    setGenerateName('')
    setGenerateExpiresAt('')
    setGeneratedResult(null)
    setSecretCopied(false)
    setGenerateModalOpen(true)
  }, [])

  const handleGenerateSubmit = useCallback(async () => {
    if (!agentRoleId) return
    setGenerating(true)
    setError(null)
    try {
      const result = await generateAgentRoleAccessKey(
        agentRoleId,
        generateName.trim() || null,
        generateExpiresAt.trim() || null
      )
      setGeneratedResult(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to generate key')
    } finally {
      setGenerating(false)
    }
  }, [agentRoleId, generateName, generateExpiresAt])

  const handleCopySecret = useCallback(() => {
    if (!generatedResult?.secretKey) return
    void navigator.clipboard.writeText(generatedResult.secretKey)
    setSecretCopied(true)
  }, [generatedResult])

  const handleCloseGenerateModal = useCallback(() => {
    setGenerateModalOpen(false)
    setGeneratedResult(null)
    if (role && agentRoleId) {
      fetchAgentRoleById(agentRoleId).then((r) => r && setRole(r))
    }
  }, [role, agentRoleId])

  const openRevokeDialog = useCallback((key: AgentRoleAccessKey) => {
    setKeyToRevoke(key)
    setRevokeDialogOpen(true)
  }, [])

  const handleRevokeConfirm = useCallback(async () => {
    if (!keyToRevoke) return
    setRevoking(true)
    try {
      await revokeAgentRoleAccessKey(keyToRevoke.accessKeyId)
      const updated = await fetchAgentRoleById(agentRoleId!)
      if (updated) setRole(updated)
      setRevokeDialogOpen(false)
      setKeyToRevoke(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to revoke key')
    } finally {
      setRevoking(false)
    }
  }, [keyToRevoke, agentRoleId])

  const handleRevokeCancel = useCallback(() => {
    setRevokeDialogOpen(false)
    setKeyToRevoke(null)
  }, [])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading agent role...
        </Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto', p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button variant="outline" onClick={handleCancel} sx={{ minWidth: 0, p: 1 }} aria-label="Back to agent roles list">
          <ArrowLeft size={20} />
        </Button>
        <Typography variant="h4" fontWeight={700}>
          {isCreate ? 'Create Agent Role' : 'Edit Agent Role'}
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack spacing={4}>
        {/* Basic info */}
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
            Basic info
          </Typography>
          <Stack spacing={2}>
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              fullWidth
              placeholder="e.g. Integration Agent"
            />
            <TextField
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              fullWidth
              multiline
              minRows={2}
            />
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
              <FormControl fullWidth>
                <InputLabel id="read-ontology-label">Read ontology</InputLabel>
                <Select
                  labelId="read-ontology-label"
                  value={readOntologyId}
                  label="Read ontology"
                  onChange={(e) => setReadOntologyId(e.target.value)}
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
              <FormControl fullWidth>
                <InputLabel id="write-ontology-label">Write ontology</InputLabel>
                <Select
                  labelId="write-ontology-label"
                  value={writeOntologyId}
                  label="Write ontology"
                  onChange={(e) => setWriteOntologyId(e.target.value)}
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
            </Box>
          </Stack>
        </Paper>

        {/* Allowed intents + Access keys in one row */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: isCreate ? '1fr' : '1fr 1fr' },
            gap: 2,
          }}
        >
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              borderRadius: 2,
              ...(isCreate && { gridColumn: { md: '1 / -1' } }),
            }}
          >
            <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
              Allowed intents
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Select which intents this role is allowed to execute.
            </Typography>
            <Paper variant="outlined" sx={{ maxHeight: 280, overflow: 'auto' }}>
              <List dense>
                {intents.length === 0 ? (
                  <ListItem>
                    <ListItemText primary="No intents available." primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }} />
                  </ListItem>
                ) : (
                  intents.map((intent) => (
                    <ListItem
                      key={intent.intentId}
                      dense
                      sx={{ cursor: 'pointer' }}
                      onClick={() => toggleIntent(intent.intentId)}
                    >
                      <Checkbox
                        checked={selectedIntentIds.has(intent.intentId)}
                        disableRipple
                        sx={{ mr: 1 }}
                        aria-label={`Toggle ${intent.opId}`}
                      />
                      <ListItemText
                        primary={intent.opId}
                        secondary={intent.intent}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItem>
                  ))
                )}
              </List>
            </Paper>
          </Paper>

          {/* Access keys (edit only) */}
          {!isCreate && (
            <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
              <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
                Access keys
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Keys allow external agents to authenticate as this role. The secret is shown only once when generated.
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Button variant="primary" size="sm" onClick={openGenerateModal}>
                  Generate key
                </Button>
              </Box>
              {role && role.accessKeys.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No access keys yet. Generate one to get a secret you can store securely.
                </Typography>
              ) : (
                <List dense disablePadding>
                  {role?.accessKeys.map((key) => (
                    <ListItem
                      key={key.accessKeyId}
                      secondaryAction={
                        <IconButton
                          size="small"
                          onClick={() => openRevokeDialog(key)}
                          sx={{ color: 'text.secondary', '&:hover': { color: 'error.main' } }}
                          aria-label="Revoke key"
                          title="Revoke"
                        >
                          <DeleteOutline fontSize="small" />
                        </IconButton>
                      }
                    >
                      <ListItemText
                        primary={key.keyPrefix}
                        secondary={
                          <>
                            {key.name && <span>{key.name} · </span>}
                            Created {formatDateTime(key.createdOn)}
                            {key.expiresAt && ` · Expires ${formatDateTime(key.expiresAt)}`}
                          </>
                        }
                        primaryTypographyProps={{ variant: 'body2', fontFamily: 'monospace' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Paper>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={handleCancel} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </Box>
      </Stack>

      {/* Generate key modal */}
      <Dialog open={generateModalOpen} onClose={handleCloseGenerateModal} maxWidth="sm" fullWidth>
        <DialogTitle>{generatedResult ? 'Key generated' : 'Generate access key'}</DialogTitle>
        <DialogContent>
          {!generatedResult ? (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                label="Name (optional)"
                value={generateName}
                onChange={(e) => setGenerateName(e.target.value)}
                fullWidth
                placeholder="e.g. Production API key"
              />
              <TextField
                label="Expires at (optional)"
                type="datetime-local"
                value={generateExpiresAt}
                onChange={(e) => setGenerateExpiresAt(e.target.value)}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Stack>
          ) : (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Alert severity="warning">
                Store this secret securely. It will not be shown again.
              </Alert>
              <FormControl fullWidth variant="outlined" size="small">
                <FormLabel sx={{ mb: 0.5 }}>Secret key</FormLabel>
                <OutlinedInput
                  readOnly
                  value={generatedResult.secretKey}
                  endAdornment={
                    <InputAdornment position="end">
                      <IconButton onClick={handleCopySecret} size="small" aria-label="Copy secret">
                        <ContentCopy fontSize="small" />
                      </IconButton>
                    </InputAdornment>
                  }
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
                {secretCopied && (
                  <Typography variant="caption" color="success.main" sx={{ mt: 0.5 }}>
                    Copied to clipboard.
                  </Typography>
                )}
              </FormControl>
              <Typography variant="body2" color="text.secondary">
                Key prefix: <code>{generatedResult.keyPrefix}</code> · ID: <code>{generatedResult.accessKeyId}</code>
              </Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {generatedResult ? (
            <Button variant="primary" onClick={handleCloseGenerateModal}>
              I have stored this
            </Button>
          ) : (
            <>
              <Button variant="secondary" onClick={handleCloseGenerateModal} disabled={generating}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleGenerateSubmit} disabled={generating}>
                {generating ? 'Generating...' : 'Generate'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* Revoke key dialog */}
      <Dialog open={revokeDialogOpen} onClose={handleRevokeCancel}>
        <DialogTitle>Revoke access key?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to revoke the key &quot;{keyToRevoke?.keyPrefix}&quot;? It will stop working
            immediately and cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button variant="secondary" onClick={handleRevokeCancel} disabled={revoking}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleRevokeConfirm} disabled={revoking}>
            {revoking ? 'Revoking...' : 'Revoke'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
