import { useEffect, useMemo, useState } from 'react'
import { Box, IconButton, Tooltip, Chip, Stack, Typography } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { ReactFlow, Background, Controls, ReactFlowProvider, Position, Handle, applyNodeChanges, type NodeChange } from '@xyflow/react'
import type { Edge as RFEdge, Node as RFNode, NodeProps as RFNodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { GraphNode, GraphEdge } from '../../services/graphql'
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'

function labelForNode(n: GraphNode): string {
  const nameProp = n.properties?.find((p) => p.key.toLowerCase() === 'name')?.value
  const base = nameProp || n.id
  const typeLabel = n.labels?.[0]
  return typeLabel ? `${base} — ${typeLabel}` : base
}

function typeForNode(n: GraphNode): string {
  return n.labels?.[0] || 'Unknown'
}

const KNOWN_TYPE_COLORS: Record<string, string> = {
  Plan: '#1976d2',
  Member: '#6a1b9a',
  Medication: '#d32f2f',
  Condition: '#2e7d32',
  Provider: '#00838f',
  Goal: '#f57c00',
  Procedure: '#5d4037',
  Observation: '#455a64',
}

function hashColorForString(input: string): string {
  let hash = 0
  for (let i = 0; i < input.length; i++) {
    hash = input.charCodeAt(i) + ((hash << 5) - hash)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue} 70% 40%)`
}

function colorForType(type: string): string {
  return KNOWN_TYPE_COLORS[type] || hashColorForString(type)
}

type NodeData = {
  node: GraphNode
  inWorkspace: boolean
  onAdd: (node: GraphNode) => void
  onRemove: (nodeId: string) => void
  color: string
}

export type WorkspaceGraphProps = {
  workspaceId?: string | null
  nodes: GraphNode[]
  edges: GraphEdge[]
  workspaceNodeIds?: string[]
  onNodeDoubleClick?: (nodeId: string) => void
  onAddNodeToWorkspace?: (node: GraphNode) => void
  onRemoveNodeFromWorkspace?: (nodeId: string) => void
}

function NodeWithAction({ data }: RFNodeProps<RFNode<NodeData>>) {
  const { node, inWorkspace, onAdd, onRemove } = data
  const label = labelForNode(node)
  return (
    <Box sx={{
      position: 'relative',
      border: '1px solid',
      borderColor: alpha(data.color, 0.6),
      borderLeftWidth: 4,
      borderLeftColor: data.color,
      bgcolor: alpha(data.color, 0.06),
      px: 1.25,
      py: 0.75,
      boxShadow: 1,
      minWidth: 180,
      maxWidth: 280,
    }}>
      <Box sx={{ fontSize: 13, fontWeight: 700, color: 'text.primary', pr: 4 }}>{label}</Box>
      <Box sx={{ position: 'absolute', top: 0, right: 0 }} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
        {inWorkspace ? (
          <Tooltip title="Remove from workspace" arrow>
            <IconButton size="small" aria-label="Remove from workspace" onClick={() => onRemove(node.id)} sx={{ color: 'error.main' }}>
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title="Add to workspace" arrow>
            <IconButton size="small" aria-label="Add to workspace" onClick={() => onAdd(node)} sx={{ color: 'success.main' }}>
              <AddCircleOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </Box>
  )
}

export default function WorkspaceGraph({ workspaceId: _workspaceId, nodes, edges, workspaceNodeIds = [], onNodeDoubleClick, onAddNodeToWorkspace, onRemoveNodeFromWorkspace }: WorkspaceGraphProps) {
  const theme = useTheme()
  const inWs = useMemo(() => new Set(workspaceNodeIds), [workspaceNodeIds])

  // Compute a columnar layout grouping nodes by primary label/type
  const computeColumnLayout = useMemo(() => {
    return (list: GraphNode[]) => {
      const groups = new Map<string, GraphNode[]>()
      for (const n of list) {
        const t = typeForNode(n)
        const arr = groups.get(t) || []
        arr.push(n)
        groups.set(t, arr)
      }

      // Order columns by a sensible known-order, then alphabetical
      const knownOrder = Object.keys(KNOWN_TYPE_COLORS)
      const types = Array.from(groups.keys()).sort((a, b) => {
        const ia = knownOrder.indexOf(a)
        const ib = knownOrder.indexOf(b)
        if (ia !== -1 || ib !== -1) return (ia === -1 ? 1 : ia) - (ib === -1 ? 1 : ib)
        return a.localeCompare(b)
      })

      const paddingX = 80
      const paddingY = 60
      const colGap = 320
      const rowGap = 130

      const pos: Record<string, { x: number; y: number }> = {}
      types.forEach((t, colIdx) => {
        const list = (groups.get(t) || []).slice().sort((a, b) => labelForNode(a).localeCompare(labelForNode(b)))
        list.forEach((n, rowIdx) => {
          pos[n.id] = { x: paddingX + colIdx * colGap, y: paddingY + rowIdx * rowGap }
        })
      })
      return pos
    }
  }, [])

  const [rfNodes, setRfNodes] = useState<RFNode<NodeData>[]>(() => {
    const layout = computeColumnLayout(nodes)
    const initial = nodes
      .slice()
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((n) => ({
        id: n.id,
        position: layout[n.id] ?? { x: 0, y: 0 },
        data: {
          node: n,
          inWorkspace: inWs.has(n.id),
          onAdd: (node: GraphNode) => onAddNodeToWorkspace?.(node),
          onRemove: (id: string) => onRemoveNodeFromWorkspace?.(id),
          color: colorForType(typeForNode(n)),
        },
        type: 'nodeWithAction',
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }))
    return initial
  })

  // Keep node list in sync with incoming graph data while preserving dragged positions
  useEffect(() => {
    const prevPos = new Map(rfNodes.map((n) => [n.id, n.position]))
    const layout = computeColumnLayout(nodes)
    const next = nodes
      .slice()
      .sort((a, b) => a.id.localeCompare(b.id))
      .map<RFNode<NodeData>>((n) => ({
        id: n.id,
        position: prevPos.get(n.id) ?? layout[n.id] ?? { x: 0, y: 0 },
        data: {
          node: n,
          inWorkspace: inWs.has(n.id),
          onAdd: (node: GraphNode) => onAddNodeToWorkspace?.(node),
          onRemove: (id: string) => onRemoveNodeFromWorkspace?.(id),
          color: colorForType(typeForNode(n)),
        },
        type: 'nodeWithAction',
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }))
    setRfNodes(next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, inWs, onAddNodeToWorkspace, onRemoveNodeFromWorkspace])

  const onNodesChange = (changes: NodeChange[]) =>
    setRfNodes((nds) => applyNodeChanges(changes, nds) as RFNode<NodeData> [])

  const rfEdges = useMemo<RFEdge[]>(() => {
    const color = alpha('#117a2a', 0.45)
    const base = {
      type: 'step' as const,
      animated: false,
      style: { stroke: color, strokeWidth: 1.5 },
    }
    return edges.map((e) => ({ id: e.id, source: e.fromId, target: e.toId, ...base }))
  }, [edges])

  const typesInGraph = useMemo(() => {
    const s = new Set<string>()
    for (const n of nodes) s.add(typeForNode(n))
    return Array.from(s)
      .sort((a, b) => a.localeCompare(b))
  }, [nodes])

  return (
    <Box sx={{
      height: 520,
      border: '1px solid',
      borderColor: 'divider',
      borderRadius: 0.5,
      overflow: 'hidden',
      bgcolor: 'background.paper',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.default' }}>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center">
          <Typography variant="body2" sx={{ color: 'text.secondary', mr: 0.5 }}>
            Key:
          </Typography>
          {typesInGraph.map((t) => (
            <Chip
              key={t}
              size="small"
              label={t}
              sx={{
                bgcolor: alpha(colorForType(t), 0.15),
                border: '1px solid',
                borderColor: alpha(colorForType(t), 0.6),
                color: 'text.primary',
                fontWeight: 600,
              }}
            />
          ))}
        </Stack>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <ReactFlowProvider>
          <ReactFlow<RFNode<NodeData>, RFEdge>
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={{ nodeWithAction: NodeWithAction }}
            fitView
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ type: 'step' }}
            panOnDrag
            nodesDraggable
            zoomOnScroll={false}
            zoomOnPinch={false}
            zoomOnDoubleClick={false}
            onNodesChange={onNodesChange}
            onNodeDoubleClick={(_, n) => onNodeDoubleClick?.(n.id)}
          >
            <Background gap={48} color={alpha(theme.palette.text.primary, 0.05)} />
            <Controls showInteractive={false} position="top-right" />
          </ReactFlow>
        </ReactFlowProvider>
      </Box>
    </Box>
  )
}

