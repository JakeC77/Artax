import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Box,
  IconButton,
  OutlinedInput,
  InputAdornment,
  Typography,
  CircularProgress,
  Container,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Tabs,
  Tab,
  Select,
  FormControl,
  Pagination,
  TextField,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Modal,
  Chip,
  Popper,
} from '@mui/material'
import { Search, Edit, TrashCan, Grid, List, OverflowMenuVertical, Archive, Restart, Close, FunnelSort, Filter, ChevronDown, ChevronUp } from '@carbon/icons-react'
import { useTheme, alpha } from '@mui/material/styles'
import { useNavigate } from 'react-router-dom'
import {
  fetchWorkspaces,
  fetchWorkspaceById,
  type Workspace,
  deleteWorkspace as gqlDeleteWorkspace,
  updateWorkspace,
  fetchUsers,
  listCompanies,
  fetchOntologies,
  type User,
} from '../services/graphql'
import Button from '../components/common/Button'
import CreateWorkspaceModal from '../components/CreateWorkspaceModal'
import { useWorkspace } from '../contexts/WorkspaceContext'
import { useAuth } from '../contexts/AuthContext'
import { formatDateTime } from '../utils/formatUtils'

// Helper function to format dates
function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  })
}

export default function WorkspacesList() {
  const theme = useTheme()
  const navigate = useNavigate()
  const { setCurrentWorkspace, setWorkspaceState } = useWorkspace()
  const { account } = useAuth()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [users, setUsers] = useState<Map<string, User>>(new Map())
  const [companyNames, setCompanyNames] = useState<Map<string, string>>(new Map())
  const [ontologyLookup, setOntologyLookup] = useState<Map<string, { name: string; semVer: string }>>(new Map())
  const [query, setQuery] = useState('')
  const [mutating, setMutating] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState<{ open: boolean, workspace: Workspace | null }>({ open: false, workspace: null })
  const [editDialog, setEditDialog] = useState<{ open: boolean, workspace: Workspace | null }>({ open: false, workspace: null })
  const [editForm, setEditForm] = useState({ name: '', description: '', visibility: 'private' })
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' })
  const [viewMode, setViewMode] = useState<'cards' | 'table'>(() => {
    const saved = localStorage.getItem('workspaces:viewMode')
    return (saved === 'table' || saved === 'cards') ? saved : 'cards'
  })
  const [menuAnchor, setMenuAnchor] = useState<{ element: HTMLElement, workspace: Workspace } | null>(null)
  const [activeTab, setActiveTab] = useState<'mine' | 'others'>('mine')
  const [sortBy, setSortBy] = useState<'name-asc' | 'name-desc' | 'date-newest' | 'date-oldest' | 'modified-recent'>('date-newest')
  const [page, setPage] = useState(1)
  const itemsPerPage = 12
  const [selectingWorkspace, setSelectingWorkspace] = useState<string | null>(null)
  const [createWorkspaceModalOpen, setCreateWorkspaceModalOpen] = useState(false)
  const [isFiltersOpen, setIsFiltersOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('all')
  const [draftStatusFilter, setDraftStatusFilter] = useState<'all' | 'active' | 'archived'>('all')
  const filtersAnchorRef = useRef<HTMLDivElement | null>(null)

  const currentUserId = useMemo(() => {
    const email = account?.username?.toLowerCase()
    if (!email) return null
    for (const user of users.values()) {
      if (user.email?.toLowerCase() === email) {
        return user.userId
      }
    }
    return null
  }, [account?.username, users])

  const currentUserIds = useMemo(() => {
    const ids = new Set<string>()
    if (account?.homeAccountId) ids.add(account.homeAccountId)
    if (account?.localAccountId) ids.add(account.localAccountId)
    if (account?.username) ids.add(account.username)
    const name = account?.name?.toLowerCase()
    for (const user of users.values()) {
      if (currentUserId && user.userId === currentUserId) {
        ids.add(user.userId)
      }
      if (name && user.displayName?.toLowerCase() === name) {
        ids.add(user.userId)
      }
    }
    return ids
  }, [account?.homeAccountId, account?.localAccountId, account?.name, account?.username, currentUserId, users])

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [workspacesData, usersData, companiesData, ontologiesData] = await Promise.all([
          fetchWorkspaces(),
          fetchUsers(),
          listCompanies(),
          fetchOntologies(),
        ])
        if (!active) return
        setWorkspaces(workspacesData)
        const userMap = new Map<string, User>()
        usersData.forEach(user => userMap.set(user.userId, user))
        setUsers(userMap)
        const companyMap = new Map<string, string>()
        companiesData.forEach(c => companyMap.set(c.companyId, c.name))
        setCompanyNames(companyMap)
        const ontologyMap = new Map<string, { name: string; semVer: string }>()
        ontologiesData.forEach(o => ontologyMap.set(o.ontologyId, { name: o.name, semVer: o.semVer }))
        setOntologyLookup(ontologyMap)
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
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    
    // Filter by tab (creator). If we can't resolve user, don't filter by creator.
    let result = workspaces.filter((w) => {
      if (!currentUserIds.size) return true
      const ownerId = w.ownerUserId ?? ''
      return activeTab === 'mine' ? currentUserIds.has(ownerId) : !currentUserIds.has(ownerId)
    })
    
    // Filter by search query
    if (q) {
      result = result.filter((w) =>
        [w.name, w.description || '', w.workspaceId].some((s) => s.toLowerCase().includes(q)),
      )
    }
    
    // Sort
    result = [...result].sort((a, b) => {
      switch (sortBy) {
        case 'name-asc':
          return a.name.localeCompare(b.name)
        case 'name-desc':
          return b.name.localeCompare(a.name)
        case 'date-newest':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        case 'date-oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        case 'modified-recent':
          return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        default:
          return 0
      }
    })
    
    if (statusFilter === 'active') {
      result = result.filter((w) => w.state !== 'archived')
    } else if (statusFilter === 'archived') {
      result = result.filter((w) => w.state === 'archived')
    }

    return result
  }, [workspaces, query, activeTab, sortBy, users, statusFilter, currentUserIds])
  
  // Pagination calculations
  const totalPages = Math.ceil(filtered.length / itemsPerPage)
  const startIndex = (page - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedWorkspaces = filtered.slice(startIndex, endIndex)
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [query, activeTab, sortBy])

  const handleSelect = async (ws: Workspace) => {
    setSelectingWorkspace(ws.workspaceId)
    try {
      // Fetch fresh workspace data to get latest setupStage and artifacts
      const freshWorkspace = await fetchWorkspaceById(ws.workspaceId)
      if (freshWorkspace) {
        setCurrentWorkspace(freshWorkspace)
        setWorkspaceState(freshWorkspace.state || 'setup')
      } else {
        // Fallback to list data if fetch fails
        console.warn('[WorkspacesList] Failed to fetch fresh workspace, using list data')
        setCurrentWorkspace(ws)
        setWorkspaceState(ws.state || 'setup')
      }
      navigate('/workspace')
    } catch (e) {
      console.error('[WorkspacesList] Failed to fetch workspace:', e)
      // Fallback to list data
      setCurrentWorkspace(ws)
      setWorkspaceState(ws.state || 'setup')
      navigate('/workspace')
    } finally {
      setSelectingWorkspace(null)
    }
  }

  const handleConfirmDelete = async () => {
    const ws = deleteConfirmation.workspace
    if (!ws) return

    try {
      setMutating(true)
      const ok = await gqlDeleteWorkspace(ws.workspaceId)
      if (!ok) throw new Error('Delete failed')
      setWorkspaces((prev) => prev.filter((w) => w.workspaceId !== ws.workspaceId))
      setSnackbar({ open: true, message: 'Workspace deleted successfully', severity: 'success' })
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.message || 'Failed to delete workspace', severity: 'error' })
    } finally {
      setMutating(false)
      setDeleteConfirmation({ open: false, workspace: null })
    }
  }

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  const handleSaveEdit = async () => {
    const ws = editDialog.workspace
    if (!ws) return

    try {
      setMutating(true)
      const success = await updateWorkspace({
        workspaceId: ws.workspaceId,
        name: editForm.name,
        description: editForm.description || null,
        visibility: editForm.visibility,
      })

      if (!success) throw new Error('Update failed')

      // Update local state
      setWorkspaces((prev) =>
        prev.map((w) =>
          w.workspaceId === ws.workspaceId
            ? { ...w, name: editForm.name, description: editForm.description, visibility: editForm.visibility }
            : w
        )
      )

      setSnackbar({ open: true, message: 'Workspace updated successfully', severity: 'success' })
      setEditDialog({ open: false, workspace: null })
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.message || 'Failed to update workspace', severity: 'error' })
    } finally {
      setMutating(false)
    }
  }

  const handleOpenCreateWorkspaceModal = () => setCreateWorkspaceModalOpen(true)

  const handleCreateWorkspaceCreated = async (workspaceId: string) => {
    try {
      const newWorkspace = await fetchWorkspaceById(workspaceId)
      if (newWorkspace) {
        setCurrentWorkspace(newWorkspace)
      }
      setWorkspaceState('setup')
      navigate('/workspace')
    } catch (e: unknown) {
      setSnackbar({
        open: true,
        message: e instanceof Error ? e.message : 'Failed to open workspace',
        severity: 'error',
      })
    }
  }

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'cards' | 'table' | null) => {
    if (newMode !== null) {
      setViewMode(newMode)
      localStorage.setItem('workspaces:viewMode', newMode)
    }
  }

  const handleApplyFilters = () => {
    setStatusFilter(draftStatusFilter)
    setIsFiltersOpen(false)
  }

  const handleToggleFilters = () => {
    setIsFiltersOpen((open) => {
      const nextOpen = !open
      if (nextOpen) {
        setDraftStatusFilter(statusFilter)
      }
      return nextOpen
    })
  }

  const handleResetFilters = () => {
    setStatusFilter('all')
    setDraftStatusFilter('all')
  }

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, workspace: Workspace) => {
    event.stopPropagation()
    setMenuAnchor({ element: event.currentTarget, workspace })
  }

  const handleMenuClose = () => {
    setMenuAnchor(null)
  }

  const handleEditFromMenu = () => {
    if (menuAnchor?.workspace) {
      const ws = menuAnchor.workspace
      setEditForm({
        name: ws.name,
        description: ws.description || '',
        visibility: ws.visibility || 'private'
      })
      setEditDialog({ open: true, workspace: ws })
    }
    handleMenuClose()
  }

  const handleDeleteFromMenu = () => {
    if (menuAnchor?.workspace) {
      setDeleteConfirmation({ open: true, workspace: menuAnchor.workspace })
    }
    handleMenuClose()
  }

  const handleArchive = async (ws: Workspace) => {
    try {
      setMutating(true)
      const success = await updateWorkspace({
        workspaceId: ws.workspaceId,
        state: 'archived',
      })

      if (!success) throw new Error('Archive failed')

      // Update local state
      setWorkspaces((prev) =>
        prev.map((w) =>
          w.workspaceId === ws.workspaceId
            ? { ...w, state: 'archived' }
            : w
        )
      )

      setSnackbar({ open: true, message: 'Workspace archived successfully', severity: 'success' })
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.message || 'Failed to archive workspace', severity: 'error' })
    } finally {
      setMutating(false)
    }
  }

  const handleUnarchive = async (ws: Workspace) => {
    try {
      setMutating(true)
      const success = await updateWorkspace({
        workspaceId: ws.workspaceId,
        state: 'working',
      })

      if (!success) throw new Error('Unarchive failed')

      // Update local state
      setWorkspaces((prev) =>
        prev.map((w) =>
          w.workspaceId === ws.workspaceId
            ? { ...w, state: 'working' }
            : w
        )
      )

      setSnackbar({ open: true, message: 'Workspace unarchived successfully', severity: 'success' })
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.message || 'Failed to unarchive workspace', severity: 'error' })
    } finally {
      setMutating(false)
    }
  }

  const handleArchiveFromMenu = () => {
    if (menuAnchor?.workspace) {
      handleArchive(menuAnchor.workspace)
    }
    handleMenuClose()
  }

  const handleUnarchiveFromMenu = () => {
    if (menuAnchor?.workspace) {
      handleUnarchive(menuAnchor.workspace)
    }
    handleMenuClose()
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto', bgcolor: 'background.default', p: 2 }}>
      <Container maxWidth={false} disableGutters>
        {/* Header */}
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
            Workspaces
          </Typography>
          <Button onClick={handleOpenCreateWorkspaceModal}>
            Create Workspace
          </Button>
        </Box>

        {/* Search bar */}
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
            placeholder="Search by name, type, or description..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <Search size="20" />
              </InputAdornment>
            }
            sx={{
              bgcolor: (t) => t.palette.mode === 'light' ? '#FFFFFF' : t.palette.background.paper,
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
              <Grid size="20" />
            </ToggleButton>
            <ToggleButton value="table" aria-label="table view">
              <List size="20" />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Tabs */}
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Box
            sx={(t) => ({
              display: 'inline-flex',
              bgcolor:
                t.palette.mode === 'light'
                  ? alpha(t.palette.primary.main, 0.20)
                  : alpha(t.palette.primary.main, 0.25),
              borderRadius: 0.5,
              p: 0.75,
            })}
          >
            <Tabs
              value={activeTab}
              onChange={(_, newValue) => setActiveTab(newValue)}
              TabIndicatorProps={{ style: { display: 'none' } }}
              variant="standard"
              sx={{
                minHeight: 0,
                '& .MuiTabs-flexContainer': {
                  gap: 0.5,
                },
              }}
            >
              {['mine', 'others'].map((value) => {
                const selected = activeTab === value
                const label = value === 'mine' ? 'My Workspaces' : 'Other Workspaces'
                return (
                  <Tab
                    key={value}
                    label={label}
                    value={value}
                    disableRipple
                    sx={{
                      textTransform: 'none',
                      minHeight: 0,
                      px: 1.5,
                      borderRadius: 0.5,
                      fontWeight: selected ? 600 : 500,
                      fontSize: 14,
                      color: selected
                        ? theme.palette.primary.main
                        : theme.palette.text.secondary,
                      bgcolor: selected
                        ? theme.palette.background.default
                        : 'transparent',
                      '&:hover': {
                        bgcolor: selected
                          ? theme.palette.background.default
                          : alpha(theme.palette.common.white, 0.3),
                      },
                      '&:focus, &:focus-visible': {
                        outline: 'none',
                        boxShadow: 'none',
                      },
                    }}
                  />
                )
              })}
            </Tabs>
          </Box>
          {!loading && !error && filtered.length > 0 && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              Showing {startIndex + 1}-{Math.min(endIndex, filtered.length)} of {filtered.length}
            </Typography>
          )}
        </Box>

        {/* Filters + Sort row */}
        <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Filters */}
          <Box sx={{ position: 'relative', flexShrink: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box ref={filtersAnchorRef} sx={{ display: 'inline-flex' }}>
                <Chip
                  label="Filters"
                  size="medium"
                  icon={<Filter size={16} />}
                  onClick={handleToggleFilters}
                  onDelete={handleToggleFilters}
                  deleteIcon={isFiltersOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  sx={{
                    bgcolor:
                      theme.palette.mode === 'dark'
                        ? alpha(theme.palette.common.white, 0.12)
                        : theme.palette.common.white,
                    borderColor: 'divider',
                    borderWidth: 1,
                    borderStyle: 'solid',
                    fontSize: 16,
                    color: 'text.primary',
                    '& .MuiChip-deleteIcon': {
                      color: 'text.primary',
                      '&:hover': {
                        opacity: 0.7,
                      },
                    },
                  }}
                />
              </Box>
              {statusFilter !== 'all' && (
                <Chip
                  label={statusFilter === 'active' ? 'Active' : 'Archived'}
                  size="medium"
                  onDelete={() => {
                    setStatusFilter('all')
                    setDraftStatusFilter('all')
                  }}
                  deleteIcon={<Close size={12} />}
                  sx={{
                    bgcolor: alpha(theme.palette.primary.main, 0.2),
                    borderColor: theme.palette.primary.main,
                    borderWidth: 1,
                    borderStyle: 'solid',
                    fontWeight: 600,
                    color: theme.palette.primary.main,
                    '& .MuiChip-deleteIcon': {
                      color: theme.palette.primary.main,
                      '&:hover': {
                        color: theme.palette.primary.dark,
                      },
                    },
                  }}
                />
              )}
            </Box>
            {isFiltersOpen && (
              <Popper
                open={isFiltersOpen}
                anchorEl={filtersAnchorRef.current}
                placement="bottom-start"
                modifiers={[{ name: 'offset', options: { offset: [0, 8] } }]}
                sx={{ zIndex: 1300 }}
              >
                <Paper
                  variant="outlined"
                  sx={{
                    p: 0,
                    width: 'min(520px, calc(100vw - 32px))',
                    minWidth: 320,
                    borderColor: 'divider',
                    boxShadow: theme.shadows[2],
                    bgcolor:
                      theme.palette.mode === 'dark'
                        ? theme.palette.background.paper
                        : theme.palette.common.white,
                    borderRadius: 1,
                    overflow: 'hidden',
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      minHeight: 220,
                    }}
                  >
                    <Box
                      sx={{
                        width: 180,
                        borderRight: '1px solid',
                        borderColor: 'divider',
                        p: 2,
                      }}
                    >
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.secondary' }}>
                        Filters
                      </Typography>
                      <Box
                        sx={{
                          mt: 1,
                          px: 1,
                          py: 0.75,
                          borderRadius: 0.75,
                          bgcolor: alpha(theme.palette.primary.main, 0.12),
                          color: theme.palette.primary.main,
                          fontWeight: 600,
                          fontSize: 13,
                        }}
                      >
                        Status
                      </Box>
                    </Box>
                    <Box sx={{ flex: 1, p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, color: 'text.secondary' }}>
                        Status
                      </Typography>
                      <RadioGroup
                        value={draftStatusFilter}
                        onChange={(event) => {
                          setDraftStatusFilter(event.target.value as 'all' | 'active' | 'archived')
                        }}
                      >
                        <FormControlLabel value="all" control={<Radio size="small" />} label="All" />
                        <FormControlLabel value="active" control={<Radio size="small" />} label="Active" />
                        <FormControlLabel value="archived" control={<Radio size="small" />} label="Archived" />
                      </RadioGroup>
                    </Box>
                  </Box>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'flex-end',
                      gap: 1,
                      px: 2,
                      py: 1.5,
                      borderTop: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ mr: 1 }}>
                      <Button size="sm" variant="outline" onClick={handleResetFilters}>
                        Reset
                      </Button>
                    </Box>
                    <Button size="sm" onClick={handleApplyFilters}>
                      Apply
                    </Button>
                  </Box>
                </Paper>
              </Popper>
            )}
          </Box>

          {/* Sort */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0, ml: 'auto' }}>
            <FormControl sx={{ minWidth: 150 }}>
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                size="small"
                displayEmpty
                renderValue={(value) => {
                  const labels: Record<typeof sortBy, string> = {
                    'name-asc': 'Name A-Z',
                    'name-desc': 'Name Z-A',
                    'date-newest': 'Newest',
                    'date-oldest': 'Oldest',
                    'modified-recent': 'Recently Modified',
                  }
                  const key = value as typeof sortBy
                  return (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <FunnelSort size={16} />
                      <span>{labels[key]}</span>
                    </Box>
                  )
                }}
                sx={{
                  bgcolor: (t) => t.palette.mode === 'light' ? '#FFFFFF' : t.palette.background.paper,
                  borderRadius: 0.5,
                  '& .MuiSelect-select': {
                    py: 0.75,
                    px: 1.5,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  },
                }}
              >
                <MenuItem value="name-asc">Name A-Z</MenuItem>
                <MenuItem value="name-desc">Name Z-A</MenuItem>
                <MenuItem value="date-newest">Newest</MenuItem>
                <MenuItem value="date-oldest">Oldest</MenuItem>
                <MenuItem value="modified-recent">Recently Modified</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        {/* Content */}
        {loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : filtered.length === 0 ? (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', py: 8 }}>
            <Typography variant="h6">
              {statusFilter === 'archived'
                ? 'No archived workspaces'
                : activeTab === 'mine'
                ? 'No workspaces created by you'
                : 'No workspaces found'}
            </Typography>
            <Typography variant="body2">
              {statusFilter === 'archived'
                ? 'All workspaces are active'
                : activeTab === 'mine'
                ? 'Create a new workspace to get started'
                : 'Try adjusting your filters or search'}
            </Typography>
          </Box>
        ) : viewMode === 'cards' ? (
          <>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: 'repeat(2, 1fr)',
                  md: 'repeat(2, 1fr)',
                  lg: 'repeat(3, 1fr)',
                  xl: 'repeat(3, 1fr)',
                },
                gap: 2,
              }}
            >
              {paginatedWorkspaces.map((ws) => (
              <Paper
                key={ws.workspaceId}
                elevation={0}
                onClick={() => !selectingWorkspace && handleSelect(ws)}
                sx={{
                  borderRadius: 0.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  cursor: selectingWorkspace ? 'default' : 'pointer',
                  transition: 'all 0.2s ease',
                  bgcolor: (t) => t.palette.mode === 'light' ? '#FFFFFF' : t.palette.background.paper,
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  py: 1,
                  px: 2,
                  position: 'relative',
                  opacity: selectingWorkspace && selectingWorkspace !== ws.workspaceId ? 0.5 : 1,
                  pointerEvents: selectingWorkspace ? 'none' : 'auto',
                  '&:hover': selectingWorkspace ? {} : {
                    borderColor: 'primary.main',
                    boxShadow: (t) => t.palette.mode === 'dark' 
                      ? '0 2px 8px rgba(0,0,0,0.4)' 
                      : '0 2px 8px rgba(0,0,0,0.1)',
                  },
                }}
              >
                {/* Loading overlay when this workspace is being selected */}
                {selectingWorkspace === ws.workspaceId && (
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      bgcolor: alpha(theme.palette.background.paper, 0.8),
                      borderRadius: 0.5,
                      zIndex: 1,
                    }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                )}
                {/* Three-dot menu button in top right */}
                <IconButton
                  size="small"
                  aria-label={`More actions for ${ws.name}`}
                  onClick={(e) => handleMenuOpen(e, ws)}
                  sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    '&:hover': {
                      bgcolor: 'action.hover',
                    },
                  }}
                >
                  <OverflowMenuVertical size="18" />
                </IconButton>
                {/* Badges/Tags at the top */}
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1 }}>
                  {/* Visibility badge - shows stage on hover (easter egg for dev) */}
                  <Box
                    component="span"
                    title={ws.state === 'setup' && ws.setupStage ? `Stage: ${ws.setupStage}` : ws.state || ''}
                    sx={{
                      p: 0.5,
                      borderRadius: 0.5,
                      fontSize: 12,
                      fontWeight: 500,
                      textTransform: 'capitalize',
                      bgcolor: alpha(theme.palette.primary.main, 0.2),
                      color: theme.palette.primary.main,
                      border: '1px solid',
                      borderColor: theme.palette.primary.main,
                      cursor: 'default',
                      '&:hover': {
                        '&::after': {
                          content: ws.state === 'setup' && ws.setupStage
                            ? `" (${ws.setupStage.replace(/_/g, ' ')})"`
                            : ws.state
                              ? `" (${ws.state})"`
                              : '""',
                          fontSize: 10,
                          opacity: 0.8,
                        },
                      },
                    }}
                  >
                    {ws.visibility || 'Private'}
                  </Box>
                  {ws.companyId && companyNames.get(ws.companyId) ? (
                    <Box
                      component="span"
                      title="Company"
                      sx={{
                        p: 0.5,
                        borderRadius: 0.5,
                        fontSize: 12,
                        fontWeight: 500,
                        bgcolor: alpha(theme.palette.secondary.main, 0.2),
                        color: theme.palette.secondary.main,
                        border: '1px solid',
                        borderColor: theme.palette.secondary.main,
                        cursor: 'default',
                      }}
                    >
                      {companyNames.get(ws.companyId)}
                    </Box>
                  ) : null}
                  {ws.ontologyId && ontologyLookup.get(ws.ontologyId) ? (
                    <Box
                      component="span"
                      title="Ontology"
                      sx={{
                        p: 0.5,
                        borderRadius: 0.5,
                        fontSize: 12,
                        fontWeight: 500,
                        bgcolor: alpha(theme.palette.info.main, 0.2),
                        color: theme.palette.info.main,
                        border: '1px solid',
                        borderColor: theme.palette.info.main,
                        cursor: 'default',
                      }}
                    >
                      {ontologyLookup.get(ws.ontologyId)!.name} ({ontologyLookup.get(ws.ontologyId)!.semVer})
                    </Box>
                  ) : null}
                </Box>
                {/* Title */}
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    mb: 1,
                    pr: 4, // Space for menu button
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    lineHeight: 1.3,
                    fontSize: '1.125rem',
                    color: 'text.primary',
                  }}
                >
                  {ws.name}
                </Typography>

                {/* Metadata section */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    <strong>Creator:</strong> {ws.ownerUserId ? (users.get(ws.ownerUserId)?.displayName || 'Unknown') : 'Unknown'}
                    {ws.ownerUserId && users.get(ws.ownerUserId)?.email && ` (${users.get(ws.ownerUserId)?.email})`}
                  </Typography>
                </Box>
                
                {/* Description */}
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                    minHeight: '2.625rem',
                    mb: 1,
                  }}
                >
                  {ws.description || 'Primary object of analysis for workspace. We need data from the last 90 days to identify patterns and trends.'}
                </Typography>

                {/* Dates in single line at bottom */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 'auto' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    <strong>Created:</strong> {formatDate(ws.createdAt)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    <strong>Last modified:</strong> {formatDateTime(ws.updatedAt)}
                  </Typography>
                </Box>
              </Paper>
            ))}
          </Box>
          
          {/* Pagination for cards view */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
                showFirstButton
                showLastButton
              />
            </Box>
          )}
        </>
        ) : (
          // 🔹 TABLE VIEW
          <>
            <TableContainer component={Box} sx={{ border: '1px solid', borderColor: 'divider' }}>
              <Table sx={{ minWidth: 650 }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Creator</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Company</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Ontology</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Visibility</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Created</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Last modified</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedWorkspaces.map((ws) => (
                  <TableRow
                    key={ws.workspaceId}
                    hover
                    onClick={() => handleSelect(ws)}
                    sx={{
                      cursor: 'pointer',
                      '&:nth-of-type(odd)': {
                        bgcolor: alpha(theme.palette.action.hover, 0.02),
                      },
                      '&:last-child td, &:last-child th': { border: 0 },
                    }}
                  >
                    <TableCell component="th" scope="row">
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {ws.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {ws.ownerUserId ? (users.get(ws.ownerUserId)?.displayName || 'Unknown') : 'Unknown'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {ws.companyId && companyNames.get(ws.companyId) ? companyNames.get(ws.companyId) : ''}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {ws.ontologyId && ontologyLookup.get(ws.ontologyId)
                          ? `${ontologyLookup.get(ws.ontologyId)!.name} (${ontologyLookup.get(ws.ontologyId)!.semVer})`
                          : ''}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box
                        component="span"
                        title={ws.state === 'setup' && ws.setupStage ? `Stage: ${ws.setupStage}` : ws.state || ''}
                        sx={{
                          p: 0.5,
                          borderRadius: 0.5,
                          fontSize: 12,
                          fontWeight: 500,
                          textTransform: 'capitalize',
                          bgcolor: alpha(theme.palette.primary.main, 0.2),
                          color: theme.palette.primary.main,
                          border: '1px solid',
                          borderColor: theme.palette.primary.main,
                          display: 'inline-block',
                          cursor: 'default',
                        }}
                      >
                        {ws.visibility || 'Private'}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {ws.description || 'No description'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {formatDate(ws.createdAt)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {formatDateTime(ws.updatedAt)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <IconButton
                          size="small"
                          aria-label={`More actions for ${ws.name}`}
                          onClick={(e) => handleMenuOpen(e, ws)}
                        >
                          <OverflowMenuVertical size="18" />
                        </IconButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          
          {/* Pagination for table view */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
                showFirstButton
                showLastButton
              />
            </Box>
          )}
        </>
        )}


        {/* Dialogs */}
        {/* Edit Workspace Dialog */}
        <Modal
          open={editDialog.open}
          onClose={() => !mutating && setEditDialog({ open: false, workspace: null })}
          aria-labelledby="edit-workspace-modal-title"
        >
          <Paper
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '90%',
              maxWidth: 600,
              maxHeight: '85vh',
              overflow: 'auto',
              p: 0,
              borderRadius: 1,
              outline: 'none',
              bgcolor: theme.palette.mode === 'light' ? '#FFFFFF' : '#1C1C1C',
            }}
          >
            {/* Modal Header */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 3,
                py: 2,
                borderBottom: '1px solid',
                borderColor: 'divider',
                position: 'sticky',
                top: 0,
                bgcolor: theme.palette.mode === 'light' ? '#1C1C1C' : '#F4F0E6',
                zIndex: 1,
              }}
            >
              <Typography
                id="edit-workspace-modal-title"
                variant="h6"
                sx={{
                  fontWeight: 600,
                  color: theme.palette.mode === 'light' ? '#F4F0E6' : '#1C1C1C',
                }}
              >
                Edit Workspace
              </Typography>
              <IconButton
                size="small"
                onClick={() => !mutating && setEditDialog({ open: false, workspace: null })}
                sx={{
                  color: theme.palette.mode === 'light' ? '#F4F0E6' : '#1C1C1C',
                }}
              >
                <Close size={20} />
              </IconButton>
            </Box>

            {/* Modal Content */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 3 }}>
              <TextField
                label="Name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                fullWidth
                required
                disabled={mutating}
              />
              <TextField
                label="Description"
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                fullWidth
                multiline
                rows={3}
                disabled={mutating}
              />
              <FormControl component="fieldset" disabled={mutating}>
                <FormLabel component="legend">Visibility</FormLabel>
                <RadioGroup
                  value={editForm.visibility}
                  onChange={(e) => setEditForm({ ...editForm, visibility: e.target.value })}
                >
                  <FormControlLabel value="private" control={<Radio />} label="Private" />
                  <FormControlLabel value="public" control={<Radio />} label="Public" />
                </RadioGroup>
              </FormControl>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1.5, px: 3, pb: 3 }}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditDialog({ open: false, workspace: null })}
                disabled={mutating}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveEdit}
                disabled={mutating || !editForm.name.trim()}
              >
                Save
              </Button>
            </Box>
          </Paper>
        </Modal>

        {/* Delete Workspace Dialog */}
        <Dialog
          open={deleteConfirmation.open}
          onClose={() => setDeleteConfirmation({ open: false, workspace: null })}
        >
          <DialogTitle>Delete Workspace</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete workspace "{deleteConfirmation.workspace?.name}"? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ mb: 2, mr: 2 }}>
            <Button
            variant="outline"
            size="sm"
            onClick={() => setDeleteConfirmation({ open: false, workspace: null })}>
              Cancel
            </Button>
            <Button
            size="sm"
            onClick={handleConfirmDelete}
            color="error"
            disabled={mutating}>
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        <CreateWorkspaceModal
          open={createWorkspaceModalOpen}
          onClose={() => setCreateWorkspaceModalOpen(false)}
          onCreated={handleCreateWorkspaceCreated}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>

        {/* Three-dot menu */}
        <Menu
          anchorEl={menuAnchor?.element}
          open={Boolean(menuAnchor)}
          onClose={handleMenuClose}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
          slotProps={{
            paper: {
              sx: {
                py: 1,
                minWidth: 180,
                borderRadius: 0.5,
              }
            }
          }}
        >
          <MenuItem 
            onClick={handleEditFromMenu}
            sx={{ px: 2.5, py: 1.25 }}
          >
            <ListItemIcon>
              <Edit size="18" />
            </ListItemIcon>
            <ListItemText>Edit</ListItemText>
          </MenuItem>
          {menuAnchor?.workspace && menuAnchor.workspace.state !== 'archived' && (
            <MenuItem 
              onClick={handleArchiveFromMenu}
              sx={{ px: 2.5, py: 1.25 }}
            >
              <ListItemIcon>
                <Archive size="18" />
              </ListItemIcon>
              <ListItemText>Archive</ListItemText>
            </MenuItem>
          )}
          {menuAnchor?.workspace && menuAnchor.workspace.state === 'archived' && (
            <MenuItem 
              onClick={handleUnarchiveFromMenu}
              sx={{ px: 2.5, py: 1.25 }}
            >
              <ListItemIcon>
                <Restart size="18" />
              </ListItemIcon>
              <ListItemText>Unarchive</ListItemText>
            </MenuItem>
          )}
          <MenuItem 
            onClick={handleDeleteFromMenu}
            sx={{ px: 2.5, py: 1.25 }}
          >
            <ListItemIcon>
              <TrashCan size="18" />
            </ListItemIcon>
            <ListItemText sx={{ color: 'error.main' }}>Delete</ListItemText>
          </MenuItem>
        </Menu>
      </Container>
    </Box>
  )
}
