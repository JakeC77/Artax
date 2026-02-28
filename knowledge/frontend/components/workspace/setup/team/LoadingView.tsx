import { useState, useEffect, useMemo } from "react";
import {
  Box,
  Typography,
  keyframes,
  Alert,
  Fade,
  Chip,
  CircularProgress,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import ErrorIcon from "@mui/icons-material/Error";
import SetupFooter from "../SetupFooter";
import type { DataScope } from "../../../../services/graphql";
import type {
  SetupProgressState,
  SetupTask,
} from "../../../../types/setupProgress";
import {
  calculateSetupProgress,
  getPhaseDisplayName,
} from "../../../../types/setupProgress";

const pulse = keyframes`
  0% {
    transform: scale(0.95);
    opacity: 0.8;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(0.95);
    opacity: 0.8;
  }
`;

const rotate = keyframes`
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
`;

// Mock entity loading states for AI team
export const aiTeamLoadingEntities = [
  { id: "analyst", name: "Data Analyst", loaded: false },
  { id: "strategist", name: "Strategist", loaded: false },
  { id: "engineer", name: "Engineer", loaded: false },
  { id: "specialist", name: "Specialist", loaded: false },
];

// ============================================================================
// Types
// ============================================================================

/** @deprecated Use SetupTask from setupProgress types instead */
export type EntityProgress = {
  entity_type?: string;
  entity?: string;
  status?: "pending" | "in_progress" | "complete" | "error";
  progress?: number;
  total?: number;
  message?: string;
};

/** Loading mode determines the visual theme and default text */
export type LoadingMode = "data_staging" | "team_building";

export type LoadingViewProps = {
  onContinue: () => void;
  currentStep?: number;
  totalSteps?: number;
  /** Loading mode - determines visual theme and default text */
  mode?: LoadingMode;
  title?: string;
  subtitle?: string;
  /** Unified progress state from useSetupProgress hook */
  progressState?: SetupProgressState;
  /** @deprecated Use progressState instead */
  entities?: Array<{ id: string; name: string; loaded: boolean }>;
  /** @deprecated Use progressState instead */
  executionProgress?: EntityProgress[];
  autoProgress?: boolean;
  /** When true, marks loading as complete (e.g., execution_complete event received) */
  isReady?: boolean;
  /** @deprecated Use progressState instead - Data scope containing the entities being fetched */
  dataScope?: DataScope | null;
  /** Error message to display if loading fails */
  error?: string | null;
};

// ============================================================================
// Helper Components
// ============================================================================

/** Task status chip with appropriate styling */
function TaskStatusChip({ task }: { task: SetupTask }) {
  const getChipProps = () => {
    switch (task.status) {
      case "completed":
        return {
          icon: <CheckIcon sx={{ fontSize: 14 }} />,
          color: "success" as const,
          label: task.title,
        };
      case "running":
        return {
          icon: <CircularProgress size={12} thickness={4} />,
          color: "primary" as const,
          label: task.title,
        };
      case "failed":
        return {
          icon: <ErrorIcon sx={{ fontSize: 14 }} />,
          color: "error" as const,
          label: task.title,
        };
      default:
        return {
          color: "default" as const,
          label: task.title,
        };
    }
  };

  const props = getChipProps();

  return (
    <Chip
      size="small"
      variant={task.status === "pending" ? "outlined" : "filled"}
      {...props}
      sx={{
        "& .MuiChip-icon": {
          ml: 0.5,
        },
      }}
    />
  );
}

/** Task list showing all tasks with their status */
function TaskList({
  tasks,
  isComplete,
}: {
  tasks: SetupTask[];
  isComplete: boolean;
}) {
  if (tasks.length === 0) return null;

  // Group tasks by type
  const entityTasks = tasks.filter((t) => t.type === "entity");
  const agentTasks = tasks.filter((t) => t.type === "agent");
  const otherTasks = tasks.filter(
    (t) => t.type !== "entity" && t.type !== "agent",
  );

  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const runningCount = tasks.filter((t) => t.status === "running").length;

  return (
    <Box sx={{ mb: 3 }}>
      {/* Summary line */}
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5 }}>
        {isComplete
          ? `${completedCount} of ${tasks.length} complete`
          : runningCount > 0
            ? `${completedCount} complete, ${runningCount} in progress`
            : `${completedCount} of ${tasks.length} complete`}
      </Typography>

      {/* Entity tasks */}
      {entityTasks.length > 0 && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 1 }}>
          {entityTasks.map((task) => (
            <TaskStatusChip key={task.id} task={task} />
          ))}
        </Box>
      )}

      {/* Agent tasks */}
      {agentTasks.length > 0 && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 1 }}>
          {agentTasks.map((task) => (
            <TaskStatusChip key={task.id} task={task} />
          ))}
        </Box>
      )}

      {/* Other tasks */}
      {otherTasks.length > 0 && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          {otherTasks.map((task) => (
            <TaskStatusChip key={task.id} task={task} />
          ))}
        </Box>
      )}
    </Box>
  );
}

