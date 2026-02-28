import { useEffect, useMemo, useState, useRef } from 'react'
import {
  Box,
  CircularProgress,
  MenuItem,
  OutlinedInput,
  Paper,
  Select,
  Switch,
  Typography,
  InputAdornment,
  Tooltip,
  Snackbar,
  Alert,
} from '@mui/material'
import { DataGrid, type GridColDef, type GridRowSelectionModel } from '@mui/x-data-grid'
import { Search, ArrowLeft } from '@carbon/icons-react'
import {
  fetchGraphNodeTypes,
  fetchGraphNodesByType,
  type GraphNode,
  addWorkspaceNode,
  fetchWorkspaceItems,
} from '../../services/graphql'

import Button from '../common/Button'
import { DataLoadingOverlay } from '../common/DataLoadingOverlay'

type WorkspaceFilter = 'all' | 'in' | 'out'

// Helper to save nodes
async function saveNodesToWorkspace(workspaceId: string, nodeIds: string[], allNodes: GraphNode[]) {
  const nodeById = new Map(allNodes.map((n) => [n.id, n]))
  for (const id of nodeIds) {
    const labels = nodeById.get(id)?.labels || []
    await addWorkspaceNode({
      workspaceId,
      graphNodeId: id,
      graphEdgeId: null,
      labels,
      pinnedBy: '11111111-1111-1111-1111-111111111111', // TODO: Get from JWT if backend doesn't handle it
    })
  }
}

// Shared Table Component
function EntityTable({
  allNodes,
  filteredNodes,
  loading,
  rowSelection,
  setRowSelection,
  selectedType,
  workspaceNodeIds,
}: {
  allNodes: GraphNode[]
  filteredNodes: GraphNode[]
  loading: boolean
  rowSelection: GridRowSelectionModel
  setRowSelection: (m: GridRowSelectionModel) => void
  selectedType?: string
  workspaceNodeIds?: Set<string>
}) {
  const propertyKeys = useMemo(() => {
    const keys = new Set<string>()
    allNodes.forEach((n) => n.properties.forEach((p) => keys.add(p.key)))
    // Filter out 'id' since it's already shown as a base column
    return Array.from(keys).filter((k) => k !== 'id').sort()
  }, [allNodes])

  const columns: GridColDef[] = useMemo(() => {
    const base: GridColDef[] = [
      {
        field: 'status',
        headerName: 'Status',
        minWidth: 70,
        width: 70,
        sortable: false,
        filterable: false,
        renderCell: (params) => {
          const nodeId = params.row.id as string
          const inWorkspace = workspaceNodeIds?.has(nodeId) ?? false
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '100%',
              }}
            >
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  bgcolor: inWorkspace ? 'success.main' : 'error.main',
                }}
              />
            </Box>
          )
        },
      },
      {
        field: 'id',
        headerName: 'ID',
        minWidth: 240,
        width: 240,
        renderCell: (params) => (
          <Box component="span" sx={{ whiteSpace: 'nowrap' }}>
            {params.value as string}
          </Box>
        ),
      },
    ]
    const propCols: GridColDef[] = propertyKeys.map((k) => ({
      field: k,
      headerName: k,
      minWidth: 160,
      width: 160,
      sortable: false,
      filterable: false,
    }))
    const all = [...base, ...propCols]
    if (all.length > 0) {
      const lastIndex = all.length - 1
      all[lastIndex] = {
        ...all[lastIndex],
        headerClassName: 'last-column',
        cellClassName: 'last-column',
      }
    }
    return all
  }, [propertyKeys, workspaceNodeIds])

  const rows = useMemo(() => {
    return filteredNodes.map((n) => {
      const row: Record<string, any> = { id: n.id }
      for (const { key, value } of n.properties) {
        row[key] = value ?? ''
      }
      return row
    })
  }, [filteredNodes])

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 0.5,
        overflow: 'hidden',
        bgcolor: 'background.default',
        width: '100%',
        maxWidth: '100%',
      }}
    >
      {/* Loading indicator row */}
      {loading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 2, color: 'text.secondary' }}>
          <CircularProgress size={18} />
          <Typography variant="body2">Loading…</Typography>
        </Box>
      )}

      <DataGrid
        autoHeight
        disableVirtualization
        rows={rows}
        columns={columns}
        checkboxSelection
        disableRowSelectionOnClick
        rowSelectionModel={rowSelection}
        onRowSelectionModelChange={(m) => setRowSelection(m)}
        density="compact"
        pagination
        pageSizeOptions={[25, 50, 100]}
        initialState={{ pagination: { paginationModel: { pageSize: 25, page: 0 } } }}
        loading={loading}
        sx={{
          border: 'none',
          fontSize: 13,

          '& .MuiDataGrid-columnHeader': {
            color: 'text.primary',
            borderRight: '1px solid',
            borderColor: 'divider',
            '&:focus, &:focus-within': { outline: 'none' },
          },
          '& .MuiDataGrid-columnHeader:first-of-type': {
            borderLeft: 'none',
          },
          '& .MuiDataGrid-columnHeader:last-of-type, & .MuiDataGrid-columnHeader.last-column': {
            borderRight: 'none',
          },
          '& .MuiDataGrid-columnHeaderTitle': {
            fontSize: 14,
            fontWeight: 600,
          },
          '& .MuiDataGrid-cell': {
            borderBottom: '1px solid',
            borderRight: '1px solid',
            borderColor: 'divider',
            color: 'text.primary',
            display: 'flex',
            alignItems: 'center',
            '&:focus, &:focus-within': { outline: 'none' },
          },
          '& .MuiDataGrid-row .MuiDataGrid-cell:first-of-type': {
            borderLeft: 'none',
          },
          '& .MuiDataGrid-row .MuiDataGrid-cell:last-of-type, & .MuiDataGrid-cell.last-column': {
            borderRight: 'none',
          },

          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'action.hover',
          },
          '& .MuiDataGrid-row.Mui-selected': {
            backgroundColor: (theme) => theme.palette.action.selected,
            '&:hover': {
              backgroundColor: (theme) => theme.palette.action.selected,
            },
          },

          '& .MuiDataGrid-checkboxInput': {
            color: 'text.secondary',
          },

          '& .MuiDataGrid-footerContainer': {
            borderTop: 'none',
            minHeight: 48,
            justifyContent: 'space-between',
          },
        }}
        slots={{
          noRowsOverlay: () => (
            <Box sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {selectedType ? 'No nodes found for this type.' : 'Select a node type to view nodes.'}
              </Typography>
            </Box>
          ),
        }}
        slotProps={{
          columnMenu: {
            sx: {
              backgroundColor: 'background.default',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 0.5,
            },
          } as any,
        }}
      />
    </Paper>
  )
}

