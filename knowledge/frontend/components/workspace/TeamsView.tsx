import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'
import { fetchAiTeamMembers, type AiTeamMember } from '../../services/graphql'
import AiTeamViewAnimated from './AiTeamViewAnimated'

export default function TeamsView({ workspaceId }: { workspaceId?: string | null }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [members, setMembers] = useState<AiTeamMember[]>([])

  if (!workspaceId) {
    return (
      <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 0.5, color: 'text.secondary' }}>
        Select a workspace to view AI team members.
      </Box>
    )
  }

  useEffect(() => {
    if (!workspaceId) return
    const wsId = workspaceId // TypeScript narrowing
    let mounted = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAiTeamMembers(wsId)
        if (!mounted) return
        setMembers(data)
      } catch (e: any) {
        if (!mounted) return
        setError(e?.message || 'Failed to load AI team members')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [workspaceId])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
        <CircularProgress size={22} />
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 0.5 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    )
  }

  if (!members.length) {
    return (
      <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 0.5, color: 'text.secondary' }}>
        No AI team members found for this workspace.
      </Box>
    )
  }

  return <AiTeamViewAnimated />
}

