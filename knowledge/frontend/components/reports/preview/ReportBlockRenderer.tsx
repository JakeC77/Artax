import RichTextBlock from './RichTextBlock'
import SingleMetricBlock from './SingleMetricBlock'
import MultiMetricBlock from './MultiMetricBlock'
import InsightCardBlock from './InsightCardBlock'
import type { ReportBlock, Source } from '../../../types/reports'

interface ReportBlockRendererProps {
  block: ReportBlock
  sources: Source[]
}

export default function ReportBlockRenderer({ block, sources }: ReportBlockRendererProps) {
  const sourceRefs = block.sourceRefs || []

  switch (block.blockType) {
    case 'rich_text':
      return <RichTextBlock reportBlockId={block.reportBlockId} sourceRefs={sourceRefs} sources={sources} />
    case 'single_metric':
      return <SingleMetricBlock reportBlockId={block.reportBlockId} sourceRefs={sourceRefs} sources={sources} />
    case 'multi_metric':
      return <MultiMetricBlock reportBlockId={block.reportBlockId} sourceRefs={sourceRefs} sources={sources} />
    case 'insight_card':
      return <InsightCardBlock reportBlockId={block.reportBlockId} sourceRefs={sourceRefs} sources={sources} />
    default:
      return <div>Unknown block type: {block.blockType}</div>
  }
}

