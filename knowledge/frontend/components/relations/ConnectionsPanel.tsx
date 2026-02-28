import { useMemo } from 'react'
import { Box, Chip, Typography } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { ReactFlow, Background, Controls, ReactFlowProvider, Position } from '@xyflow/react'
import type { Edge, Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

type Plan = { id: string; title: string; members: number; spend: string }
type Insight = { id: string; title: string; summary: string }
type Drug = { id: string; title: string; tier: string; members: number; cost: string }

const plans: Plan[] = [
  { id: 'plan-1', title: 'Acme Corp Commercial - West', members: 487, spend: '$3.1M' },
  { id: 'plan-2', title: 'Acme Corp Commercial - Central', members: 487, spend: '$3.1M' },
  { id: 'plan-3', title: 'Acme Corp Commercial - East', members: 487, spend: '$3.1M' },
]

const insights: Insight[] = [
  {
    id: 'ins-1',
    title: 'Ozempic drives 58% of annual spend',
    summary: '11.3M annual spend concentrated within one specialty drug across all staged plans.',
  },
  {
    id: 'ins-2',
    title: 'Spend concentrated in one GLP-1 brand',
    summary: 'Utilization rising faster than eligible population growth across plans.',
  },
  {
    id: 'ins-3',
    title: 'Immediate opportunity for step therapy',
    summary: 'Consider tiering changes with member notifications and clinical monitoring.',
  },
  {
    id: 'ins-4',
    title: 'Projected savings $1.7M–$2.4M / yr',
    summary: 'Phased rollout with generic steering incentives recommended.',
  },
]

const drugs: Drug[] = [
  { id: 'drug-1', title: 'Metformin ER (Generic)', tier: 'Tier: 2', members: 847, cost: '$12/claim / $1.2M' },
  { id: 'drug-2', title: 'Metformin ER (Generic)', tier: 'Tier: 2', members: 847, cost: '$12/claim / $1.2M' },
  { id: 'drug-3', title: 'Metformin ER (Generic)', tier: 'Tier: 2', members: 847, cost: '$12/claim / $1.2M' },
]

function PlanCard({ data }: any) {
  const theme = useTheme()
  return (
    <Box sx={{
      width: 220,
      p: 1.25,
      borderRadius: 1.5,
      border: '1px solid',
      borderColor: 'divider',
      bgcolor: theme.palette.background.paper,
      boxShadow: 'none',
    }}>
      <Typography sx={{ fontWeight: 700, fontSize: 13, mb: 0.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {data.title}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        Members: {data.members}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        Spend: {data.spend}
      </Typography>
    </Box>
  )
}

function InsightCard({ data }: any) {
  const theme = useTheme()
  return (
    <Box sx={{
      width: 260,
      p: 1.25,
      borderRadius: 1.5,
      border: '1px solid',
      borderColor: alpha(theme.palette.success.main, 0.25),
      bgcolor: alpha(theme.palette.success.main, 0.08),
    }}>
      <Typography sx={{ fontWeight: 700, fontSize: 13, mb: 0.25 }}>
        {data.title}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {data.summary}
      </Typography>
    </Box>
  )
}

function DrugCard({ data }: any) {
  const theme = useTheme()
  return (
    <Box sx={{
      width: 240,
      p: 1.25,
      borderRadius: 1.5,
      border: '1px solid',
      borderColor: alpha(theme.palette.warning.main, 0.25),
      bgcolor: alpha(theme.palette.warning.main, 0.08),
    }}>
      <Typography sx={{ fontWeight: 700, fontSize: 13, mb: 0.25 }}>
        {data.title}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {data.tier} • Members: {data.members}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {data.cost}
      </Typography>
    </Box>
  )
}

export default function ConnectionsPanel() {
  const theme = useTheme()

  const nodes = useMemo<Node[]>(() => {
    const leftX = 80
    const midX = 380
    const rightX = 760

    const gapY = 120
    const startY = 40

    const planNodes: Node[] = plans.map((p, i) => ({
      id: p.id,
      type: 'plan',
      position: { x: leftX, y: startY + i * gapY },
      data: p,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }))

    const insightNodes: Node[] = insights.map((ins, i) => ({
      id: ins.id,
      type: 'insight',
      position: { x: midX, y: startY + i * gapY },
      data: ins,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }))

    const drugNodes: Node[] = drugs.map((d, i) => ({
      id: d.id,
      type: 'drug',
      position: { x: rightX, y: startY + i * gapY + gapY / 2 },
      data: d,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }))

    return [...planNodes, ...insightNodes, ...drugNodes]
  }, [])

  const edges = useMemo<Edge[]>(() => {
    const color = alpha(theme.palette.success.dark, 0.45)
    const base = {
      type: 'step' as const,
      animated: false,
      style: { stroke: color, strokeWidth: 1.5 },
    }
    return [
      // Plans -> Insights
      { id: 'e-p1-i1', source: 'plan-1', target: 'ins-1', ...base },
      { id: 'e-p2-i2', source: 'plan-2', target: 'ins-2', ...base },
      { id: 'e-p3-i4', source: 'plan-3', target: 'ins-4', ...base },
      // Insights -> Drugs
      { id: 'e-i1-d1', source: 'ins-1', target: 'drug-1', ...base },
      { id: 'e-i2-d2', source: 'ins-2', target: 'drug-2', ...base },
      { id: 'e-i3-d3', source: 'ins-3', target: 'drug-3', ...base },
      { id: 'e-i4-d1', source: 'ins-4', target: 'drug-1', ...base },
    ]
  }, [theme])

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
        <Chip size="small" label="Plans" variant="outlined" />
        <Chip size="small" label="Insights" color="success" variant="outlined" />
        <Chip size="small" label="Drugs" color="warning" variant="outlined" />
      </Box>

      <Box sx={{
        height: 520,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        overflow: 'hidden',
        bgcolor: 'background.paper',
      }}>
        <ReactFlowProvider>
          <ReactFlow
            defaultNodes={nodes}
            defaultEdges={edges}
            nodeTypes={{ plan: PlanCard as any, insight: InsightCard as any, drug: DrugCard as any }}
            fitView
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ type: 'step' }}
            panOnDrag
            nodesDraggable
            zoomOnScroll={false}
            zoomOnPinch={false}
            zoomOnDoubleClick={false}
          >
            <Background gap={48} color={alpha(theme.palette.text.primary, 0.05)} />
            <Controls showInteractive={false} position="top-right" />
          </ReactFlow>
        </ReactFlowProvider>
      </Box>
    </Box>
  )
}
