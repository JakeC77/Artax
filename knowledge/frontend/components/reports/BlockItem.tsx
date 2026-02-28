import { useState } from 'react'
import { Box, Paper, Typography, IconButton, Chip, Collapse } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import BlockContentEditor from './BlockContentEditor'
import BlockContentPreview from './BlockContentPreview'
import type { ReportBlock } from '../../types/reports'

interface BlockItemProps {
  block: ReportBlock
  onSave?: () => void
}

const blockTypeLabels = {
  rich_text: 'Rich Text',
  single_metric: 'Single Metric',
  multi_metric: 'Multi Metric',
  insight_card: 'Insight Card',
}

export default function BlockItem({ block, onSave }: BlockItemProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Paper
      elevation={0}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1.5,
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {blockTypeLabels[block.blockType]}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Order: {block.order}
          </Typography>
          {!expanded && <BlockContentPreview block={block} />}
        </Box>
        <Chip label={block.blockType} size="small" variant="outlined" />
        <IconButton size="small" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}>
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <BlockContentEditor block={block} onSave={onSave} />
        </Box>
      </Collapse>
    </Paper>
  )
}

