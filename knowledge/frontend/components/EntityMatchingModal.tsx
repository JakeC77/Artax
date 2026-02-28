import { useCallback, useEffect, useState } from 'react'
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
} from '@mui/material'
import { Search, CloseOutline } from '@carbon/icons-react'
import { alpha, useTheme } from '@mui/material/styles'
import {
  fetchGraphNodeTypes,
  fetchGraphNodesByFuzzySearchOr,
  fetchOntologyPackage,
  type GraphNodeSearchResult,
  type GraphFilterGroupInput,
} from '../services/graphql'
import type { OntologyPackage } from '../types/ontology'
import Button from './common/Button'

export type EntityMatchingModalProps = {
  open: boolean
  onClose: () => void
  onSelect: (node: GraphNodeSearchResult) => void
  entityName: string
  entityType: 'source' | 'terminal'
  ontologyId?: string | null
  ontologyPackage?: OntologyPackage | null
}

export default function EntityMatchingModal({
  open,
  onClose,
  onSelect,
  entityName,
  entityType,
  ontologyId,
  ontologyPackage,
}: EntityMatchingModalProps) {
  const theme = useTheme()
  const [loadingNodeTypes, setLoadingNodeTypes] = useState(false)
  const [loadingMatches, setLoadingMatches] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nodeTypes, setNodeTypes] = useState<string[]>([])
  const [selectedNodeType, setSelectedNodeType] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>(entityName)
  const [matchingNodes, setMatchingNodes] = useState<GraphNodeSearchResult[]>([])

  // Load node types on mount
  useEffect(() => {
    if (!open) return
    let active = true
    async function load() {
      setLoadingNodeTypes(true)
      setError(null)
      try {
        // If ontology package is provided, use entity names from it
        if (ontologyPackage) {
          // Extract entity names from the ontology package directly
          const entityNames = ontologyPackage.entities.map((e) => e.name)
          setNodeTypes(entityNames)
          if (entityNames.length > 0 && !selectedNodeType) {
            setSelectedNodeType(entityNames[0])
          } else if (entityNames.length === 0) {
            setError('No entities found in the selected ontology')
          }
        } else if (ontologyId) {
          // If ontologyId is provided but package not passed, fetch it
          const fetchedPackage = await fetchOntologyPackage(ontologyId)
          if (!active) return

          if (fetchedPackage) {
            const entityNames = fetchedPackage.entities.map((e) => e.name)
            setNodeTypes(entityNames)
            if (entityNames.length > 0 && !selectedNodeType) {
              setSelectedNodeType(entityNames[0])
            } else if (entityNames.length === 0) {
              setError('No entities found in the selected ontology')
            }
          } else {
            // If ontology package couldn't be fetched, fall back to all graph node types
            const allTypes = await fetchGraphNodeTypes()
            if (!active) return
            setNodeTypes(allTypes)
            if (allTypes.length > 0 && !selectedNodeType) {
              setSelectedNodeType(allTypes[0])
            }
          }
        } else {
          // No ontology selected, show all graph node types
          const allTypes = await fetchGraphNodeTypes()
          if (!active) return
          setNodeTypes(allTypes)
          if (allTypes.length > 0 && !selectedNodeType) {
            setSelectedNodeType(allTypes[0])
          }
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load node types')
      } finally {
        if (active) setLoadingNodeTypes(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [open, selectedNodeType, ontologyId, ontologyPackage])

  // Reset search query when entity name changes
  useEffect(() => {
    if (open) {
      setSearchQuery(entityName)
    }
  }, [open, entityName])

  // Perform fuzzy search when node type or search query changes
  useEffect(() => {
    if (!open || !selectedNodeType || !searchQuery.trim()) {
      setMatchingNodes([])
      return
    }

      let active = true
      const timeoutId = setTimeout(async () => {
        setLoadingMatches(true)
        setError(null)
        try {
          const searchValue = searchQuery.trim()
          const filterGroup: GraphFilterGroupInput = {
            operator: 'OR',
            filters: [
              {
                property: 'name',
                value: searchValue,
                fuzzySearch: true,
                maxDistance: 2,
              },
              {
                property: 'lastName',
                value: searchValue,
                fuzzySearch: true,
                maxDistance: 2,
              },
            ],
          }
          const results = await fetchGraphNodesByFuzzySearchOr(filterGroup, selectedNodeType, ontologyId || null)
          if (!active) return
          setMatchingNodes(results)
        } catch (e: any) {
          if (!active) return
          setError(e?.message || 'Failed to search nodes')
          setMatchingNodes([])
        } finally {
          if (active) setLoadingMatches(false)
        }
      }, 400) // Debounce 400ms

    return () => {
      active = false
      clearTimeout(timeoutId)
    }
  }, [open, selectedNodeType, searchQuery])

  const handleSelect = useCallback(
    (node: GraphNodeSearchResult) => {
      onSelect(node)
      onClose()
    },
    [onClose, onSelect]
  )

  const handleNodeTypeChange = (nodeType: string) => {
    setSelectedNodeType(nodeType)
  }

  const getNodeDisplayName = (node: GraphNodeSearchResult): string => {
    return node.properties?.name || node.id
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
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
            Match Entity to Domain Node
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {entityType === 'source' ? 'Source' : 'Terminal'} Entity: <strong>{entityName}</strong>
          </Typography>
        </Box>
        <IconButton onClick={onClose} aria-label="Close entity matching dialog" size="small">
          <CloseOutline size="24" />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2 }}>
        {/* Node Type Selector */}
        <Box sx={{ mb: 2 }}>
          <FormControl fullWidth size="small">
            <InputLabel id="node-type-select-label">Node Type</InputLabel>
            <Select
              labelId="node-type-select-label"
              id="node-type-select"
              value={selectedNodeType}
              label="Node Type"
              onChange={(e) => handleNodeTypeChange(e.target.value)}
              disabled={loadingNodeTypes || nodeTypes.length === 0}
            >
              {loadingNodeTypes ? (
                <MenuItem disabled>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Loading types...
                </MenuItem>
              ) : (
                nodeTypes.map((type) => (
                  <MenuItem key={type} value={type}>
                    {type}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Box>

        {/* Search Input */}
        <Box sx={{ mb: 2 }}>
          <OutlinedInput
            fullWidth
            size="small"
            placeholder="Search for matching nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <Search size="24" />
              </InputAdornment>
            }
            sx={{ bgcolor: 'background.paper' }}
          />
        </Box>

        {/* Error Display */}
        {error && (
          <Box sx={{ mb: 2, p: 1.5, bgcolor: 'error.light', borderRadius: 1 }}>
            <Typography color="error" variant="body2">
              {error}
            </Typography>
          </Box>
        )}

        {/* Results List */}
        {loadingMatches ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={22} />
          </Box>
        ) : matchingNodes.length === 0 && searchQuery.trim() && selectedNodeType ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">No matching nodes found</Typography>
          </Box>
        ) : (
          <List sx={{ maxHeight: 400, overflowY: 'auto' }}>
            {matchingNodes.map((node) => {
              const displayName = getNodeDisplayName(node)
              return (
                <ListItemButton
                  key={node.id}
                  onClick={() => handleSelect(node)}
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
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography sx={{ fontWeight: 600 }}>{displayName}</Typography>
                        {node.labels.map((label) => (
                          <Chip key={label} label={label} size="small" variant="outlined" />
                        ))}
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                          ID: {node.id}
                        </Typography>
                        {node.properties && Object.keys(node.properties).length > 1 && (
                          <Box sx={{ mt: 0.5 }}>
                            {Object.entries(node.properties)
                              .filter(([key]) => key !== 'name')
                              .slice(0, 3)
                              .map(([key, value]) => (
                                <Typography key={key} variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                                  {key}: {String(value)}
                                </Typography>
                              ))}
                          </Box>
                        )}
                      </Box>
                    }
                  />
                </ListItemButton>
              )
            })}
          </List>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button variant="outline" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  )
}
