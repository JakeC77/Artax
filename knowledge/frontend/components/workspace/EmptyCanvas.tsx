import type React from 'react'
import { useCallback, useEffect, useState } from 'react'
import { Box, Chip, CircularProgress, Paper, Typography } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import {
  fetchWorkspaceAnalyses,
  fetchScenarios,
  fetchReportByAttachment,
  type WorkspaceAnalysis,
  type Scenario,
  type Report,
} from '../../services/graphql'

const CARD_WIDTH = 450
const CARD_HEIGHT = 140

export type EmptyCanvasProps = {
  workspaceId: string
  onActivate: (reportId: string) => void
  workflowInProgress?: boolean
}

export default function EmptyCanvas({ workspaceId, onActivate, workflowInProgress = false }: EmptyCanvasProps) {
  const theme = useTheme()
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const [workspaceAnalyses, setWorkspaceAnalyses] = useState<WorkspaceAnalysis[]>([])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [analysisReports, setAnalysisReports] = useState<Map<string, Report>>(new Map())
  const [scenarioReports, setScenarioReports] = useState<Map<string, Report>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const [analyses, scens] = await Promise.all([
          fetchWorkspaceAnalyses(workspaceId),
          fetchScenarios(workspaceId),
        ])

        const analysisReportPromises = analyses.map((a) =>
          fetchReportByAttachment(a.workspaceAnalysisId).then((r) => [a.workspaceAnalysisId, r] as const),
        )
        const scenarioReportPromises = scens.map((s) =>
          fetchReportByAttachment(undefined, s.scenarioId).then((r) => [s.scenarioId, r] as const),
        )

        const [analysisReportsArr, scenarioReportsArr] = await Promise.all([
          Promise.all(analysisReportPromises),
          Promise.all(scenarioReportPromises),
        ])

        setWorkspaceAnalyses(analyses)
        setScenarios(scens)
        setAnalysisReports(new Map(analysisReportsArr.filter(([, r]) => r !== null) as [string, Report][]))
        setScenarioReports(new Map(scenarioReportsArr.filter(([, r]) => r !== null) as [string, Report][]))
      } catch (error) {
        console.error('[EmptyCanvas] Failed to load data:', error)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [workspaceId])

  const onDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDraggingOver(true)
  }, [])

  const onDragLeave = useCallback(() => setIsDraggingOver(false), [])

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDraggingOver(false)
      const dataStr = e.dataTransfer.getData('text/plain')
      try {
        const dragData = JSON.parse(dataStr)
        if (dragData.reportId) {
          onActivate(dragData.reportId)
        }
      } catch {
        // Ignore parse errors
      }
    },
    [onActivate],
  )

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '62vh' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (workspaceAnalyses.length === 0 && scenarios.length === 0) {
    return (
      <Box>
        <Box>
          <Box
            sx={{
              position: 'relative',
              minHeight: '62vh',
              border: '2px dashed',
              borderColor: 'divider',
              borderRadius: 0.5,
              overflow: 'hidden',
              bgcolor: 'background.paper',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              px: 2,
              backgroundImage:
                `linear-gradient(${alpha(theme.palette.text.primary, 0.03)} 1px, transparent 1px), linear-gradient(90deg, ${alpha(theme.palette.text.primary, 0.03)} 1px, transparent 1px)`,
              backgroundSize: '48px 48px',
              backgroundPosition: 'center',
              '&::after': {
                content: '""',
                position: 'absolute',
                inset: 0,
                background:
                  `radial-gradient(ellipse at center, ${alpha(theme.palette.background.default, 0)} 0%, ${alpha(theme.palette.background.paper, 0.35)} 55%, ${alpha(theme.palette.background.paper, 0.9)} 100%)`,
                pointerEvents: 'none',
              },
            }}
          >
            <Box sx={{ position: 'relative', textAlign: 'center', maxWidth: 520 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                No analyses or scenarios yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Run an analysis workflow or create a scenario to get started.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>
    )
  }

  return (
    <Box>
      <Box>
        <Box
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          sx={{
            position: 'relative',
            minHeight: '62vh',
            border: '2px dashed',
            borderColor: isDraggingOver ? 'success.main' : 'divider',
            borderRadius: 0.5,
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            px: 2,
            transition: 'border-color 120ms ease',
            backgroundImage: "url('/images/empty-state.png')",
            backgroundRepeat: 'no-repeat',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            '&::after': {
              content: '""',
              position: 'absolute',
              inset: 0,
              background:
                `radial-gradient(ellipse at center, ${alpha(theme.palette.background.default, 0)} 0%, ${alpha(theme.palette.background.paper, 0.2)} 55%, ${alpha(theme.palette.background.paper, 0.7)} 100%)`,
              pointerEvents: 'none',
            },
          }}
        >
          <Box sx={{ position: 'relative', textAlign: 'center', maxWidth: 520 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Use chat or drag an item below to start
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Drop an analysis or scenario card onto this canvas, or type a question in the chat to generate insights.
            </Typography>
          </Box>
        </Box>

        {/* Analysis */}
        {workspaceAnalyses.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Analysis
              </Typography>
              <Box sx={{ flex: 1 }} />
              {workspaceAnalyses.length > 4 && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ cursor: 'pointer' }}
                >
                  See more
                </Typography>
              )}
            </Box>

            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 2,
              }}
            >
              {workspaceAnalyses.map((analysis) => {
                const report = analysisReports.get(analysis.workspaceAnalysisId)

                // Format creation date
                const createdDate = new Date(analysis.createdOn).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })

                const hasReport = !!report?.reportId
                const isActionable = hasReport && !workflowInProgress

                return (
                  <Paper
                    key={analysis.workspaceAnalysisId}
                    draggable={isActionable}
                    onDragStart={(e) => {
                      if (!isActionable) {
                        e.preventDefault()
                        return
                      }
                      const dragData = {
                        type: 'analysis',
                        analysisId: analysis.workspaceAnalysisId,
                        reportId: report.reportId,
                      }
                      e.dataTransfer.setData('text/plain', JSON.stringify(dragData))
                      e.dataTransfer.effectAllowed = 'copyMove'
                    }}
                    sx={{
                      flex: `0 0 ${CARD_WIDTH}px`,
                      maxWidth: CARD_WIDTH,
                      height: CARD_HEIGHT,
                      p: 1.5,
                      borderRadius: 0.5,
                      border: '1px solid',
                      borderColor: 'divider',
                      bgcolor: 'background.default',
                      cursor: isActionable ? 'grab' : 'not-allowed',
                      opacity: isActionable ? 1 : 0.6,
                      display: 'flex',
                      flexDirection: 'column',
                      '&:active': { cursor: isActionable ? 'grabbing' : 'not-allowed' },
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      {workflowInProgress && !hasReport && (
                        <Chip
                          size="small"
                          label="Generating..."
                          color="info"
                          variant="outlined"
                        />
                      )}
                      {report && (
                        <Chip
                          size="small"
                          label={report.status}
                          color="warning"
                          variant="outlined"
                        />
                      )}
                      <Typography
                        sx={{
                          fontWeight: 700,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          flex: 1,
                        }}
                      >
                        {analysis.titleText}
                      </Typography>
                    </Box>

                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ mb: 0.75, display: 'block' }}
                    >
                      {createdDate} • v{analysis.version}
                    </Typography>

                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        flexGrow: 1,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {analysis.bodyText || 'No description available'}
                    </Typography>
                  </Paper>
                )
              })}
            </Box>
          </Box>
        )}

        {/* Scenarios */}
        {scenarios.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Scenarios
            </Typography>

            <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 1 }}>
              {scenarios.map((scenario) => {
                const report = scenarioReports.get(scenario.scenarioId)

                // Extract chips from report metadata if available
                let chips: string[] = []
                if (report?.metadata) {
                  try {
                    const metadata = JSON.parse(report.metadata)
                    if (metadata.chips && Array.isArray(metadata.chips)) {
                      chips = metadata.chips
                    }
                  } catch {
                    // Ignore JSON parse errors
                  }
                }

                // Format creation date
                const createdDate = new Date(scenario.createdAt).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })

                // Get description from mainText or headerText
                const description = scenario.mainText || scenario.headerText || 'No description available'

                const hasReport = !!report?.reportId
                const isActionable = hasReport && !workflowInProgress

                return (
                  <Paper
                    key={scenario.scenarioId}
                    draggable={isActionable}
                    onDragStart={(e) => {
                      if (!isActionable) {
                        e.preventDefault()
                        return
                      }
                      const dragData = {
                        type: 'scenario',
                        scenarioId: scenario.scenarioId,
                        reportId: report.reportId,
                      }
                      e.dataTransfer.setData('text/plain', JSON.stringify(dragData))
                      e.dataTransfer.effectAllowed = 'copyMove'
                    }}
                    sx={{
                      flex: `0 0 ${CARD_WIDTH}px`,
                      maxWidth: CARD_WIDTH,
                      height: CARD_HEIGHT,
                      p: 1.5,
                      borderRadius: 0.5,
                      border: '1px solid',
                      borderColor: 'divider',
                      cursor: isActionable ? 'grab' : 'not-allowed',
                      opacity: isActionable ? 1 : 0.6,
                      bgcolor: 'background.default',
                      display: 'flex',
                      flexDirection: 'column',
                      '&:active': { cursor: isActionable ? 'grabbing' : 'not-allowed' },
                    }}
                  >
                    <Typography
                      sx={{
                        fontWeight: 700,
                        mb: 0.5,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {scenario.name}
                    </Typography>

                    <Box sx={{ mb: 0.75, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                      >
                        {createdDate}
                        {report && ` • ${report.status}`}
                      </Typography>
                      {workflowInProgress && !hasReport && (
                        <Chip
                          size="small"
                          label="Generating..."
                          color="info"
                          variant="outlined"
                        />
                      )}
                    </Box>

                    {chips.length > 0 && (
                      <Box
                        sx={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 0.5,
                          mb: 0.75,
                        }}
                      >
                        {chips.map((c) => (
                          <Chip key={c} label={c} size="small" />
                        ))}
                      </Box>
                    )}

                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        flexGrow: 1,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: chips.length > 0 ? 2 : 3,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {description}
                    </Typography>
                  </Paper>
                )
              })}
            </Box>
          </Box>
        )}



      </Box>
    </Box>
  )
}

