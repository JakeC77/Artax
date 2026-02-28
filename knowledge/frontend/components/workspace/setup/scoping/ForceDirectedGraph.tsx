/**
 * ForceDirectedGraph Component
 *
 * Graph visualization for the data scope query structure.
 * Supports two layout modes:
 * 1. Force-directed (default): Physics-based simulation with nodes orbiting primary
 * 2. Hierarchical: Layered layout using elkjs, flows top-to-bottom based on relationships
 *
 * Key Features:
 * - Dual layout modes with smooth transitions
 * - Primary entity anchored at center (force) or top (hierarchical)
 * - Canvas-based edge rendering with curved paths
 * - Hover highlighting of connected nodes/edges
 * - Click to select entity and show details in sidebar
 * - Read-only visualization (no direct editing)
 */

import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { Box, Chip, Typography, alpha, useTheme } from '@mui/material'
import type { ScopeState, ScopeEntity, RelevanceLevel } from '../../../../types/scopeState'
import type { Theme } from '@mui/material/styles'
import {
  getLayoutConfig,
  getGraphSize,
  NODE_DIMENSIONS,
  EDGE_STYLES,
  type ForceLayoutParams,
} from './forceLayoutConfig'

// ============================================================================
// Types
// ============================================================================

interface Position2D {
  x: number
  y: number
  vx: number
  vy: number
  fx: number
  fy: number
}

interface GraphNode {
  id: string
  entity: ScopeEntity
  position: Position2D
}

interface GraphEdge {
  from: string
  to: string
  label: string
  relationshipType: string
}

export interface ForceDirectedGraphProps {
  scopeState: ScopeState | null
  onEntityClick?: (entity: ScopeEntity) => void
  height?: number
  /** Selected entity ID (for highlighting) */
  selectedEntityId?: string | null
}

// ============================================================================
// Color Configuration
// ============================================================================

interface NodeColors {
  background: string
  border: string
  text: string
  badge: string
  badgeText: string
  footer: string
  footerText: string
}

function getNodeColors(level: RelevanceLevel, theme: Theme): NodeColors {
  switch (level) {
    case 'primary':
      return {
        background: theme.palette.mode === 'dark' ? '#2A2418' : '#FFFFFF',
        border: '#C6A664', // gold
        text: theme.palette.text.primary,
        badge: '#C6A664',
        badgeText: '#FFFFFF',
        footer: theme.palette.mode === 'dark' ? '#3A3020' : '#F5EFE0',
        footerText: theme.palette.mode === 'dark' ? '#C6A664' : '#A08540',
      }
    case 'related':
      return {
        background: theme.palette.mode === 'dark' ? '#0A2820' : '#FFFFFF',
        border: '#0F5C4C', // emerald
        text: theme.palette.text.primary,
        badge: '#0F5C4C',
        badgeText: '#FFFFFF',
        footer: theme.palette.mode === 'dark' ? '#0A3830' : alpha('#0F5C4C', 0.08),
        footerText: '#0F5C4C',
      }
    case 'contextual':
      return {
        background: theme.palette.mode === 'dark' ? '#1A1A1A' : '#FFFFFF',
        border: '#B0B0B0', // contextual gray (no opacity)
        text: theme.palette.text.primary, // Same as other nodes - not diminished
        badge: theme.palette.mode === 'dark' ? '#3A3A3A' : '#D6D6D6',
        badgeText: theme.palette.mode === 'dark' ? '#888888' : '#666666',
        footer: theme.palette.mode === 'dark' ? '#1E1E1E' : alpha('#000000', 0.02),
        footerText: '#888888',
      }
  }
}

// ============================================================================
// Force Layout Algorithm
// ============================================================================

