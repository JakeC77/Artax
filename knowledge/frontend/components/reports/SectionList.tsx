import { Box } from '@mui/material'
import SectionItem from './SectionItem'
import type { ReportSection, ReportTemplateSection } from '../../types/reports'

interface SectionListProps {
  sections: ReportSection[]
  templateSections: ReportTemplateSection[]
  reportId: string
  onSectionsChange: () => void
}

export default function SectionList({
  sections,
  templateSections,
  onSectionsChange,
}: SectionListProps) {
  return (
    <Box>
      {sections
        .sort((a, b) => a.order - b.order)
        .map((section) => {
          const templateSection = templateSections.find(
            (ts) => ts.templateSectionId === section.templateSectionId
          )
          return (
            <SectionItem
              key={section.reportSectionId}
              section={section}
              templateSection={templateSection || null}
              onSectionChange={onSectionsChange}
            />
          )
        })}
    </Box>
  )
}

