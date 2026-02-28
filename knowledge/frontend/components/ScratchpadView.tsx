import type React from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Box, CircularProgress, IconButton, Menu, MenuItem, OutlinedInput, Paper, Tooltip, Typography } from '@mui/material'
import Button from './common/Button'
import {
  fetchScratchpadNotes,
  fetchScratchpadAttachments,
  createScratchpadNote,
  deleteScratchpadNote,
  createScratchpadAttachment,
  deleteScratchpadAttachment,
  openFileInNewWindow,
  type ScratchpadNote,
  type ScratchpadAttachment,
  getApiBase,
  getTenantId,
} from '../services/graphql'

export default function ScratchpadView({ workspaceId }: { workspaceId?: string }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState<ScratchpadNote[]>([])
  const [attachments, setAttachments] = useState<ScratchpadAttachment[]>([])

  const [noteTitle, setNoteTitle] = useState('')
  const [noteText, setNoteText] = useState('')

  const [submitting, setSubmitting] = useState(false)
  
  // UI state
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null)
  const dropRef = useRef<HTMLDivElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null)
  const [menuForAttachment, setMenuForAttachment] = useState<null | string>(null)

  const refresh = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    setError(null)
    try {
      const [n, a] = await Promise.all([
        fetchScratchpadNotes(workspaceId),
        fetchScratchpadAttachments(workspaceId),
      ])
      setNotes(n)
      setAttachments(a)
    } catch (e: any) {
      setError(e?.message || 'Failed to load scratchpad')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleCreateNote = async () => {
    if (!workspaceId) return
    if (!noteTitle.trim() && !noteText.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await createScratchpadNote({ workspaceId, title: noteTitle, text: noteText })
      setNoteTitle('')
      setNoteText('')
      await refresh()
    } catch (e: any) {
      setError(e?.message || 'Failed to create note')
    } finally {
      setSubmitting(false)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f && workspaceId) {
      try {
        setSubmitting(true)
        setError(null)
        const derivedTitle = f.name.replace(/\.[^.]+$/, '')
        await createScratchpadAttachment({ workspaceId, title: derivedTitle, description: null, file: f })
        if (fileInputRef.current) fileInputRef.current.value = ''
        await refresh()
      } catch (err: any) {
        setError(err?.message || 'Failed to upload attachment')
      } finally {
        setSubmitting(false)
      }
    }
  }
  
  const onDrop = useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDraggingOver(false)
      const f = e.dataTransfer.files?.[0]
      if (f && workspaceId) {
        try {
          setSubmitting(true)
          setError(null)
          const derivedTitle = f.name.replace(/\.[^.]+$/, '')
          await createScratchpadAttachment({ workspaceId, title: derivedTitle, description: null, file: f })
          await refresh()
        } catch (err: any) {
          setError(err?.message || 'Failed to upload attachment')
        } finally {
          setSubmitting(false)
        }
      }
    },
    [workspaceId, refresh]
  )
  
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDraggingOver(true)
  }
  
  const onDragLeave = () => setIsDraggingOver(false)

  const fmtDate = (iso?: string) => {
    if (!iso) return ''
    try { return new Date(iso).toLocaleString() } catch { return iso }
  }
  
  const selectedNote = useMemo(() => notes.find(n => n.scratchpadNoteId === selectedNoteId) || null, [notes, selectedNoteId])
  
  // Load selected note into editor
  useEffect(() => {
    if (selectedNote) {
      setNoteTitle(selectedNote.title || '')
      setNoteText(selectedNote.text || '')
    }
  }, [selectedNote?.scratchpadNoteId])

  if (!workspaceId) {
    return (
      <Box>
        <Typography variant='body2' color='text.secondary'>Select a workspace to use Scratchpad.</Typography>
      </Box>
    )
  }

  return (
    <Box>
      {error && (
        <Typography color='error' variant='body2' sx={{ mb: 1 }}>{error}</Typography>
      )}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 2 }}>
        {/* Left: Note editor / viewer */}
        <Paper variant='outlined' sx={{ p: 1.5, borderRadius: 0.5, minHeight: 380, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Typography variant='subtitle2' sx={{ fontWeight: 700 }}>Notes</Typography>
            <Box sx={{ flex: 1 }} />
            <Tooltip title='Save note'>
              <span>
                <Button size='sm' variant='primary' onClick={handleCreateNote} disabled={submitting || (!noteTitle.trim() && !noteText.trim())}>Save Note</Button>
              </span>
            </Tooltip>
          </Box>
          <OutlinedInput size='small' placeholder='Title' value={noteTitle} onChange={(e) => setNoteTitle(e.target.value)} fullWidth sx={{ mb: 1 }} />
          <OutlinedInput size='small' placeholder='Write your note...' value={noteText} onChange={(e) => setNoteText(e.target.value)} fullWidth multiline minRows={10} sx={{ mb: 1, alignItems: 'flex-start' }} />
          {submitting && <CircularProgress size={18} />}
        </Paper>

        {/* Right: Files + Notes list */}
        <Box sx={{ display: 'grid', gap: 2 }}>
          <Paper variant='outlined' sx={{ p: 1.5, borderRadius: 0.5 }}>
            <Typography variant='subtitle2' sx={{ fontWeight: 700, mb: 1 }}>Files</Typography>
            {/* Drop zone */}
            <Box
              ref={dropRef}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              sx={{
                border: '2px dashed',
                borderColor: isDraggingOver ? 'success.main' : 'divider',
                borderRadius: 0.5,
                p: 2,
                textAlign: 'center',
                color: 'text.secondary',
                cursor: 'pointer',
                transition: 'border-color 120ms ease',
                mb: 1.5,
                userSelect: 'none',
              }}
            >
              <Typography variant='body2'>Drag and drop your files here</Typography>
              <Typography variant='caption'>or choose files</Typography>
            </Box>
            <input ref={fileInputRef} id='scratchpad-file-input' type='file' style={{ display: 'none' }} onChange={handleFileSelect} />

            {/* Attachments list */}
            <Box sx={{ display: 'grid', gap: 1 }}>
              {loading && !attachments.length ? (
                <Typography variant='body2' color='text.secondary'>Loading...</Typography>
              ) : attachments.length === 0 ? (
                <Typography variant='body2' color='text.secondary'>No files yet.</Typography>
              ) : (
                attachments.map((a) => (
                  <Paper key={a.scratchpadAttachmentId} variant='outlined' sx={{ p: 1, borderRadius: 0.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <OutlinedInput size='small' value={a.title || 'Untitled'} readOnly sx={{
                        '& .MuiInputBase-input': { p: 0.5, fontWeight: 600 },
                        px: 0.5,
                        flex: 1,
                      }} />
                      <Typography variant='caption' color='text.secondary'>Uploaded {fmtDate(a.createdOn)}</Typography>
                      <IconButton size='small' onClick={(e) => { setMenuAnchorEl(e.currentTarget); setMenuForAttachment(a.scratchpadAttachmentId) }}>⋯</IconButton>
                    </Box>
                  </Paper>
                ))
              )}
            </Box>
          </Paper>

          <Paper variant='outlined' sx={{ p: 1.5, borderRadius: 0.5 }}>
            <Typography variant='subtitle2' sx={{ fontWeight: 700, mb: 1 }}>Notes</Typography>
            <Box sx={{ display: 'grid', gap: 1 }}>
              {loading && !notes.length ? (
                <Typography variant='body2' color='text.secondary'>Loading...</Typography>
              ) : notes.length === 0 ? (
                <Typography variant='body2' color='text.secondary'>No notes yet.</Typography>
              ) : (
                notes.map((n) => (
                  <Paper key={n.scratchpadNoteId} variant='outlined' sx={{ p: 1, borderRadius: 0.5, cursor: 'pointer', bgcolor: selectedNoteId === n.scratchpadNoteId ? 'action.hover' : 'background.paper' }} onClick={() => setSelectedNoteId(n.scratchpadNoteId)}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography sx={{ fontWeight: 600, flex: 1 }} noWrap title={n.title || 'Untitled'}>{n.title || 'Untitled'}</Typography>
                      <Typography variant='caption' color='text.secondary'>Last edited {fmtDate(n.createdOn)}</Typography>
                      <Tooltip title='Delete'>
                        <IconButton size='small' onClick={async (e) => { e.stopPropagation(); await deleteScratchpadNote(n.scratchpadNoteId); if (selectedNoteId === n.scratchpadNoteId) setSelectedNoteId(null); await refresh() }}>x</IconButton>
                      </Tooltip>
                    </Box>
                  </Paper>
                ))
              )}
            </Box>
          </Paper>
        </Box>
      </Box>

      {/* Attachment actions menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={() => { setMenuAnchorEl(null); setMenuForAttachment(null) }}
      >
        <MenuItem
          onClick={async () => {
            const a = attachments.find(x => x.scratchpadAttachmentId === menuForAttachment)
            if (a) {
              try {
                const apiBase = getApiBase().replace(/\/$/, '')
                const tid = getTenantId?.() || ''
                const url = `${apiBase}/scratchpad/attachments/${a.scratchpadAttachmentId}/download` + (tid ? `?tid=${encodeURIComponent(tid)}` : '')
                await openFileInNewWindow(url)
              } catch (error: any) {
                console.error('Failed to open attachment:', error)
                setError(error?.message || 'Failed to open attachment')
              }
            }
            setMenuAnchorEl(null)
            setMenuForAttachment(null)
          }}
        >Preview</MenuItem>
        <MenuItem
          onClick={async () => {
            if (menuForAttachment) {
              await deleteScratchpadAttachment(menuForAttachment)
              await refresh()
            }
            setMenuAnchorEl(null)
            setMenuForAttachment(null)
          }}
        >Delete</MenuItem>
      </Menu>
    </Box>
  )
}