function runForceSimulation(
  nodes: GraphNode[],
  edges: GraphEdge[],
  centerX: number,
  centerY: number,
  params: ForceLayoutParams
): Map<string, Position2D> {
  const positions = new Map<string, Position2D>()
  const primaryNode = nodes.find((n) => n.entity.relevance_level === 'primary')
  const relatedNodes = nodes.filter((n) => n.entity.relevance_level === 'related')
  const contextualNodes = nodes.filter((n) => n.entity.relevance_level === 'contextual')

  // Initialize primary at center
  if (primaryNode) {
    positions.set(primaryNode.id, { x: centerX, y: centerY, vx: 0, vy: 0, fx: 0, fy: 0 })
  }

  // Initialize related nodes in inner ring - evenly distributed
  relatedNodes.forEach((node, i) => {
    const angle = (i / Math.max(relatedNodes.length, 1)) * Math.PI * 2 - Math.PI / 2
    const r = params.distPrimaryRelated
    positions.set(node.id, {
      x: centerX + Math.cos(angle) * r,
      y: centerY + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
      fx: 0,
      fy: 0,
    })
  })

  // Initialize contextual nodes in outer ring - offset from related
  contextualNodes.forEach((node, i) => {
    const angleOffset = relatedNodes.length > 0 ? Math.PI / Math.max(relatedNodes.length, 1) : 0
    const angle = (i / Math.max(contextualNodes.length, 1)) * Math.PI * 2 - Math.PI / 2 + angleOffset
    const r = params.distPrimaryContextual
    positions.set(node.id, {
      x: centerX + Math.cos(angle) * r,
      y: centerY + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
      fx: 0,
      fy: 0,
    })
  })

  // Run simulation
  for (let iter = 0; iter < params.iterations; iter++) {
    const alpha = 1 - iter / params.iterations

    // Reset forces
    positions.forEach((pos) => {
      pos.fx = 0
      pos.fy = 0
    })

    // Repulsion between all nodes
    const nodeList = Array.from(positions.entries())
    for (let i = 0; i < nodeList.length; i++) {
      for (let j = i + 1; j < nodeList.length; j++) {
        const [idA, posA] = nodeList[i]
        const [idB, posB] = nodeList[j]
        const nodeA = nodes.find((n) => n.id === idA)
        const nodeB = nodes.find((n) => n.id === idB)

        let dx = posB.x - posA.x
        let dy = posB.y - posA.y
        let dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 1) dist = 1

        // Minimum separation based on node sizes
        const wA = NODE_DIMENSIONS[nodeA?.entity.relevance_level || 'related'].width
        const wB = NODE_DIMENSIONS[nodeB?.entity.relevance_level || 'related'].width
        const minSep = Math.max(wA, wB) * 1.1 + params.minDist

        // Repulsion force
        const rep = params.repulsion / (dist * dist)
        const nx = dx / dist
        const ny = dy / dist

        posA.fx -= nx * rep
        posA.fy -= ny * rep
        posB.fx += nx * rep
        posB.fy += ny * rep

        // Collision handling
        if (dist < minSep) {
          const overlap = (minSep - dist) / 2
          posA.fx -= nx * overlap * params.collision
          posA.fy -= ny * overlap * params.collision
          posB.fx += nx * overlap * params.collision
          posB.fy += ny * overlap * params.collision
        }
      }
    }

    // Edge spring attraction
    edges.forEach((edge) => {
      const posFrom = positions.get(edge.from)
      const posTo = positions.get(edge.to)
      if (!posFrom || !posTo) return

      const nodeFrom = nodes.find((n) => n.id === edge.from)
      const nodeTo = nodes.find((n) => n.id === edge.to)

      let dx = posTo.x - posFrom.x
      let dy = posTo.y - posFrom.y
      let dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < 1) dist = 1

      // Determine ideal distance based on node types
      let ideal = params.distOther
      if (nodeFrom?.entity.relevance_level === 'primary' || nodeTo?.entity.relevance_level === 'primary') {
        const otherLevel =
          nodeFrom?.entity.relevance_level === 'primary'
            ? nodeTo?.entity.relevance_level
            : nodeFrom?.entity.relevance_level
        ideal = otherLevel === 'related' ? params.distPrimaryRelated : params.distPrimaryContextual
      }

      const force = (dist - ideal) * params.spring
      const nx = dx / dist
      const ny = dy / dist
      posFrom.fx += nx * force
      posFrom.fy += ny * force
      posTo.fx -= nx * force
      posTo.fy -= ny * force
    })

    // Center gravity for non-primary nodes
    nodes.forEach((node) => {
      const pos = positions.get(node.id)
      if (!pos) return
      const str = node.entity.relevance_level === 'primary' ? 0.8 : params.gravity
      pos.fx += (centerX - pos.x) * str
      pos.fy += (centerY - pos.y) * str
    })

    // Apply forces
    nodes.forEach((node) => {
      if (node.entity.relevance_level === 'primary') {
        // Keep primary anchored at center
        const pos = positions.get(node.id)
        if (pos) {
          pos.x = centerX
          pos.y = centerY
        }
        return
      }

      const pos = positions.get(node.id)
      if (!pos) return

      pos.vx = (pos.vx + pos.fx * alpha) * params.damping
      pos.vy = (pos.vy + pos.fy * alpha) * params.damping
      pos.x += pos.vx
      pos.y += pos.vy

      // Boundary constraints
      const margin = 100
      const maxX = centerX * 2 - margin
      const maxY = centerY * 2 - margin
      pos.x = Math.max(margin, Math.min(maxX, pos.x))
      pos.y = Math.max(margin, Math.min(maxY, pos.y))
    })
  }

  return positions
}

