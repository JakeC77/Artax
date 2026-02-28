import { useCallback, useEffect, useMemo, useState } from 'react'
import type { SyntheticEvent } from 'react'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import {
  fetchGraphNodeTypes,
  fetchGraphNodePropertyMetadata,
  fetchGraphNodeRelationshipTypes,
  fetchSemanticFields,
  getOrCreateSemanticEntity,
  createSemanticField,
  updateSemanticField,
  updateSemanticEntity,
} from '../services/graphql'
import type { GraphNodePropertyMetadata } from '../services/graphql'

type FieldDescriptionMap = Record<string, string>
type FieldBooleanMap = Record<string, boolean>
type FieldIdMap = Record<string, string | undefined>

type NodeSemanticsState = {
  metadata?: GraphNodePropertyMetadata[]
  relationships?: string[]
  metadataDescriptions: FieldDescriptionMap
  metadataSavedDescriptions: FieldDescriptionMap
  metadataFieldIds: FieldIdMap
  metadataEditing: FieldBooleanMap
  metadataSaving: FieldBooleanMap
  relationshipDescriptions: FieldDescriptionMap
  relationshipSavedDescriptions: FieldDescriptionMap
  relationshipFieldIds: FieldIdMap
  relationshipEditing: FieldBooleanMap
  relationshipSaving: FieldBooleanMap
  semanticEntityId?: string
  entityDescription: string
  entityDescriptionDraft: string
  entityDescriptionEditing: boolean
  entityDescriptionSaving: boolean
  loading: boolean
  error?: string
}

const createEmptyState = (): NodeSemanticsState => ({
  metadataDescriptions: {},
  metadataSavedDescriptions: {},
  metadataFieldIds: {},
  metadataEditing: {},
  metadataSaving: {},
  relationshipDescriptions: {},
  relationshipSavedDescriptions: {},
  relationshipFieldIds: {},
  relationshipEditing: {},
  relationshipSaving: {},
  semanticEntityId: undefined,
  entityDescription: '',
  entityDescriptionDraft: '',
  entityDescriptionEditing: false,
  entityDescriptionSaving: false,
  loading: false,
  error: undefined,
})

const emptyState = createEmptyState()

function MetadataList({
  nodeType,
  items,
  descriptions,
  savedDescriptions,
  editing,
  saving,
  onChange,
  onToggleEdit,
  onSave,
}: {
  nodeType: string
  items: GraphNodePropertyMetadata[]
  descriptions: FieldDescriptionMap
  savedDescriptions: FieldDescriptionMap
  editing: FieldBooleanMap
  saving: FieldBooleanMap
  onChange: (nodeType: string, name: string, value: string) => void
  onToggleEdit: (nodeType: string, name: string, editing: boolean) => void
  onSave: (nodeType: string, name: string) => void
}) {
  if (!items.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No property metadata found for this node type.
      </Typography>
    )
  }
  return (
    <Stack spacing={2}>
      {items.map((item) => (
        <Box
          key={item.name}
          sx={{
            p: 2,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 1,
            }}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              {item.name}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip label={item.dataType} size="small" color="primary" variant="outlined" />
              <Tooltip title={editing[item.name] ? 'Cancel editing' : 'Edit description'}>
                <span>
                  <IconButton
                    aria-label={editing[item.name] ? 'Cancel editing' : 'Edit description'}
                    onClick={() => onToggleEdit(nodeType, item.name, !editing[item.name])}
                    size="small"
                    disabled={saving[item.name]}
                  >
                    {editing[item.name] ? <CloseRoundedIcon fontSize="small" /> : <EditRoundedIcon fontSize="small" />}
                  </IconButton>
                </span>
              </Tooltip>
            </Stack>
          </Box>
          {editing[item.name] ? (
            <TextField
              label="Description"
              placeholder={`Describe the ${item.name} property`}
              value={descriptions[item.name] ?? ''}
              onChange={(event) => onChange(nodeType, item.name, event.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
          ) : (
            <Typography
              variant="body2"
              color={descriptions[item.name]?.trim() ? 'text.primary' : 'text.secondary'}
              sx={{ whiteSpace: 'pre-wrap' }}
            >
              {descriptions[item.name]?.trim() ? descriptions[item.name] : 'No description yet.'}
            </Typography>
          )}
          {editing[item.name] && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                size="small"
                onClick={() => onSave(nodeType, item.name)}
                disabled={saving[item.name] || (descriptions[item.name] ?? '') === (savedDescriptions[item.name] ?? '')}
                startIcon={saving[item.name] ? <CircularProgress size={16} /> : undefined}
              >
                {saving[item.name] ? 'Saving...' : 'Save'}
              </Button>
            </Box>
          )}
        </Box>
      ))}
    </Stack>
  )
}

