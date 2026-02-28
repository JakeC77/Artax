import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Box,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
  Tooltip,
} from '@mui/material'
import { Checkmark } from '@carbon/icons-react'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked'
import Button from '../components/common/Button'
import FilePreview from '../components/FilePreview'
import EntityMatchingModal from '../components/EntityMatchingModal'
import {
  fetchWorkspaces,
  fetchScratchpadAttachments,
  fetchScratchpadAttachmentAssertions,
  fetchGraphNodeRelationshipTypes,
  startDocumentIndexingPipeline,
  fetchScratchpadAttachmentById,
  createScratchpadAttachment,
  fetchOntologies,
  fetchOntologyPackage,
  type Workspace,
  type ScratchpadAttachment,
  type ScratchpadAttachmentAssertion,
  type GraphNodeSearchResult,
  type Ontology,
} from '../services/graphql'
import type { OntologyPackage } from '../types/ontology'

export default function Knowledge() {
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>('')
  const [attachments, setAttachments] = useState<ScratchpadAttachment[]>([])
  const [selectedAttachmentId, setSelectedAttachmentId] = useState<string>('')
  const [assertions, setAssertions] = useState<ScratchpadAttachmentAssertion[]>([])
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false)
  const [loadingAttachments, setLoadingAttachments] = useState(false)
  const [loadingAssertions, setLoadingAssertions] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Extraction state
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractionStatus, setExtractionStatus] = useState<string | null>(null)
  const [extractionError, setExtractionError] = useState<string | null>(null)
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isExtractingRef = useRef(false)
  const hasAutoFetchedRef = useRef(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const extractionStatusRef = useRef<string | null>(null)
  const [uploading, setUploading] = useState(false)

  // Modal state
  const [matchingModalOpen, setMatchingModalOpen] = useState(false)
  const [matchingEntityType, setMatchingEntityType] = useState<'source' | 'terminal' | null>(null)
  const [matchingAssertionIndex, setMatchingAssertionIndex] = useState<number | null>(null)

  // Edge type selection state
  const [loadingEdgeTypes, setLoadingEdgeTypes] = useState<Record<number, boolean>>({})
  const [edgeTypes, setEdgeTypes] = useState<Record<number, string[]>>({})

  // Ontology selection state
  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [selectedOntologyId, setSelectedOntologyId] = useState<string>('')
  const [loadingOntologies, setLoadingOntologies] = useState(false)
  const [, setLoadingOntologyPackage] = useState(false)
  const [selectedOntologyPackage, setSelectedOntologyPackage] = useState<OntologyPackage | null>(null)

  // Load workspaces on mount
  useEffect(() => {
    let active = true
    async function load() {
      setLoadingWorkspaces(true)
      setError(null)
      try {
        const data = await fetchWorkspaces()
        if (!active) return
        setWorkspaces(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load workspaces')
      } finally {
        if (active) setLoadingWorkspaces(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  // Load ontologies on mount
  useEffect(() => {
    let active = true
    async function load() {
      setLoadingOntologies(true)
      setError(null)
      try {
        const data = await fetchOntologies()
        if (!active) return
        setOntologies(data)
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load ontologies')
      } finally {
        if (active) setLoadingOntologies(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  // Load ontology package when ontology is selected
  useEffect(() => {
    if (!selectedOntologyId) {
      setSelectedOntologyPackage(null)
      return
    }

    let active = true
    async function load() {
      setLoadingOntologyPackage(true)
      setError(null)
      try {
        const packageData = await fetchOntologyPackage(selectedOntologyId)
        if (!active) return
        setSelectedOntologyPackage(packageData)
      } catch (e: any) {
        if (!active) return
        console.error('Failed to load ontology package:', e)
        setSelectedOntologyPackage(null)
      } finally {
        if (active) setLoadingOntologyPackage(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [selectedOntologyId])


  // Load attachments function (reusable)
  const loadAttachments = useCallback(async () => {
    if (!selectedWorkspaceId) {
      setAttachments([])
      setSelectedAttachmentId('')
      return
    }

    setLoadingAttachments(true)
    setError(null)
    try {
      const data = await fetchScratchpadAttachments(selectedWorkspaceId)
      setAttachments(data)
      // Reset selected attachment if it's not in the new list
      if (selectedAttachmentId && !data.find((a) => a.scratchpadAttachmentId === selectedAttachmentId)) {
        setSelectedAttachmentId('')
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load attachments')
    } finally {
      setLoadingAttachments(false)
    }
  }, [selectedWorkspaceId, selectedAttachmentId])

  // Load attachments when workspace is selected
  useEffect(() => {
    loadAttachments()
  }, [loadAttachments])

  // Handle file upload
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !selectedWorkspaceId) {
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setUploading(true)
    setError(null)
    try {
      const derivedTitle = file.name.replace(/\.[^.]+$/, '')
      await createScratchpadAttachment({
        workspaceId: selectedWorkspaceId,
        title: derivedTitle,
        description: null,
        file: file,
      })
      // Refresh attachments list
      await loadAttachments()
    } catch (e: any) {
      setError(e?.message || 'Failed to upload document')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [selectedWorkspaceId, loadAttachments])

  const handleGetDocumentKnowledge = useCallback(async () => {
    if (!selectedAttachmentId) return

    setLoadingAssertions(true)
    setError(null)
    try {
      const data = await fetchScratchpadAttachmentAssertions(selectedAttachmentId)
      setAssertions(data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load document knowledge')
      setAssertions([])
    } finally {
      setLoadingAssertions(false)
    }
  }, [selectedAttachmentId])

  // Define processing steps in order
  const processingSteps = [
    { id: 'unprocessed', label: 'Unprocessed' },
    { id: 'queued', label: 'Queued' },
    { id: 'downloading-blob', label: 'Download blob from storage' },
    { id: 'chunking/normalizing', label: 'Normalize document to spans' },
    { id: 'entity-extraction', label: 'Begin Graphiti entity extraction' },
    { id: 'entities-extracted', label: 'Entity extraction complete' },
    { id: 'assertion-mining', label: 'Begin mining assertions from extracted entities' },
    { id: 'entity-resolution', label: 'Begin resolving entities to domain graph' },
    { id: 'completed', label: 'Workflow finished successfully' },
  ]

  const handleExtractKnowledge = useCallback(async () => {
    if (!selectedAttachmentId) return

    setIsExtracting(true)
    isExtractingRef.current = true
    setExtractionStatus(null)
    setExtractionError(null)
    setError(null)

    try {
      await startDocumentIndexingPipeline(selectedAttachmentId)
      // Start polling immediately
      setExtractionStatus('queued')
    } catch (e: any) {
      setIsExtracting(false)
      isExtractingRef.current = false
      setError(e?.message || 'Failed to start document indexing')
    }
  }, [selectedAttachmentId])

  // Update refs when state changes
  useEffect(() => {
    isExtractingRef.current = isExtracting
  }, [isExtracting])

  useEffect(() => {
    extractionStatusRef.current = extractionStatus
  }, [extractionStatus])

  // Polling effect for extraction status
  useEffect(() => {
    if (!selectedAttachmentId) {
      // Clear polling if no attachment selected
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      return
    }

    // Check if we should poll - use refs to avoid dependency issues
    const shouldPoll = isExtractingRef.current || extractionStatusRef.current === 'failed'

    if (!shouldPoll) {
      // Clear polling if not needed
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      return
    }

    // Poll immediately, then set up interval
    const pollStatus = async () => {
      // Use the current selectedAttachmentId from closure
      const currentAttachmentId = selectedAttachmentId
      if (!currentAttachmentId) {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
        return
      }

      try {
        console.log('[Knowledge] Polling status for attachment:', currentAttachmentId)
        const attachment = await fetchScratchpadAttachmentById(currentAttachmentId)
        if (attachment) {
          const status = attachment.processingStatus || null
          const error = attachment.processingError || null

          console.log('[Knowledge] Status update:', { status, error, attachmentId: currentAttachmentId })

          setExtractionStatus(status)
          extractionStatusRef.current = status
          setExtractionError(error)

          // Update attachment in attachments array
          setAttachments((prev) =>
            prev.map((att) =>
              att.scratchpadAttachmentId === currentAttachmentId
                ? { ...att, processingStatus: status, processingError: error }
                : att
            )
          )

          // If status changed from failed to a new status, keep extracting active
          if (extractionStatusRef.current === 'failed' && status && status !== 'failed') {
            setIsExtracting(true)
            isExtractingRef.current = true
          }

          // Stop polling only when completed (keep polling for failed to detect restarts)
          if (status === 'completed') {
            console.log('[Knowledge] Extraction completed, stopping polling')
            setIsExtracting(false)
            isExtractingRef.current = false
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
              pollingIntervalRef.current = null
            }
          }
        }
      } catch (e: any) {
        console.error('[Knowledge] Failed to poll extraction status:', e)
        // Don't stop polling on error, just log it
      }
    }

    // Clear any existing interval first
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }

    // Poll immediately
    pollStatus()

    // Set up interval polling every 1 second
    pollingIntervalRef.current = setInterval(pollStatus, 1000)
    console.log('[Knowledge] Started polling interval for attachment:', selectedAttachmentId, 'isExtracting:', isExtractingRef.current)

    // Cleanup on unmount or dependency change
    return () => {
      console.log('[Knowledge] Cleaning up polling interval')
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [isExtracting, selectedAttachmentId, attachments])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [])

  // Get selected attachment details for preview
  const selectedAttachment = useMemo(() => {
    return attachments.find((a) => a.scratchpadAttachmentId === selectedAttachmentId) || null
  }, [attachments, selectedAttachmentId])

  // Get current status for timeline (after selectedAttachment is defined)
  const currentStatus = extractionStatus || selectedAttachment?.processingStatus
  const currentError = extractionError || selectedAttachment?.processingError
  const isFailed = currentStatus === 'failed'
  const isStatusCompleted = currentStatus === 'completed'

  // Extract base status and episode count from status string
  const parseStatus = useCallback((status: string | null | undefined) => {
    if (!status) return { baseStatus: null, episodeCount: null }
    
    // Handle formats like "entity-extraction (1 episodes)" or "entity-extraction (5 episodes)"
    const episodeMatch = status.match(/^(.+?)\s*\((\d+)\s+episodes?\)$/)
    if (episodeMatch) {
      return {
        baseStatus: episodeMatch[1].trim(),
        episodeCount: parseInt(episodeMatch[2], 10),
      }
    }
    
    return { baseStatus: status, episodeCount: null }
  }, [])

  // Find current step index
  const getCurrentStepIndex = useCallback(() => {
    if (!currentStatus || isFailed) return -1
    if (isStatusCompleted) return processingSteps.length - 1
    
    const { baseStatus } = parseStatus(currentStatus)
    if (!baseStatus) return 0
    
    const index = processingSteps.findIndex((step) => step.id === baseStatus)
    return index >= 0 ? index : 0
  }, [currentStatus, isFailed, isStatusCompleted, processingSteps, parseStatus])

  const currentStepIndex = getCurrentStepIndex()
  const { episodeCount } = parseStatus(currentStatus)

  // Reset extraction state when attachment changes
  useEffect(() => {
    // Clear assertions whenever selectedAttachmentId changes
    setAssertions([])
    hasAutoFetchedRef.current = false
    
    // Reset extraction state based on new attachment's status
    if (selectedAttachmentId) {
      const attachment = attachments.find((a) => a.scratchpadAttachmentId === selectedAttachmentId)
      const attachmentStatus = attachment?.processingStatus || null
      
      // If attachment is unprocessed or null, reset extraction state
      if (!attachmentStatus || attachmentStatus === 'unprocessed') {
        setIsExtracting(false)
        isExtractingRef.current = false
        setExtractionStatus(null)
        extractionStatusRef.current = null
        setExtractionError(null)
      } else {
        // For other statuses, set the status but don't set isExtracting unless actively processing
        setExtractionStatus(attachmentStatus)
        extractionStatusRef.current = attachmentStatus
        setExtractionError(attachment?.processingError || null)
        
        // Only set isExtracting if the status indicates active processing
        // (not completed, failed, or unprocessed)
        const isActivelyProcessing = attachmentStatus !== 'completed' && 
                                      attachmentStatus !== 'failed' && 
                                      attachmentStatus !== 'unprocessed'
        setIsExtracting(isActivelyProcessing)
        isExtractingRef.current = isActivelyProcessing
      }
    } else {
      // No attachment selected, reset everything
      setIsExtracting(false)
      isExtractingRef.current = false
      setExtractionStatus(null)
      extractionStatusRef.current = null
      setExtractionError(null)
    }
  }, [selectedAttachmentId, attachments])

  // Auto-fetch document knowledge when attachment is selected and already completed
  useEffect(() => {
    if (!selectedAttachmentId) {
      return
    }

    const attachment = attachments.find((a) => a.scratchpadAttachmentId === selectedAttachmentId)
    const attachmentStatus = attachment?.processingStatus || null
    const attachmentIsCompleted = attachmentStatus === 'completed'

    // If attachment is completed and we haven't fetched yet, auto-fetch
    if (
      attachmentIsCompleted &&
      !hasAutoFetchedRef.current &&
      !loadingAssertions
    ) {
      console.log('[Knowledge] Attachment already completed, auto-fetching document knowledge')
      hasAutoFetchedRef.current = true
      handleGetDocumentKnowledge()
    }
  }, [selectedAttachmentId, attachments, loadingAssertions, handleGetDocumentKnowledge])

  // Reset auto-fetch flag when extraction starts
  useEffect(() => {
    if (isExtracting) {
      hasAutoFetchedRef.current = false
    }
  }, [isExtracting])

  // Auto-fetch when extraction completes (during active extraction)
  useEffect(() => {
    if (
      isStatusCompleted &&
      selectedAttachmentId &&
      !hasAutoFetchedRef.current &&
      !loadingAssertions &&
      isExtracting
    ) {
      console.log('[Knowledge] Extraction completed, auto-fetching document knowledge')
      hasAutoFetchedRef.current = true
      handleGetDocumentKnowledge()
    }
  }, [isStatusCompleted, selectedAttachmentId, loadingAssertions, isExtracting, handleGetDocumentKnowledge])

  // Get entity name for modal
  const matchingEntityName = useMemo(() => {
    if (matchingAssertionIndex === null || matchingEntityType === null) return ''
    const assertion = assertions[matchingAssertionIndex]
    if (!assertion) return ''
    return matchingEntityType === 'source'
      ? assertion.source_entity.document_entity_name
      : assertion.terminal_entity.document_entity_name
  }, [assertions, matchingAssertionIndex, matchingEntityType])

  // Click handler for entity matching
  const handleEntityClick = useCallback((assertionIndex: number, entityType: 'source' | 'terminal') => {
    const assertion = assertions[assertionIndex]
    if (!assertion) return

    const entity = entityType === 'source' ? assertion.source_entity : assertion.terminal_entity
    // Only allow matching if domain_entity is not set
    if (!entity.domain_entity) {
      setMatchingAssertionIndex(assertionIndex)
      setMatchingEntityType(entityType)
      setMatchingModalOpen(true)
    }
  }, [assertions])

  // Handle node selection from modal
  const handleSelectMatch = useCallback((node: GraphNodeSearchResult) => {
    if (matchingAssertionIndex === null || matchingEntityType === null) return

    setAssertions((prev) => {
      const updated = [...prev]
      const assertion = { ...updated[matchingAssertionIndex] }
      
      if (matchingEntityType === 'source') {
        assertion.source_entity = {
          ...assertion.source_entity,
          domain_entity: {
            nodeId: node.id,
            nodeType: node.labels[0] || '',
            nodeName: node.properties?.name || node.id,
          },
        }
      } else {
        assertion.terminal_entity = {
          ...assertion.terminal_entity,
          domain_entity: {
            nodeId: node.id,
            nodeType: node.labels[0] || '',
            nodeName: node.properties?.name || node.id,
          },
        }
      }

      updated[matchingAssertionIndex] = assertion
      return updated
    })

    setMatchingModalOpen(false)
    setMatchingAssertionIndex(null)
    setMatchingEntityType(null)
  }, [matchingAssertionIndex, matchingEntityType])

  const handleCloseModal = useCallback(() => {
    setMatchingModalOpen(false)
    setMatchingAssertionIndex(null)
    setMatchingEntityType(null)
  }, [])

  // Load edge types for an assertion when source entity is matched
  const loadEdgeTypes = useCallback(
    async (assertionIndex: number, nodeType: string) => {
      if (edgeTypes[assertionIndex]) return // Already loaded

      setLoadingEdgeTypes((prev) => ({ ...prev, [assertionIndex]: true }))
      try {
        let types: string[] = []

        // If ontology is selected, extract relationship types from ontology
        if (selectedOntologyPackage) {
          // Find the entity in the ontology that matches the nodeType (case-insensitive)
          const entity = selectedOntologyPackage.entities.find(
            (e) => e.name.toLowerCase().trim() === nodeType.toLowerCase().trim()
          )
          
          if (entity) {
            console.log(`[Knowledge] Found entity "${entity.name}" (${entity.entity_id}) for nodeType "${nodeType}"`)
            
            // Find all relationships where this entity is either the source (from_entity) or target (to_entity)
            // This allows relationships to be traversed in both directions
            const relationshipsFrom = selectedOntologyPackage.relationships.filter(
              (rel) => rel.from_entity === entity.entity_id
            )
            const relationshipsTo = selectedOntologyPackage.relationships.filter(
              (rel) => rel.to_entity === entity.entity_id
            )
            
            // Combine both directions and extract unique relationship types
            const allRelationships = [...relationshipsFrom, ...relationshipsTo]
            console.log(`[Knowledge] Found ${allRelationships.length} relationships involving entity "${entity.name}":`, 
              allRelationships.map(r => `${r.relationship_type} (${r.from_entity} -> ${r.to_entity})`))
            
            types = [...new Set(allRelationships.map((rel) => rel.relationship_type))]
          } else {
            console.warn(`[Knowledge] Could not find entity with name "${nodeType}" in ontology. Available entities:`, 
              selectedOntologyPackage.entities.map(e => e.name))
          }
        }

        // If no ontology or no relationships found, fall back to graph relationship types
        if (types.length === 0) {
          console.log(`[Knowledge] Falling back to graph relationship types for nodeType "${nodeType}"`)
          types = await fetchGraphNodeRelationshipTypes(nodeType)
        }

        console.log(`[Knowledge] Final edge types for assertion ${assertionIndex}:`, types)
        setEdgeTypes((prev) => ({ ...prev, [assertionIndex]: types }))
      } catch (e: any) {
        console.error('Failed to load edge types:', e)
      } finally {
        setLoadingEdgeTypes((prev) => ({ ...prev, [assertionIndex]: false }))
      }
    },
    [edgeTypes, selectedOntologyPackage]
  )

  // Handle edge type change
  const handleEdgeTypeChange = useCallback((assertionIndex: number, edgeType: string) => {
    setAssertions((prev) => {
      const updated = [...prev]
      const assertion = { ...updated[assertionIndex] }
      assertion.domain_edge_type = edgeType || null
      updated[assertionIndex] = assertion
      return updated
    })
  }, [])

  // Load edge types when source entity gets matched
  useEffect(() => {
    assertions.forEach((assertion, index) => {
      if (assertion.source_entity.domain_entity?.nodeType && !edgeTypes[index]) {
        loadEdgeTypes(index, assertion.source_entity.domain_entity.nodeType)
      }
    })
  }, [assertions, edgeTypes, loadEdgeTypes])

  return (
    <Box sx={{ maxWidth: 1600, mx: 'auto', p: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Knowledge Management
        </Typography>
        <Typography color="text.secondary">
          Select a workspace and document to extract knowledge graph assertions from document content.
        </Typography>
      </Box>

      {/* Controls */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'stretch', md: 'flex-end' }}>
          <FormControl fullWidth sx={{ minWidth: 200 }}>
            <InputLabel id="workspace-select-label">Workspace</InputLabel>
            <Select
              labelId="workspace-select-label"
              id="workspace-select"
              value={selectedWorkspaceId}
              label="Workspace"
              onChange={(e) => setSelectedWorkspaceId(e.target.value)}
              disabled={loadingWorkspaces}
            >
              {loadingWorkspaces ? (
                <MenuItem disabled>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Loading...
                </MenuItem>
              ) : (
                workspaces.map((ws) => (
                  <MenuItem key={ws.workspaceId} value={ws.workspaceId}>
                    {ws.name}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ minWidth: 200 }} disabled={!selectedWorkspaceId || loadingAttachments}>
            <InputLabel id="attachment-select-label">Document</InputLabel>
            <Select
              labelId="attachment-select-label"
              id="attachment-select"
              value={selectedAttachmentId}
              label="Document"
              onChange={(e) => setSelectedAttachmentId(e.target.value)}
              disabled={!selectedWorkspaceId || loadingAttachments}
            >
              {loadingAttachments ? (
                <MenuItem disabled>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Loading...
                </MenuItem>
              ) : attachments.length === 0 ? (
                <MenuItem disabled>No documents available</MenuItem>
              ) : (
                attachments.map((att) => (
                  <MenuItem key={att.scratchpadAttachmentId} value={att.scratchpadAttachmentId}>
                    {att.title || 'Untitled'}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ minWidth: 200 }}>
            <InputLabel id="ontology-select-label">Ontology</InputLabel>
            <Select
              labelId="ontology-select-label"
              id="ontology-select"
              value={selectedOntologyId}
              label="Ontology"
              onChange={(e) => setSelectedOntologyId(e.target.value)}
              disabled={loadingOntologies}
            >
              {loadingOntologies ? (
                <MenuItem disabled>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  Loading...
                </MenuItem>
              ) : (
                [
                  <MenuItem key="" value="">
                    <em>None</em>
                  </MenuItem>,
                  ...ontologies.map((ont) => (
                    <MenuItem key={ont.ontologyId} value={ont.ontologyId}>
                      {ont.name}
                    </MenuItem>
                  )),
                ]
              )}
            </Select>
          </FormControl>

          <Box>
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
              accept="*/*"
            />
            <Button
              variant="primary"
              onClick={() => fileInputRef.current?.click()}
              disabled={!selectedWorkspaceId || uploading || loadingAttachments}
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </Button>
          </Box>

          <Box>
            <Button
              variant="primary"
              onClick={handleExtractKnowledge}
              disabled={!selectedAttachmentId || isExtracting || selectedAttachment?.processingStatus === 'completed'}
            >
              {isExtracting ? 'Extracting...' : 'Extract Knowledge'}
            </Button>
          </Box>

        </Stack>
      </Paper>

      {/* Error Display */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Extraction Status Display - Timeline */}
      {(isExtracting || extractionStatus || extractionError || selectedAttachment?.processingStatus || selectedAttachment?.processingError) && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          {currentError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              <Typography variant="body2" fontWeight={600} gutterBottom>
                Extraction Failed
              </Typography>
              <Typography variant="body2">{currentError}</Typography>
            </Alert>
          )}
          
          <Typography variant="subtitle1" fontWeight={600} gutterBottom sx={{ mb: 3 }}>
            Extraction Progress
          </Typography>

          <Box sx={{ position: 'relative', py: 2, overflowX: 'auto' }}>
            {/* Timeline Steps - Horizontal */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 0,
                minWidth: 'max-content',
                position: 'relative',
              }}
            >
              {processingSteps.map((step, index) => {
                const stepCompleted = index < currentStepIndex || (isStatusCompleted && index === processingSteps.length - 1)
                // Don't show as active if status is "unprocessed" - it means workflow hasn't started
                const isActive = index === currentStepIndex && !isFailed && !isStatusCompleted && currentStatus !== 'unprocessed'
                const isPending = index > currentStepIndex || (index === currentStepIndex && currentStatus === 'unprocessed')
                const isLast = index === processingSteps.length - 1

                return (
                  <Box
                    key={step.id}
                    sx={{
                      position: 'relative',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      flex: '0 0 auto',
                      minWidth: 120,
                      maxWidth: 150,
                    }}
                  >
                    {/* Step Icon */}
                    <Box
                      sx={{
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 40,
                        height: 40,
                        flexShrink: 0,
                        zIndex: 2,
                        bgcolor: 'background.paper',
                      }}
                    >
                      {stepCompleted ? (
                        <CheckCircleIcon
                          sx={{
                            fontSize: 32,
                            color: 'success.main',
                          }}
                        />
                      ) : isActive ? (
                        <Box
                          sx={{
                            position: 'relative',
                            width: 32,
                            height: 32,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <CircularProgress
                            size={32}
                            sx={{
                              color: 'primary.main',
                              position: 'absolute',
                            }}
                          />
                          <Box
                            sx={{
                              width: 16,
                              height: 16,
                              borderRadius: '50%',
                              bgcolor: 'primary.main',
                              border: '2px solid',
                              borderColor: 'background.paper',
                            }}
                          />
                        </Box>
                      ) : (
                        <RadioButtonUncheckedIcon
                          sx={{
                            fontSize: 32,
                            color: isPending ? 'action.disabled' : 'action.active',
                          }}
                        />
                      )}
                    </Box>

                    {/* Connecting Line */}
                    {!isLast && (
                      <Box
                        sx={{
                          position: 'absolute',
                          left: '50%',
                          top: 20,
                          width: 'calc(100% - 40px)',
                          height: 2,
                          bgcolor: index < currentStepIndex ? 'success.main' : 'divider',
                          zIndex: 1,
                          transform: 'translateX(20px)',
                        }}
                      />
                    )}

                    {/* Step Label */}
                    <Box
                      sx={{
                        mt: 1.5,
                        textAlign: 'center',
                        px: 1,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: isActive ? 600 : stepCompleted ? 500 : 400,
                          color: isPending
                            ? 'text.disabled'
                            : isActive
                            ? 'primary.main'
                            : stepCompleted
                            ? 'text.primary'
                            : 'text.secondary',
                          fontSize: '0.875rem',
                          lineHeight: 1.4,
                        }}
                      >
                        {step.label}
                      </Typography>
                      {isActive && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ mt: 0.5, display: 'block', fontSize: '0.75rem' }}
                        >
                          {episodeCount !== null
                            ? `${episodeCount} ${episodeCount === 1 ? 'episode' : 'episodes'}`
                            : 'In progress...'}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                )
              })}
            </Box>
          </Box>
        </Paper>
      )}

      {/* Two Column Layout: Assertions and Preview */}
      {selectedAttachmentId && (
        <Box sx={{ display: 'flex', gap: 3, flex: 1, minHeight: 600, maxHeight: 'calc(100vh - 300px)' }}>
          {/* Left Column: Knowledge Assertions */}
          <Box sx={{ width: '40%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Knowledge Graph Assertions
              {assertions.length > 0 && ` (${assertions.length})`}
            </Typography>
            
            {loadingAssertions ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
                <CircularProgress />
              </Box>
            ) : assertions.length > 0 ? (
              <Box
                sx={{
                  flex: 1,
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  mt: 2,
                  minHeight: 0,
                }}
              >
                <Stack spacing={2}>
                  {assertions.map((assertion, index) => (
                    <Paper
                      key={index}
                      variant="outlined"
                      sx={{
                        p: 2,
                        borderRadius: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        {/* Source Entity */}
                        <Tooltip
                          title={
                            assertion.source_entity.domain_entity
                              ? `Matched to: ${assertion.source_entity.domain_entity.nodeName}`
                              : 'Click to match with domain node'
                          }
                        >
                          <Box
                            onClick={() => handleEntityClick(index, 'source')}
                            sx={{
                              px: 2,
                              py: 1,
                              borderRadius: 1,
                              bgcolor: assertion.source_entity.domain_entity
                                ? 'success.main'
                                : 'primary.main',
                              color: 'primary.contrastText',
                              fontWeight: 600,
                              cursor: assertion.source_entity.domain_entity ? 'default' : 'pointer',
                              border: assertion.source_entity.domain_entity
                                ? 'none'
                                : '2px dashed',
                              borderColor: assertion.source_entity.domain_entity
                                ? 'transparent'
                                : 'primary.light',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              transition: 'all 0.2s',
                              '&:hover': {
                                opacity: assertion.source_entity.domain_entity ? 1 : 0.8,
                                transform: assertion.source_entity.domain_entity ? 'none' : 'scale(1.05)',
                              },
                            }}
                          >
                            {assertion.source_entity.domain_entity && (
                              <Checkmark size="16" />
                            )}
                            {assertion.source_entity.document_entity_name}
                          </Box>
                        </Tooltip>

                        {/* Arrow and Assertion */}
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            flex: 1,
                            minWidth: 200,
                          }}
                        >
                          <Box
                            sx={{
                              width: 40,
                              height: 2,
                              bgcolor: 'text.secondary',
                            }}
                          />
                          <Typography
                            variant="body2"
                            sx={{
                              px: 1.5,
                              py: 0.5,
                              borderRadius: 1,
                              bgcolor: 'background.default',
                              border: '1px solid',
                              borderColor: 'divider',
                              fontStyle: 'italic',
                              color: 'text.secondary',
                            }}
                          >
                            {assertion.assertion}
                          </Typography>
                          <Box
                            sx={{
                              width: 40,
                              height: 2,
                              bgcolor: 'text.secondary',
                            }}
                          />
                          <Box
                            component="span"
                            sx={{
                              width: 0,
                              height: 0,
                              borderLeft: '6px solid',
                              borderLeftColor: 'text.secondary',
                              borderTop: '4px solid transparent',
                              borderBottom: '4px solid transparent',
                            }}
                          />
                        </Box>

                        {/* Terminal Entity */}
                        <Tooltip
                          title={
                            assertion.terminal_entity.domain_entity
                              ? `Matched to: ${assertion.terminal_entity.domain_entity.nodeName}`
                              : 'Click to match with domain node'
                          }
                        >
                          <Box
                            onClick={() => handleEntityClick(index, 'terminal')}
                            sx={{
                              px: 2,
                              py: 1,
                              borderRadius: 1,
                              bgcolor: assertion.terminal_entity.domain_entity
                                ? 'success.main'
                                : 'primary.main',
                              color: 'primary.contrastText',
                              fontWeight: 600,
                              cursor: assertion.terminal_entity.domain_entity ? 'default' : 'pointer',
                              border: assertion.terminal_entity.domain_entity
                                ? 'none'
                                : '2px dashed',
                              borderColor: assertion.terminal_entity.domain_entity
                                ? 'transparent'
                                : 'primary.light',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              transition: 'all 0.2s',
                              '&:hover': {
                                opacity: assertion.terminal_entity.domain_entity ? 1 : 0.8,
                                transform: assertion.terminal_entity.domain_entity ? 'none' : 'scale(1.05)',
                              },
                            }}
                          >
                            {assertion.terminal_entity.domain_entity && (
                              <Checkmark size="16" />
                            )}
                            {assertion.terminal_entity.document_entity_name}
                          </Box>
                        </Tooltip>
                      </Box>

                      {/* Domain Edge Type Selector */}
                      {assertion.source_entity.domain_entity && (
                        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                          <FormControl fullWidth size="small">
                            <InputLabel id={`edge-type-select-${index}`}>Domain Edge Type</InputLabel>
                            <Select
                              labelId={`edge-type-select-${index}`}
                              id={`edge-type-select-${index}`}
                              value={assertion.domain_edge_type || ''}
                              label="Domain Edge Type"
                              onChange={(e) => handleEdgeTypeChange(index, e.target.value)}
                              disabled={loadingEdgeTypes[index]}
                            >
                              {loadingEdgeTypes[index] ? (
                                <MenuItem disabled>
                                  <CircularProgress size={16} sx={{ mr: 1 }} />
                                  Loading edge types...
                                </MenuItem>
                              ) : edgeTypes[index] && edgeTypes[index].length > 0 ? (
                                [
                                  <MenuItem key="none" value="">
                                    <em>None</em>
                                  </MenuItem>,
                                  ...edgeTypes[index].map((edgeType) => (
                                    <MenuItem key={edgeType} value={edgeType}>
                                      {edgeType}
                                    </MenuItem>
                                  )),
                                ]
                              ) : (
                                <MenuItem disabled>No edge types available</MenuItem>
                              )}
                            </Select>
                          </FormControl>
                          {assertion.domain_edge_type && (
                            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                              Selected: <strong>{assertion.domain_edge_type}</strong>
                            </Typography>
                          )}
                        </Box>
                      )}

                      {/* Submit Knowledge Button - Show when all three pieces are matched */}
                      {assertion.source_entity.domain_entity &&
                        assertion.terminal_entity.domain_entity &&
                        assertion.domain_edge_type && (
                          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                            <Button variant="primary" size="sm" fullWidth>
                              Submit Knowledge
                            </Button>
                          </Box>
                        )}

                      {/* Source Metadata */}
                      {(assertion.source || assertion.source_url) && (
                        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                          <Typography variant="caption" color="text.secondary">
                            Source: {assertion.source}
                            {assertion.source_url && (
                              <>
                                {' • '}
                                <Box
                                  component="a"
                                  href={assertion.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  sx={{ color: 'primary.main', textDecoration: 'none' }}
                                >
                                  {assertion.source_url}
                                </Box>
                              </>
                            )}
                          </Typography>
                        </Box>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Box>
            ) : (
              <Alert severity="info" sx={{ mt: 2 }}>
                {selectedAttachment?.processingStatus === 'completed'
                  ? 'Loading assertions...'
                  : 'No assertions found. Extract knowledge to generate assertions.'}
              </Alert>
            )}
          </Box>

          {/* Right Column: File Preview */}
          <Box sx={{ width: '60%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Document Preview
            </Typography>
            <Box sx={{ flex: 1, mt: 2, minHeight: 0, overflow: 'hidden' }}>
              <FilePreview
                attachmentId={selectedAttachmentId}
                fileType={selectedAttachment?.fileType || null}
                title={selectedAttachment?.title || null}
              />
            </Box>
          </Box>
        </Box>
      )}

      {/* Empty State - No document selected */}
      {!selectedAttachmentId && (
        <Alert severity="info">
          Select a document to view knowledge assertions and preview.
        </Alert>
      )}

      {/* Entity Matching Modal */}
      <EntityMatchingModal
        open={matchingModalOpen}
        onClose={handleCloseModal}
        onSelect={handleSelectMatch}
        entityName={matchingEntityName}
        entityType={matchingEntityType || 'source'}
        ontologyId={selectedOntologyId || null}
        ontologyPackage={selectedOntologyPackage}
      />
    </Box>
  )
}
