import { useState, useEffect, useCallback } from 'react'
import { Box, CircularProgress, Typography, Snackbar, Alert } from '@mui/material'
import ReportHeader from './ReportHeader'
import SectionList from './SectionList'
import { fetchReportById, fetchReportTemplateById } from '../../services/graphql'
import type { Report, ReportTemplate } from '../../types/reports'

interface ReportEditorProps {
  reportId: string
}

export default function ReportEditor({ reportId }: ReportEditorProps) {
  const [report, setReport] = useState<Report | null>(null)
  const [template, setTemplate] = useState<ReportTemplate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })

  const loadReport = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const reportData = await fetchReportById(reportId)
      if (!reportData) {
        setError('Report not found')
        setLoading(false)
        return
      }
      setReport(reportData)

      // Load template structure only if templateId exists
      if (reportData.templateId && reportData.templateVersion !== null) {
        const templateData = await fetchReportTemplateById(reportData.templateId, reportData.templateVersion)
        setTemplate(templateData)
      } else {
        // No template associated with this report
        setTemplate(null)
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load report')
    } finally {
      setLoading(false)
    }
  }, [reportId])

  useEffect(() => {
    loadReport()
  }, [loadReport])

  const handleSectionsChange = useCallback(() => {
    loadReport()
  }, [loadReport])

  const handleUpdateReport = useCallback(async () => {
    // For now, just refetch - in a real app you'd have an updateReport mutation
    await loadReport()
    setSnackbar({ open: true, message: 'Report updated', severity: 'success' })
  }, [loadReport])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error || !report) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="error">{error || 'Report not found'}</Typography>
      </Box>
    )
  }

  return (
    <Box>
      <ReportHeader report={report} onUpdate={handleUpdateReport} />
      <SectionList
        sections={report.sections}
        templateSections={template?.sections || []}
        reportId={report.reportId}
        onSectionsChange={handleSectionsChange}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

