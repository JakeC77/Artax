import { useMemo, useEffect, useState, useCallback } from 'react'
import { Box, Typography, Paper, alpha, useTheme } from '@mui/material'
import { ReactFlow, Background, Controls, ReactFlowProvider, Position, Handle, useReactFlow, applyNodeChanges, type Node, type Edge, type NodeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { OntologyPackage, EntityDefinition, RelationshipDefinition } from '../../types/ontology'

export interface OntologyVisualizerProps {
  ontologyPackage: OntologyPackage | null
}

// Custom node component for entities
function EntityNode({ data }: { data: { entity: EntityDefinition } }) {
  const theme = useTheme()
  const entity = data.entity

  return (
    <Paper
      elevation={2}
      sx={{
        p: 2,
        minWidth: 200,
        bgcolor: theme.palette.mode === 'dark' ? theme.palette.background.paper : theme.palette.common.white,
        border: '2px solid',
        borderColor: theme.palette.primary.main,
        borderRadius: 2,
        position: 'relative',
        overflow: 'visible', // Ensure handles are visible
        cursor: 'grab',
        '&:active': {
          cursor: 'grabbing',
        },
      }}
    >
      {/* Source handle (right side) - for outgoing edges */}
      <Handle
        type="source"
        position={Position.Right}
        id="source"
        style={{
          background: theme.palette.primary.main,
          width: 12,
          height: 12,
          border: `2px solid ${theme.palette.mode === 'dark' ? theme.palette.background.paper : theme.palette.common.white}`,
        }}
      />
      
      {/* Target handle (left side) - for incoming edges */}
      <Handle
        type="target"
        position={Position.Left}
        id="target"
        style={{
          background: theme.palette.primary.main,
          width: 12,
          height: 12,
          border: `2px solid ${theme.palette.mode === 'dark' ? theme.palette.background.paper : theme.palette.common.white}`,
        }}
      />

      <Typography variant="h6" fontWeight={600} sx={{ mb: 1, color: theme.palette.primary.main }}>
        {entity.name}
      </Typography>
      {entity.description && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {entity.description}
        </Typography>
      )}
      {entity.fields.length > 0 && (
        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Fields ({entity.fields.length})
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            {entity.fields.slice(0, 5).map((field, idx) => (
              <Typography key={idx} variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                {field.name}: {field.data_type}
                {field.is_identifier && ' (ID)'}
              </Typography>
            ))}
            {entity.fields.length > 5 && (
              <Typography variant="caption" color="text.secondary">
                +{entity.fields.length - 5} more
              </Typography>
            )}
          </Box>
        </Box>
      )}
    </Paper>
  )
}

// Helper function to compute hierarchical layout based on relationships
function computeHierarchicalLayout(
  entities: EntityDefinition[],
  relationships: RelationshipDefinition[]
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const layerSpacing = 600 // Horizontal spacing between layers
  const nodeSpacing = 400 // Vertical spacing between nodes in same layer
  const startX = 200
  const startY = 200

  // Build adjacency maps
  const incomingEdges = new Map<string, Set<string>>() // entity_id -> set of source entity_ids
  const outgoingEdges = new Map<string, Set<string>>() // entity_id -> set of target entity_ids
  const entityIds = new Set(entities.map((e) => e.entity_id))

  // Initialize maps
  entityIds.forEach((id) => {
    incomingEdges.set(id, new Set())
    outgoingEdges.set(id, new Set())
  })

  // Build edge maps
  relationships.forEach((rel) => {
    if (entityIds.has(rel.from_entity) && entityIds.has(rel.to_entity)) {
      outgoingEdges.get(rel.from_entity)!.add(rel.to_entity)
      incomingEdges.get(rel.to_entity)!.add(rel.from_entity)
    }
  })

  // Compute layers using topological sort (entities with no incoming edges go first)
  const layers: string[][] = []
  const processed = new Set<string>()
  const inDegree = new Map<string, number>()

  // Calculate in-degrees
  entityIds.forEach((id) => {
    inDegree.set(id, incomingEdges.get(id)!.size)
  })

  // Build layers iteratively
  while (processed.size < entityIds.size) {
    const currentLayer: string[] = []
    
    entityIds.forEach((id) => {
      if (!processed.has(id) && inDegree.get(id) === 0) {
        currentLayer.push(id)
        processed.add(id)
      }
    })

    // If no nodes with in-degree 0, pick any unprocessed node (handles cycles)
    if (currentLayer.length === 0) {
      const remaining = Array.from(entityIds).filter((id) => !processed.has(id))
      if (remaining.length > 0) {
        currentLayer.push(remaining[0])
        processed.add(remaining[0])
        // Reset in-degree for this node to break cycles
        inDegree.set(remaining[0], 0)
      }
    }

    if (currentLayer.length === 0) break

    // Sort layer by name for consistent ordering
    currentLayer.sort()
    layers.push(currentLayer)

    // Update in-degrees for next iteration
    currentLayer.forEach((id) => {
      outgoingEdges.get(id)!.forEach((targetId) => {
        const currentDegree = inDegree.get(targetId)!
        inDegree.set(targetId, Math.max(0, currentDegree - 1))
      })
    })
  }

  // Position nodes in layers
  layers.forEach((layer, layerIndex) => {
    const x = startX + layerIndex * layerSpacing
    const totalHeight = Math.max(0, (layer.length - 1) * nodeSpacing)
    const startYForLayer = startY + (totalHeight > 0 ? -totalHeight / 2 : 0)

    layer.forEach((entityId, nodeIndex) => {
      positions.set(entityId, {
        x,
        y: startYForLayer + nodeIndex * nodeSpacing,
      })
    })
  })

  // Handle any entities not placed (shouldn't happen, but safety check)
  entityIds.forEach((id) => {
    if (!positions.has(id)) {
      // Place unplaced entities in a fallback position
      const fallbackY = startY + (positions.size * nodeSpacing)
      positions.set(id, { x: startX, y: fallbackY })
    }
  })

  return positions
}