// ============================================================================
// Edge Canvas Renderer
// ============================================================================

interface EdgeCanvasProps {
  edges: GraphEdge[]
  positions: Map<string, Position2D>
  nodes: GraphNode[]
  highlightedNodeId: string | null
  width: number
  height: number
}

function renderEdges(
  ctx: CanvasRenderingContext2D,
  { edges, positions, nodes, highlightedNodeId, width, height }: EdgeCanvasProps
): { label: string; x: number; y: number; highlighted: boolean }[] {
  const dpr = window.devicePixelRatio || 1
  ctx.clearRect(0, 0, width * dpr, height * dpr)
  ctx.scale(dpr, dpr)

  // Build connected set for highlighting
  const connectedEdges = new Set<number>()
  if (highlightedNodeId) {
    edges.forEach((edge, idx) => {
      if (edge.from === highlightedNodeId || edge.to === highlightedNodeId) {
        connectedEdges.add(idx)
      }
    })
  }

  const edgeLabels: { label: string; x: number; y: number; highlighted: boolean }[] = []

  edges.forEach((edge, idx) => {
    const fromPos = positions.get(edge.from)
    const toPos = positions.get(edge.to)
    if (!fromPos || !toPos) return

    const fromNode = nodes.find((n) => n.id === edge.from)
    const toNode = nodes.find((n) => n.id === edge.to)
    const isPrimaryEdge =
      fromNode?.entity.relevance_level === 'primary' || toNode?.entity.relevance_level === 'primary'
    const isContextualEdge =
      !isPrimaryEdge &&
      (fromNode?.entity.relevance_level === 'contextual' ||
        toNode?.entity.relevance_level === 'contextual')

    // Determine if this edge should be dimmed
    let edgeAlpha = 1
    if (highlightedNodeId) {
      edgeAlpha = connectedEdges.has(idx) ? 1 : 0.08
    }

    // Calculate curve control point
    const dx = toPos.x - fromPos.x
    const dy = toPos.y - fromPos.y
    const mx = (fromPos.x + toPos.x) / 2
    const my = (fromPos.y + toPos.y) / 2
    const curve = isPrimaryEdge ? 0 : 0.15
    const cpx = mx - dy * curve
    const cpy = my + dx * curve

    ctx.save()
    ctx.globalAlpha = edgeAlpha

    // Get edge style
    let style = EDGE_STYLES.other
    if (highlightedNodeId && connectedEdges.has(idx)) {
      style = EDGE_STYLES.highlighted
    } else if (isPrimaryEdge) {
      style = EDGE_STYLES.primaryToRelated
    } else if (isContextualEdge) {
      style = EDGE_STYLES.primaryToContextual
    }

    ctx.beginPath()
    ctx.moveTo(fromPos.x, fromPos.y)
    ctx.quadraticCurveTo(cpx, cpy, toPos.x, toPos.y)
    ctx.strokeStyle = style.color
    ctx.lineWidth = style.width
    if (style.dash) {
      ctx.setLineDash(style.dash)
    } else {
      ctx.setLineDash([])
    }
    ctx.stroke()
    ctx.restore()

    // Calculate label position (midpoint of curve)
    const t = 0.5
    const lx = (1 - t) * (1 - t) * fromPos.x + 2 * (1 - t) * t * cpx + t * t * toPos.x
    const ly = (1 - t) * (1 - t) * fromPos.y + 2 * (1 - t) * t * cpy + t * t * toPos.y

    edgeLabels.push({
      label: edge.label,
      x: lx,
      y: ly,
      highlighted: highlightedNodeId ? connectedEdges.has(idx) : false,
    })
  })

  // Reset transform for next render
  ctx.setTransform(1, 0, 0, 1, 0, 0)

  return edgeLabels
}

