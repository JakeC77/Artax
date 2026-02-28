/**
 * DataScopingView Component
 *
 * Unified view for data scoping that merges the previous Scoping and Review stages.
 * Primary view is card-based entities; graph is secondary (View Relationships toggle).
 *
 * Key Principles:
 * - UI expresses intent → Chat carries the message → AI executes
 * - All filter/entity modifications flow through chat
 * - Cards are the primary view; Graph is read-only visualization toggle
 * - Tab toggle is instant (no page reload)
 */

import { useState, useCallback, useMemo, useEffect } from "react";
import {
  Box,
  Typography,
  Button,
  Stack,
  CircularProgress,
  Fade,
  ToggleButtonGroup,
  ToggleButton,
  Alert,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import VisibilityIcon from "@mui/icons-material/Visibility";
import ViewModuleIcon from "@mui/icons-material/ViewModule";
import AccountTreeIcon from "@mui/icons-material/AccountTree";

import ChatDock from "../../ChatDock";
import IntentViewerModal from "../../IntentViewerModal";
import SetupFooter from "../SetupFooter";
import ForceDirectedGraph from "./ForceDirectedGraph";
import EntityCard, { type EntityUpdate } from "./EntityCard";
import AddEntityCard from "./AddEntityCard";
import EntityPreviewView, { type StagedRowsContext } from "./EntityPreviewView";

import type { ScopeState, ScopeEntity } from "../../../../types/scopeState";
import type { IntentPackage } from "../../../../services/graphql";
import type {
  ClarificationQuestion,
  ClarificationAnswer,
} from "../../chat/ClarificationPanel";

// ============================================================================
// Types
// ============================================================================

type ViewMode = "cards" | "relationships";

export interface DataScopingViewProps {
  workspaceId: string;
  workspaceName?: string;
  scopeState: ScopeState | null;
  isScopeReady: boolean;
  onStageData: () => void;
  currentStep?: number;
  totalSteps?: number;
  // Chat props - parent provides messages, ChatDock displays them
  setupRunId?: string;
  onChatSubmit: (message: string) => void;
  chatDisabled?: boolean;
  // Messages from parent's useChatStream (required for isSetupMode)
  messages?: Array<{ id: string; role: "user" | "assistant" | "feedback" | "feedback_received"; content: string; timestamp: number; isComplete?: boolean }>;
  isAgentWorking?: boolean;
  // Clarification props
  pendingClarifications?: ClarificationQuestion[];
  onClarificationSubmit?: (answers: ClarificationAnswer[]) => void;
  // Intent props
  intentPackage?: IntentPackage | null;
  // Available entities from schema (for Add Entity modal)
  availableEntities?: string[];
  // Callbacks for scope changes via chat
  onEntityToggle?: (entityType: string, enabled: boolean) => void;
  // Entity update notifications (from SSE events)
  entityUpdates?: Record<string, EntityUpdate>;
  // Error state - if set, display error instead of loading
  workflowError?: string | null;
  // Retry callback
  onRetry?: () => void;
}

// ============================================================================
// Loading Messages
// ============================================================================

const LOADING_MESSAGES = [
  "Traversing the knowledge graph...",
  "Mapping intent to data entities...",
  "Analyzing relationship patterns...",
  "Identifying relevant data scopes...",
  "Evaluating entity connections...",
  "Building scope recommendations...",
];

// ============================================================================
// Main Component
// ============================================================================

export default function DataScopingView({
  workspaceId,
  workspaceName,
  scopeState,
  isScopeReady,
  onStageData,
  currentStep = 2,
  totalSteps = 3,
  // Chat props
  setupRunId,
  onChatSubmit,
  chatDisabled = false,
  messages = [],
  isAgentWorking = false,
  // Clarification props
  pendingClarifications = [],
  onClarificationSubmit,
  // Intent props
  intentPackage,
  // Available entities
  availableEntities = [],
  // Callbacks
  onEntityToggle,
  // Entity updates
  entityUpdates = {},
  // Error state
  workflowError,
  onRetry,
}: DataScopingViewProps) {
  const theme = useTheme();

  // UI State
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [intentModalOpen, setIntentModalOpen] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [previewEntity, setPreviewEntity] = useState<ScopeEntity | null>(null);
  const [stagedRowsContext, setStagedRowsContext] = useState<StagedRowsContext | null>(null);

  // Check for reduced motion preference
  const prefersReducedMotion = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  // Cycle loading messages
  useEffect(() => {
    if (scopeState?.entities && scopeState.entities.length > 0) return;
    if (prefersReducedMotion) return; // Don't animate if user prefers reduced motion

    const interval = setInterval(() => {
      setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [scopeState?.entities, prefersReducedMotion]);

  // Stats for display
  const stats = useMemo(() => {
    if (!scopeState)
      return {
        entities: 0,
        filters: 0,
        relationships: 0,
        confidence: "low" as const,
      };

    const enabledEntities = scopeState.entities.filter((e) => e.enabled);
    const totalFilters = enabledEntities.reduce(
      (sum, e) => sum + e.filters.length,
      0,
    );

    return {
      entities: enabledEntities.length,
      filters: totalFilters,
      relationships: scopeState.relationships.length,
      confidence: scopeState.confidence,
    };
  }, [scopeState]);

  // Confidence color
  const confidenceColor = useMemo(() => {
    switch (stats.confidence) {
      case "high":
        return theme.palette.success.main;
      case "medium":
        return theme.palette.warning.main;
      case "low":
        return theme.palette.error.main;
      default:
        return theme.palette.grey[500];
    }
  }, [stats.confidence, theme]);

  // Get connection info for an entity based on relationships
  const getConnectionInfo = useCallback(
    (entity: ScopeEntity): string | undefined => {
      if (entity.relevance_level === "primary" || !scopeState) return undefined;

      // Find a relationship that connects to this entity
      const relationship = scopeState.relationships.find(
        (r) =>
          r.to_entity === entity.entity_type ||
          r.from_entity === entity.entity_type,
      );
      if (!relationship) return undefined;

      const otherEntity =
        relationship.to_entity === entity.entity_type
          ? relationship.from_entity
          : relationship.to_entity;

      return `Connected via ${otherEntity}`;
    },
    [scopeState],
  );

  // Handlers
  const handleViewModeChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, newMode: ViewMode | null) => {
      if (newMode) setViewMode(newMode);
    },
    [],
  );


  // Handle batched changes from EntityCard edit mode
  const handleEntityChanges = useCallback(
    (chatMessage: string) => {
      onChatSubmit(chatMessage);
      // If it's a removal, also toggle the entity off
      if (
        chatMessage.startsWith("Remove ") &&
        chatMessage.includes(" from the scope")
      ) {
        const entityMatch = chatMessage.match(/^Remove (\w+) from the scope/);
        if (entityMatch && entityMatch[1]) {
          onEntityToggle?.(entityMatch[1], false);
        }
      }
    },
    [onChatSubmit, onEntityToggle],
  );

  // Handle preview mode
  const handlePreview = useCallback((entity: ScopeEntity) => {
    setPreviewEntity(entity);
  }, []);

  const handlePreviewBack = useCallback(() => {
    setPreviewEntity(null);
    setStagedRowsContext(null); // Clear staged rows when leaving preview
  }, []);

  // Sorted entities: primary first, then related, then contextual
  const sortedEntities = useMemo(() => {
    if (!scopeState) return [];
    const order = { primary: 0, related: 1, contextual: 2 };
    return [...scopeState.entities]
      .filter((e) => e.enabled)
      .sort((a, b) => order[a.relevance_level] - order[b.relevance_level]);
  }, [scopeState]);

  // Check if we're in loading state (no entities yet and no error)
  const isLoading = !workflowError && (!scopeState || scopeState.entities.length === 0);

  return (
    <Box sx={{ display: "flex", position: "relative", height: "100%" }}>
      {/* Main content area */}
      <Box
        sx={{
          flexGrow: 1,
          mr: { xs: 0, sm: "26vw", md: "26vw" },
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header - hidden in preview mode */}
        {!previewEntity && (
          <Box sx={{ px: 4, py: 3, flexShrink: 0 }}>
            {/* Workspace title */}
            {workspaceName && (
              <Typography variant="h4" sx={{ fontWeight: 600, mb: 2 }}>
                {workspaceName}
              </Typography>
            )}

            {/* Title row */}
            <Stack
              direction="row"
              alignItems="flex-start"
              justifyContent="space-between"
              sx={{ mb: 2 }}
            >
              <Box>
                <Typography variant="h5" sx={{ fontWeight: 600 }}>
                  Recommended Scoping
                </Typography>
                {/* {scopeState && (
                  <Typography variant="body2" sx={{ color: 'primary.main', mt: 0.5 }}>
                    {stats.entities} entities for {intentPackage?.title || 'Analysis'}
                  </Typography>
                )} */}
              </Box>

              <Stack direction="row" spacing={1} alignItems="center">
                {intentPackage && (
                  <Button
                    variant="text"
                    size="small"
                    startIcon={<VisibilityIcon sx={{ fontSize: 16 }} />}
                    onClick={() => setIntentModalOpen(true)}
                    sx={{ textTransform: "none", color: "text.secondary" }}
                  >
                    View Intent
                  </Button>
                )}
              </Stack>
            </Stack>

            {/* Stats bar and view toggle */}
            {scopeState && scopeState.entities.length > 0 && (
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
              >
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    {stats.entities} entities
                  </Typography>
                  <Typography variant="body2" sx={{ color: "text.disabled" }}>
                    |
                  </Typography>
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    {stats.relationships} relationships
                  </Typography>
                  <Typography variant="body2" sx={{ color: "text.disabled" }}>
                    |
                  </Typography>
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    Confidence:{" "}
                    <span style={{ color: confidenceColor, fontWeight: 600 }}>
                      {stats.confidence.toUpperCase()}
                    </span>
                  </Typography>
                </Stack>

                <Stack direction="row" spacing={1} alignItems="center">
                  <ToggleButtonGroup
                    value={viewMode}
                    exclusive
                    onChange={handleViewModeChange}
                    size="small"
                    aria-label="View mode"
                    sx={{
                      "& .MuiToggleButton-root": {
                        px: 1.5,
                        py: 0.5,
                        textTransform: "none",
                        fontSize: "0.8rem",
                      },
                    }}
                  >
                    <ToggleButton value="cards" aria-label="Cards view">
                      <ViewModuleIcon
                        sx={{ fontSize: 16, mr: 0.5 }}
                        aria-hidden="true"
                      />
                      Cards
                    </ToggleButton>
                    <ToggleButton
                      value="relationships"
                      aria-label="View relationships"
                    >
                      <AccountTreeIcon
                        sx={{ fontSize: 16, mr: 0.5 }}
                        aria-hidden="true"
                      />
                      View Relationships
                    </ToggleButton>
                  </ToggleButtonGroup>

                </Stack>
              </Stack>
            )}
          </Box>
        )}

        {/* Content area */}
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflow: "auto",
            px: previewEntity ? 0 : 4,
            pb: previewEntity ? 0 : "100px",
          }}
        >
          {previewEntity ? (
            /* Preview mode - full screen entity data */
            <EntityPreviewView
              entity={previewEntity}
              onBack={handlePreviewBack}
              onSelectionChange={setStagedRowsContext}
            />
          ) : workflowError ? (
            /* Error state */
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                py: 8,
                gap: 3,
              }}
            >
              <Alert
                severity="error"
                sx={{
                  maxWidth: 500,
                  width: "100%",
                }}
                action={
                  onRetry && (
                    <Button color="inherit" size="small" onClick={onRetry}>
                      Retry
                    </Button>
                  )
                }
              >
                {workflowError}
              </Alert>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                The data scoping workflow encountered an error. You can try again or contact support if the issue persists.
              </Typography>
            </Box>
          ) : isLoading ? (
            /* Loading state */
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                py: 8,
                gap: 3,
              }}
            >
              <Box sx={{ position: "relative" }}>
                <CircularProgress
                  size={48}
                  thickness={2}
                  sx={{ color: alpha(theme.palette.primary.main, 0.2) }}
                />
                <CircularProgress
                  size={48}
                  thickness={2}
                  sx={{
                    color: "primary.main",
                    position: "absolute",
                    left: 0,
                    animationDuration: "1.5s",
                  }}
                  variant="indeterminate"
                />
              </Box>

              <Box
                sx={{
                  height: 48,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 1,
                }}
              >
                <Fade
                  in
                  key={loadingMessageIndex}
                  timeout={prefersReducedMotion ? 0 : 500}
                >
                  <Typography
                    variant="body1"
                    sx={{ color: "text.primary", fontWeight: 500 }}
                  >
                    {LOADING_MESSAGES[loadingMessageIndex]}
                  </Typography>
                </Fade>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Theo is analyzing your workspace intent
                </Typography>
              </Box>

              <Box sx={{ display: "flex", gap: 0.75 }} aria-hidden="true">
                {LOADING_MESSAGES.map((_, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor:
                        idx === loadingMessageIndex
                          ? "primary.main"
                          : alpha(theme.palette.primary.main, 0.2),
                      transition: prefersReducedMotion
                        ? "none"
                        : "background-color 0.3s ease",
                    }}
                  />
                ))}
              </Box>
            </Box>
          ) : viewMode === "cards" ? (
            /* Cards view (primary) */
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {sortedEntities.map((entity) => (
                <EntityCard
                  key={entity.entity_type}
                  entity={entity}
                  scopeState={scopeState}
                  connectionInfo={getConnectionInfo(entity)}
                  onSubmitChanges={handleEntityChanges}
                  onPreview={() => handlePreview(entity)}
                  actualCount={scopeState?.counts[entity.entity_type]}
                  lastUpdate={entityUpdates[entity.entity_type] || null}
                />
              ))}

              {/* Add Entity Card */}
              <AddEntityCard
                scopeState={scopeState}
                availableEntities={availableEntities}
                onSubmit={onChatSubmit}
                disabled={availableEntities.length === 0}
              />
            </Box>
          ) : (
            /* Relationships view (secondary) - Graph visualization */
            <ForceDirectedGraph
              scopeState={scopeState}
              onEntityClick={() => {}} // Read-only, just visualization
              height={680}
            />
          )}
        </Box>

        {/* Footer - hidden in preview mode */}
        {!previewEntity && (
          <SetupFooter
            currentStep={currentStep}
            totalSteps={totalSteps}
            onContinue={onStageData}
            buttonText="Continue"
            buttonDisabled={
              !isScopeReady || !scopeState || scopeState.entities.length === 0
            }
          />
        )}
      </Box>

      {/* Chat Dock (right side) */}
      <ChatDock
        workspaceId={workspaceId}
        setupRunId={setupRunId}
        open={true}
        onClose={() => {}} // No-op in setup mode - always visible
        onSubmit={onChatSubmit}
        fullScreen={false}
        isSetupMode
        inputDisabled={chatDisabled}
        initialMessages={messages}
        initialIsAgentWorking={isAgentWorking}
        externalClarifications={pendingClarifications}
        onExternalClarificationSubmit={onClarificationSubmit}
        stagedRowsContext={stagedRowsContext}
        onClearStagedRows={() => setStagedRowsContext(null)}
      />

      {/* Intent Viewer Modal (keeping this one - it's read-only viewing) */}
      <IntentViewerModal
        open={intentModalOpen}
        onClose={() => setIntentModalOpen(false)}
        intentPackage={intentPackage ?? null}
      />
    </Box>
  );
}