function AutoLayout({ nodes }: { nodes: Node[]; edges: Edge[] }) {
  const { fitView } = useReactFlow()

  useEffect(() => {
    // Fit view after nodes are positioned
    const timer = setTimeout(() => {
      fitView({ padding: 0.2, duration: 400 })
    }, 100)

    return () => clearTimeout(timer)
  }, [nodes, fitView])

  return null
}

export default function OntologyVisualizer({ ontologyPackage }: OntologyVisualizerProps) {
  const theme = useTheme()
  const [rfNodes, setRfNodes] = useState<Node[]>([])

  const { initialNodes, edges } = useMemo(() => {
    if (!ontologyPackage || ontologyPackage.entities.length === 0) {
      return { initialNodes: [], edges: [] }
    }

    // Compute hierarchical layout
    const positions = computeHierarchicalLayout(
      ontologyPackage.entities,
      ontologyPackage.relationships
    )

    // Create nodes with computed positions
    const entityNodes: Node[] = ontologyPackage.entities.map((entity) => {
      const pos = positions.get(entity.entity_id) || { x: 0, y: 0 }
      return {
        id: entity.entity_id,
        type: 'entity',
        position: pos,
        data: { entity },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        draggable: true,
      }
    })

    // Create edges for relationships with better styling
    const relationshipEdges: Edge[] = ontologyPackage.relationships
      .flatMap((rel) => {
        const fromEntity = ontologyPackage.entities.find((e) => e.entity_id === rel.from_entity)
        const toEntity = ontologyPackage.entities.find((e) => e.entity_id === rel.to_entity)

        if (!fromEntity || !toEntity) return []

        return [
          {
            id: rel.relationship_id,
            source: rel.from_entity,
            target: rel.to_entity,
            sourceHandle: 'source',
            targetHandle: 'target',
            type: 'smoothstep',
            animated: false,
            style: {
              stroke: theme.palette.primary.main,
              strokeWidth: 2.5,
            },
            label: rel.relationship_type,
            labelStyle: {
              fill: theme.palette.text.primary,
              fontWeight: 600,
              fontSize: 11,
            },
            labelBgStyle: {
              fill: theme.palette.mode === 'dark' ? theme.palette.background.paper : theme.palette.common.white,
              fillOpacity: 0.95,
              padding: '2px 6px',
              borderRadius: '4px',
            },
            markerEnd: {
              type: 'arrowclosed',
              color: theme.palette.primary.main,
              width: 20,
              height: 20,
            },
          } as Edge,
        ]
      })

    return {
      initialNodes: entityNodes,
      edges: relationshipEdges,
    }
  }, [ontologyPackage, theme])

  // Initialize nodes on mount or when ontology changes
  useEffect(() => {
    if (initialNodes.length > 0) {
      setRfNodes(initialNodes)
    }
  }, [initialNodes])

  // Handle node changes (dragging, etc.)
  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setRfNodes((nds) => applyNodeChanges(changes, nds))
  }, [])

  if (!ontologyPackage) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Waiting for ontology to be created...
        </Typography>
      </Box>
    )
  }

  if (ontologyPackage.entities.length === 0) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography variant="body2" color="text.secondary">
          No entities defined yet. Add entities to see the visualization.
        </Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        height: '100%',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        overflow: 'hidden',
        bgcolor: theme.palette.mode === 'dark' ? theme.palette.background.default : theme.palette.grey[50],
      }}
    >
      <ReactFlowProvider>
        <ReactFlow
          nodes={rfNodes}
          edges={edges}
          nodeTypes={{ entity: EntityNode as any }}
          fitView
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
          panOnDrag={[1, 2]}
          nodesDraggable={true}
          zoomOnScroll
          zoomOnPinch
          zoomOnDoubleClick={false}
          onNodesChange={onNodesChange}
        >
          <AutoLayout nodes={rfNodes} edges={edges} />
          <Background gap={32} color={alpha(theme.palette.text.primary, 0.05)} />
          <Controls showInteractive={false} position="top-right" />
        </ReactFlow>
      </ReactFlowProvider>
    </Box>
  )
}
