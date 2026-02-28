import { Box, Container } from '@mui/material'
import { useParams } from 'react-router-dom'
import ReportEditor from '../components/reports/ReportEditor'

export default function ReportBuilder() {
  const { reportId } = useParams<{ reportId: string }>()

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
        <ReportEditor reportId={reportId} />
      </Container>
    </Box>
  )
}


