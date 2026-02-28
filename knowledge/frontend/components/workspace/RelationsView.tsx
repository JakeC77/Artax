import { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'
import WorkspaceGraph from '../relations/WorkspaceGraph'
import {
  fetchWorkspaceItems,
  fetchGraphEdgeById,
  fetchGraphNodeById,
  fetchNeighbors,
  type GraphNode,
  type GraphEdge,
  addWorkspaceNode,
  deleteWorkspaceItem,
} from '../../services/graphql'

function canonicalEdgeKey(e: GraphEdge): string {
  return `${e.fromId}__${e.toId}__${e.type || ''}`
}

export default function RelationsView({ workspaceId }: { workspaceId?: string | null }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [workspaceNodeIds, setWorkspaceNodeIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    let mounted = true
    async function load() {
      if (!workspaceId) {
        setNodes([])
        setEdges([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        const items = await fetchWorkspaceItems(workspaceId)
        const nodeIdsInWorkspace = new Set(items.filter((i) => !i.graphEdgeId).map((i) => i.graphNodeId))
        const nodeIds = new Set(items.filter((i) => !i.graphEdgeId).map((i) => i.graphNodeId))
        const edgeIds = items.map((i) => i.graphEdgeId).filter((x): x is string => !!x)

        const fetchedEdges = await Promise.all(edgeIds.map((id) => fetchGraphEdgeById(id)))
        const validEdges = fetchedEdges.filter((e): e is GraphEdge => !!e)
        for (const e of validEdges) {
          nodeIds.add(e.fromId)
          nodeIds.add(e.toId)
        }

        const fetchedNodes = await Promise.all(Array.from(nodeIds).map((id) => fetchGraphNodeById(id)))
        const validNodes = fetchedNodes.filter((n): n is GraphNode => !!n)

        const nodeIdSet = new Set(validNodes.map((n) => n.id))
        const inferredArrays = await Promise.all(
          Array.from(nodeIdSet).map((id) =>
            fetchNeighbors(id).then((nb) => nb.edges).catch(() => [] as GraphEdge[]),
          ),
        )
        const inferredEdges = inferredArrays
          .flat()
          .filter((e) => nodeIdSet.has(e.fromId) && nodeIdSet.has(e.toId))

        const seen = new Set<string>()
        const combined: GraphEdge[] = []
        for (const e of [...validEdges, ...inferredEdges]) {
          const k = canonicalEdgeKey(e)
          if (seen.has(k)) continue
          seen.add(k)
          combined.push(e)
        }

        if (!mounted) return
        setNodes(validNodes)
        setEdges(combined)
        setWorkspaceNodeIds(nodeIdsInWorkspace)
      } catch (e: any) {
        if (!mounted) return
        setError(e?.message || 'Failed to load workspace graph')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [workspaceId])

  if (!workspaceId) {
    return (
      <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 0.5, color: 'text.secondary' }}>
        Select a workspace to view relations.
      </Box>
    )
  }

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

  if (!nodes.length) {
    return (
      <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 0.5, color: 'text.secondary' }}>
        No graph items saved to this workspace yet.
      </Box>
    )
  }

  return (
    <WorkspaceGraph
      workspaceId={workspaceId}
      nodes={nodes}
      edges={edges}
      workspaceNodeIds={Array.from(workspaceNodeIds)}
      onNodeDoubleClick={async (nodeId) => {
        try {
          const res = await fetchNeighbors(nodeId)
          if (!res) return
          setNodes((prev) => {
            const seen = new Set(prev.map((n) => n.id))
            const toAdd = res.nodes.filter((n) => !seen.has(n.id))
            return toAdd.length ? [...prev, ...toAdd] : prev
          })
          setEdges((prev) => {
            const seen = new Set(prev.map((e) => canonicalEdgeKey(e)))
            const toAdd = res.edges.filter((e) => !seen.has(canonicalEdgeKey(e)))
            return toAdd.length ? [...prev, ...toAdd] : prev
          })
        } catch (e) {
          // Silent fail for now; could surface toast later
          console.warn('Failed to load neighbors for', nodeId, e)
        }
      }}
      onAddNodeToWorkspace={async (node) => {
        if (!workspaceId) return
        try {
          await addWorkspaceNode({
            workspaceId,
            graphNodeId: node.id,
            graphEdgeId: null,
            labels: node.labels,
            pinnedBy: '11111111-1111-1111-1111-111111111111', // TODO: Get from JWT if backend doesn't handle it
          })
          setWorkspaceNodeIds((prev) => new Set([...Array.from(prev), node.id]))
          alert('Added to workspace')
        } catch (e: any) {
          alert(e?.message || 'Failed to add to workspace')
        }
      }}
      onRemoveNodeFromWorkspace={async (nodeId) => {
        if (!workspaceId) return
        const ok = window.confirm('Remove this item from the workspace?')
        if (!ok) return
        try {
          await deleteWorkspaceItem({ workspaceId, graphNodeId: nodeId, graphEdgeId: null })
          setWorkspaceNodeIds((prev) => {
            const next = new Set(Array.from(prev))
            next.delete(nodeId)
            return next
          })
          alert('Removed from workspace')
        } catch (e: any) {
          alert(e?.message || 'Failed to remove from workspace')
        }
      }}
    />
  )
}