// Section for a single type in Recommendations View
function EntitySection({ type, workspaceNodeIds }: { type: string; workspaceNodeIds?: Set<string> }) {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)
  const [rowSelection, setRowSelection] = useState<GridRowSelectionModel>([])

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      try {
        const n = await fetchGraphNodesByType(type)
        if (mounted) setNodes(n)
      } catch (e) {
        console.error(e)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [type])

  if (!loading && nodes.length === 0) return null

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ mb: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {type}
        </Typography>
      </Box>
      <EntityTable
        allNodes={nodes}
        filteredNodes={nodes}
        loading={loading}
        rowSelection={rowSelection}
        setRowSelection={setRowSelection}
        selectedType={type}
        workspaceNodeIds={workspaceNodeIds}
      />
    </Box>
  )
}

// Recommendations View
function RecommendationsView({
  types,
  onBack,
  workspaceNodeIds,
}: {
  types: string[]
  onBack: () => void
  workspaceNodeIds?: Set<string>
}) {
  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3,
          position: 'sticky',
          top: 51,
          zIndex: 10,
          bgcolor: 'background.default',
          py: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box
          onClick={onBack}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            cursor: 'pointer',
            color: 'text.secondary',
            '&:hover': { color: 'text.primary' }
          }}
        >
          <ArrowLeft size={16} />
          <Typography variant="body2" sx={{ fontWeight: 700 }}>Go back</Typography>
        </Box>
        <Button size="sm" variant="primary">
          ADD ALL
        </Button>
      </Box>

      {types.map((t) => (
        <EntitySection key={t} type={t} workspaceNodeIds={workspaceNodeIds} />
      ))}
    </Box>
  )
}

