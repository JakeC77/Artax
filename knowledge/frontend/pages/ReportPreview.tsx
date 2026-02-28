import { Box, Container } from '@mui/material'
import { useParams, useNavigate } from 'react-router-dom'
import ReportPreviewView from '../components/reports/ReportPreviewView'
import Button from '../components/common/Button'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'

export default function ReportPreview() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()

  if (!reportId) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <span>Report ID is required</span>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100%', overflowY: 'auto', bgcolor: 'background.default', p: 2 }}>
      <Container maxWidth="lg" disableGutters>
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <ArrowBackIcon sx={{ fontSize: 18 }} />
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/reports/${reportId}`)}
          >
            Back to Editor
          </Button>
        </Box>
        <Box sx={{ bgcolor: 'background.paper', p: 4, borderRadius: 2, boxShadow: 1 }}>
          <ReportPreviewView reportId={reportId} />
        </Box>
      </Container>
    </Box>
  )
}