function RelationshipList({
  nodeType,
  relationships,
  descriptions,
  savedDescriptions,
  editing,
  saving,
  onChange,
  onToggleEdit,
  onSave,
}: {
  nodeType: string
  relationships: string[]
  descriptions: FieldDescriptionMap
  savedDescriptions: FieldDescriptionMap
  editing: FieldBooleanMap
  saving: FieldBooleanMap
  onChange: (nodeType: string, name: string, value: string) => void
  onToggleEdit: (nodeType: string, name: string, editing: boolean) => void
  onSave: (nodeType: string, name: string) => void
}) {
  if (!relationships.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No relationship types defined for this node type.
      </Typography>
    )
  }
  return (
    <Stack spacing={2}>
      {relationships.map((name) => (
        <Box
          key={name}
          sx={{
            p: 2,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Typography variant="subtitle1" fontWeight={600}>
              {name}
            </Typography>
            <Tooltip title={editing[name] ? 'Cancel editing' : 'Edit description'}>
              <span>
                <IconButton
                  aria-label={editing[name] ? 'Cancel editing' : 'Edit description'}
                  onClick={() => onToggleEdit(nodeType, name, !editing[name])}
                  size="small"
                  disabled={saving[name]}
                >
                  {editing[name] ? <CloseRoundedIcon fontSize="small" /> : <EditRoundedIcon fontSize="small" />}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
          {editing[name] ? (
            <TextField
              label="Description"
              placeholder={`Describe the ${name} relationship`}
              value={descriptions[name] ?? ''}
              onChange={(event) => onChange(nodeType, name, event.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
          ) : (
            <Typography
              variant="body2"
              color={descriptions[name]?.trim() ? 'text.primary' : 'text.secondary'}
              sx={{ whiteSpace: 'pre-wrap' }}
            >
              {descriptions[name]?.trim() ? descriptions[name] : 'No description yet.'}
            </Typography>
          )}
          {editing[name] && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                size="small"
                onClick={() => onSave(nodeType, name)}
                disabled={saving[name] || (descriptions[name] ?? '') === (savedDescriptions[name] ?? '')}
                startIcon={saving[name] ? <CircularProgress size={16} /> : undefined}
              >
                {saving[name] ? 'Saving...' : 'Save'}
              </Button>
            </Box>
          )}
        </Box>
      ))}
    </Stack>
  )
}

export default function Semantics() {
  const [nodeTypes, setNodeTypes] = useState<string[]>([])
  const [nodeTypesLoading, setNodeTypesLoading] = useState(true)
  const [nodeTypesError, setNodeTypesError] = useState<string | null>(null)
  const [expandedType, setExpandedType] = useState<string | false>(false)
  const [semantics, setSemantics] = useState<Record<string, NodeSemanticsState>>({})

  const sortedNodeTypes = useMemo(() => [...nodeTypes].sort((a, b) => a.localeCompare(b)), [nodeTypes])

  const loadNodeTypes = useCallback(async () => {
    setNodeTypesLoading(true)
    setNodeTypesError(null)
    try {
      const types = await fetchGraphNodeTypes()
      setNodeTypes(types)
    } catch (error) {
      setNodeTypesError(error instanceof Error ? error.message : String(error))
    } finally {
      setNodeTypesLoading(false)
    }
  }, [])

  useEffect(() => {
    loadNodeTypes()
  }, [loadNodeTypes])

  const ensureSemantics = useCallback(
    async (type: string) => {
      const current = semantics[type]
      if (current && !current.loading && current.metadata && current.relationships && current.semanticEntityId) {
        return
      }

      setSemantics((prev) => {
        const curr = prev[type] ?? createEmptyState()
        return {
          ...prev,
          [type]: {
            ...curr,
            loading: true,
            error: undefined,
          },
        }
      })

      try {
        const [metadata, relationships, semanticEntity] = await Promise.all([
          fetchGraphNodePropertyMetadata(type),
          fetchGraphNodeRelationshipTypes(type),
          getOrCreateSemanticEntity(type),
        ])
        const semanticFields = await fetchSemanticFields(semanticEntity.semanticEntityId)
        const semanticFieldMap = semanticFields.reduce<Record<string, { id: string; description: string }>>(
          (acc, field) => {
            acc[field.name] = { id: field.semanticFieldId, description: field.description ?? '' }
            return acc
          },
          {}
        )

        const metadataSavedDescriptions = metadata.reduce<FieldDescriptionMap>((acc, item) => {
          acc[item.name] = semanticFieldMap[item.name]?.description ?? ''
          return acc
        }, {})
        const metadataFieldIds = metadata.reduce<FieldIdMap>((acc, item) => {
          acc[item.name] = semanticFieldMap[item.name]?.id
          return acc
        }, {})

        const relationshipSavedDescriptions = relationships.reduce<FieldDescriptionMap>((acc, name) => {
          acc[name] = semanticFieldMap[name]?.description ?? ''
          return acc
        }, {})
        const relationshipFieldIds = relationships.reduce<FieldIdMap>((acc, name) => {
          acc[name] = semanticFieldMap[name]?.id
          return acc
        }, {})

        setSemantics((prev) => {
          const curr = prev[type] ?? createEmptyState()
          const metadataDescriptions = metadata.reduce<FieldDescriptionMap>((acc, item) => {
            const prevValue = curr.metadataDescriptions[item.name]
            acc[item.name] = prevValue ?? metadataSavedDescriptions[item.name] ?? ''
            return acc
          }, {})
          const relationshipDescriptions = relationships.reduce<FieldDescriptionMap>((acc, name) => {
            const prevValue = curr.relationshipDescriptions[name]
            acc[name] = prevValue ?? relationshipSavedDescriptions[name] ?? ''
            return acc
          }, {})

          return {
            ...prev,
            [type]: {
              ...curr,
              metadata,
              relationships,
              metadataDescriptions,
              metadataSavedDescriptions,
              metadataFieldIds,
              metadataEditing: {},
              metadataSaving: {},
              relationshipDescriptions,
              relationshipSavedDescriptions,
              relationshipFieldIds,
              relationshipEditing: {},
              relationshipSaving: {},
              semanticEntityId: semanticEntity.semanticEntityId,
              entityDescription: semanticEntity.description ?? '',
              entityDescriptionDraft: semanticEntity.description ?? '',
              entityDescriptionEditing: false,
              entityDescriptionSaving: false,
              loading: false,
              error: undefined,
            },
          }
        })
      } catch (error) {
        setSemantics((prev) => {
          const curr = prev[type] ?? createEmptyState()
          return {
            ...prev,
            [type]: {
              ...curr,
              loading: false,
              error: error instanceof Error ? error.message : String(error),
            },
          }
        })
      }
    },
    [semantics]
  )

  const handleAccordionChange = useCallback(
    (nodeType: string) => async (_: SyntheticEvent, isExpanded: boolean) => {
      setExpandedType(isExpanded ? nodeType : false)
      if (isExpanded) {
        await ensureSemantics(nodeType)
      }
    },
    [ensureSemantics]
  )

  const handleMetadataDescriptionChange = useCallback(
    (nodeType: string, name: string, value: string) => {
      setSemantics((prev) => {
        const curr = prev[nodeType] ?? createEmptyState()
        return {
          ...prev,
          [nodeType]: {
            ...curr,
            metadataDescriptions: { ...curr.metadataDescriptions, [name]: value },
          },
        }
      })
    },
    []
  )

  const handleRelationshipDescriptionChange = useCallback(
    (nodeType: string, name: string, value: string) => {
      setSemantics((prev) => {
        const curr = prev[nodeType] ?? createEmptyState()
        return {
          ...prev,
          [nodeType]: {
            ...curr,
            relationshipDescriptions: { ...curr.relationshipDescriptions, [name]: value },
          },
        }
      })
    },
    []
  )

  const handleMetadataToggleEdit = useCallback((nodeType: string, name: string, editing: boolean) => {
    setSemantics((prev) => {
      const curr = prev[nodeType] ?? createEmptyState()
      const metadataEditing = { ...curr.metadataEditing }
      if (editing) {
        metadataEditing[name] = true
      } else {
        delete metadataEditing[name]
      }
      return {
        ...prev,
        [nodeType]: {
          ...curr,
          metadataEditing,
          metadataDescriptions: editing
            ? curr.metadataDescriptions
            : { ...curr.metadataDescriptions, [name]: curr.metadataSavedDescriptions[name] ?? '' },
        },
      }
    })
  }, [])

  const handleRelationshipToggleEdit = useCallback((nodeType: string, name: string, editing: boolean) => {
    setSemantics((prev) => {
      const curr = prev[nodeType] ?? createEmptyState()
      const relationshipEditing = { ...curr.relationshipEditing }
      if (editing) {
        relationshipEditing[name] = true
      } else {
        delete relationshipEditing[name]
      }
      return {
        ...prev,
        [nodeType]: {
          ...curr,
          relationshipEditing,
          relationshipDescriptions: editing
            ? curr.relationshipDescriptions
            : { ...curr.relationshipDescriptions, [name]: curr.relationshipSavedDescriptions[name] ?? '' },
        },
      }
    })
  }, [])

  const handleMetadataSave = useCallback(
    async (nodeType: string, name: string) => {
      const current = semantics[nodeType]
      if (!current?.semanticEntityId) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              error: 'Semantic entity is not available for this node type.',
            },
          }
        })
        return
      }

      const description = current.metadataDescriptions[name] ?? ''
      const existingFieldId = current.metadataFieldIds[name]

      setSemantics((prev) => {
        const curr = prev[nodeType] ?? createEmptyState()
        return {
          ...prev,
          [nodeType]: {
            ...curr,
            metadataSaving: { ...curr.metadataSaving, [name]: true },
            error: undefined,
          },
        }
      })

      try {
        let semanticFieldId = existingFieldId
        if (semanticFieldId) {
          await updateSemanticField({ semanticFieldId, description })
        } else {
          semanticFieldId = await createSemanticField({
            semanticEntityId: current.semanticEntityId,
            name,
            description,
          })
        }

        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          const metadataEditing = { ...curr.metadataEditing }
          delete metadataEditing[name]
          const metadataSaving = { ...curr.metadataSaving }
          delete metadataSaving[name]
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              metadataFieldIds: { ...curr.metadataFieldIds, [name]: semanticFieldId },
              metadataSavedDescriptions: { ...curr.metadataSavedDescriptions, [name]: description },
              metadataEditing,
              metadataSaving,
            },
          }
        })
      } catch (error) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          const metadataSaving = { ...curr.metadataSaving }
          delete metadataSaving[name]
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              metadataSaving,
              error: error instanceof Error ? error.message : String(error),
            },
          }
        })
      }
    },
    [semantics]
  )

  const handleRelationshipSave = useCallback(
    async (nodeType: string, name: string) => {
      const current = semantics[nodeType]
      if (!current?.semanticEntityId) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              error: 'Semantic entity is not available for this node type.',
            },
          }
        })
        return
      }

      const description = current.relationshipDescriptions[name] ?? ''
      const existingFieldId = current.relationshipFieldIds[name]

      setSemantics((prev) => {
        const curr = prev[nodeType] ?? createEmptyState()
        return {
          ...prev,
          [nodeType]: {
            ...curr,
            relationshipSaving: { ...curr.relationshipSaving, [name]: true },
            error: undefined,
          },
        }
      })

      try {
        let semanticFieldId = existingFieldId
        if (semanticFieldId) {
          await updateSemanticField({ semanticFieldId, description })
        } else {
          semanticFieldId = await createSemanticField({
            semanticEntityId: current.semanticEntityId,
            name,
            description,
          })
        }

        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          const relationshipEditing = { ...curr.relationshipEditing }
          delete relationshipEditing[name]
          const relationshipSaving = { ...curr.relationshipSaving }
          delete relationshipSaving[name]
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              relationshipFieldIds: { ...curr.relationshipFieldIds, [name]: semanticFieldId },
              relationshipSavedDescriptions: { ...curr.relationshipSavedDescriptions, [name]: description },
              relationshipEditing,
              relationshipSaving,
            },
          }
        })
      } catch (error) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          const relationshipSaving = { ...curr.relationshipSaving }
          delete relationshipSaving[name]
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              relationshipSaving,
              error: error instanceof Error ? error.message : String(error),
            },
          }
        })
      }
    },
    [semantics]
  )

  const handleEntityDescriptionChange = useCallback((nodeType: string, value: string) => {
    setSemantics((prev) => {
      const curr = prev[nodeType] ?? createEmptyState()
      return {
        ...prev,
        [nodeType]: {
          ...curr,
          entityDescriptionDraft: value,
        },
      }
    })
  }, [])

  const handleEntityToggleEdit = useCallback((nodeType: string, editing: boolean) => {
    setSemantics((prev) => {
      const curr = prev[nodeType] ?? createEmptyState()
      return {
        ...prev,
        [nodeType]: {
          ...curr,
          entityDescriptionEditing: editing,
          entityDescriptionDraft: curr.entityDescription,
        },
      }
    })
  }, [])

  const handleEntitySave = useCallback(
    async (nodeType: string) => {
      const current = semantics[nodeType]
      if (!current?.semanticEntityId) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              error: 'Semantic entity is not available for this node type.',
            },
          }
        })
        return
      }

      const description = current.entityDescriptionDraft ?? ''

      setSemantics((prev) => {
        const curr = prev[nodeType] ?? createEmptyState()
        return {
          ...prev,
          [nodeType]: {
            ...curr,
            entityDescriptionSaving: true,
            error: undefined,
          },
        }
      })

      try {
        await updateSemanticEntity({ semanticEntityId: current.semanticEntityId, description })
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              entityDescription: description,
              entityDescriptionDraft: description,
              entityDescriptionEditing: false,
              entityDescriptionSaving: false,
            },
          }
        })
      } catch (error) {
        setSemantics((prev) => {
          const curr = prev[nodeType] ?? createEmptyState()
          return {
            ...prev,
            [nodeType]: {
              ...curr,
              entityDescriptionSaving: false,
              error: error instanceof Error ? error.message : String(error),
            },
          }
        })
      }
    },
    [semantics]
  )

  if (nodeTypesLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 'calc(100vh - 160px)' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (nodeTypesError) {
    return (
      <Stack spacing={2}>
        <Alert severity="error">Failed to load node types: {nodeTypesError}</Alert>
        <Box>
          <Button variant="contained" onClick={loadNodeTypes}>
            Retry
          </Button>
        </Box>
      </Stack>
    )
  }

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Semantics
        </Typography>
        <Typography color="text.secondary">
          Review each node type, update semantic descriptions for its metadata, and capture how it relates to other nodes.
        </Typography>
      </Box>

      {!sortedNodeTypes.length ? (
        <Alert severity="info">No node types are currently available.</Alert>
      ) : (
        sortedNodeTypes.map((type) => {
          const state = semantics[type] ?? emptyState
          return (
            <Accordion key={type} expanded={expandedType === type} onChange={handleAccordionChange(type)}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls={`${type}-content`} id={`${type}-header`}>
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {type}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {state.metadata?.length ? `${state.metadata.length} metadata field(s)` : 'Metadata not loaded'}
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {state.loading && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
                    <CircularProgress size={24} />
                  </Box>
                )}
                {state.error && <Alert severity="error">{state.error}</Alert>}
                {!state.loading && (
                  <Stack spacing={3}>
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Semantic Entity
                      </Typography>
                      <Box
                        sx={{
                          p: 2,
                          borderRadius: 2,
                          border: '1px solid',
                          borderColor: 'divider',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                          <Typography variant="subtitle1" fontWeight={600}>
                            Entity Description
                          </Typography>
                          <Tooltip
                            title={
                              !state.semanticEntityId
                                ? 'Semantic entity unavailable'
                                : state.entityDescriptionEditing
                                  ? 'Cancel editing'
                                  : 'Edit description'
                            }
                          >
                            <span>
                              <IconButton
                                aria-label={state.entityDescriptionEditing ? 'Cancel editing' : 'Edit description'}
                                onClick={() => handleEntityToggleEdit(type, !state.entityDescriptionEditing)}
                                size="small"
                                disabled={!state.semanticEntityId || state.entityDescriptionSaving}
                              >
                                {state.entityDescriptionEditing ? (
                                  <CloseRoundedIcon fontSize="small" />
                                ) : (
                                  <EditRoundedIcon fontSize="small" />
                                )}
                              </IconButton>
                            </span>
                          </Tooltip>
                        </Box>
                        {state.entityDescriptionEditing ? (
                          <>
                            <TextField
                              label="Description"
                              placeholder={`Describe the ${type} entity`}
                              value={state.entityDescriptionDraft ?? ''}
                              onChange={(event) => handleEntityDescriptionChange(type, event.target.value)}
                              multiline
                              minRows={3}
                              fullWidth
                            />
                            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                              <Button
                                variant="contained"
                                size="small"
                                onClick={() => handleEntitySave(type)}
                                disabled={
                                  state.entityDescriptionSaving ||
                                  state.entityDescriptionDraft === state.entityDescription
                                }
                                startIcon={state.entityDescriptionSaving ? <CircularProgress size={16} /> : undefined}
                              >
                                {state.entityDescriptionSaving ? 'Saving...' : 'Save'}
                              </Button>
                            </Box>
                          </>
                        ) : (
                          <Typography
                            variant="body2"
                            color={state.entityDescription?.trim() ? 'text.primary' : 'text.secondary'}
                            sx={{ whiteSpace: 'pre-wrap' }}
                          >
                            {state.entityDescription?.trim() ? state.entityDescription : 'No description yet.'}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    <Divider />
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Property Metadata
                      </Typography>
                      <MetadataList
                        nodeType={type}
                        items={state.metadata ?? []}
                        descriptions={state.metadataDescriptions}
                        savedDescriptions={state.metadataSavedDescriptions}
                        editing={state.metadataEditing}
                        saving={state.metadataSaving}
                        onChange={handleMetadataDescriptionChange}
                        onToggleEdit={handleMetadataToggleEdit}
                        onSave={handleMetadataSave}
                      />
                    </Box>
                    <Divider />
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Relationship Types
                      </Typography>
                      <RelationshipList
                        nodeType={type}
                        relationships={state.relationships ?? []}
                        descriptions={state.relationshipDescriptions}
                        savedDescriptions={state.relationshipSavedDescriptions}
                        editing={state.relationshipEditing}
                        saving={state.relationshipSaving}
                        onChange={handleRelationshipDescriptionChange}
                        onToggleEdit={handleRelationshipToggleEdit}
                        onSave={handleRelationshipSave}
                      />
                    </Box>
                  </Stack>
                )}
              </AccordionDetails>
            </Accordion>
          )
        })
      )}
    </Box>
  )
}
