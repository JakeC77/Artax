import RichTextEditor from './editors/RichTextEditor'
import SingleMetricEditor from './editors/SingleMetricEditor'
import MultiMetricEditor from './editors/MultiMetricEditor'
import InsightCardEditor from './editors/InsightCardEditor'
import type { ReportBlock } from '../../types/reports'

interface BlockContentEditorProps {
  block: ReportBlock
  onSave?: () => void
}

export default function BlockContentEditor({ block, onSave }: BlockContentEditorProps) {
  switch (block.blockType) {
    case 'rich_text':
      return <RichTextEditor reportBlockId={block.reportBlockId} onSave={onSave} />
    case 'single_metric':
      return <SingleMetricEditor reportBlockId={block.reportBlockId} onSave={onSave} />
    case 'multi_metric':
      return <MultiMetricEditor reportBlockId={block.reportBlockId} onSave={onSave} />
    case 'insight_card':
      return <InsightCardEditor reportBlockId={block.reportBlockId} onSave={onSave} />
    default:
      return <div>Unknown block type: {block.blockType}</div>
  }
}


