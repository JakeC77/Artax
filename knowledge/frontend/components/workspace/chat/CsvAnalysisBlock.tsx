import { Box, Typography, Paper, Chip, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material'
import { alpha } from '@mui/material/styles'
import TableChartIcon from '@mui/icons-material/TableChart'

export type CsvColumn = {
  name: string
  data_type: string
  sample_values: string[]
  nullable: boolean
}

export type CsvAnalysisData = {
  columns: CsvColumn[]
  row_count: number
  has_headers: boolean
}

type CsvAnalysisBlockProps = {
  analysis: CsvAnalysisData
}

export default function CsvAnalysisBlock({ analysis }: CsvAnalysisBlockProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'light' ? 0.04 : 0.08),
        mt: 1.5,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <TableChartIcon sx={{ color: 'primary.main', fontSize: 24 }} />
        <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
          CSV Structure Analysis
        </Typography>
        <Chip
          label={`${analysis.row_count} row${analysis.row_count !== 1 ? 's' : ''}`}
          size="small"
          sx={{ ml: 'auto', fontWeight: 500 }}
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Found <strong>{analysis.columns.length}</strong> column{analysis.columns.length !== 1 ? 's' : ''}
          {analysis.has_headers && ' (with headers)'}
        </Typography>
      </Box>

      <TableContainer
        sx={{
          maxHeight: 400,
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.default' }}>Column Name</TableCell>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.default' }}>Data Type</TableCell>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.default' }}>Nullable</TableCell>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.default' }}>Sample Values</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {analysis.columns.map((column, index) => (
              <TableRow key={index} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 500, fontFamily: 'monospace' }}>
                    {column.name}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={column.data_type}
                    size="small"
                    variant="outlined"
                    sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={column.nullable ? 'Yes' : 'No'}
                    size="small"
                    color={column.nullable ? 'default' : 'primary'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, maxWidth: 300 }}>
                    {column.sample_values.slice(0, 3).map((value, valIndex) => (
                      <Chip
                        key={valIndex}
                        label={String(value)}
                        size="small"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.7rem',
                          height: 20,
                          bgcolor: 'action.hover',
                        }}
                      />
                    ))}
                    {column.sample_values.length > 3 && (
                      <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center', ml: 0.5 }}>
                        +{column.sample_values.length - 3} more
                      </Typography>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}
