import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  OutlinedInput,
  InputAdornment,
  Typography,
  CircularProgress,
  Divider,
  DialogActions,
  TextField,
} from '@mui/material'
import { Search } from '@carbon/icons-react';
import { Edit } from '@carbon/icons-react';
import { TrashCan } from '@carbon/icons-react';
import { CloseOutline } from '@carbon/icons-react';
import { alpha, useTheme } from '@mui/material/styles'
import { fetchWorkspaces, type Workspace, deleteWorkspace as gqlDeleteWorkspace, updateWorkspace as gqlUpdateWorkspace } from '../services/graphql'
import Button from './common/Button'
import CreateWorkspaceModal from './CreateWorkspaceModal'

export type SelectWorkspaceModalProps = {
  open: boolean
  onClose: () => void
  onSelect: (ws: Workspace) => void
  onUpdate?: (ws: Workspace) => void
}

export default function SelectWorkspaceModal({ open, onClose, onSelect, onUpdate }: SelectWorkspaceModalProps) {
  const theme = useTheme()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [query, setQuery] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Workspace | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editIntent, setEditIntent] = useState('')
  const [editVisibility, setEditVisibility] = useState<string>('private')
  const [mutating, setMutating] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchWorkspaces()
        if (!active) return
        setWorkspaces(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load workspaces')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [open])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return workspaces
    return workspaces.filter((w) =>
      [w.name, w.description || '', w.workspaceId].some((s) => s.toLowerCase().includes(q)),
    )
  }, [workspaces, query])

  const handleSelect = useCallback(
    (ws: Workspace) => {
      onSelect(ws)
      onClose()
    },
    [onClose, onSelect],
  )

  const handleDelete = async (ws: Workspace, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete workspace "${ws.name}"? This cannot be undone.`)) return
    try {
      setMutating(true)
      const ok = await gqlDeleteWorkspace(ws.workspaceId)
      if (!ok) throw new Error('Delete failed')
      setWorkspaces((prev) => prev.filter((w) => w.workspaceId !== ws.workspaceId))
    } catch (e: any) {
      alert(e?.message || 'Failed to delete workspace')
    } finally {
      setMutating(false)
    }
  }

  const openEdit = (ws: Workspace, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditTarget(ws)
    setEditName(ws.name)
    setEditDescription(ws.description || '')
    setEditIntent(ws.intent || '')
    setEditVisibility(ws.visibility || 'private')
    setEditOpen(true)
  }

  const submitEdit = async () => {
    if (!editTarget) return
    try {
      setMutating(true)
      const ok = await gqlUpdateWorkspace({
        workspaceId: editTarget.workspaceId,
        name: editName,
        description: editDescription,
        intent: editIntent,
        visibility: editVisibility,
      })
      if (!ok) throw new Error('Update failed')
      const updated: Workspace = {
        ...editTarget,
        name: editName,
        description: editDescription,
        intent: editIntent,
        visibility: editVisibility,
      }
      setWorkspaces((prev) => prev.map((w) => (w.workspaceId === updated.workspaceId ? updated : w)))
      // Persist selection if this is the currently stored workspace
      try {
        const raw = localStorage.getItem('workspace:selected')
        if (raw) {
          const cur = JSON.parse(raw) as Workspace
          if (cur.workspaceId === updated.workspaceId) {
            localStorage.setItem('workspace:selected', JSON.stringify(updated))
          }
        }
      } catch {}
      // Notify parent so it can refresh header if needed
      onUpdate?.(updated)
      setEditOpen(false)
      setEditTarget(null)
    } catch (e: any) {
      alert(e?.message || 'Failed to update workspace')
    } finally {
      setMutating(false)
    }
  }

  const handleCreateWorkspaceCreated = useCallback(
    async (workspaceId: string) => {
      const data = await fetchWorkspaces()
      setWorkspaces(data)
      setCreateOpen(false)
      const newWs = data.find((w) => w.workspaceId === workspaceId)
      if (newWs) {
        handleSelect(newWs)
      }
    },
    [handleSelect],
  )

  return (
    <Dialog
      open={open}
      onClose={onClose}
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
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Select Workspace
        </Typography>
        <IconButton onClick={onClose} aria-label="Close select workspace dialog" size="small">
          <CloseOutline size="24" />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2 }}>
        <Box sx={{ mb: 2 }}>
          <OutlinedInput
            fullWidth
            size="small"
            placeholder="Search workspaces"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <Search size="24" />
              </InputAdornment>
            }
            sx={{ bgcolor: 'background.paper' }}
          />
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={22} />
          </Box>
        ) : error ? (
          <Typography color="error">{error}</Typography>
        ) : (
          <List sx={{ maxHeight: 360, overflowY: 'auto' }}>
            {filtered.map((ws) => (
              <ListItemButton
                key={ws.workspaceId}
                onClick={() => handleSelect(ws)}
                sx={{
                  alignItems: 'flex-start',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1.5,
                  mb: 1,
                }}
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography sx={{ fontWeight: 700 }}>{ws.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {ws.visibility || 'private'}
                      </Typography>
                    </Box>
                  }
                  secondary={
                    <Typography variant="body2" color="text.secondary">
                      {ws.description || 'No description'}
                    </Typography>
                  }
                />
                <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <IconButton
                    size="small"
                    aria-label={`Edit workspace ${ws.name}`}
                    onClick={(e) => openEdit(ws, e)}
                    disabled={mutating}
                  >
                    <Edit size="24" />
                  </IconButton>
                  <IconButton
                    size="small"
                    aria-label={`Delete workspace ${ws.name}`}
                    onClick={(e) => handleDelete(ws, e)}
                    disabled={mutating}
                  >
                    <TrashCan size="24" />
                  </IconButton>
                </Box>
              </ListItemButton>
            ))}
            {!filtered.length && (
              <Box sx={{ textAlign: 'center', color: 'text.secondary', py: 4 }}>
                <Typography>No workspaces found</Typography>
              </Box>
            )}
          </List>
        )}
      </DialogContent>

      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'center' }}>
        <Button size="sm" onClick={() => setCreateOpen(true)} disabled={mutating}>
          Create Workspace
        </Button>
      </Box>

      {/* Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Workspace</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2 }}>
          <TextField
            label="Name"
            size="small"
            fullWidth
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
          <TextField
            label="Description"
            size="small"
            fullWidth
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
          />
          <TextField
            label="Intent"
            size="small"
            fullWidth
            value={editIntent}
            onChange={(e) => setEditIntent(e.target.value)}
            placeholder="Describe the workspace intent"
          />
          <TextField
            label="Visibility"
            size="small"
            fullWidth
            value={editVisibility}
            onChange={(e) => setEditVisibility(e.target.value)}
            placeholder="private | public"
          />
        </DialogContent>
        <DialogActions>
          <Button size="sm" variant="outline" onClick={() => setEditOpen(false)} disabled={mutating}>Cancel</Button>
          <Button size="sm" onClick={submitEdit} disabled={mutating}>Save</Button>
        </DialogActions>
      </Dialog>

      <CreateWorkspaceModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreateWorkspaceCreated}
      />
    </Dialog>
  )
}
