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
  Chip,
  IconButton,
} from '@mui/material'
import { Search, Grid, List } from '@carbon/icons-react'
import { Settings, CloudUpload, Description } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import {
  fetchOntologies,
  deleteOntology,
  type Ontology,
} from '../services/graphql'
import Button from '../components/common/Button'
import Neo4jSettingsModal from '../components/ontology/Neo4jSettingsModal'
import DomainExamplesModal from '../components/ontology/DomainExamplesModal'
import { formatDateTime } from '../utils/formatUtils'

// Helper function to format dates
function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function OntologiesList() {
  const navigate = useNavigate()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>(() => {
    const saved = localStorage.getItem('ontologies:viewMode')
    return saved === 'table' || saved === 'cards' ? saved : 'cards'
  })
  const [sortBy, setSortBy] = useState<'name-asc' | 'name-desc' | 'date-newest' | 'date-oldest' | 'modified-recent'>('date-newest')
  const [page, setPage] = useState(1)
  const itemsPerPage = 12
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)
  const [selectedOntologyForSettings, setSelectedOntologyForSettings] = useState<Ontology | null>(null)
  const [domainExamplesModalOpen, setDomainExamplesModalOpen] = useState(false)
  const [selectedOntologyForDomainExamples, setSelectedOntologyForDomainExamples] = useState<Ontology | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchOntologies()
        if (!active) return
        setOntologies(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load ontologies')
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
    let result = [...ontologies]

    // Filter by search query
    if (query.trim()) {
      const q = query.toLowerCase()
      result = result.filter(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          (o.description && o.description.toLowerCase().includes(q)) ||
          o.semVer.toLowerCase().includes(q) ||
          o.status.toLowerCase().includes(q)
      )
    }

    // Sort
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
          return (b.lastEdit ? new Date(b.lastEdit).getTime() : 0) - (a.lastEdit ? new Date(a.lastEdit).getTime() : 0)
        default:
          return 0
      }
    })

    return result
  }, [ontologies, query, sortBy])

  // Pagination calculations
  const totalPages = Math.ceil(filtered.length / itemsPerPage)
  const startIndex = (page - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedOntologies = filtered.slice(startIndex, endIndex)

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [query, sortBy])

  const handleSelect = (ontology: Ontology) => {
    navigate(`/knowledge/ontology/${ontology.ontologyId}`)
  }

  const handleCreate = () => {
    navigate('/knowledge/ontology/create')
  }

  const handleLoadDataForOntology = (ontology: Ontology, e: React.MouseEvent) => {
    e.stopPropagation()
    navigate(`/knowledge/data-loader?ontologyId=${ontology.ontologyId}`)
  }

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'cards' | 'table' | null) => {
    if (newMode !== null) {
      setViewMode(newMode)
      localStorage.setItem('ontologies:viewMode', newMode)
    }
  }

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  const handleOpenSettings = (ontology: Ontology, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedOntologyForSettings(ontology)
    setSettingsModalOpen(true)
  }

  const handleCloseSettings = () => {
    setSettingsModalOpen(false)
    setSelectedOntologyForSettings(null)
  }

  const handleSettingsSuccess = () => {
    setSnackbar({
      open: true,
      message: 'Neo4j connection settings saved successfully',
      severity: 'success',
    })
  }

  const handleOpenDomainExamples = (ontology: Ontology, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedOntologyForDomainExamples(ontology)
    setDomainExamplesModalOpen(true)
  }

  const handleCloseDomainExamples = () => {
    setDomainExamplesModalOpen(false)
    setSelectedOntologyForDomainExamples(null)
  }

  const handleDomainExamplesSuccess = async () => {
    setSnackbar({
      open: true,
      message: 'Domain examples saved successfully',
      severity: 'success',
    })
    const data = await fetchOntologies()
    setOntologies(data)
  }


  const getStatusColor = (status: string): 'default' | 'primary' | 'success' | 'warning' | 'error' => {
    switch (status.toLowerCase()) {
      case 'finalized':
        return 'success'
      case 'draft':
        return 'warning'
      default:
        return 'default'
    }
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
            Ontologies
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button onClick={handleCreate}>Create Ontology</Button>
          </Box>
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
            placeholder="Search by name, description, or version..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <Search size="20" />
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
              <Grid size="20" />
            </ToggleButton>
            <ToggleButton value="table" aria-label="table view">
              <List size="20" />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Sort and filter controls */}
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
                '&:hover': {
                  borderColor: 'primary.main',
                },
              }}
            >
              <option value="date-newest">Newest First</option>
              <option value="date-oldest">Oldest First</option>
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
              <option value="modified-recent">Recently Modified</option>
            </Box>
          </Box>
          <Typography variant="body2" color="text.secondary">
            {filtered.length} {filtered.length === 1 ? 'ontology' : 'ontologies'}
          </Typography>
        </Box>

        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Loading State */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : filtered.length === 0 ? (
          <Paper
            variant="outlined"
            sx={{
              p: 6,
              textAlign: 'center',
              bgcolor: 'background.paper',
            }}
          >
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {query ? 'No ontologies found' : 'No ontologies yet'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {query
                ? 'Try adjusting your search terms'
                : 'Create your first ontology to get started'}
            </Typography>
            {!query && (
              <Button onClick={handleCreate}>Create Ontology</Button>
            )}
          </Paper>
        ) : viewMode === 'cards' ? (
          <>
            {/* Cards View */}
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
              {paginatedOntologies.map((ontology) => (
                <Paper
                  key={ontology.ontologyId}
                  variant="outlined"
                  sx={{
                    p: 2,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      boxShadow: 4,
                      transform: 'translateY(-2px)',
                    },
                    bgcolor: 'background.paper',
                  }}
                  onClick={() => handleSelect(ontology)}
                >
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="h6" fontWeight={600} sx={{ flex: 1, mr: 1 }}>
                      {ontology.name}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={(e) => handleLoadDataForOntology(ontology, e)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                            bgcolor: 'action.hover',
                          },
                        }}
                        aria-label="Load data for this ontology"
                        title="Load Data"
                      >
                        <CloudUpload fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => handleOpenDomainExamples(ontology, e)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                            bgcolor: 'action.hover',
                          },
                        }}
                        aria-label="Edit domain examples"
                        title="Domain examples"
                      >
                        <Description fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => handleOpenSettings(ontology, e)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                            bgcolor: 'action.hover',
                          },
                        }}
                        aria-label="Open Neo4j settings"
                      >
                        <Settings fontSize="small" />
                      </IconButton>
                      <Chip
                        label={ontology.status}
                        size="small"
                        color={getStatusColor(ontology.status)}
                        sx={{ flexShrink: 0 }}
                      />
                    </Box>
                  </Box>
                  {ontology.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, minHeight: 40 }}>
                      {ontology.description.length > 100
                        ? `${ontology.description.substring(0, 100)}...`
                        : ontology.description}
                    </Typography>
                  )}
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Version: {ontology.semVer}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Created: {formatDate(ontology.createdOn)}
                    </Typography>
                    {ontology.lastEdit && (
                      <Typography variant="caption" color="text.secondary">
                        Modified: {formatDate(ontology.lastEdit)}
                      </Typography>
                    )}
                  </Box>
                </Paper>
              ))}
            </Box>
            {/* Pagination */}
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
              </Box>
            )}
          </>
        ) : (
          <>
            {/* Table View */}
            <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'background.paper' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Version</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Created</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Last Modified</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedOntologies.map((ontology) => (
                    <TableRow
                      key={ontology.ontologyId}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleSelect(ontology)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {ontology.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {ontology.description || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{ontology.semVer}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={ontology.status} size="small" color={getStatusColor(ontology.status)} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDate(ontology.createdOn)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {formatDateTime(ontology.lastEdit, 'Never')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <IconButton
                            size="small"
                            onClick={(e) => handleLoadDataForOntology(ontology, e)}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': {
                                color: 'primary.main',
                                bgcolor: 'action.hover',
                              },
                            }}
                            aria-label="Load data for this ontology"
                            title="Load Data"
                          >
                            <CloudUpload fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => handleOpenDomainExamples(ontology, e)}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': {
                                color: 'primary.main',
                                bgcolor: 'action.hover',
                              },
                            }}
                            aria-label="Edit domain examples"
                            title="Domain examples"
                          >
                            <Description fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => handleOpenSettings(ontology, e)}
                            sx={{
                              color: 'text.secondary',
                              '&:hover': {
                                color: 'primary.main',
                                bgcolor: 'action.hover',
                              },
                            }}
                            aria-label="Open Neo4j settings"
                          >
                            <Settings fontSize="small" />
                          </IconButton>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            {/* Pagination */}
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
              </Box>
            )}
          </>
        )}

        {/* Snackbar for notifications */}
        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleCloseSnackbar}>
          <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>

        {/* Domain examples modal */}
        <DomainExamplesModal
          open={domainExamplesModalOpen}
          onClose={handleCloseDomainExamples}
          ontology={selectedOntologyForDomainExamples}
          onSuccess={handleDomainExamplesSuccess}
        />

        {/* Neo4j Settings Modal */}
        {selectedOntologyForSettings && (
          <Neo4jSettingsModal
            open={settingsModalOpen}
            onClose={handleCloseSettings}
            ontologyId={selectedOntologyForSettings.ontologyId}
            ontologyName={selectedOntologyForSettings.name}
            onSuccess={handleSettingsSuccess}
            onCloneSuccess={async (newOntologyId) => {
              const data = await fetchOntologies()
              setOntologies(data)
              setSnackbar({
                open: true,
                message: 'Ontology cloned successfully',
                severity: 'success',
              })
              navigate(`/knowledge/ontology/${newOntologyId}`)
            }}
            onDelete={async () => {
              try {
                await deleteOntology(selectedOntologyForSettings.ontologyId)
                setSnackbar({
                  open: true,
                  message: `Ontology "${selectedOntologyForSettings.name}" deleted successfully`,
                  severity: 'success',
                })
                // Refresh the ontologies list
                const data = await fetchOntologies()
                setOntologies(data)
                handleCloseSettings()
              } catch (e: any) {
                throw e // Re-throw to let the modal handle the error
              }
            }}
          />
        )}
      </Container>
    </Box>
  )
}