// Default View
function DefaultEntitiesView({
  workspaceId,
  types,
  workspaceNodeIds,
  onRefreshWorkspace,
}: {
  workspaceId?: string | null
  types: string[]
  workspaceNodeIds?: Set<string>
  onRefreshWorkspace: () => void
}) {
  const [loadingNodes, setLoadingNodes] = useState(false)
  const [selectedType, setSelectedType] = useState<string>('')
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [rowSelection, setRowSelection] = useState<GridRowSelectionModel>([])
  const [saving, setSaving] = useState(false)
  const [workspaceFilter, setWorkspaceFilter] = useState<WorkspaceFilter>('all')
  const [showChanged, setShowChanged] = useState(false)
  
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })

  // Initialize selectedType
  useEffect(() => {
    if (types.length > 0 && !selectedType) {
      setSelectedType(types[0])
    }
  }, [types, selectedType])

  useEffect(() => {
    let mounted = true
    async function loadNodes() {
      if (!selectedType) return
      setLoadingNodes(true)
      setError(null)
      try {
        const n = await fetchGraphNodesByType(selectedType)
        if (!mounted) return
        setNodes(n)
      } catch (e: any) {
        if (!mounted) return
        setError(e?.message || 'Failed to load nodes')
      } finally {
        if (mounted) setLoadingNodes(false)
      }
    }
    loadNodes()
    return () => {
      mounted = false
    }
  }, [selectedType])

  const filteredNodes = useMemo(() => {
    let filtered = nodes

    // Apply workspace filter
    if (workspaceNodeIds && workspaceFilter !== 'all') {
      filtered = filtered.filter((n) => {
        const inWorkspace = workspaceNodeIds.has(n.id)
        return workspaceFilter === 'in' ? inWorkspace : !inWorkspace
      })
    }

    // Apply search query
    const q = query.trim().toLowerCase()
    if (q) {
      filtered = filtered.filter((n) => {
        if (n.id.toLowerCase().includes(q)) return true
        return n.properties.some((p) => `${p.key}:${p.value}`.toLowerCase().includes(q))
      })
    }

    return filtered
  }, [nodes, query, workspaceFilter, workspaceNodeIds])

  async function handleSaveSelected() {
    if (!workspaceId) return
    const ids = (rowSelection || []).map(String)
    if (ids.length === 0) return
    setSaving(true)
    setError(null)
    
    // Ensure loading state lasts at least 3 seconds
    const minDelay = new Promise((resolve) => setTimeout(resolve, 3000))

    try {
      await Promise.all([
        saveNodesToWorkspace(workspaceId, ids, nodes),
        minDelay
      ])
      
      onRefreshWorkspace()
      setRowSelection([])
      setSnackbar({
        open: true,
        message: `Saved ${ids.length} item(s) to workspace.`,
        severity: 'success',
      })
    } catch (e: any) {
      setError(e?.message || 'Failed to save to workspace')
      setSnackbar({
        open: true,
        message: e?.message || 'Failed to save to workspace',
        severity: 'error',
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Box sx={{ position: 'relative', minHeight: 360, overflow: 'hidden' }}>
      {saving && <DataLoadingOverlay variant="container" />}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
          minHeight: 40,
        }}
      >
        <OutlinedInput
          placeholder="Search"
          size="small"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          startAdornment={
            <InputAdornment position="start">
              <Search size="18" />
            </InputAdornment>
          }
          sx={{ width: '100%' }}
        />
      </Box>

      {/* Filter row */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          mb: 2,
          flexWrap: 'wrap',
        }}
      >
        <Select
          size="small"
          value={selectedType || ''}
          onChange={(e) => setSelectedType(e.target.value as string)}
          sx={{ minWidth: 200 }}
          disabled={types.length === 0}
        >
          {types.map((t) => (
            <MenuItem key={t} value={t}>
              {t}
            </MenuItem>
          ))}
        </Select>

        <Select
          size="small"
          value={workspaceFilter}
          onChange={(e) => setWorkspaceFilter(e.target.value as WorkspaceFilter)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="all">Show all</MenuItem>
          <MenuItem value="in">In Workspace</MenuItem>
          <MenuItem value="out">Not in Workspace</MenuItem>
        </Select>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.75,
              cursor: 'default',
            }}
          >
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: 'success.main',
              }}
            />
            <Typography variant="body2">In Workspace</Typography>
          </Box>

          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.75,
              cursor: 'default',
            }}
          >
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: 'error.main',
              }}
            />
            <Typography variant="body2">Not in Workspace</Typography>
          </Box>

          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.5,
              cursor: 'pointer',
            }}
            onClick={() => setShowChanged(!showChanged)}
          >
            <Switch
              size="small"
              checked={showChanged}
              onChange={(e) => setShowChanged(e.target.checked)}
              sx={{
                '& .MuiSwitch-switchBase.Mui-checked': {
                  color: 'background.paper',
                },
                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                  backgroundColor: 'secondary.main',
                  opacity: 1,
                },
              }}
            />
            <Typography variant="body2" color="text.secondary">
              Changed last 7 days
            </Typography>
          </Box>

          {(rowSelection?.length || 0) > 0 && (
            <Tooltip title={workspaceId ? '' : 'Select a workspace first'} disableHoverListener={!!workspaceId}>
              <span>
                <Button size="sm" onClick={handleSaveSelected} disabled={!workspaceId || saving}>
                  Add to workspace
                </Button>
              </span>
            </Tooltip>
          )}
        </Box>

        <Box sx={{ flex: 1 }} />

        {/* Temporary Debug Button */}
        {/* <Button size="sm" variant="secondary" onClick={() => {
          setSaving(true)
          setTimeout(() => setSaving(false), 5000)
        }}>
          Test Animation
        </Button> */}

      </Box>

      {error ? (
        <Typography color="error" variant="body2" sx={{ mb: 1 }}>
          {error}
        </Typography>
      ) : null}

      <EntityTable
        allNodes={nodes}
        filteredNodes={filteredNodes}
        loading={loadingNodes}
        rowSelection={rowSelection}
        setRowSelection={setRowSelection}
        selectedType={selectedType}
        workspaceNodeIds={workspaceNodeIds}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

