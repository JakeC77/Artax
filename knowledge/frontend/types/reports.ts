// Report Template Types (Read-Only Structure)
export interface ReportTemplate {
  templateId: string
  version: number
  name: string
  description: string | null
  createdAt: string
  sections: ReportTemplateSection[]
}

export interface ReportTemplateSection {
  templateSectionId: string
  sectionType: string
  header: string
  order: number
  semanticDefinition: string | null
  blocks: ReportTemplateBlock[]
}

export interface ReportTemplateBlock {
  templateBlockId: string
  blockType: 'rich_text' | 'single_metric' | 'multi_metric' | 'insight_card'
  order: number
  layoutHints: string | null // JSON string
  semanticDefinition: string | null
}

// Report Types (User-Editable Instances)
export interface Report {
  reportId: string
  templateId: string | null
  templateVersion: number | null
  title: string
  status: string
  type: 'analysis' | 'scenario'
  metadata: string | null
  sections: ReportSection[]
  sources: Source[]
}

export interface ReportSection {
  reportSectionId: string
  templateSectionId: string
  sectionType: string
  header: string
  order: number
  blocks: ReportBlock[]
}

export interface ReportBlock {
  reportBlockId: string
  templateBlockId: string
  blockType: 'rich_text' | 'single_metric' | 'multi_metric' | 'insight_card'
  order: number
  sourceRefs: string[]
  provenance: string | null // JSON string
  layoutHints: string | null // JSON string
}

export interface Source {
  sourceId: string
  sourceType: string
  uri: string | null
  title: string
  description: string | null
}

// Block Content Types
export interface RichTextContent {
  reportBlockId: string
  content: string
}

export interface SingleMetricContent {
  reportBlockId: string
  label: string
  value: string
  unit: string | null
  trend: 'up' | 'down' | 'stable' | null
}

export interface Metric {
  label: string
  value: string
  unit: string | null
  trend: 'up' | 'down' | 'stable' | null
}

export interface MultiMetricContent {
  reportBlockId: string
  metrics: string // JSON string of Metric[]
}

export interface InsightCardContent {
  reportBlockId: string
  title: string
  body: string
  badge: string | null
  severity: 'info' | 'warning' | 'critical' | null
}

// Union type for block content
export type BlockContent = RichTextContent | SingleMetricContent | MultiMetricContent | InsightCardContent


