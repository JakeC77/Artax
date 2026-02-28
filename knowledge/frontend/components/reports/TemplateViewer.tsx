import { Box, Typography, Paper, Chip, Tooltip, Accordion, AccordionSummary, AccordionDetails } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import DescriptionIcon from '@mui/icons-material/Description'
import BarChartIcon from '@mui/icons-material/BarChart'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import LightbulbIcon from '@mui/icons-material/Lightbulb'
import type { ReportTemplate, ReportTemplateBlock } from '../../types/reports'

// Parse layoutHints to get width fraction
function parseWidth(layoutHints: string | null): number {
  if (!layoutHints) return 1 // Default to full width
  
  try {
    const hints = JSON.parse(layoutHints)
    const width = hints.width
    
    if (width === 'full') return 1
    if (typeof width === 'string' && width.includes('/')) {
      const [numerator, denominator] = width.split('/').map(Number)
      return numerator / denominator
    }
    return 1 // Default to full width
  } catch {
    return 1 // Default to full width on parse error
  }
}

// Group blocks into rows based on their widths
// IMPORTANT: This function preserves the original order of blocks - it only groups them
// visually into rows. Blocks are processed sequentially and added to rows in order.
function groupTemplateBlocksIntoRows(blocks: ReportTemplateBlock[]): ReportTemplateBlock[][] {
  const rows: ReportTemplateBlock[][] = []
  let currentRow: ReportTemplateBlock[] = []
  let currentRowWidth = 0
  
  // Process blocks in order - this preserves the original sequence
  for (const block of blocks) {
    const width = parseWidth(block.layoutHints)
    
    // If block is full width, start a new row
    if (width >= 1) {
      // Push current row if it has blocks
      if (currentRow.length > 0) {
        rows.push(currentRow)
        currentRow = []
        currentRowWidth = 0
      }
      // Add full-width block as its own row
      rows.push([block])
      continue
    }
    
    // Check if block fits in current row
    if (currentRowWidth + width <= 1 + 0.001) { // Small epsilon for floating point
      currentRow.push(block)
      currentRowWidth += width
    } else {
      // Start a new row
      if (currentRow.length > 0) {
        rows.push(currentRow)
      }
      currentRow = [block]
      currentRowWidth = width
    }
  }
  
  // Push remaining blocks
  if (currentRow.length > 0) {
    rows.push(currentRow)
  }
  
  return rows
}

interface TemplateViewerProps {
  template: ReportTemplate
}

const blockTypeIcons = {
  rich_text: DescriptionIcon,
  single_metric: BarChartIcon,
  multi_metric: ShowChartIcon,
  insight_card: LightbulbIcon,
}

const blockTypeLabels = {
  rich_text: 'Rich Text',
  single_metric: 'Single Metric',
  multi_metric: 'Multi Metric',
  insight_card: 'Insight Card',
}

export default function TemplateViewer({ template }: TemplateViewerProps) {
  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
          {template.name}
        </Typography>
        {template.description && (
          <Typography variant="body2" color="text.secondary">
            {template.description}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Chip label={`Version ${template.version}`} size="small" />
          <Chip label={`${template.sections.length} Sections`} size="small" variant="outlined" />
        </Box>
      </Box>

      {template.sections
        .sort((a, b) => a.order - b.order)
        .map((section) => {
          return (
            <Accordion key={section.templateSectionId} defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {section.header}
                  </Typography>
                  <Chip label={section.sectionType} size="small" variant="outlined" />
                  <Typography variant="caption" color="text.secondary">
                    {section.blocks.length} block{section.blocks.length !== 1 ? 's' : ''}
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {section.semanticDefinition && (
                  <Box sx={{ mb: 2, p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                      Semantic Definition:
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      {section.semanticDefinition}
                    </Typography>
                  </Box>
                )}
                {(() => {
                  // Group blocks into rows based on their layoutHints.width
                  // Blocks are first sorted by their order field, then grouped into rows while preserving that order
                  const sortedBlocks = [...section.blocks].sort((a, b) => a.order - b.order)
                  const blockRows = groupTemplateBlocksIntoRows(sortedBlocks)
                  
                  return (
                    <Box>
                      {blockRows.map((row, rowIndex) => (
                        <Box
                          key={`row-${rowIndex}`}
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(12, 1fr)',
                            gap: 1,
                            mb: 1,
                          }}
                        >
                          {row.map((block) => {
                            const BlockIcon = blockTypeIcons[block.blockType]
                            const width = parseWidth(block.layoutHints)
                            const gridSpan = width >= 1 ? 12 : Math.round(width * 12)
                            return (
                              <Box
                                key={block.templateBlockId}
                                sx={{
                                  gridColumn: `span ${gridSpan}`,
                                }}
                              >
                                <Paper
                                  elevation={0}
                                  sx={{
                                    p: 1.5,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1.5,
                                  }}
                                >
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                                    <BlockIcon sx={{ fontSize: 20 }} />
                                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                      {blockTypeLabels[block.blockType]}
                                    </Typography>
                                    {block.semanticDefinition && (
                                      <Tooltip title={block.semanticDefinition}>
                                        <Chip label="ℹ️" size="small" sx={{ height: 20, fontSize: '0.7rem' }} />
                                      </Tooltip>
                                    )}
                                  </Box>
                                  <Typography variant="caption" color="text.secondary">
                                    Order: {block.order}
                                  </Typography>
                                </Paper>
                              </Box>
                            )
                          })}
                        </Box>
                      ))}
                    </Box>
                  )
                })()}
              </AccordionDetails>
            </Accordion>
          )
        })}
    </Box>
  )
}

