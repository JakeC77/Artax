import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Box,
  Alert,
  CircularProgress,
  TextField,
  Typography,
  Paper,
  Stack,
  FormControl,
  FormLabel,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material'
import { ArrowLeft, Add, Close } from '@carbon/icons-react'
import Button from '../components/common/Button'
import {
  fetchIntentById,
  createIntent,
  updateIntent,
  getTenantId,
  fetchOntologies,
  fetchOntologyPackage,
} from '../services/graphql'
import type { OntologyPackage, EntityDefinition, FieldDefinition } from '../types/ontology'
import type { Ontology } from '../services/graphql'

function safeJsonParse(value: string): Record<string, unknown> | null {
  const t = value.trim()
  if (!t) return null
  try {
    const parsed = JSON.parse(t)
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

function safeJsonStringify(obj: Record<string, unknown> | null): string {
  if (obj == null) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return ''
  }
}

/** A field selected for input or output payload (from ontology entity). */
export type SelectedPayloadField = {
  entityName: string
  fieldName: string
  dataType: string
  description?: string
}

function dataTypeToJsonSchemaType(dataType: string): { type: string; format?: string } {
  const d = (dataType || 'string').toLowerCase()
  if (d === 'integer') return { type: 'integer' }
  if (d === 'float' || d === 'number') return { type: 'number' }
  if (d === 'boolean') return { type: 'boolean' }
  if (d === 'date') return { type: 'string', format: 'date' }
  if (d === 'datetime') return { type: 'string', format: 'date-time' }
  return { type: 'string' }
}

function buildSchemaFromSelectedFields(fields: SelectedPayloadField[]): Record<string, unknown> | null {
  if (fields.length === 0) return null
  const properties: Record<string, unknown> = {}
  const required: string[] = []
  for (const f of fields) {
    const key = `${f.entityName}.${f.fieldName}`
    properties[key] = {
      type: dataTypeToJsonSchemaType(f.dataType).type,
      ...(dataTypeToJsonSchemaType(f.dataType).format && { format: dataTypeToJsonSchemaType(f.dataType).format }),
      description: f.description || undefined,
    }
  }
  return { type: 'object', properties, required }
}

/** Parse existing JSON Schema and extract selected fields (keys like "EntityName.fieldName"). */
function parseSchemaToSelectedFields(schema: Record<string, unknown> | null): SelectedPayloadField[] {
  if (!schema || typeof schema !== 'object') return []
  const props = schema.properties as Record<string, { type?: string; format?: string; description?: string }> | undefined
  if (!props || typeof props !== 'object') return []
  const out: SelectedPayloadField[] = []
  for (const key of Object.keys(props)) {
    const dot = key.indexOf('.')
    if (dot <= 0 || dot === key.length - 1) continue
    const entityName = key.slice(0, dot)
    const fieldName = key.slice(dot + 1)
    const val = props[key]
    const dataType = val && typeof val === 'object' && typeof val.type === 'string'
      ? (val.type === 'integer'
          ? 'integer'
          : val.type === 'number'
            ? 'float'
            : val.type === 'boolean'
              ? 'boolean'
              : val.type === 'string' && typeof val.format === 'string'
                ? (val.format === 'date-time' ? 'datetime' : val.format === 'date' ? 'date' : 'string')
                : 'string')
      : 'string'
    out.push({
      entityName,
      fieldName,
      dataType,
      description: val && typeof val === 'object' && typeof val.description === 'string' ? val.description : undefined,
    })
  }
  return out
}

export type PayloadShape = 'object' | 'array'

/** Parse root schema: if it's an array, extract fields from items; otherwise from root object. */
function parseSchemaToShape(schema: Record<string, unknown> | null): { kind: PayloadShape; fields: SelectedPayloadField[] } {
  if (!schema || typeof schema !== 'object') return { kind: 'object', fields: [] }
  const type = schema.type as string | undefined
  const items = schema.items as Record<string, unknown> | undefined
  if (type === 'array' && items && typeof items === 'object') {
    return { kind: 'array', fields: parseSchemaToSelectedFields(items) }
  }
  return { kind: 'object', fields: parseSchemaToSelectedFields(schema) }
}

/** Build root schema: object or array of items with the given fields. */
function buildSchemaFromSelectedFieldsWithShape(
  fields: SelectedPayloadField[],
  kind: PayloadShape
): Record<string, unknown> | null {
  const itemSchema = buildSchemaFromSelectedFields(fields)
  if (!itemSchema) return null
  if (kind === 'array') {
    return { type: 'array', items: itemSchema }
  }
  return itemSchema
}

export default function IntentCreateEdit() {
  const navigate = useNavigate()
  const { intentId } = useParams<{ intentId?: string }>()
  const isCreate = !intentId || intentId === 'create'

  const [loading, setLoading] = useState(!isCreate)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [opId, setOpId] = useState('')
  const [intent, setIntent] = useState('')
  const [route, setRoute] = useState('')
  const [description, setDescription] = useState('')
  const [grounding, setGrounding] = useState('')
  const [ontologyId, setOntologyId] = useState<string>('')

  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [ontologyPackage, setOntologyPackage] = useState<OntologyPackage | null>(null)
  const [loadingOntology, setLoadingOntology] = useState(false)

  const [selectedInputFields, setSelectedInputFields] = useState<SelectedPayloadField[]>([])
  const [selectedOutputFields, setSelectedOutputFields] = useState<SelectedPayloadField[]>([])
  const [inputPayloadKind, setInputPayloadKind] = useState<PayloadShape>('object')
  const [outputPayloadKind, setOutputPayloadKind] = useState<PayloadShape>('object')
  const [selectedEntityId, setSelectedEntityId] = useState<string>('')

  const [inputSchemaRaw, setInputSchemaRaw] = useState('')
  const [outputSchemaRaw, setOutputSchemaRaw] = useState('')
  const [useDesigner, setUseDesigner] = useState(true)
  const [inputSchemaError, setInputSchemaError] = useState<string | null>(null)
  const [outputSchemaError, setOutputSchemaError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const list = await fetchOntologies()
        if (!active) return
        setOntologies(list)
      } catch {
        if (!active) return
      }
    }
    load()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!ontologyId) {
      setOntologyPackage(null)
      setSelectedEntityId('')
      return
    }
    let active = true
    setLoadingOntology(true)
    setSelectedEntityId('')
    fetchOntologyPackage(ontologyId)
      .then((pkg) => {
        if (!active) return
        setOntologyPackage(pkg)
      })
      .finally(() => {
        if (active) setLoadingOntology(false)
      })
    return () => { active = false }
  }, [ontologyId])

  useEffect(() => {
    if (isCreate) return
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchIntentById(intentId!)
        if (!active) return
        if (!data) {
          setError('Intent not found')
          setLoading(false)
          return
        }
        setOpId(data.opId)
        setIntent(data.intent)
        setRoute(data.route ?? '')
        setDescription(data.description ?? '')
        setGrounding(data.grounding ?? '')
        setOntologyId(data.ontologyId ?? '')
        setInputSchemaRaw(safeJsonStringify(data.input_schema))
        setOutputSchemaRaw(safeJsonStringify(data.output_schema))
        const inputShape = parseSchemaToShape(data.input_schema)
        const outputShape = parseSchemaToShape(data.output_schema)
        setSelectedInputFields(inputShape.fields)
        setSelectedOutputFields(outputShape.fields)
        setInputPayloadKind(inputShape.kind)
        setOutputPayloadKind(outputShape.kind)
        setUseDesigner(!!data.ontologyId)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load intent')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [intentId, isCreate])

  const addToInput = useCallback((entity: EntityDefinition, field: FieldDefinition) => {
    setSelectedInputFields((prev) => {
      if (prev.some((f) => f.entityName === entity.name && f.fieldName === field.name)) return prev
      return [...prev, { entityName: entity.name, fieldName: field.name, dataType: field.data_type, description: field.description }]
    })
  }, [])

  const addToOutput = useCallback((entity: EntityDefinition, field: FieldDefinition) => {
    setSelectedOutputFields((prev) => {
      if (prev.some((f) => f.entityName === entity.name && f.fieldName === field.name)) return prev
      return [...prev, { entityName: entity.name, fieldName: field.name, dataType: field.data_type, description: field.description }]
    })
  }, [])

  const removeFromInput = useCallback((index: number) => {
    setSelectedInputFields((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const removeFromOutput = useCallback((index: number) => {
    setSelectedOutputFields((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const validateSchemas = useCallback((): boolean => {
    if (useDesigner && ontologyPackage) {
      setInputSchemaError(null)
      setOutputSchemaError(null)
      return true
    }
    let ok = true
    if (inputSchemaRaw.trim()) {
      const parsed = safeJsonParse(inputSchemaRaw)
      if (parsed === null) {
        setInputSchemaError('Invalid JSON')
        ok = false
      } else setInputSchemaError(null)
    } else setInputSchemaError(null)
    if (outputSchemaRaw.trim()) {
      const parsed = safeJsonParse(outputSchemaRaw)
      if (parsed === null) {
        setOutputSchemaError('Invalid JSON')
        ok = false
      } else setOutputSchemaError(null)
    } else setOutputSchemaError(null)
    return ok
  }, [useDesigner, ontologyPackage, inputSchemaRaw, outputSchemaRaw])

  const getInputSchemaForSave = useCallback((): Record<string, unknown> | null => {
    if (useDesigner && ontologyPackage) {
      return buildSchemaFromSelectedFieldsWithShape(selectedInputFields, inputPayloadKind)
    }
    return safeJsonParse(inputSchemaRaw)
  }, [useDesigner, ontologyPackage, selectedInputFields, inputSchemaRaw, inputPayloadKind])

  const getOutputSchemaForSave = useCallback((): Record<string, unknown> | null => {
    if (useDesigner && ontologyPackage) {
      return buildSchemaFromSelectedFieldsWithShape(selectedOutputFields, outputPayloadKind)
    }
    return safeJsonParse(outputSchemaRaw)
  }, [useDesigner, ontologyPackage, selectedOutputFields, outputSchemaRaw, outputPayloadKind])

  const handleSave = useCallback(async () => {
    if (!opId.trim() || !intent.trim()) {
      setError('Op ID and Intent are required')
      return
    }
    if (!validateSchemas()) {
      setError('Please fix JSON errors in input or output schema')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const tenantId = getTenantId()
      if (!tenantId) {
        setError('Tenant ID is required')
        setSaving(false)
        return
      }

      const input_schema = getInputSchemaForSave()
      const output_schema = getOutputSchemaForSave()

      if (isCreate) {
        await createIntent({
          tenantId,
          opId: opId.trim(),
          intent: intent.trim(),
          route: route.trim() || null,
          description: description.trim() || null,
          grounding: grounding.trim() || null,
          input_schema,
          output_schema,
          ontologyId: ontologyId.trim() || null,
        })
        navigate('/intents')
      } else {
        await updateIntent({
          intentId: intentId!,
          opId: opId.trim(),
          intent: intent.trim(),
          route: route.trim() || null,
          description: description.trim() || null,
          grounding: grounding.trim() || null,
          input_schema,
          output_schema,
          ontologyId: ontologyId.trim() || null,
        })
        navigate('/intents')
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to save intent')
    } finally {
      setSaving(false)
    }
  }, [
    isCreate,
    intentId,
    opId,
    intent,
    route,
    description,
    grounding,
    ontologyId,
    validateSchemas,
    getInputSchemaForSave,
    getOutputSchemaForSave,
    navigate,
  ])

  const handleCancel = useCallback(() => navigate('/intents'), [navigate])

  /** Sync designer state into raw JSON strings, then switch to JSON mode. */
  const handleSwitchToJson = useCallback(() => {
    const inputSchema = buildSchemaFromSelectedFieldsWithShape(selectedInputFields, inputPayloadKind)
    const outputSchema = buildSchemaFromSelectedFieldsWithShape(selectedOutputFields, outputPayloadKind)
    setInputSchemaRaw(safeJsonStringify(inputSchema))
    setOutputSchemaRaw(safeJsonStringify(outputSchema))
    setInputSchemaError(null)
    setOutputSchemaError(null)
    setUseDesigner(false)
  }, [selectedInputFields, selectedOutputFields, inputPayloadKind, outputPayloadKind])

  /** Parse raw JSON into designer state, then switch to designer mode. Fails if JSON is invalid. */
  const handleSwitchToDesigner = useCallback(() => {
    const inputParsed = inputSchemaRaw.trim() ? safeJsonParse(inputSchemaRaw) : null
    const outputParsed = outputSchemaRaw.trim() ? safeJsonParse(outputSchemaRaw) : null
    if (inputSchemaRaw.trim() && inputParsed === null) {
      setInputSchemaError('Invalid JSON — fix input schema before switching to designer')
      return
    }
    if (outputSchemaRaw.trim() && outputParsed === null) {
      setOutputSchemaError('Invalid JSON — fix output schema before switching to designer')
      return
    }
    const inputShape = parseSchemaToShape(inputParsed)
    const outputShape = parseSchemaToShape(outputParsed)
    setSelectedInputFields(inputShape.fields)
    setSelectedOutputFields(outputShape.fields)
    setInputPayloadKind(inputShape.kind)
    setOutputPayloadKind(outputShape.kind)
    setInputSchemaError(null)
    setOutputSchemaError(null)
    setUseDesigner(true)
  }, [inputSchemaRaw, outputSchemaRaw])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading intent...
        </Typography>
      </Box>
    )
  }

  const showDesigner = useDesigner && !!ontologyPackage

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto', p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button variant="outline" onClick={handleCancel} sx={{ minWidth: 0, p: 1 }} aria-label="Back to intents list">
          <ArrowLeft size={20} />
        </Button>
        <Typography variant="h4" fontWeight={700}>
          {isCreate ? 'Create Intent' : 'Edit Intent'}
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
        <Stack spacing={3}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
            <TextField
              label="Op ID"
              value={opId}
              onChange={(e) => setOpId(e.target.value)}
              required
              fullWidth
              placeholder="e.g. memberAuthentication"
            />
            <TextField
              label="Intent"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              required
              fullWidth
              placeholder="e.g. member.authentication"
            />
            <FormControl fullWidth>
              <InputLabel id="intent-ontology-label">Ontology</InputLabel>
              <Select
                labelId="intent-ontology-label"
                id="intent-ontology"
                value={ontologyId}
                label="Ontology"
                onChange={(e) => setOntologyId(e.target.value)}
                disabled={loadingOntology}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {ontologies.map((o) => (
                  <MenuItem key={o.ontologyId} value={o.ontologyId}>
                    {o.name}
                  </MenuItem>
                ))}
              </Select>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                Optional. When set, you can build request/response payloads from ontology entities and fields.
              </Typography>
            </FormControl>
            <TextField
              label="Route"
              value={route}
              onChange={(e) => setRoute(e.target.value)}
              fullWidth
              placeholder="e.g. POST api/intents/route"
            />
          </Box>
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            minRows={2}
          />
          <FormControl fullWidth>
            <FormLabel sx={{ mb: 1 }}>Grounding (templated query)</FormLabel>
            <TextField
              value={grounding}
              onChange={(e) => setGrounding(e.target.value)}
              fullWidth
              multiline
              minRows={3}
              placeholder="Cypher, GraphQL, or SQL templated query (executed at runtime with parameters)"
              sx={{ '& .MuiInputBase-root': { fontFamily: 'monospace' } }}
            />
          </FormControl>

          {showDesigner ? (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Build payloads from ontology
                </Typography>
                <Chip
                  label="Designer"
                  size="small"
                  color="primary"
                  variant="filled"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSwitchToJson}
                >
                  Switch to JSON
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Select an entity, then add its fields to the request (input) or response (output) payloads.
              </Typography>

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', md: 'minmax(280px, 1fr) 1fr' },
                  gap: 2,
                  alignItems: 'start',
                }}
              >
                {/* Left: entity picklist */}
                <Stack spacing={2}>
                  <FormControl fullWidth size="small">
                    <InputLabel id="intent-entity-label">Entity</InputLabel>
                    <Select
                      labelId="intent-entity-label"
                      id="intent-entity"
                      value={selectedEntityId}
                      label="Entity"
                      onChange={(e) => setSelectedEntityId(e.target.value)}
                    >
                      <MenuItem value="">
                        <em>Select an entity…</em>
                      </MenuItem>
                      {ontologyPackage?.entities.map((entity) => (
                        <MenuItem key={entity.entity_id} value={entity.entity_id}>
                          {entity.name}
                          {entity.description ? ` — ${entity.description}` : ''}
                        </MenuItem>
                      ))}
                    </Select>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                      Choose an entity to see its fields and add them to input or output.
                    </Typography>
                  </FormControl>

                  {selectedEntityId && (() => {
                    const entity = ontologyPackage?.entities.find((e) => e.entity_id === selectedEntityId)
                    if (!entity) return null
                    return (
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                          {entity.name} — fields
                        </Typography>
                        {entity.description && (
                          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                            {entity.description}
                          </Typography>
                        )}
                        <List dense disablePadding>
                          {entity.fields.map((field) => (
                            <ListItem key={field.name}>
                              <ListItemText
                                primary={field.name}
                                secondary={`${field.data_type}${field.nullable ? ' (nullable)' : ''}${field.description ? ` — ${field.description}` : ''}`}
                                primaryTypographyProps={{ variant: 'body2' }}
                                secondaryTypographyProps={{ variant: 'caption' }}
                              />
                              <ListItemSecondaryAction>
                                <IconButton
                                  size="small"
                                  onClick={() => addToInput(entity, field)}
                                  aria-label={`Add ${entity.name}.${field.name} to input`}
                                  title="Add to input"
                                >
                                  <Add size={16} />
                                </IconButton>
                                <IconButton
                                  size="small"
                                  onClick={() => addToOutput(entity, field)}
                                  aria-label={`Add ${entity.name}.${field.name} to output`}
                                  title="Add to output"
                                  sx={{ ml: 0.5 }}
                                >
                                  <Add size={16} />
                                </IconButton>
                              </ListItemSecondaryAction>
                            </ListItem>
                          ))}
                        </List>
                      </Paper>
                    )
                  })()}
                </Stack>

                {/* Right: input and output payloads */}
                <Stack spacing={2}>
                  <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover' }}>
                    <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                      Input payload (request)
                    </Typography>
                    <List dense sx={{ py: 0 }}>
                      {selectedInputFields.length === 0 ? (
                        <ListItem><ListItemText primary="No fields selected. Select an entity and add fields." primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }} /></ListItem>
                      ) : (
                        selectedInputFields.map((f, i) => (
                          <ListItem key={`${f.entityName}.${f.fieldName}-${i}`}>
                            <ListItemText primary={`${f.entityName}.${f.fieldName}`} secondary={f.dataType} />
                            <ListItemSecondaryAction>
                              <IconButton size="small" onClick={() => removeFromInput(i)} aria-label="Remove from input">
                                <Close size={16} />
                              </IconButton>
                            </ListItemSecondaryAction>
                          </ListItem>
                        ))
                      )}
                    </List>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                      <Typography variant="subtitle2" fontWeight={600}>
                        Output payload (response)
                      </Typography>
                      <ToggleButtonGroup
                        value={outputPayloadKind}
                        exclusive
                        onChange={(_, v) => v != null && setOutputPayloadKind(v)}
                        size="small"
                        aria-label="Response shape"
                      >
                        <ToggleButton value="object" aria-label="Single object">Single object</ToggleButton>
                        <ToggleButton value="array" aria-label="List of items">List of items</ToggleButton>
                      </ToggleButtonGroup>
                    </Box>
                    {outputPayloadKind === 'array' && (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                        Response will be an array; each item has the fields below (e.g. a list of prescriptions with name and dosage).
                      </Typography>
                    )}
                    <List dense sx={{ py: 0 }}>
                      {selectedOutputFields.length === 0 ? (
                        <ListItem><ListItemText primary="No fields selected. Select an entity and add fields." primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }} /></ListItem>
                      ) : (
                        selectedOutputFields.map((f, i) => (
                          <ListItem key={`${f.entityName}.${f.fieldName}-${i}`}>
                            <ListItemText primary={`${f.entityName}.${f.fieldName}`} secondary={f.dataType} />
                            <ListItemSecondaryAction>
                              <IconButton size="small" onClick={() => removeFromOutput(i)} aria-label="Remove from output">
                                <Close size={16} />
                              </IconButton>
                            </ListItemSecondaryAction>
                          </ListItem>
                        ))
                      )}
                    </List>
                  </Paper>
                </Stack>
              </Box>
            </>
          ) : (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Input / Output schema (JSON)
                </Typography>
                {ontologyId && (
                  <Button variant="outline" size="sm" onClick={handleSwitchToDesigner}>
                    Switch to designer
                  </Button>
                )}
              </Box>
              <FormControl fullWidth error={!!inputSchemaError}>
                <FormLabel sx={{ mb: 1 }}>Input schema (JSON)</FormLabel>
                <TextField
                  value={inputSchemaRaw}
                  onChange={(e) => { setInputSchemaRaw(e.target.value); setInputSchemaError(null) }}
                  onBlur={() => {
                    if (inputSchemaRaw.trim()) {
                      setInputSchemaError(safeJsonParse(inputSchemaRaw) === null ? 'Invalid JSON' : null)
                    } else setInputSchemaError(null)
                  }}
                  fullWidth
                  multiline
                  minRows={4}
                  placeholder='{"type": "object", "properties": {...}}'
                  helperText={inputSchemaError}
                  sx={{ '& .MuiInputBase-root': { fontFamily: 'monospace' } }}
                />
              </FormControl>
              <FormControl fullWidth error={!!outputSchemaError}>
                <FormLabel sx={{ mb: 1 }}>Output schema (JSON)</FormLabel>
                <TextField
                  value={outputSchemaRaw}
                  onChange={(e) => { setOutputSchemaRaw(e.target.value); setOutputSchemaError(null) }}
                  onBlur={() => {
                    if (outputSchemaRaw.trim()) {
                      setOutputSchemaError(safeJsonParse(outputSchemaRaw) === null ? 'Invalid JSON' : null)
                    } else setOutputSchemaError(null)
                  }}
                  fullWidth
                  multiline
                  minRows={4}
                  placeholder='{"type": "object", "properties": {...}}'
                  helperText={outputSchemaError}
                  sx={{ '& .MuiInputBase-root': { fontFamily: 'monospace' } }}
                />
              </FormControl>
            </>
          )}

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', pt: 2 }}>
            <Button variant="secondary" onClick={handleCancel} disabled={saving}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  )
}
