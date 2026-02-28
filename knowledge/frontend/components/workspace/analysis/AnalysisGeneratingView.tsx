import { useEffect, useMemo } from "react";
import {
  Box,
  Typography,
  LinearProgress,
  Alert,
  Paper,
  Chip,
  CircularProgress,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { CheckCircle } from "@mui/icons-material";
import { useAnalysisProgress } from "./useAnalysisProgress";
import {
  UI_PHASE_ORDER,
  UI_PHASE_LABELS,
  UI_PHASE_DISPLAY_NAMES,
  PHASE_MAPPING,
  calculateOverallProgress,
  type UIPhase,
  type BackendPhase,
} from "./types";

interface AnalysisGeneratingViewProps {
  runId: string | null;
  onComplete: (reportIds: string[]) => void;
  onCancel: () => void;
}

const CARD_WIDTH = 450;
const CARD_HEIGHT = 140;

export default function AnalysisGeneratingView({
  runId,
  onComplete,
}: AnalysisGeneratingViewProps) {
  const theme = useTheme();

  const progress = useAnalysisProgress({
    onComplete: (reportIds) => {
      onComplete(reportIds);
    },
    onError: (error) => {
      console.error("[AnalysisGeneratingView] Workflow error:", error);
    },
  });

  // Start stream when runId changes
  useEffect(() => {
    if (runId) {
      progress.startStream(runId);
    }
    return () => {
      progress.stopStream();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // Calculate UI phase from backend phase
  const uiPhaseIndex = progress.phase
    ? UI_PHASE_ORDER.indexOf(
        PHASE_MAPPING[progress.phase.name as BackendPhase],
      ) + 1
    : 1;

  const uiPhaseName: UIPhase = UI_PHASE_ORDER[uiPhaseIndex - 1];

  // Separate analyses and scenarios for display
  const analyses = useMemo(
    () => progress.tasks.filter((t) => t.type === "analysis"),
    [progress.tasks],
  );
  const scenarios = useMemo(
    () => progress.tasks.filter((t) => t.type === "scenario"),
    [progress.tasks],
  );

  // Calculate overall progress percentage
  const overallProgress = useMemo(
    () => calculateOverallProgress(progress),
    [progress],
  );

  return (
    <Box>
      <Box>
        {/* Canvas area with progress */}
        <Box
          sx={{
            position: "relative",
            minHeight: "62vh",
            border: "2px dashed",
            borderColor: "primary.main",
            borderRadius: 0.5,
            overflow: "hidden",
            bgcolor: "background.paper",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            px: 2,
            backgroundImage: `linear-gradient(${alpha(theme.palette.text.primary, 0.03)} 1px, transparent 1px), linear-gradient(90deg, ${alpha(theme.palette.text.primary, 0.03)} 1px, transparent 1px)`,
            backgroundSize: "48px 48px",
            backgroundPosition: "center",
            "&::after": {
              content: '""',
              position: "absolute",
              inset: 0,
              background: `radial-gradient(ellipse at center, ${alpha(theme.palette.background.default, 0)} 0%, ${alpha(theme.palette.background.paper, 0.35)} 55%, ${alpha(theme.palette.background.paper, 0.9)} 100%)`,
              pointerEvents: "none",
            },
          }}
        >
          <Box
            sx={{
              position: "relative",
              textAlign: "center",
              maxWidth: 520,
              zIndex: 1,
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                mb: 2,
              }}
            >
              <CircularProgress
                size={32}
                thickness={4}
                sx={{ color: "primary.main" }}
              />
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Generating Analysis and Scenarios
              </Typography>
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Phase {uiPhaseIndex} of 4: {UI_PHASE_DISPLAY_NAMES[uiPhaseName]}
            </Typography>

            {/* Phase indicators */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                mb: 3,
              }}
            >
              {UI_PHASE_ORDER.map((phase, idx) => {
                const isCompleted = idx + 1 < uiPhaseIndex;
                const isActive = idx + 1 === uiPhaseIndex;

                return (
                  <Box
                    key={phase}
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 0.5,
                    }}
                  >
                    <Box
                      sx={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: isCompleted
                          ? "primary.main"
                          : isActive
                            ? "primary.main"
                            : "action.hover",
                        color:
                          isCompleted || isActive
                            ? "primary.contrastText"
                            : "text.secondary",
                      }}
                    >
                      {isCompleted ? (
                        <CheckCircle sx={{ fontSize: 18 }} />
                      ) : (
                        <Box
                          sx={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            bgcolor: isActive
                              ? "primary.contrastText"
                              : "text.disabled",
                          }}
                        />
                      )}
                    </Box>
                    <Typography
                      variant="caption"
                      sx={{
                        color: isActive ? "primary.main" : "text.secondary",
                        fontWeight: isActive ? 600 : 400,
                      }}
                    >
                      {UI_PHASE_LABELS[phase]}
                    </Typography>
                  </Box>
                );
              })}
            </Box>

            {/* Progress bar */}
            <LinearProgress
              variant="determinate"
              value={overallProgress}
              sx={{
                height: 8,
                borderRadius: 1,
                bgcolor: "action.hover",
                "& .MuiLinearProgress-bar": {
                  bgcolor: "primary.main",
                  borderRadius: 1,
                },
              }}
            />

            {/* Status messages */}
            {progress.messages.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    display: "block",
                    fontStyle: "italic",
                  }}
                >
                  {progress.messages[progress.messages.length - 1]}
                </Typography>
              </Box>
            )}

            {/* Task progress during analyzing phase */}
            {uiPhaseName === "analyzing" && analyses.length > 0 && (
              <Box
                sx={{
                  mt: 3,
                  p: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.05),
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant="caption"
                  fontWeight={600}
                  color="text.secondary"
                  sx={{ mb: 1, display: "block" }}
                >
                  {analyses.filter((t) => t.status === "completed").length} of{" "}
                  {analyses.length} complete
                  {analyses.filter((t) => t.status === "running").length > 0 &&
                    ` (${analyses.filter((t) => t.status === "running").length} running)`}
                </Typography>
                <Box
                  sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}
                >
                  {analyses.slice(0, 3).map((task) => (
                    <Box
                      key={task.id}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <Box sx={{ width: 16, height: 16, flexShrink: 0 }}>
                        {task.status === "completed" && (
                          <CheckCircle
                            sx={{ fontSize: 16, color: "success.main" }}
                          />
                        )}
                        {task.status === "running" && (
                          <CircularProgress
                            size={16}
                            thickness={6}
                            sx={{ color: "primary.main" }}
                          />
                        )}
                        {task.status === "pending" && (
                          <Box
                            sx={{
                              width: 16,
                              height: 16,
                              borderRadius: "50%",
                              border: "2px solid",
                              borderColor: "divider",
                            }}
                          />
                        )}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{
                          flex: 1,
                          color:
                            task.status === "pending"
                              ? "text.secondary"
                              : "text.primary",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {task.title}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 500,
                          color:
                            task.status === "completed"
                              ? "success.main"
                              : task.status === "running"
                                ? "primary.main"
                                : "text.disabled",
                        }}
                      >
                        {task.status === "completed" && "Done"}
                        {task.status === "running" && "Running..."}
                        {task.status === "pending" && "Pending"}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {/* Task progress during modeling phase (planning scenarios) */}
            {uiPhaseName === "modeling" && scenarios.length > 0 && (
              <Box
                sx={{
                  mt: 3,
                  p: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.05),
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant="caption"
                  fontWeight={600}
                  color="text.secondary"
                  sx={{ mb: 1, display: "block" }}
                >
                  Planning {scenarios.length} scenario{scenarios.length !== 1 ? 's' : ''}
                </Typography>
                <Box
                  sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}
                >
                  {scenarios.slice(0, 3).map((task) => (
                    <Box
                      key={task.id}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <Box sx={{ width: 16, height: 16, flexShrink: 0 }}>
                        {task.status === "completed" && (
                          <CheckCircle
                            sx={{ fontSize: 16, color: "success.main" }}
                          />
                        )}
                        {task.status === "running" && (
                          <CircularProgress
                            size={16}
                            thickness={6}
                            sx={{ color: "primary.main" }}
                          />
                        )}
                        {task.status === "pending" && (
                          <Box
                            sx={{
                              width: 16,
                              height: 16,
                              borderRadius: "50%",
                              border: "2px solid",
                              borderColor: "divider",
                            }}
                          />
                        )}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{
                          flex: 1,
                          color:
                            task.status === "pending"
                              ? "text.secondary"
                              : "text.primary",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {task.title}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 500,
                          color:
                            task.status === "completed"
                              ? "success.main"
                              : task.status === "running"
                                ? "primary.main"
                                : "text.disabled",
                        }}
                      >
                        {task.status === "completed" && "Done"}
                        {task.status === "running" && "Running..."}
                        {task.status === "pending" && "Pending"}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {/* Task progress during scenarios phase (executing scenarios) */}
            {uiPhaseName === "scenarios" && scenarios.length > 0 && (
              <Box
                sx={{
                  mt: 3,
                  p: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.05),
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant="caption"
                  fontWeight={600}
                  color="text.secondary"
                  sx={{ mb: 1, display: "block" }}
                >
                  {scenarios.filter((t) => t.status === "completed").length} of{" "}
                  {scenarios.length} complete
                  {scenarios.filter((t) => t.status === "running").length > 0 &&
                    ` (${scenarios.filter((t) => t.status === "running").length} running)`}
                </Typography>
                <Box
                  sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}
                >
                  {scenarios.slice(0, 3).map((task) => (
                    <Box
                      key={task.id}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <Box sx={{ width: 16, height: 16, flexShrink: 0 }}>
                        {task.status === "completed" && (
                          <CheckCircle
                            sx={{ fontSize: 16, color: "success.main" }}
                          />
                        )}
                        {task.status === "running" && (
                          <CircularProgress
                            size={16}
                            thickness={6}
                            sx={{ color: "primary.main" }}
                          />
                        )}
                        {task.status === "pending" && (
                          <Box
                            sx={{
                              width: 16,
                              height: 16,
                              borderRadius: "50%",
                              border: "2px solid",
                              borderColor: "divider",
                            }}
                          />
                        )}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{
                          flex: 1,
                          color:
                            task.status === "pending"
                              ? "text.secondary"
                              : "text.primary",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {task.title}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 500,
                          color:
                            task.status === "completed"
                              ? "success.main"
                              : task.status === "running"
                                ? "primary.main"
                                : "text.disabled",
                        }}
                      >
                        {task.status === "completed" && "Done"}
                        {task.status === "running" && "Running..."}
                        {task.status === "pending" && "Pending"}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        </Box>

        {/* Analysis section */}
        {analyses.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Box
              sx={{ mb: 1.5, display: "flex", alignItems: "center", gap: 1 }}
            >
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Analysis
              </Typography>
              <Chip
                size="small"
                label={`${analyses.filter((t) => t.status === "completed").length}/${analyses.length} Complete`}
                color="primary"
                variant="outlined"
              />
            </Box>

            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                gap: 2,
              }}
            >
              {analyses.map((task) => (
                <Paper
                  key={task.id}
                  sx={{
                    flex: `0 0 ${CARD_WIDTH}px`,
                    maxWidth: CARD_WIDTH,
                    height: CARD_HEIGHT,
                    p: 1.5,
                    borderRadius: 0.5,
                    border: "1px solid",
                    borderColor: "divider",
                    bgcolor: "background.default",
                    cursor: "not-allowed",
                    opacity: task.status === "completed" ? 0.8 : 0.6,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 0.5,
                    }}
                  >
                    <Chip
                      size="small"
                      label={
                        task.status === "completed"
                          ? "Complete"
                          : task.status === "running"
                            ? "Generating..."
                            : task.status === "failed"
                              ? "Failed"
                              : "Pending"
                      }
                      color={
                        task.status === "completed"
                          ? "success"
                          : task.status === "running"
                            ? "primary"
                            : task.status === "failed"
                              ? "error"
                              : "default"
                      }
                      variant="outlined"
                      icon={
                        task.status === "running" ? (
                          <CircularProgress size={12} />
                        ) : undefined
                      }
                    />
                    <Typography
                      sx={{
                        fontWeight: 700,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flex: 1,
                      }}
                    >
                      {task.title}
                    </Typography>
                  </Box>

                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      flexGrow: 1,
                      overflow: "hidden",
                      display: "-webkit-box",
                      WebkitLineClamp: 4,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    Analysis in progress...
                  </Typography>
                </Paper>
              ))}
            </Box>
          </Box>
        )}

        {/* Scenarios section */}
        {scenarios.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Box
              sx={{ mb: 1.5, display: "flex", alignItems: "center", gap: 1 }}
            >
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Scenarios
              </Typography>
              <Chip
                size="small"
                label={`${scenarios.filter((t) => t.status === "completed").length}/${scenarios.length} Complete`}
                color="primary"
                variant="outlined"
              />
            </Box>

            <Box sx={{ display: "flex", gap: 2, overflowX: "auto", pb: 1 }}>
              {scenarios.map((task) => (
                <Paper
                  key={task.id}
                  sx={{
                    flex: `0 0 ${CARD_WIDTH}px`,
                    maxWidth: CARD_WIDTH,
                    height: CARD_HEIGHT,
                    p: 1.5,
                    borderRadius: 0.5,
                    border: "1px solid",
                    borderColor: "divider",
                    cursor: "not-allowed",
                    opacity: task.status === "completed" ? 0.8 : 0.6,
                    bgcolor: "background.default",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <Typography
                    sx={{
                      fontWeight: 700,
                      mb: 0.5,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {task.title}
                  </Typography>

                  <Box
                    sx={{
                      mb: 0.75,
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                    }}
                  >
                    <Chip
                      size="small"
                      label={
                        task.status === "completed"
                          ? "Complete"
                          : task.status === "running"
                            ? "Generating..."
                            : task.status === "failed"
                              ? "Failed"
                              : "Pending"
                      }
                      color={
                        task.status === "completed"
                          ? "success"
                          : task.status === "running"
                            ? "primary"
                            : task.status === "failed"
                              ? "error"
                              : "default"
                      }
                      variant="outlined"
                      icon={
                        task.status === "running" ? (
                          <CircularProgress size={12} />
                        ) : undefined
                      }
                    />
                  </Box>

                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      flexGrow: 1,
                      overflow: "hidden",
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    Scenario in progress...
                  </Typography>
                </Paper>
              ))}
            </Box>
          </Box>
        )}

        {/* Error Display */}
        {progress.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {progress.error}
          </Alert>
        )}
      </Box>
    </Box>
  );
}