// ============================================================================
// Default Configuration
// ============================================================================

const MODE_DEFAULTS: Record<LoadingMode, { title: string; subtitle: string }> =
  {
    data_staging: {
      title: "Scope Confirmed!",
      subtitle: "Staging data to workspace...",
    },
    team_building: {
      title: "Building Your AI Team",
      subtitle: "Configuring agents for your workspace...",
    },
  };

// ============================================================================
// Main Component
// ============================================================================

export default function LoadingView({
  onContinue,
  currentStep = 3,
  totalSteps = 4,
  mode = "data_staging",
  title: titleProp,
  subtitle: subtitleProp,
  progressState,
  entities: _initialEntities,
  executionProgress,
  autoProgress = false,
  isReady = false,
  dataScope,
  error: errorProp = null,
}: LoadingViewProps) {
  const [isComplete, setIsComplete] = useState(false);
  const [visibleStartIndex, setVisibleStartIndex] = useState(0);
  // Time-based progress for team_building mode (starts at 10%, +10% every 15s, caps at 90%)
  const [timeBasedProgress, setTimeBasedProgress] = useState(10);

  // Reset state when mode changes (e.g., transitioning from data_staging to team_building)
  useEffect(() => {
    setIsComplete(false);
    setTimeBasedProgress(10);
    setVisibleStartIndex(0);
  }, [mode]);

  // Use mode defaults if title/subtitle not provided
  const title = titleProp || MODE_DEFAULTS[mode].title;
  const subtitle = subtitleProp || MODE_DEFAULTS[mode].subtitle;

  // Determine error from props or progress state
  const error = errorProp || progressState?.error || null;

  // Number of entities to show at once (legacy animation)
  const VISIBLE_ENTITY_COUNT = 1;
  const ROTATION_INTERVAL = 20000;

  // Time-based progress increment for team_building mode
  // Team building takes ~90-115 seconds, so we increment 10% every 10 seconds
  // This gives us 10% -> 90% over ~80 seconds, never reaching 100% before completion
  useEffect(() => {
    if (mode !== "team_building" || isComplete) return;

    const interval = setInterval(() => {
      setTimeBasedProgress((prev) => Math.min(prev + 10, 90));
    }, 10000);

    return () => clearInterval(interval);
  }, [mode, isComplete]);

  // ============================================================================
  // Progress Calculation
  // ============================================================================

  // Calculate progress from unified state or legacy props
  const progressPercent = useMemo(() => {
    if (isComplete) return 100;

    // Prefer unified progress state (if it has tasks)
    if (progressState && progressState.tasks.length > 0) {
      return calculateSetupProgress(progressState);
    }

    // Legacy: Calculate from executionProgress
    const progressEntries = executionProgress || [];
    if (progressEntries.length > 0) {
      const ratios = progressEntries.map((entry) => {
        if (entry.status === "complete") return 1;
        if (typeof entry.progress === "number" && entry.total) {
          return Math.min(entry.progress / entry.total, 1);
        }
        return entry.status === "in_progress" ? 0.5 : 0;
      });
      const average =
        ratios.length > 0
          ? ratios.reduce((sum, value) => sum + value, 0) / ratios.length
          : 0;
      return Math.round(average * 100);
    }

    // For team_building mode without real progress data, use time-based progress
    if (mode === "team_building") {
      return timeBasedProgress;
    }

    return 30; // Default starting progress for data_staging
  }, [isComplete, progressState, executionProgress, mode, timeBasedProgress]);

  // ============================================================================
  // Display Entities (Legacy Compatibility)
  // ============================================================================

  const displayEntities = useMemo(() => {
    // If using unified progress state, convert tasks to display format
    if (progressState && progressState.tasks.length > 0) {
      return progressState.tasks.map((task) => ({
        id: task.id,
        name: task.title,
        loaded: task.status === "completed",
      }));
    }

    // Legacy: Derive from dataScope
    if (dataScope?.scopes && dataScope.scopes.length > 0) {
      const progressMap = new Map<string, EntityProgress>();
      (executionProgress || []).forEach((entry) => {
        const key = entry.entity_type || entry.entity || "";
        if (key) progressMap.set(key, entry);
      });

      return dataScope.scopes.map((scope) => ({
        id: scope.entity_type,
        name: scope.entity_type,
        loaded:
          isComplete ||
          progressMap.get(scope.entity_type)?.status === "complete",
      }));
    }

    // Legacy: Use initial entities
    if (_initialEntities && _initialEntities.length > 0) {
      return _initialEntities.map((entity) => ({
        id: entity.id,
        name: entity.name,
        loaded: entity.loaded || isComplete,
      }));
    }

    // Legacy: Derive from executionProgress
    if (executionProgress && executionProgress.length > 0) {
      return executionProgress.map((entry, index) => ({
        id: entry.entity_type || entry.entity || `entity-${index}`,
        name: entry.entity_type || entry.entity || "Entity",
        loaded: entry.status === "complete" || isComplete,
      }));
    }

    return [];
  }, [
    progressState,
    dataScope,
    _initialEntities,
    executionProgress,
    isComplete,
  ]);

  // ============================================================================
  // Completion Handling
  // ============================================================================

  // Mark complete from unified progress state
  useEffect(() => {
    if (progressState?.isComplete) {
      setIsComplete(true);
    }
  }, [progressState?.isComplete]);

  // Mark complete from isReady prop
  useEffect(() => {
    if (isReady) {
      setIsComplete(true);
    }
  }, [isReady]);

  // Auto-continue when complete
  useEffect(() => {
    if (isComplete && autoProgress) {
      const timer = setTimeout(() => {
        onContinue();
      }, 500);
      return () => {
        clearTimeout(timer);
      };
    }
  }, [isComplete, autoProgress, onContinue]);

  // ============================================================================
  // Legacy Animation (for non-unified mode)
  // ============================================================================

  // Check if we have real progress data (tasks) vs just an empty progressState object
  const hasProgressTasks = progressState && progressState.tasks.length > 0;

  useEffect(() => {
    // Only animate if using legacy mode (no real progress tasks) and not complete
    if (
      hasProgressTasks ||
      isComplete ||
      displayEntities.length <= VISIBLE_ENTITY_COUNT
    ) {
      return;
    }

    const interval = setInterval(() => {
      setVisibleStartIndex((prevIndex) => {
        const nextIndex = prevIndex + VISIBLE_ENTITY_COUNT;
        return nextIndex >= displayEntities.length ? 0 : nextIndex;
      });
    }, ROTATION_INTERVAL);

    return () => clearInterval(interval);
  }, [hasProgressTasks, isComplete, displayEntities.length]);

  const visibleEntities = useMemo(() => {
    // Show all entities if we have real progress tasks or loading is complete
    if (hasProgressTasks || isComplete) {
      return displayEntities;
    }

    // Otherwise cycle through entities one at a time
    if (displayEntities.length <= VISIBLE_ENTITY_COUNT) {
      return displayEntities;
    }

    const entities = [];
    for (let i = 0; i < VISIBLE_ENTITY_COUNT; i++) {
      const index = (visibleStartIndex + i) % displayEntities.length;
      entities.push(displayEntities[index]);
    }
    return entities;
  }, [hasProgressTasks, displayEntities, visibleStartIndex, isComplete]);

  // ============================================================================
  // Phase Display
  // ============================================================================

  const phaseDisplayName = useMemo(() => {
    if (progressState?.phase) {
      return getPhaseDisplayName(progressState.phase.name);
    }
    return null;
  }, [progressState?.phase]);

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Main content */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          px: 4,
        }}
      >
        {/* Left side: Animation */}
        <Box sx={{ position: "relative", width: 264, height: 286 }}>
          {/* Animated rings background */}
          <Box
            sx={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              animation: `${rotate} 10s linear infinite`,
              transformOrigin: "130.5px 142.2px",
            }}
          >
            <svg
              width="264"
              height="286"
              viewBox="0 0 264 285"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ position: "absolute", top: 0, left: 0 }}
            >
              <circle
                opacity="0.9"
                cx="130.479"
                cy="142.479"
                r="95.229"
                stroke="#C6A664"
                strokeWidth="0.5"
              />
              <circle
                opacity="0.8"
                cx="130.961"
                cy="141.961"
                r="112.711"
                stroke="#C6A664"
                strokeWidth="0.5"
              />
              <circle
                cx="130.256"
                cy="142.256"
                r="68.7559"
                fill="#C6A664"
                fillOpacity="0.2"
                stroke="#F4F0E6"
              />
            </svg>
          </Box>

          {/* Main pulsing content */}
          <Box sx={{ animation: `${pulse} 2s ease-in-out infinite` }}>
            <svg
              width="264"
              height="286"
              viewBox="0 0 264 285"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Central document icon */}
              <rect
                x="83.1621"
                y="111.079"
                width="94.8066"
                height="64.1178"
                rx="3"
                fill="#F4F0E6"
                fillOpacity="0.85"
              />
              <circle
                cx="87.2722"
                cy="114.641"
                r="1.37004"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <circle
                cx="91.1082"
                cy="114.641"
                r="1.37004"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <circle
                cx="94.9444"
                cy="114.641"
                r="1.37004"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <rect
                x="86.4501"
                y="119.3"
                width="87.6824"
                height="23.0166"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <rect
                x="130.839"
                y="145.604"
                width="43.2932"
                height="9.31626"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <rect
                x="86.4501"
                y="158.757"
                width="87.6824"
                height="9.31626"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <rect
                x="86.4501"
                y="146.7"
                width="26.8527"
                height="2.74008"
                rx="1.37004"
                fill="#C6A664"
                fillOpacity="0.5"
              />
              <rect
                x="86.4501"
                y="151.084"
                width="38.9091"
                height="2.74008"
                rx="1.37004"
                fill="#C6A664"
                fillOpacity="0.5"
              />

              {/* Connection lines and circles */}
              <path
                d="M133.507 39.0052C134.979 39.0052 136.173 37.8113 136.173 36.3386C136.173 34.8658 134.979 33.6719 133.507 33.6719C132.034 33.6719 130.84 34.8658 130.84 36.3386C130.84 37.8113 132.034 39.0052 133.507 39.0052ZM133.507 110.597L134.007 110.597L134.007 36.3386L133.507 36.3386L133.007 36.3386L133.007 110.597L133.507 110.597Z"
                fill="#0F5C4C"
              />
              <path
                d="M133.507 244.597C132.034 244.597 130.84 245.791 130.84 247.264C130.84 248.737 132.034 249.931 133.507 249.931C134.979 249.931 136.173 248.737 136.173 247.264C136.173 245.791 134.979 244.597 133.507 244.597ZM133.507 175.376L133.007 175.376L133.007 247.264L133.507 247.264L134.007 247.264L134.007 175.376L133.507 175.376Z"
                fill="#0F5C4C"
              />
              <path
                d="M231.167 139.036C231.167 140.509 232.361 141.703 233.834 141.703C235.307 141.703 236.501 140.509 236.501 139.036C236.501 137.563 235.307 136.369 233.834 136.369C232.361 136.369 231.167 137.563 231.167 139.036ZM177.746 139.036V139.536H233.834V139.036V138.536H177.746V139.036Z"
                fill="#0F5C4C"
              />
              <path
                d="M31.8959 139.036C31.8959 137.563 30.702 136.369 29.2292 136.369C27.7565 136.369 26.5626 137.563 26.5626 139.036C26.5626 140.509 27.7565 141.703 29.2292 141.703C30.702 141.703 31.8959 140.509 31.8959 139.036ZM82.9479 139.036L82.9479 138.536L29.2292 138.536L29.2292 139.036L29.2292 139.536L82.9479 139.536L82.9479 139.036Z"
                fill="#0F5C4C"
              />
              <path
                d="M194.954 69.9492C196.065 70.9161 197.75 70.7994 198.716 69.6885C199.683 68.5776 199.567 66.8932 198.456 65.9263C197.345 64.9594 195.66 65.0761 194.694 66.187C193.727 67.2979 193.843 68.9823 194.954 69.9492ZM159.576 110.597L159.953 110.925L197.082 68.266L196.705 67.9378L196.328 67.6095L159.199 110.268L159.576 110.597Z"
                fill="#0F5C4C"
              />
              <path
                d="M57.629 61.4247C58.8312 60.5739 59.116 58.9097 58.2653 57.7075C57.4145 56.5054 55.7503 56.2205 54.5481 57.0713C53.3459 57.922 53.061 59.5863 53.9118 60.7884C54.7626 61.9906 56.4268 62.2755 57.629 61.4247ZM92.4276 110.597L92.8357 110.308L56.4967 58.9591L56.0885 59.248L55.6804 59.5368L92.0195 110.886L92.4276 110.597Z"
                fill="#0F5C4C"
              />
              <path
                d="M61.4895 210.268C60.2538 209.466 58.6025 209.818 57.8011 211.054C56.9998 212.29 57.3519 213.941 58.5876 214.742C59.8232 215.544 61.4745 215.192 62.2759 213.956C63.0772 212.72 62.7251 211.069 61.4895 210.268ZM84.1169 175.376L83.6974 175.104L59.619 212.233L60.0385 212.505L60.458 212.777L84.5364 175.648L84.1169 175.376Z"
                fill="#0F5C4C"
              />
              <path
                d="M199.913 210.323C198.707 211.169 198.416 212.832 199.262 214.037C200.109 215.243 201.772 215.534 202.977 214.687C204.183 213.841 204.474 212.178 203.627 210.973C202.781 209.767 201.118 209.476 199.913 210.323ZM175.376 175.376L174.966 175.663L201.036 212.792L201.445 212.505L201.854 212.218L175.785 175.089L175.376 175.376Z"
                fill="#0F5C4C"
              />
              <circle
                cx="133.255"
                cy="18.4213"
                r="17.4213"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="133.388"
                cy="263.734"
                r="16.2605"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="206.304"
                cy="56.2078"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="55.4177"
                cy="45.1482"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="53.8378"
                cy="225.263"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="211.044"
                cy="223.683"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="248.173"
                cy="137.638"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
              <circle
                cx="15.1287"
                cy="137.638"
                r="14.1287"
                stroke="#0F5C4C"
                strokeWidth="2"
              />
            </svg>
          </Box>
        </Box>

        {/* Right side: Text content */}
        <Box sx={{ maxWidth: 500 }}>
          {/* Error state */}
          {error ? (
            <>
              <Typography
                variant="h3"
                sx={{ fontWeight: 700, mb: 1, color: "error.main" }}
              >
                Something went wrong
              </Typography>
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                Please create a new workspace to try again.
              </Typography>
            </>
          ) : (
            <>
              <Typography variant="h3" sx={{ fontWeight: 700, mb: 1 }}>
                {title}
              </Typography>
              <Typography variant="h6" sx={{ color: "text.secondary", mb: 3 }}>
                {subtitle}
              </Typography>

              {/* Phase indicator (unified mode) */}
              {phaseDisplayName && (
                <Typography
                  variant="body2"
                  sx={{ color: "text.secondary", mb: 1 }}
                >
                  {phaseDisplayName}
                </Typography>
              )}

              {/* Progress bar */}
              <Box sx={{ mb: 3 }}>
                <Box
                  sx={{
                    position: "relative",
                    height: 24,
                    bgcolor: "action.hover",
                    borderRadius: 0.5,
                    overflow: "hidden",
                  }}
                >
                  <Box
                    sx={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: `${progressPercent}%`,
                      bgcolor: "primary.main",
                      transition: "width 0.2s ease-out",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ color: "primary.contrastText", fontWeight: 600 }}
                    >
                      {progressPercent}%
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Task list (unified mode) */}
              {progressState && progressState.tasks.length > 0 ? (
                <TaskList tasks={progressState.tasks} isComplete={isComplete} />
              ) : displayEntities.length > 0 ? (
                /* Legacy entity loading indicators */
                <Box sx={{ mb: 4, minHeight: 28 }}>
                  {isComplete ? (
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 2,
                        flexWrap: "wrap",
                      }}
                    >
                      {displayEntities.map((entity, index) => (
                        <Box
                          key={entity.id}
                          sx={{ display: "flex", alignItems: "center", gap: 2 }}
                        >
                          <Typography
                            variant="body2"
                            sx={{ color: "text.primary", fontWeight: 500 }}
                          >
                            {entity.name}
                          </Typography>
                          {index < displayEntities.length - 1 && (
                            <Box
                              sx={{ width: 24, height: 1, bgcolor: "divider" }}
                            />
                          )}
                        </Box>
                      ))}
                    </Box>
                  ) : (
                    <Fade in={true} timeout={600} key={visibleStartIndex}>
                      <Box>
                        {visibleEntities.map((entity) => (
                          <Typography
                            key={`${entity.id}-${visibleStartIndex}`}
                            variant="body2"
                            sx={{ color: "text.secondary", fontWeight: 400 }}
                          >
                            {entity.name}
                          </Typography>
                        ))}
                      </Box>
                    </Fade>
                  )}
                </Box>
              ) : (
                <Box sx={{ mb: 4 }}>
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    {mode === "team_building"
                      ? "Configuring agents..."
                      : "Loading entities..."}
                  </Typography>
                </Box>
              )}

              {/* Latest status message (unified mode) */}
              {progressState &&
                progressState.messages.length > 0 &&
                !isComplete && (
                  <Typography
                    variant="body2"
                    sx={{ color: "text.secondary", fontStyle: "italic", mb: 2 }}
                  >
                    {progressState.messages[progressState.messages.length - 1]}
                  </Typography>
                )}

              {/* <Typography variant="body2" sx={{ color: "text.secondary" }}>
                You can close this window, we'll notify you when ready.
              </Typography> */}
            </>
          )}
        </Box>
      </Box>

      {/* Footer */}
      <SetupFooter
        currentStep={currentStep}
        totalSteps={totalSteps}
        onContinue={onContinue}
        buttonDisabled={!isComplete}
      />
    </Box>
  );
}
