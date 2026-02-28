import { useCallback, useState } from 'react'
import {
  Box,
  Paper,
  Typography,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Checkbox,
  IconButton,
  Stack,
  Divider,
  Select,
  MenuItem,
  FormControl,
  Tabs,
  Tab,
} from '@mui/material'
import { Add, Delete, Edit } from '@mui/icons-material'
import type { OntologyPackage, EntityDefinition, FieldDefinition } from '../../types/ontology'
import OntologyVisualizer from './OntologyVisualizer'

export interface OntologyEditorProps {
  ontologyPackage: OntologyPackage | null
  onChange?: (pkg: OntologyPackage) => void
  editable?: boolean
  height?: number | string
}

const DATA_TYPES = ['string', 'integer', 'float', 'date', 'boolean', 'json', 'uuid']

export default function OntologyEditor({
  ontologyPackage,
  onChange,
  editable = true,
  height = '100%',
}: OntologyEditorProps) {
  const [activeTab, setActiveTab] = useState<'editor' | 'visualizer'>('editor')
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [isEditingDescription, setIsEditingDescription] = useState(false)
  const handleTitleChange = useCallback(
    (newTitle: string) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        title: newTitle,
      })
    },
    [ontologyPackage, onChange]
  )

  const handleDescriptionChange = useCallback(
    (newDescription: string) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        description: newDescription,
      })
    },
    [ontologyPackage, onChange]
  )

  const handleEntityNameChange = useCallback(
    (entityId: string, newName: string) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.map((e) =>
          e.entity_id === entityId ? { ...e, name: newName } : e
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const handleEntityDescriptionChange = useCallback(
    (entityId: string, newDescription: string) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.map((e) =>
          e.entity_id === entityId ? { ...e, description: newDescription } : e
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const handleFieldChange = useCallback(
    (entityId: string, fieldIndex: number, updates: Partial<FieldDefinition>) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.map((e) =>
          e.entity_id === entityId
            ? {
                ...e,
                fields: e.fields.map((f, idx) =>
                  idx === fieldIndex ? { ...f, ...updates } : f
                ),
              }
            : e
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const handleAddField = useCallback(
    (entityId: string) => {
      if (!ontologyPackage || !onChange) return
      const entity = ontologyPackage.entities.find((e) => e.entity_id === entityId)
      if (!entity) return

      const newField: FieldDefinition = {
        name: '',
        data_type: 'string',
        nullable: true,
        is_identifier: false,
        description: '',
      }

      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.map((e) =>
          e.entity_id === entityId ? { ...e, fields: [...e.fields, newField] } : e
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const handleDeleteField = useCallback(
    (entityId: string, fieldIndex: number) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.map((e) =>
          e.entity_id === entityId
            ? {
                ...e,
                fields: e.fields.filter((_, idx) => idx !== fieldIndex),
              }
            : e
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const handleAddEntity = useCallback(() => {
    if (!ontologyPackage || !onChange) return
    const newEntity: EntityDefinition = {
      entity_id: `ent_${Date.now()}`,
      name: 'New Entity',
      description: '',
      fields: [],
    }
    onChange({
      ...ontologyPackage,
      entities: [...ontologyPackage.entities, newEntity],
    })
  }, [ontologyPackage, onChange])

  const handleDeleteEntity = useCallback(
    (entityId: string) => {
      if (!ontologyPackage || !onChange) return
      onChange({
        ...ontologyPackage,
        entities: ontologyPackage.entities.filter((e) => e.entity_id !== entityId),
        relationships: ontologyPackage.relationships.filter(
          (r) => r.from_entity !== entityId && r.to_entity !== entityId
        ),
      })
    },
    [ontologyPackage, onChange]
  )

  const getEntityName = useCallback(
    (entityId: string) => {
      const entity = ontologyPackage?.entities.find((e) => e.entity_id === entityId)
      return entity?.name || entityId
    },
    [ontologyPackage]
  )

  if (!ontologyPackage) {
    return (
      <Box
        sx={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Waiting for ontology to be created...
        </Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        height,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header with version and status */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 3, pb: 0 }}>
        <Box sx={{ flex: 1, mr: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {isEditingTitle && editable ? (
              <TextField
                value={ontologyPackage.title || ''}
                onChange={(e) => handleTitleChange(e.target.value)}
                onBlur={() => setIsEditingTitle(false)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setIsEditingTitle(false)
                  }
                }}
                placeholder="Untitled Ontology"
                variant="standard"
                fullWidth
                autoFocus
                sx={{
                  '& .MuiInputBase-input': {
                    fontSize: '1.5rem',
                    fontWeight: 600,
                    py: 0.5,
                  },
                }}
              />
            ) : (
              <>
                <Typography variant="h5" fontWeight={600}>
                  {ontologyPackage.title || 'Untitled Ontology'}
                </Typography>
                {editable && (
                  <IconButton
                    size="small"
                    onClick={() => setIsEditingTitle(true)}
                    sx={{ ml: 0.5 }}
                  >
                    <Edit fontSize="small" />
                  </IconButton>
                )}
              </>
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mt: 0.5 }}>
            {isEditingDescription && editable ? (
              <TextField
                value={ontologyPackage.description || ''}
                onChange={(e) => handleDescriptionChange(e.target.value)}
                onBlur={() => setIsEditingDescription(false)}
                placeholder="No description"
                variant="standard"
                fullWidth
                multiline
                autoFocus
                sx={{
                  '& .MuiInputBase-input': {
                    fontSize: '0.875rem',
                    color: 'text.secondary',
                    py: 0.5,
                  },
                }}
              />
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
                  {ontologyPackage.description || 'No description'}
                </Typography>
                {editable && (
                  <IconButton
                    size="small"
                    onClick={() => setIsEditingDescription(true)}
                    sx={{ mt: -0.5 }}
                  >
                    <Edit fontSize="small" />
                  </IconButton>
                )}
              </>
            )}
          </Box>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            label={`v${ontologyPackage.semantic_version}`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Chip
            label={ontologyPackage.finalized ? 'Finalized' : 'Draft'}
            size="small"
            color={ontologyPackage.finalized ? 'success' : 'default'}
          />
        </Stack>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3, mt: 2 }}>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
          <Tab label="Editor" value="editor" />
          <Tab label="Visualizer" value="visualizer" />
        </Tabs>
      </Box>

      {/* Tab Content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
        {activeTab === 'editor' ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Entities Section */}
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" fontWeight={600}>
                  Entities ({ontologyPackage.entities.length})
                </Typography>
                {editable && (
                  <IconButton onClick={handleAddEntity} size="small" color="primary">
                    <Add />
                  </IconButton>
                )}
              </Box>

              <Stack spacing={3}>
                {ontologyPackage.entities.map((entity) => (
                  <Paper key={entity.entity_id} variant="outlined" sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                      <Box sx={{ flex: 1 }}>
                        {editable ? (
                          <TextField
                            value={entity.name}
                            onChange={(e) => handleEntityNameChange(entity.entity_id, e.target.value)}
                            placeholder="Entity Name"
                            variant="standard"
                            fullWidth
                            sx={{ mb: 1 }}
                          />
                        ) : (
                          <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>
                            {entity.name}
                          </Typography>
                        )}
                        {editable ? (
                          <TextField
                            value={entity.description}
                            onChange={(e) => handleEntityDescriptionChange(entity.entity_id, e.target.value)}
                            placeholder="Entity description"
                            variant="standard"
                            fullWidth
                            multiline
                            size="small"
                          />
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            {entity.description || 'No description'}
                          </Typography>
                        )}
                      </Box>
                      {editable && (
                        <IconButton
                          onClick={() => handleDeleteEntity(entity.entity_id)}
                          size="small"
                          color="error"
                          sx={{ ml: 2 }}
                        >
                          <Delete />
                        </IconButton>
                      )}
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Fields Table */}
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="subtitle2" fontWeight={600}>
                          Fields ({entity.fields.length})
                        </Typography>
                        {editable && (
                          <IconButton onClick={() => handleAddField(entity.entity_id)} size="small" color="primary">
                            <Add fontSize="small" />
                          </IconButton>
                        )}
                      </Box>

                      {entity.fields.length > 0 ? (
                        <TableContainer>
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Name</TableCell>
                                <TableCell>Type</TableCell>
                                <TableCell align="center">Nullable</TableCell>
                                <TableCell align="center">ID</TableCell>
                                <TableCell>Description</TableCell>
                                {editable && <TableCell align="center" width={50} />}
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {entity.fields.map((field, fieldIndex) => (
                                <TableRow key={fieldIndex}>
                                  <TableCell>
                                    {editable ? (
                                      <TextField
                                        value={field.name}
                                        onChange={(e) =>
                                          handleFieldChange(entity.entity_id, fieldIndex, { name: e.target.value })
                                        }
                                        placeholder="Field name"
                                        size="small"
                                        fullWidth
                                      />
                                    ) : (
                                      field.name || '-'
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {editable ? (
                                      <FormControl size="small" fullWidth>
                                        <Select
                                          value={field.data_type}
                                          onChange={(e) =>
                                            handleFieldChange(entity.entity_id, fieldIndex, {
                                              data_type: e.target.value,
                                            })
                                          }
                                        >
                                          {DATA_TYPES.map((type) => (
                                            <MenuItem key={type} value={type}>
                                              {type}
                                            </MenuItem>
                                          ))}
                                        </Select>
                                      </FormControl>
                                    ) : (
                                      field.data_type
                                    )}
                                  </TableCell>
                                  <TableCell align="center">
                                    {editable ? (
                                      <Checkbox
                                        checked={field.nullable}
                                        onChange={(e) =>
                                          handleFieldChange(entity.entity_id, fieldIndex, {
                                            nullable: e.target.checked,
                                          })
                                        }
                                        size="small"
                                      />
                                    ) : (
                                      field.nullable ? '✓' : '-'
                                    )}
                                  </TableCell>
                                  <TableCell align="center">
                                    {editable ? (
                                      <Checkbox
                                        checked={field.is_identifier}
                                        onChange={(e) =>
                                          handleFieldChange(entity.entity_id, fieldIndex, {
                                            is_identifier: e.target.checked,
                                          })
                                        }
                                        size="small"
                                      />
                                    ) : (
                                      field.is_identifier ? '✓' : '-'
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {editable ? (
                                      <TextField
                                        value={field.description}
                                        onChange={(e) =>
                                          handleFieldChange(entity.entity_id, fieldIndex, {
                                            description: e.target.value,
                                          })
                                        }
                                        placeholder="Description"
                                        size="small"
                                        fullWidth
                                      />
                                    ) : (
                                      field.description || '-'
                                    )}
                                  </TableCell>
                                  {editable && (
                                    <TableCell align="center">
                                      <IconButton
                                        onClick={() => handleDeleteField(entity.entity_id, fieldIndex)}
                                        size="small"
                                        color="error"
                                      >
                                        <Delete fontSize="small" />
                                      </IconButton>
                                    </TableCell>
                                  )}
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ) : (
                        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                          No fields defined
                        </Typography>
                      )}
                    </Box>
                  </Paper>
                ))}

                {ontologyPackage.entities.length === 0 && (
                  <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      No entities defined. {editable && 'Add an entity to get started.'}
                    </Typography>
                  </Paper>
                )}
              </Stack>
            </Box>

            {/* Relationships Section */}
            {ontologyPackage.relationships.length > 0 && (
              <Box>
                <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
                  Relationships ({ontologyPackage.relationships.length})
                </Typography>
                <Stack spacing={2}>
                  {ontologyPackage.relationships.map((rel) => (
                    <Paper key={rel.relationship_id} variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="body1" fontWeight={600}>
                        {getEntityName(rel.from_entity)} --[{rel.relationship_type}]--&gt; {getEntityName(rel.to_entity)}
                      </Typography>
                      {rel.cardinality && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                          Cardinality: {rel.cardinality}
                        </Typography>
                      )}
                      {rel.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                          {rel.description}
                        </Typography>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Box>
            )}
          </Box>
        ) : (
          <OntologyVisualizer ontologyPackage={ontologyPackage} />
        )}
      </Box>
    </Box>
  )
}