// ============================================================================
// Node Component
// ============================================================================

interface NodeCardProps {
  node: GraphNode
  position: Position2D
  colors: NodeColors
  isHighlighted: boolean
  isDimmed: boolean
  onClick: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
}

function NodeCard({
  node,
  position,
  colors,
  isHighlighted,
  isDimmed,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: NodeCardProps) {
  const { entity } = node
  const dims = NODE_DIMENSIONS[entity.relevance_level]

  const formatCount = (count: number | null | undefined): string => {
    if (count == null) return '—'
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`
    return count.toLocaleString()
  }

  const filterLabel =
    entity.filters.length > 0
      ? `${entity.filters.length} filter${entity.filters.length > 1 ? 's' : ''}`
      : 'No filters'

  return (
    <Box
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      sx={{
        position: 'absolute',
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, -50%)',
        zIndex: isHighlighted ? 20 : 10,
        cursor: 'pointer',
        transition: 'opacity 0.2s ease',
        opacity: isDimmed ? 0.12 : 1,
        '&:hover': {
          zIndex: 20,
        },
      }}
    >
      <Box
        sx={{
          width: dims.width,
          backgroundColor: colors.background,
          border: entity.relevance_level === 'contextual' ? '1.5px dashed' : '2px solid',
          borderWidth: entity.relevance_level === 'primary' ? 2.5 : 1.5,
          borderColor: colors.border,
          borderRadius: entity.relevance_level === 'primary' ? '14px' : '10px',
          boxShadow:
            entity.relevance_level === 'primary'
              ? `0 0 0 5px ${alpha(colors.border, 0.25)}, 0 3px 16px rgba(0,0,0,0.07)`
              : '0 2px 10px rgba(0,0,0,0.05)',
          overflow: 'hidden',
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
          '&:hover': {
            boxShadow: '0 6px 24px rgba(0,0,0,0.12)',
            transform: 'scale(1.03)',
          },
        }}
      >
        {/* Header */}
        <Box sx={{ px: entity.relevance_level === 'primary' ? 2 : 1.5, pt: 1.5, pb: 1 }}>
          <Chip
            size="small"
            label={entity.relevance_level.toUpperCase()}
            sx={{
              height: 18,
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: 0.5,
              bgcolor: colors.badge,
              color: colors.badgeText,
              mb: 0.75,
            }}
          />
          <Typography
            sx={{
              fontSize: entity.relevance_level === 'primary' ? 17 : 13,
              fontWeight: entity.relevance_level === 'primary' ? 700 : 600,
              color: colors.text,
              mb: 0.25,
            }}
          >
            {entity.entity_type}
          </Typography>
          <Typography
            sx={{
              fontSize: entity.relevance_level === 'primary' ? 12 : 11,
              color: (theme) => theme.palette.text.secondary,
            }}
          >
            <strong style={{ fontWeight: 600 }}>{formatCount(entity.estimated_count)}</strong> records
          </Typography>
        </Box>

        {/* Footer */}
        <Box
          sx={{
            px: entity.relevance_level === 'primary' ? 2 : 1.5,
            py: entity.relevance_level === 'primary' ? 1 : 0.75,
            backgroundColor: colors.footer,
            borderTop: '1px solid',
            borderTopColor: alpha(colors.border, 0.2),
          }}
        >
          <Typography
            sx={{
              fontSize: entity.relevance_level === 'primary' ? 11 : 10,
              fontWeight: 500,
              color: colors.footerText,
            }}
          >
            {filterLabel}
          </Typography>
        </Box>
      </Box>
    </Box>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export default function ForceDirectedGraph({
  scopeState,
  onEntityClick,
  height = 600,
  selectedEntityId = null,
}: ForceDirectedGraphProps) {
  const theme = useTheme()
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height })
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [edgeLabels, setEdgeLabels] = useState<{ label: string; x: number; y: number; highlighted: boolean }[]>([])

  // The highlighted node is either hovered or selected
  const highlightedNodeId = hoveredNodeId || selectedEntityId

  // Build graph nodes from scope state
  const nodes = useMemo<GraphNode[]>(() => {
    if (!scopeState?.entities) return []
    return scopeState.entities
      .filter((e) => e.enabled)
      .map((entity) => ({
        id: entity.entity_type,
        entity,
        position: { x: 0, y: 0, vx: 0, vy: 0, fx: 0, fy: 0 },
      }))
  }, [scopeState?.entities])

  // Build graph edges from relationships
  const edges = useMemo<GraphEdge[]>(() => {
    if (!scopeState?.relationships) return []
    const enabledIds = new Set(nodes.map((n) => n.id))
    return scopeState.relationships
      .filter((r) => enabledIds.has(r.from_entity) && enabledIds.has(r.to_entity))
      .map((r) => ({
        from: r.from_entity,
        to: r.to_entity,
        label: r.display_label,
        relationshipType: r.relationship_type,
      }))
  }, [scopeState?.relationships, nodes])

  // Get layout config based on graph size
  const layoutConfig = useMemo(() => {
    return getLayoutConfig(nodes.length)
  }, [nodes.length])

  // Run force simulation (synchronous)
  const forcePositions = useMemo(() => {
    if (nodes.length === 0) return new Map<string, Position2D>()
    const centerX = dimensions.width / 2
    const centerY = dimensions.height / 2
    return runForceSimulation(nodes, edges, centerX, centerY, layoutConfig)
  }, [nodes, edges, dimensions, layoutConfig])

  const positions = forcePositions

  // Handle resize
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateDimensions = () => {
      setDimensions({
        width: container.clientWidth,
        height: container.clientHeight,
      })
    }

    updateDimensions()
    const resizeObserver = new ResizeObserver(updateDimensions)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [])

  // Render edges on canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || positions.size === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = dimensions.width * dpr
    canvas.height = dimensions.height * dpr
    canvas.style.width = `${dimensions.width}px`
    canvas.style.height = `${dimensions.height}px`

    const labels = renderEdges(ctx, {
      edges,
      positions,
      nodes,
      highlightedNodeId,
      width: dimensions.width,
      height: dimensions.height,
    })
    setEdgeLabels(labels)
  }, [edges, positions, nodes, highlightedNodeId, dimensions])

  // Build connected nodes set for dimming
  const connectedNodes = useMemo(() => {
    if (!highlightedNodeId) return null
    const connected = new Set<string>([highlightedNodeId])
    edges.forEach((e) => {
      if (e.from === highlightedNodeId) connected.add(e.to)
      if (e.to === highlightedNodeId) connected.add(e.from)
    })
    return connected
  }, [highlightedNodeId, edges])

  // Handlers
  const handleNodeClick = useCallback(
    (entity: ScopeEntity) => {
      onEntityClick?.(entity)
    },
    [onEntityClick]
  )

  const handleNodeMouseEnter = useCallback((nodeId: string) => {
    setHoveredNodeId(nodeId)
  }, [])

  const handleNodeMouseLeave = useCallback(() => {
    setHoveredNodeId(null)
  }, [])

  // Stats for display
  const graphSize = getGraphSize(nodes.length)

  if (!scopeState || nodes.length === 0) {
    return (
      <Box
        sx={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          bgcolor: 'background.paper',
        }}
      >
        <Typography color="text.secondary">No entities in scope</Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        height,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        bgcolor: theme.palette.mode === 'dark' ? 'background.default' : '#F4F0E6',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Graph Area */}
      <Box
        ref={containerRef}
        sx={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Dot Grid Background */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `radial-gradient(circle, ${alpha(theme.palette.text.primary, 0.06)} 0.8px, transparent 0.8px)`,
            backgroundSize: '28px 28px',
            pointerEvents: 'none',
          }}
        />

        {/* Edge Canvas */}
        <canvas
          ref={canvasRef}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            zIndex: 1,
            pointerEvents: 'none',
          }}
        />

        {/* Edge Labels */}
        {edgeLabels.map((label, idx) => (
          <Box
            key={idx}
            sx={{
              position: 'absolute',
              left: label.x,
              top: label.y,
              transform: 'translate(-50%, -50%)',
              zIndex: label.highlighted ? 15 : 5,
              pointerEvents: 'none',
              fontSize: 11,
              fontWeight: label.highlighted ? 600 : 500,
              color: label.highlighted ? '#FFFFFF' : theme.palette.text.secondary,
              whiteSpace: 'nowrap',
              opacity: highlightedNodeId && !label.highlighted ? 0.15 : 1,
              transition: 'all 0.2s',
              // Background only on highlight
              ...(label.highlighted && {
                bgcolor: '#0F5C4C',
                px: 1,
                py: 0.375,
                borderRadius: 0.5,
                boxShadow: '0 2px 8px rgba(15, 92, 76, 0.3)',
              }),
            }}
          >
            {label.label}
          </Box>
        ))}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = positions.get(node.id)
          if (!pos) return null

          const colors = getNodeColors(node.entity.relevance_level, theme)
          const isHighlighted = highlightedNodeId === node.id
          const isDimmed = connectedNodes !== null && !connectedNodes.has(node.id)

          return (
            <NodeCard
              key={node.id}
              node={node}
              position={pos}
              colors={colors}
              isHighlighted={isHighlighted}
              isDimmed={isDimmed}
              onClick={() => handleNodeClick(node.entity)}
              onMouseEnter={() => handleNodeMouseEnter(node.id)}
              onMouseLeave={handleNodeMouseLeave}
            />
          )
        })}

        {/* Legend */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 14,
            left: 14,
            display: 'flex',
            gap: 2,
            px: 1.75,
            py: 1,
            bgcolor: theme.palette.mode === 'dark' ? alpha('#141414', 0.9) : '#FFFFFF',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            zIndex: 50,
            boxShadow: '0 2px 6px rgba(0,0,0,0.05)',
          }}
        >
          <LegendItem color="#C6A664" label="Primary" borderStyle="solid" />
          <LegendItem color="#0F5C4C" label="Related" borderStyle="solid" />
          <LegendItem color="#B0B0B0" label="Contextual" borderStyle="dashed" />
        </Box>

        {/* Stats Badge */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 14,
            right: 14,
            px: 1.5,
            py: 0.75,
            bgcolor: theme.palette.mode === 'dark' ? alpha('#141414', 0.9) : '#FFFFFF',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            zIndex: 50,
            fontSize: 11,
            color: 'text.secondary',
          }}
        >
          <strong style={{ color: '#0F5C4C' }}>{nodes.length}</strong> nodes ·{' '}
          <strong style={{ color: '#0F5C4C' }}>{edges.length}</strong> edges ·{' '}
          <span style={{ textTransform: 'capitalize' }}>{graphSize}</span> graph
        </Box>
      </Box>

      {/* Footer Summary */}
      {scopeState.natural_language_summary && (
        <Box
          sx={{
            px: 3,
            py: 1.5,
            bgcolor: theme.palette.mode === 'dark' ? '#141414' : '#FFFFFF',
            borderTop: '1px solid',
            borderColor: 'divider',
            flexShrink: 0,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              fontStyle: 'italic',
              color: 'text.secondary',
              '& strong': {
                fontStyle: 'normal',
                color: 'primary.main',
              },
            }}
            dangerouslySetInnerHTML={{
              __html: `"${scopeState.natural_language_summary.replace(
                /\*\*(.*?)\*\*/g,
                '<strong>$1</strong>'
              )}"`,
            }}
          />
        </Box>
      )}
    </Box>
  )
}

// ============================================================================
// Legend Item Component
// ============================================================================

interface LegendItemProps {
  color: string
  label: string
  borderStyle: 'solid' | 'dashed'
}

function LegendItem({ color, label, borderStyle }: LegendItemProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: 0.5,
          bgcolor: alpha(color, 0.1),
          border: `2px ${borderStyle}`,
          borderColor: color,
        }}
      />
      <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>{label}</Typography>
    </Box>
  )
}
