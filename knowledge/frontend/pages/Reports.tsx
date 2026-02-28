import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Typography, Container, CircularProgress, Paper, Chip, IconButton, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import Button from '../components/common/Button'
import CreateReportDialog from '../components/reports/CreateReportDialog'
import { fetchReports, deleteReport } from '../services/graphql'
import type { Report } from '../types/reports'

type ReportListItem = Omit<Report, 'sections' | 'sources'>

export default function Reports() {
  const navigate = useNavigate()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [reportToDelete, setReportToDelete] = useState<ReportListItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const loadReports = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchReports()
      setReports(data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReports()
  }, [])

  const handleCreateSuccess = (reportId: string) => {
    loadReports() // Refresh the list
    navigate(`/reports/${reportId}`)
  }

  const handleReportClick = (reportId: string) => {
    navigate(`/reports/${reportId}`)
  }

  const handleDeleteClick = (e: React.MouseEvent, report: ReportListItem) => {
    e.stopPropagation() // Prevent navigation when clicking delete
    setReportToDelete(report)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!reportToDelete) return

    try {
      setDeleting(true)
      await deleteReport(reportToDelete.reportId)
      setDeleteDialogOpen(false)
      setReportToDelete(null)
      loadReports() // Refresh the list
    } catch (e: any) {
      setError(e?.message || 'Failed to delete report')
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setReportToDelete(null)
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto', bgcolor: 'background.default', p: 2 }}>
      <Container maxWidth={false} disableGutters>
        <Box
          sx={{
            mb: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>
            Reports
          </Typography>
          <Button onClick={() => setCreateDialogOpen(true)}>Create Report</Button>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography color="error">{error}</Typography>
            <Box sx={{ mt: 2 }}>
              <Button onClick={loadReports}>
                Retry
              </Button>
            </Box>
          </Box>
        ) : reports.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
            <Typography variant="h6">No reports yet</Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              Create a new report from a template to get started
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
              gap: 2,
            }}
          >
            {reports.map((report) => (
              <Paper
                key={report.reportId}
                elevation={0}
                sx={{
                  p: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  position: 'relative',
                  '&:hover': {
                    borderColor: 'primary.main',
                    boxShadow: 2,
                  },
                }}
                onClick={() => handleReportClick(report.reportId)}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant="h6" sx={{ fontWeight: 600, flex: 1 }}>
                    {report.title}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={(e) => handleDeleteClick(e, report)}
                    sx={{
                      color: 'error.main',
                      '&:hover': { bgcolor: 'error.light', color: 'error.dark' },
                    }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
                  <Chip label={report.status} size="small" variant="outlined" />
                  <Chip label={report.type} size="small" variant="outlined" />
                </Box>
              </Paper>
            ))}
          </Box>
        )}

        <CreateReportDialog
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={handleCreateSuccess}
          scenarioId="85dca23d-ca25-4f49-8719-e2b8a20bd329"
        />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Delete Report</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete "{reportToDelete?.title}"? This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button size="sm" variant="outline" onClick={handleDeleteCancel} disabled={deleting}>
              Cancel
            </Button>
            <Button size="sm" color="error" onClick={handleDeleteConfirm} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  )
}

