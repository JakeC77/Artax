import { useEffect, useMemo, useState } from 'react'
import {
  Box,
  OutlinedInput,
  InputAdornment,
  Typography,
  CircularProgress,
  Container,
  Paper,
  Snackbar,
  Alert,
  ToggleButtonGroup,
  ToggleButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Pagination,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material'
import { Search, Grid, List } from '@carbon/icons-react'
import DeleteOutline from '@mui/icons-material/DeleteOutline'
import Edit from '@mui/icons-material/Edit'
import { useNavigate } from 'react-router-dom'
import {
  fetchIntents,
  deleteIntent,
  type Intent,
} from '../services/graphql'
import Button from '../components/common/Button'
import { formatDateTime, truncate } from '../utils/formatUtils'

export default function IntentsList() {
  const navigate = useNavigate()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [intents, setIntents] = useState<Intent[]>([])
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>(() => {
    const saved = localStorage.getItem('intents:viewMode')
    return saved === 'table' || saved === 'cards' ? saved : 'cards'
  })
  const [sortBy, setSortBy] = useState<'opId-asc' | 'opId-desc' | 'date-newest' | 'date-oldest' | 'modified-recent'>(
    'date-newest'
  )
  const [page, setPage] = useState(1)
  const itemsPerPage = 12
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [intentToDelete, setIntentToDelete] = useState<Intent | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchIntents()
        if (!active) return
        setIntents(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load intents')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  const filtered = useMemo(() => {
    let result = [...intents]

    if (query.trim()) {
      const q = query.toLowerCase()
      result = result.filter(
        (i) =>
          i.opId.toLowerCase().includes(q) ||
          i.intent.toLowerCase().includes(q) ||
          (i.ontologyName && i.ontologyName.toLowerCase().includes(q)) ||
          (i.route && i.route.toLowerCase().includes(q)) ||
          (i.description && i.description.toLowerCase().includes(q)) ||
          (i.data_source && i.data_source.toLowerCase().includes(q))
      )
    }

    result.sort((a, b) => {
      switch (sortBy) {
        case 'opId-asc':
          return a.opId.localeCompare(b.opId)
        case 'opId-desc':
          return b.opId.localeCompare(a.opId)
        case 'date-newest':
          return new Date(b.createdOn).getTime() - new Date(a.createdOn).getTime()
        case 'date-oldest':
          return new Date(a.createdOn).getTime() - new Date(b.createdOn).getTime()
        case 'modified-recent':
          return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        default:
          return 0
      }
    })

    return result
  }, [intents, query, sortBy])

  const totalPages = Math.ceil(filtered.length / itemsPerPage)
  const startIndex = (page - 1) * itemsPerPage
  const paginatedIntents = filtered.slice(startIndex, startIndex + itemsPerPage)

  useEffect(() => {
    setPage(1)
  }, [query, sortBy])

  const handleSelect = (intent: Intent) => {
    navigate(`/intent/${intent.intentId}`)
  }

  const handleCreate = () => {
    navigate('/intent/create')
  }

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'cards' | 'table' | null) => {
    if (newMode !== null) {
      setViewMode(newMode)
      localStorage.setItem('intents:viewMode', newMode)
    }
  }

  const handleCloseSnackbar = () => {
    setSnackbar((s) => ({ ...s, open: false }))
  }

  const handleDeleteClick = (intent: Intent, e: React.MouseEvent) => {
    e.stopPropagation()
    setIntentToDelete(intent)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!intentToDelete) return
    setDeleting(true)
    try {
      await deleteIntent(intentToDelete.intentId)
      setSnackbar({
        open: true,
        message: `Intent "${intentToDelete.opId}" deleted successfully`,
        severity: 'success',
      })
      const data = await fetchIntents()
      setIntents(data)
      setDeleteDialogOpen(false)
      setIntentToDelete(null)
    } catch (e: any) {
      setSnackbar({
        open: true,
        message: e?.message || 'Failed to delete intent',
        severity: 'error',
      })
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setIntentToDelete(null)
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto', bgcolor: 'background.default', p: 2 }}>
      <Container maxWidth={false} disableGutters>
        <Box
          sx={{
            mb: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>
            Intents
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button onClick={handleCreate}>Create Intent</Button>
          </Box>
        </Box>

        <Box
          sx={{
            mb: 3,
            display: 'flex',
            gap: 2,
            alignItems: 'center',
          }}
        >
          <OutlinedInput
            fullWidth
            size="small"
            placeholder="Search by opId, intent, route, description, or data source..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <Search size={20} />
              </InputAdornment>
            }
            sx={{
              bgcolor: (t) => (t.palette.mode === 'light' ? '#FFFFFF' : t.palette.background.paper),
            }}
          />
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            aria-label="view mode"
            sx={{ flexShrink: 0 }}
          >
            <ToggleButton value="cards" aria-label="cards view">
              <Grid size={20} />
            </ToggleButton>
            <ToggleButton value="table" aria-label="table view">
              <List size={20} />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Sort by:
            </Typography>
            <Box
              component="select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                px: 1.5,
                py: 0.5,
                bgcolor: 'background.paper',
                fontSize: '0.875rem',
                cursor: 'pointer',
                '&:hover': { borderColor: 'primary.main' },
              }}
            >
              <option value="date-newest">Newest First</option>
              <option value="date-oldest">Oldest First</option>
              <option value="opId-asc">Op ID (A-Z)</option>
              <option value="opId-desc">Op ID (Z-A)</option>
              <option value="modified-recent">Recently Modified</option>
            </Box>
          </Box>
          <Typography variant="body2" color="text.secondary">
            {filtered.length} {filtered.length === 1 ? 'intent' : 'intents'}
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : filtered.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 6, textAlign: 'center', bgcolor: 'background.paper' }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {query ? 'No intents found' : 'No intents yet'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {query ? 'Try adjusting your search terms' : 'Create your first intent to get started'}
            </Typography>
            {!query && <Button onClick={handleCreate}>Create Intent</Button>}
          </Paper>
        ) : viewMode === 'cards' ? (
          <>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: 'repeat(2, 1fr)',
                  md: 'repeat(3, 1fr)',
                  lg: 'repeat(4, 1fr)',
                },
                gap: 2,
                mb: 3,
              }}
            >
              {paginatedIntents.map((intent) => (
                <Paper
                  key={intent.intentId}
                  variant="outlined"
                  sx={{
                    p: 2,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': { boxShadow: 4, transform: 'translateY(-2px)' },
                    bgcolor: 'background.paper',
                  }}
                  onClick={() => handleSelect(intent)}
                >
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="h6" fontWeight={600} sx={{ flex: 1, mr: 1 }}>
                      {intent.opId}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelect(intent);
                        }}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
                        }}
                        aria-label="Edit intent"
                        title="Edit"
                      >
                        <Edit fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => handleDeleteClick(intent, e)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: 'error.main', bgcolor: 'action.hover' },
                        }}
                        aria-label="Delete intent"
                        title="Delete"
                      >
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </Box>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                    {intent.intent}
                  </Typography>
                  {intent.route && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      {intent.route}
                    </Typography>
                  )}
                  {intent.ontologyName && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      Ontology: {intent.ontologyName}
                    </Typography>
                  )}
                  {intent.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, minHeight: 36 }}>
                      {truncate(intent.description, 80, '-')}
                    </Typography>
                  )}
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 2 }}>
                    {intent.data_source && (
                      <Typography variant="caption" color="text.secondary">
                        Data source: {intent.data_source}
                      </Typography>
                    )}
                    <Typography variant="caption" color="text.secondary">
                      Updated: {formatDateTime(intent.updatedAt, 'Never')}
                    </Typography>
                  </Box>
                </Paper>
              ))}
            </Box>
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
              </Box>
            )}
          </>
        ) : (
          <>
            <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'background.paper' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Op ID</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Intent</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Ontology</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Route</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Data source</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Last updated</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedIntents.map((intent) => (
                    <TableRow
                      key={intent.intentId}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleSelect(intent)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {intent.opId}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{intent.intent}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {intent.ontologyName || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {intent.route || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {truncate(intent.description, 60, '-')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {intent.data_source || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDateTime(intent.updatedAt, 'Never')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleSelect(intent)
                            }}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
                            }}
                            aria-label="Edit intent"
                            title="Edit"
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => handleDeleteClick(intent, e)}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': { color: 'error.main', bgcolor: 'action.hover' },
                            }}
                            aria-label="Delete intent"
                            title="Delete"
                          >
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
              </Box>
            )}
          </>
        )}

        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleCloseSnackbar}>
          <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Delete intent?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete the intent &quot;{intentToDelete?.opId}&quot;? This cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button variant="secondary" onClick={handleDeleteCancel} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleDeleteConfirm} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  )
}
