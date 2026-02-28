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
  fetchAgentRoles,
  deleteAgentRole,
  type AgentRole,
} from '../services/graphql'
import Button from '../components/common/Button'
import { formatDateTime, truncate } from '../utils/formatUtils'

export default function AgentRolesList() {
  const navigate = useNavigate()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [roles, setRoles] = useState<AgentRole[]>([])
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>(() => {
    const saved = localStorage.getItem('agentRoles:viewMode')
    return saved === 'table' || saved === 'cards' ? saved : 'cards'
  })
  const [sortBy, setSortBy] = useState<
    'name-asc' | 'name-desc' | 'date-newest' | 'date-oldest' | 'modified-recent'
  >('date-newest')
  const [page, setPage] = useState(1)
  const itemsPerPage = 12
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [roleToDelete, setRoleToDelete] = useState<AgentRole | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAgentRoles()
        if (!active) return
        setRoles(data)
      } catch (e: unknown) {
        if (!active) return
        setError(e instanceof Error ? e.message : 'Failed to load agent roles')
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
    let result = [...roles]

    if (query.trim()) {
      const q = query.toLowerCase()
      result = result.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.description && r.description.toLowerCase().includes(q)) ||
          (r.readOntologyName && r.readOntologyName.toLowerCase().includes(q)) ||
          (r.writeOntologyName && r.writeOntologyName.toLowerCase().includes(q))
      )
    }

    result.sort((a, b) => {
      switch (sortBy) {
        case 'name-asc':
          return a.name.localeCompare(b.name)
        case 'name-desc':
          return b.name.localeCompare(a.name)
        case 'date-newest':
          return new Date(b.createdOn).getTime() - new Date(a.createdOn).getTime()
        case 'date-oldest':
          return new Date(a.createdOn).getTime() - new Date(b.createdOn).getTime()
        case 'modified-recent':
          return (
            new Date(b.lastEdit ?? b.createdOn).getTime() -
            new Date(a.lastEdit ?? a.createdOn).getTime()
          )
        default:
          return 0
      }
    })

    return result
  }, [roles, query, sortBy])

  const totalPages = Math.ceil(filtered.length / itemsPerPage)
  const startIndex = (page - 1) * itemsPerPage
  const paginatedRoles = filtered.slice(startIndex, startIndex + itemsPerPage)

  useEffect(() => {
    setPage(1)
  }, [query, sortBy])

  const handleSelect = (role: AgentRole) => {
    navigate(`/agent-role/${role.agentRoleId}`)
  }

  const handleCreate = () => {
    navigate('/agent-role/create')
  }

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'cards' | 'table' | null) => {
    if (newMode !== null) {
      setViewMode(newMode)
      localStorage.setItem('agentRoles:viewMode', newMode)
    }
  }

  const handleCloseSnackbar = () => {
    setSnackbar((s) => ({ ...s, open: false }))
  }

  const handleDeleteClick = (role: AgentRole, e: React.MouseEvent) => {
    e.stopPropagation()
    setRoleToDelete(role)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!roleToDelete) return
    setDeleting(true)
    try {
      await deleteAgentRole(roleToDelete.agentRoleId)
      setSnackbar({
        open: true,
        message: `Agent role "${roleToDelete.name}" deleted successfully`,
        severity: 'success',
      })
      const data = await fetchAgentRoles()
      setRoles(data)
      setDeleteDialogOpen(false)
      setRoleToDelete(null)
    } catch (e: unknown) {
      setSnackbar({
        open: true,
        message: e instanceof Error ? e.message : 'Failed to delete agent role',
        severity: 'error',
      })
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setRoleToDelete(null)
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
            Agent Roles
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button onClick={handleCreate}>Create Agent Role</Button>
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
            placeholder="Search by name, description, or ontology..."
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
              <option value="name-asc">Name (A–Z)</option>
              <option value="name-desc">Name (Z–A)</option>
              <option value="modified-recent">Recently Modified</option>
            </Box>
          </Box>
          <Typography variant="body2" color="text.secondary">
            {filtered.length} {filtered.length === 1 ? 'role' : 'roles'}
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
              {query ? 'No agent roles found' : 'No agent roles yet'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {query ? 'Try adjusting your search terms' : 'Create your first agent role to get started'}
            </Typography>
            {!query && <Button onClick={handleCreate}>Create Agent Role</Button>}
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
              {paginatedRoles.map((role) => (
                <Paper
                  key={role.agentRoleId}
                  variant="outlined"
                  sx={{
                    p: 2,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': { boxShadow: 4, transform: 'translateY(-2px)' },
                    bgcolor: 'background.paper',
                  }}
                  onClick={() => handleSelect(role)}
                >
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="h6" fontWeight={600} sx={{ flex: 1, mr: 1 }}>
                      {role.name}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelect(role);
                        }}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
                        }}
                        aria-label="Edit agent role"
                        title="Edit"
                      >
                        <Edit fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => handleDeleteClick(role, e)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: 'error.main', bgcolor: 'action.hover' },
                        }}
                        aria-label="Delete agent role"
                        title="Delete"
                      >
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </Box>
                  </Box>
                  {role.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, minHeight: 36 }}>
                      {truncate(role.description, 80)}
                    </Typography>
                  )}
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Read: {role.readOntologyName || '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Write: {role.writeOntologyName || '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                      Updated: {formatDateTime(role.lastEdit ?? role.createdOn, 'Never')}
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
                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Read ontology</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Write ontology</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Last updated</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedRoles.map((role) => (
                    <TableRow
                      key={role.agentRoleId}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleSelect(role)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {role.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {truncate(role.description, 60)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {role.readOntologyName || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {role.writeOntologyName || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDateTime(role.lastEdit ?? role.createdOn, 'Never')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleSelect(role)
                            }}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
                            }}
                            aria-label="Edit agent role"
                            title="Edit"
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => handleDeleteClick(role, e)}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': { color: 'error.main', bgcolor: 'action.hover' },
                            }}
                            aria-label="Delete agent role"
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
          <DialogTitle>Delete agent role?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete the agent role &quot;{roleToDelete?.name}&quot;? This cannot be undone.
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
