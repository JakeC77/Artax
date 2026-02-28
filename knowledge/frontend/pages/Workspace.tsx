import { useMemo, useState, useCallback } from "react";
import { alpha, useTheme } from "@mui/material/styles";
import Button from "../components/common/Button";
import { Box, Tab, Tabs, Typography, Button as MUIButton } from "@mui/material";
import { View } from "@carbon/icons-react";
import ScratchpadView from "../components/ScratchpadView";
import IntentViewerModal from "../components/workspace/IntentViewerModal";

import WorkspaceSetupFlow from "../components/workspace/WorkspaceSetupFlow";
import EmptyCanvas from "../components/workspace/EmptyCanvas";
import EntitiesView from "../components/workspace/EntitiesView";
import RelationsView from "../components/workspace/RelationsView";
import TeamsView from "../components/workspace/TeamsView";
import ChatDock from "../components/workspace/ChatDock";
import { AnalysisGeneratingView } from "../components/workspace/analysis";
import ReportPreviewView from "../components/reports/ReportPreviewView";
import { cancelAnalysisWorkflow } from "../services/graphql";

import { useWorkspace } from "../contexts/WorkspaceContext";

type TabKey = "canvas" | "entities" | "relationships" | "scratchpad" | "teams";

export default function Workspace() {
  const theme = useTheme();
  const {
    currentWorkspace,
    setCurrentWorkspace,
    chatOpen,
    setChatOpen,
    workspaceState,
    setWorkspaceState,
  } = useWorkspace();
  const [tab, setTab] = useState<TabKey>("canvas");
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [intentModalOpen, setIntentModalOpen] = useState(false);
  const intentPackage = currentWorkspace?.setupIntentPackage || null;

  const tabs: TabKey[] = [
    "canvas",
    "entities",
    "relationships",
    "scratchpad",
    "teams",
  ];
  const tabIndex = useMemo(() => tabs.indexOf(tab), [tab]);

  // Handle analysis workflow completion
  const handleAnalysisComplete = useCallback(() => {
    // Clear the analysisRunId from workspace
    if (currentWorkspace) {
      setCurrentWorkspace({
        ...currentWorkspace,
        analysisRunId: null,
      });
    }
  }, [currentWorkspace, setCurrentWorkspace]);

  // Handle analysis workflow cancellation
  const handleAnalysisCancel = useCallback(async () => {
    if (currentWorkspace?.analysisRunId) {
      try {
        await cancelAnalysisWorkflow(currentWorkspace.analysisRunId);
      } catch (e) {
        console.error("[Workspace] Failed to cancel analysis workflow:", e);
      }
      // Clear the analysisRunId from workspace
      setCurrentWorkspace({
        ...currentWorkspace,
        analysisRunId: null,
      });
    }
  }, [currentWorkspace, setCurrentWorkspace]);

  const renderView = () => {
    switch (tab) {
      case "entities":
        return <EntitiesView workspaceId={currentWorkspace?.workspaceId} />;
      case "scratchpad":
        return <ScratchpadView workspaceId={currentWorkspace?.workspaceId} />;
      case "relationships":
        return <RelationsView workspaceId={currentWorkspace?.workspaceId} />;
      case "teams":
        return <TeamsView workspaceId={currentWorkspace?.workspaceId} />;
      default:
        // Show analysis generating view if workflow is running
        if (currentWorkspace?.analysisRunId) {
          return (
            <AnalysisGeneratingView
              runId={currentWorkspace.analysisRunId}
              onComplete={handleAnalysisComplete}
              onCancel={handleAnalysisCancel}
            />
          );
        }
        // Show report preview if a report is active
        if (activeReportId) {
          return (
            <Box>
              <Box sx={{ mb: 2 }}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setActiveReportId(null)}
                >
                  ← Back to Canvas
                </Button>
              </Box>
              <ReportPreviewView reportId={activeReportId} />
            </Box>
          );
        }
        // Show empty canvas with drag-drop functionality
        return (
          <EmptyCanvas
            workspaceId={currentWorkspace?.workspaceId || ""}
            onActivate={(reportId) => setActiveReportId(reportId)}
            workflowInProgress={!!currentWorkspace?.analysisRunId}
          />
        );
    }
  };

  // If in setup or draft mode, show the setup flow
  if (workspaceState === "setup" || workspaceState === "draft") {
    return (
      <Box sx={{ height: "100vh", overflow: "hidden" }}>
        <WorkspaceSetupFlow
          onComplete={() => {
            // Transition to working state when setup is complete
            setWorkspaceState("working");
          }}
        />
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", position: "relative" }}>
      <Box
        sx={{
          flexGrow: 1,
          mr: { xs: 0, sm: chatOpen ? "26vw" : 0, md: chatOpen ? "26vw" : 0 },
          transition: theme.transitions.create("margin", {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          px: 2,
          py: 2,
          minWidth: 0,
        }}
      >
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {currentWorkspace?.name || "Q4 Formulary Review - Diabetes Drugs"}
            </Typography>

            <Box sx={{ flex: 1 }} />
            {(intentPackage || currentWorkspace?.intent?.trim()) && (
              <MUIButton
                variant="text"
                size="small"
                startIcon={<View size={16} />}
                onClick={() => setIntentModalOpen(true)}
                sx={{
                  textTransform: "none",
                  color: "text.secondary",
                  minWidth: "auto",
                  px: 1,
                  "&:hover": {
                    color: "primary.main",
                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                  },
                }}
              >
                View Intent
              </MUIButton>
            )}
          </Box>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Box
            sx={(t) => ({
              display: "inline-flex", // container shrinks to the tabs width
              bgcolor:
                t.palette.mode === "light"
                  ? alpha(t.palette.primary.main, 0.2) // soft green bar
                  : alpha(t.palette.primary.main, 0.25),
              borderRadius: 0.5,
              p: 0.75,
            })}
          >
            <Tabs
              value={tabIndex}
              onChange={(_, i) => setTab(tabs[i] ?? "canvas")}
              TabIndicatorProps={{ style: { display: "none" } }}
              variant="standard"
              sx={{
                minHeight: 0,
                "& .MuiTabs-flexContainer": {
                  gap: 0.5,
                },
              }}
            >
              {["Canvas", "Data", "Relationships", "Scratchpad", "Team"].map(
                (label, i) => {
                  const selected = tabIndex === i;
                  return (
                    <Tab
                      key={label}
                      label={label}
                      disableRipple
                      sx={{
                        textTransform: "none",
                        minHeight: 0,
                        px: 1.5,
                        borderRadius: 0.5,
                        fontWeight: selected ? 600 : 500,
                        fontSize: 14,
                        color: selected
                          ? theme.palette.primary.main // green text for active tab
                          : theme.palette.text.secondary, // gray text for inactive tabs
                        bgcolor: selected
                          ? theme.palette.background.default // white pill for active tab
                          : "transparent",
                        "&:hover": {
                          bgcolor: selected
                            ? theme.palette.background.default
                            : alpha(theme.palette.common.white, 0.3),
                        },
                        "&:focus, &:focus-visible": {
                          outline: "none", // remove browser focus outline
                          boxShadow: "none", // in case something else adds a shadow
                        },
                      }}
                    />
                  );
                },
              )}
            </Tabs>
          </Box>
        </Box>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr)",
            gap: 2,
          }}
        >
          <Box>{renderView()}</Box>
        </Box>
      </Box>

      <IntentViewerModal
        open={intentModalOpen}
        onClose={() => setIntentModalOpen(false)}
        intentPackage={intentPackage}
        legacyIntent={currentWorkspace?.intent?.trim()}
      />

      <ChatDock
        key="chat-main"
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        workspaceId={currentWorkspace?.workspaceId}
        onSubmit={() => {
          // Chat submissions don't automatically activate canvas anymore
          // Reports will be created and can be dragged onto canvas
        }}
      />
    </Box>
  );
}
