import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Box, Alert, CircularProgress, Button as MUIButton, Typography } from '@mui/material'
import ChatDock from '../components/workspace/ChatDock'
import OntologyEditor from '../components/ontology/OntologyEditor'
import { useChatStream } from '../components/workspace/chat/useChatStream'
import {
  startOntologyCreationPipeline,
  appendScenarioRunLog,
  fetchWorkspaces,
  getTenantId,
  createOntology,
  updateOntology,
  fetchUsers,
  fetchOntologies,
  getApiBase,
  downloadFile,
} from '../services/graphql'
import { useWorkspace } from '../contexts/WorkspaceContext'
import type { OntologyPackage } from '../types/ontology'

export default function OntologyCreation() {
  const navigate = useNavigate()
  const { ontologyId: ontologyIdParam } = useParams<{ ontologyId?: string }>()
  const { currentWorkspace } = useWorkspace()
  const [ontologyPackage, setOntologyPackage] = useState<OntologyPackage | null>(null)
  const [ontologyId, setOntologyId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [isFinalized, setIsFinalized] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  // Ref to track current ontology package for sending with messages
  const ontologyPackageRef = useRef<OntologyPackage | null>(null)
  const activeStreamRunIdRef = useRef<string | null>(null)

  // Update ref when ontology package changes
  useEffect(() => {
    ontologyPackageRef.current = ontologyPackage
  }, [ontologyPackage])

  // Initialize workflow on mount
  useEffect(() => {
    let active = true

    async function initializeWorkflow() {
      try {
        setIsInitializing(true)
        setError(null)

        // If loading an existing ontology
        if (ontologyIdParam) {
          const ontologies = await fetchOntologies()
          const existingOntology = ontologies.find((o) => o.ontologyId === ontologyIdParam)

          if (!existingOntology) {
            throw new Error('Ontology not found')
          }

          if (!active) return

          setOntologyId(existingOntology.ontologyId)

          // If there's a runId, reconnect to the stream
          if (existingOntology.runId) {
            setRunId(existingOntology.runId)
            setIsInitializing(false)
            return
          } else {
            // No runId, need to start a new workflow
            // Get workspace ID
            let workspaceId = currentWorkspace?.workspaceId
            if (!workspaceId) {
              const workspaces = await fetchWorkspaces()
              if (workspaces.length > 0) {
                workspaceId = workspaces[0].workspaceId
              } else {
                throw new Error('No workspace found. Please create a workspace first.')
              }
            }

            // Start the ontology creation pipeline
            const result = await startOntologyCreationPipeline(workspaceId, existingOntology.ontologyId)

            if (!active) return

            if (!result.success) {
              throw new Error('Failed to start ontology creation pipeline')
            }

            setRunId(result.runId)
            // Update ontology with new runId
            await updateOntology(
              existingOntology.ontologyId,
              existingOntology.name,
              existingOntology.description || undefined,
              existingOntology.semVer,
              existingOntology.status,
              result.runId
            )
            setIsInitializing(false)
            return
          }
        }

        // Creating a new ontology
        // Get workspace ID - use current workspace if available, otherwise get first workspace
        let workspaceId = currentWorkspace?.workspaceId
        if (!workspaceId) {
          const workspaces = await fetchWorkspaces()
          if (workspaces.length > 0) {
            workspaceId = workspaces[0].workspaceId
          } else {
            throw new Error('No workspace found. Please create a workspace first.')
          }
        }

        // Get tenant ID
        const tenantId = getTenantId() || currentWorkspace?.tenantId
        if (!tenantId) {
          throw new Error('No tenant ID found')
        }

        // Get current user ID
        const users = await fetchUsers()
        const createdBy = users.length > 0 ? users[0].userId : undefined

        // Create placeholder ontology before starting workflow
        const newOntologyId = await createOntology(
          tenantId,
          'New Ontology',
          'Ontology being created',
          '0.1.0',
          createdBy,
          'draft'
        )

        if (!active) return

        setOntologyId(newOntologyId)

        // Start the ontology creation pipeline
        const result = await startOntologyCreationPipeline(workspaceId, newOntologyId)

        if (!active) return

        if (!result.success) {
          throw new Error('Failed to start ontology creation pipeline')
        }

        setRunId(result.runId)
        setIsInitializing(false)
      } catch (e: any) {
        if (!active) return
        console.error('[OntologyCreation] Failed to initialize workflow:', e)
        setError(e?.message || 'Failed to start ontology creation workflow')
        setIsInitializing(false)
      }
    }
    //if(!isInitializing) {
      initializeWorkflow()
    //}

    return () => {
      active = false
    }
  }, [ontologyIdParam])

  // Handle ontology proposed event
  const handleOntologyProposed = useCallback((pkg: OntologyPackage) => {
    console.log('[OntologyCreation] Ontology proposed:', pkg)
    setOntologyPackage(pkg)
  }, [])

  // Handle ontology updated event
  const handleOntologyUpdated = useCallback((pkg: OntologyPackage, updateSummary?: string) => {
    console.log('[OntologyCreation] Ontology updated:', pkg, updateSummary)
    setOntologyPackage(pkg)
    // Optionally show a notification about the update
    if (updateSummary) {
      console.log('[OntologyCreation] Update summary:', updateSummary)
    }
  }, [])

  // Handle ontology finalized event
  const handleOntologyFinalized = useCallback((pkg: OntologyPackage) => {
    console.log('[OntologyCreation] Ontology finalized:', pkg)
    setOntologyPackage(pkg)
    setIsFinalized(true)
  }, [])

  // Use chat stream hook for SSE connection
  const chatStream = useChatStream({
    workspaceId: currentWorkspace?.workspaceId,
    currentWorkspace: currentWorkspace || undefined,
    initialMessages: [], // Start with empty messages, will be populated from stream
    onOntologyProposed: handleOntologyProposed,
    onOntologyUpdated: handleOntologyUpdated,
    onOntologyFinalized: handleOntologyFinalized,
  })

  // Connect to SSE stream when runId is available
  useEffect(() => {
    const tenantId = getTenantId()
    if (runId && tenantId && runId !== activeStreamRunIdRef.current) {
      activeStreamRunIdRef.current = runId
      chatStream.startStream(runId, tenantId)
    }
    // Cleanup on unmount
    return () => {
      if (activeStreamRunIdRef.current) {
        chatStream.stopStream()
        activeStreamRunIdRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]) // Only depend on runId, not chatStream object

  // Handle chat message submission
  const handleChatSubmit = useCallback(
    async (message: string) => {
      if (!runId || !message.trim()) return

      try {
        // Create user_message event with current ontology package
        const userMessageEvent = {
          event_type: 'user_message',
          message: message,
          metadata: {
            current_ontology_package: ontologyPackageRef.current,
          },
        }

        // Append to scenario run log (this sends the message to the workflow)
        await appendScenarioRunLog(runId, JSON.stringify(userMessageEvent))
        // The chatStream hook will handle setting isAgentWorking based on events
      } catch (e: any) {
        console.error('[OntologyCreation] Failed to send message:', e)
        setError(e?.message || 'Failed to send message')
      }
    },
    [runId]
  )

  // Handle finalize ontology
  const handleFinalizeOntology = useCallback(async () => {
    if (!runId || !ontologyPackage) return

    try {
      // Create finalize_ontology event with final ontology package
      const finalizeEvent = {
        event_type: 'finalize_ontology',
        metadata: {
          final_ontology_package: ontologyPackage,
        },
      }

      // Append to scenario run log
      await appendScenarioRunLog(runId, JSON.stringify(finalizeEvent))
      // The chatStream hook will handle setting isAgentWorking based on events
    } catch (e: any) {
      console.error('[OntologyCreation] Failed to finalize ontology:', e)
      setError(e?.message || 'Failed to finalize ontology')
    }
  }, [runId, ontologyPackage])

  // Handle ontology editor changes (don't auto-save, wait for Save Draft button)
  const handleOntologyChange = useCallback((pkg: OntologyPackage) => {
    setOntologyPackage(pkg)
  }, [])

  // Handle Save Draft button click
  const handleSaveDraft = useCallback(async () => {
    if (!ontologyId || !ontologyPackage) return

    setIsSaving(true)
    setError(null)

    try {
      await updateOntology(
        ontologyId,
        ontologyPackage.title,
        ontologyPackage.description,
        ontologyPackage.semantic_version,
        'draft',
        runId || undefined
      )
    } catch (e: any) {
      console.error('[OntologyCreation] Failed to save draft:', e)
      setError(e?.message || 'Failed to save draft')
    } finally {
      setIsSaving(false)
    }
  }, [ontologyId, ontologyPackage, runId])

  const handleDownloadDraft = useCallback(async () => {
    if (!ontologyId) return
    setIsDownloading(true)
    setError(null)
    try {
      const apiBase = getApiBase().replace(/\/$/, '')
      const url = `${apiBase}/api/ontology/${ontologyId}/draft/download`
      const name = (ontologyPackage?.title || 'ontology').replace(/[^a-zA-Z0-9-_]/g, '_')
      await downloadFile(url, `${name}-draft.json`)
    } catch (e: any) {
      setError(e?.message || 'Failed to download ontology JSON')
    } finally {
      setIsDownloading(false)
    }
  }, [ontologyId, ontologyPackage?.title])

  if (isInitializing) {
    return (
      <Box
        sx={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6">Starting ontology creation workflow...</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Please wait while we connect to the AI agent.
          </Typography>
        </Box>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', overflow: 'hidden', position: 'relative' }}>
      {/* Left: Ontology Editor */}
      <Box
        sx={{
          width: { xs: 0, sm: '65%' },
          display: { xs: 'none', sm: 'flex' },
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          sx={{
            p: 2,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="h6" fontWeight={600}>
            Ontology Editor
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {ontologyId && (
              <MUIButton
                variant="outlined"
                onClick={handleDownloadDraft}
                disabled={isDownloading}
              >
                {isDownloading ? 'Downloading...' : 'Download JSON'}
              </MUIButton>
            )}
            {ontologyPackage && !isFinalized && (
              <>
                <MUIButton
                  variant="outlined"
                  onClick={handleSaveDraft}
                  disabled={isSaving || !ontologyId || chatStream.isAgentWorking || chatStream.isTurnOpen}
                >
                  {isSaving ? 'Saving...' : 'Save Draft'}
                </MUIButton>
                <MUIButton
                  variant="contained"
                  color="primary"
                  onClick={handleFinalizeOntology}
                  disabled={chatStream.isAgentWorking || chatStream.isTurnOpen}
                >
                  Finalize Ontology
                </MUIButton>
              </>
            )}
            {isFinalized && (
              <MUIButton variant="outlined" onClick={() => navigate('/knowledge')}>
                Back to Knowledge
              </MUIButton>
            )}
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ m: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          <OntologyEditor
            ontologyPackage={ontologyPackage}
            onChange={handleOntologyChange}
            editable={!isFinalized}
            height="100%"
          />
        </Box>
      </Box>

      {/* Right: Chat Interface */}
      <Box
        sx={{
          width: { xs: '100%', sm: '35%' },
          borderLeft: { xs: 'none', sm: '1px solid' },
          borderColor: { xs: 'transparent', sm: 'divider' },
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          position: 'relative',
        }}
      >
        <ChatDock
          open={true}
          onClose={() => navigate('/knowledge')}
          onSubmit={handleChatSubmit}
          setupRunId={runId}
          initialMessages={chatStream.messages}
          initialIsAgentWorking={chatStream.isAgentWorking}
          inputDisabled={isFinalized || chatStream.isAgentWorking || chatStream.isTurnOpen}
          onOntologyProposed={handleOntologyProposed}
          onOntologyUpdated={handleOntologyUpdated}
          onOntologyFinalized={handleOntologyFinalized}
          isSetupMode={true}
          fullScreen={true}
        />
      </Box>
    </Box>
  )
}