// Main Component
export default function EntitiesView({ workspaceId }: { workspaceId?: string | null }) {
  const [loadingTypes, setLoadingTypes] = useState(false)
  const [types, setTypes] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'default' | 'recommendations'>('default')
  const [workspaceNodeIds, setWorkspaceNodeIds] = useState<Set<string>>(new Set())
  const workspaceIdRef = useRef<string | null | undefined>(workspaceId)

  const refreshWorkspaceItems = async () => {
    const currentWorkspaceId = workspaceIdRef.current
    if (!currentWorkspaceId) {
      setWorkspaceNodeIds(new Set())
      return
    }
    try {
      const items = await fetchWorkspaceItems(currentWorkspaceId)
      // Check if workspaceId hasn't changed before updating state
      if (workspaceIdRef.current !== currentWorkspaceId) return
      // Extract node IDs from workspace items (filter out edges)
      const nodeIds = new Set(items.filter((i) => !i.graphEdgeId).map((i) => i.graphNodeId))
      setWorkspaceNodeIds(nodeIds)
    } catch (e) {
      console.error('Failed to load workspace items:', e)
      // Check if workspaceId hasn't changed before updating state
      if (workspaceIdRef.current !== currentWorkspaceId) return
      setWorkspaceNodeIds(new Set())
    }
  }

  useEffect(() => {
    let mounted = true
    async function loadTypes() {
      setLoadingTypes(true)
      setError(null)
      try {
        const t = await fetchGraphNodeTypes()
        if (!mounted) return
        setTypes(t)
      } catch (e: any) {
        if (!mounted) return
        setError(e?.message || 'Failed to load node types')
      } finally {
        if (mounted) setLoadingTypes(false)
      }
    }
    loadTypes()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    let mounted = true
    workspaceIdRef.current = workspaceId
    async function loadWorkspaceItems() {
      if (!workspaceId) {
        if (mounted) setWorkspaceNodeIds(new Set())
        return
      }
      try {
        const items = await fetchWorkspaceItems(workspaceId)
        if (!mounted) return
        // Check if workspaceId hasn't changed during the fetch
        if (workspaceIdRef.current !== workspaceId) return
        // Extract node IDs from workspace items (filter out edges)
        const nodeIds = new Set(items.filter((i) => !i.graphEdgeId).map((i) => i.graphNodeId))
        setWorkspaceNodeIds(nodeIds)
      } catch (e) {
        if (!mounted) return
        // Check if workspaceId hasn't changed during the fetch
        if (workspaceIdRef.current !== workspaceId) return
        console.error('Failed to load workspace items:', e)
        setWorkspaceNodeIds(new Set())
      }
    }
    loadWorkspaceItems()
    return () => {
      mounted = false
    }
  }, [workspaceId])

  if (loadingTypes) {
    return (
      <Box sx={{ position: 'relative', minHeight: 360, overflow: 'hidden' }}>
        <DataLoadingOverlay message="Loading data" variant="container" />
      </Box>
    )
  }

  if (error) {
    return (
      <Typography color="error" variant="body2" sx={{ mb: 1 }}>
        {error}
      </Typography>
    )
  }

  return viewMode === 'recommendations' ? (
    <RecommendationsView 
      types={types} 
      onBack={() => setViewMode('default')}
      workspaceNodeIds={workspaceNodeIds}
    />
  ) : (
    <DefaultEntitiesView
      types={types}
      workspaceId={workspaceId}
      workspaceNodeIds={workspaceNodeIds}
      onRefreshWorkspace={refreshWorkspaceItems}
    />
  )
}
