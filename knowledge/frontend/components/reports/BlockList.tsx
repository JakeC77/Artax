import { useMemo } from 'react'
import { Box } from '@mui/material'
import BlockItem from './BlockItem'
import type { ReportBlock, ReportTemplateBlock } from '../../types/reports'

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
function groupBlocksIntoRows(blocks: ReportBlock[]): ReportBlock[][] {
  const rows: ReportBlock[][] = []
  let currentRow: ReportBlock[] = []
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

interface BlockListProps {
  blocks: ReportBlock[]
  reportSectionId: string
  templateBlocks: ReportTemplateBlock[]
  onBlocksChange: () => void
}

export default function BlockList({
  blocks,
  onBlocksChange,
}: BlockListProps) {
  // Group blocks into rows based on their layoutHints.width
  // Blocks are first sorted by their order field, then grouped into rows while preserving that order
  const blockRows = useMemo(() => {
    const sortedBlocks = [...blocks].sort((a, b) => a.order - b.order)
    return groupBlocksIntoRows(sortedBlocks)
  }, [blocks])

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
            const width = parseWidth(block.layoutHints)
            const gridSpan = width >= 1 ? 12 : Math.round(width * 12)
            return (
              <Box
                key={block.reportBlockId}
                sx={{
                  gridColumn: `span ${gridSpan}`,
                }}
              >
                <BlockItem block={block} onSave={onBlocksChange} />
              </Box>
            )
          })}
        </Box>
      ))}
    </Box>
  )
}

