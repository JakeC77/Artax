import { useState, useCallback } from 'react'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  IconButton,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  DialogContentText,
} from '@mui/material'
import { CloseOutline } from '@carbon/icons-react'
import { alpha, useTheme } from '@mui/material/styles'
import { setOntologyNeo4jConnection, getTenantId, cloneOntology, syncOntologyToSemanticEntities, type SetOntologyNeo4jConnectionInput } from '../../services/graphql'
import Button from '../common/Button'

export type Neo4jSettingsModalProps = {
  open: boolean
  onClose: () => void
  ontologyId: string
  ontologyName: string
  onSuccess?: () => void
  onDelete?: () => void
  /** Called after a successful clone with the new ontology ID (e.g. to refetch list and navigate). */
  onCloneSuccess?: (newOntologyId: string) => void
}

export default function Neo4jSettingsModal({
  open,
  onClose,
  ontologyId,
  ontologyName,
  onSuccess,
  onDelete,
  onCloneSuccess,
}: Neo4jSettingsModalProps) {
  const theme = useTheme()
  const [uri, setUri] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [cloneName, setCloneName] = useState('')
  const [cloning, setCloning] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ entitiesCreated: number; entitiesUpdated: number; fieldsWithRangeUpdated: number } | null>(null)

  // Reset form when modal opens/closes
  const handleClose = useCallback(() => {
    if (!loading && !cloning && !syncing) {
      setUri('')
      setUsername('')
      setPassword('')
      setCloneName('')
      setSyncResult(null)
      setError(null)
      onClose()
    }
  }, [loading, cloning, syncing, onClose])

  const handleSave = useCallback(async () => {
    // Validation
    if (!uri.trim() || !username.trim() || !password.trim()) {
      setError('All fields are required')
      return
    }

    // Basic URI validation
    try {
      new URL(uri)
    } catch {
      setError('Please enter a valid URI (e.g., bolt+s://xxxx.databases.neo4j.io)')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const tenantId = getTenantId()
      if (!tenantId) {
        throw new Error('No tenant ID found')
      }

      const input: SetOntologyNeo4jConnectionInput = {
        uri: uri.trim(),
        username: username.trim(),
        password: password.trim(),
      }

      await setOntologyNeo4jConnection(tenantId, ontologyId, input)
      
      // Reset form and close
      setUri('')
      setUsername('')
      setPassword('')
      setError(null)
      
      if (onSuccess) {
        onSuccess()
      }
      
      onClose()
    } catch (e: any) {
      console.error('[Neo4jSettingsModal] Failed to save settings:', e)
      setError(e?.message || 'Failed to save Neo4j connection settings')
    } finally {
      setLoading(false)
    }
  }, [uri, username, password, ontologyId, onSuccess, onClose])

  const handleDeleteClick = useCallback(() => {
    setDeleteDialogOpen(true)
  }, [])

  const handleDeleteCancel = useCallback(() => {
    setDeleteDialogOpen(false)
  }, [])

  const handleDeleteConfirm = useCallback(async () => {
    if (!onDelete) return

    setDeleting(true)
    try {
      await onDelete()
      setDeleteDialogOpen(false)
      onClose()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete ontology')
    } finally {
      setDeleting(false)
    }
  }, [onDelete, onClose])

  const handleClone = useCallback(async () => {
    const tenantId = getTenantId()
    if (!tenantId) {
      setError('No tenant ID found')
      return
    }
    setCloning(true)
    setError(null)
    try {
      const newId = await cloneOntology({
        sourceOntologyId: ontologyId,
        tenantId,
        name: cloneName.trim() || undefined,
      })
      setCloneName('')
      onClose()
      onCloneSuccess?.(newId)
    } catch (e: any) {
      setError(e?.message || 'Failed to clone ontology')
    } finally {
      setCloning(false)
    }
  }, [ontologyId, cloneName, onClose, onCloneSuccess])

  const handleSyncToSemanticEntities = useCallback(async () => {
    setSyncing(true)
    setError(null)
    setSyncResult(null)
    try {
      const result = await syncOntologyToSemanticEntities(ontologyId)
      setSyncResult(result)
      onSuccess?.()
    } catch (e: any) {
      setError(e?.message || 'Failed to sync ontology to semantic entities')
    } finally {
      setSyncing(false)
    }
  }, [ontologyId, onSuccess])

  const isValid = uri.trim() && username.trim() && password.trim()

  return (
    <>
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          boxShadow: `0 8px 24px ${alpha(theme.palette.common.black, 0.15)}`,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1.5 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Neo4j Connection Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Ontology: <strong>{ontologyName}</strong>
          </Typography>
        </Box>
        <IconButton onClick={handleClose} aria-label="Close Neo4j settings dialog" size="small" disabled={loading || cloning || syncing}>
          <CloseOutline size="24" />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="URI"
            fullWidth
            required
            value={uri}
            onChange={(e) => setUri(e.target.value)}
            placeholder="bolt+s://xxxx.databases.neo4j.io"
            disabled={loading}
            helperText="Neo4j database connection URI"
            autoFocus
          />
          <TextField
            label="Username"
            fullWidth
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="neo4j"
            disabled={loading}
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your Neo4j password"
            disabled={loading}
          />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.5 }}>
            Sync to semantic entities
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Sync this ontology to semantic entity definitions and update field ranges.
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="outline"
              onClick={handleSyncToSemanticEntities}
              disabled={syncing}
              sx={{ alignSelf: 'flex-start' }}
            >
              {syncing ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={16} />
                  Syncing...
                </Box>
              ) : (
                'Sync ontology'
              )}
            </Button>
            {syncResult && (
              <Typography variant="body2" color="text.secondary">
                Created: {syncResult.entitiesCreated}, updated: {syncResult.entitiesUpdated}, fields with range updated: {syncResult.fieldsWithRangeUpdated}
              </Typography>
            )}
          </Box>
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.5 }}>
            Clone ontology
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Create a copy of this ontology (metadata and draft JSON). Neo4j connection and intents are not copied.
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <TextField
              size="small"
              label="Name for clone (optional)"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              placeholder={`Copy of ${ontologyName}`}
              disabled={cloning}
              sx={{ minWidth: 220, flex: '1 1 200px' }}
            />
            <Button
              variant="outline"
              onClick={handleClone}
              disabled={cloning}
              sx={{ alignSelf: 'flex-start' }}
            >
              {cloning ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={16} />
                  Cloning...
                </Box>
              ) : (
                'Clone ontology'
              )}
            </Button>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 2, pb: 2, justifyContent: 'space-between' }}>
        <Box>
          {onDelete && (
            <Button onClick={handleDeleteClick} disabled={loading || deleting || cloning || syncing} variant="outline">
              Delete Ontology
            </Button>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button onClick={handleClose} disabled={loading || deleting || cloning || syncing} variant="outline">
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={loading || deleting || cloning || syncing || !isValid}>
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                Saving...
              </Box>
            ) : (
              'Save'
            )}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>

    {/* Delete Confirmation Dialog */}
    <Dialog
      open={deleteDialogOpen}
      onClose={handleDeleteCancel}
      aria-labelledby="delete-dialog-title"
      aria-describedby="delete-dialog-description"
    >
      <DialogTitle id="delete-dialog-title">Delete Ontology</DialogTitle>
      <DialogContent>
        <DialogContentText id="delete-dialog-description">
          Are you sure you want to delete the ontology "{ontologyName}"? This action cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleDeleteCancel} disabled={deleting} variant="outline">
          Cancel
        </Button>
        <Button onClick={handleDeleteConfirm} disabled={deleting}>
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
    </>
  )
}
