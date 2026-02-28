import { useState, useEffect, useRef, useCallback } from "react";
import { Box, Typography, TextField, IconButton, Alert } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { Edit } from "@carbon/icons-react";
import ChatDock from "../../ChatDock";
import { type ChatMessage } from "../../chat/ChatMessages";
import SetupFooter from "../SetupFooter";
import StructuredIntentEditor, {
  type StructuredIntentEditorRef,
} from "../../../tiptap/StructuredIntentEditor";
import {
  confirmIntentAndStartDataScoping,
  fetchWorkspaceById,
  type IntentPackage,
} from "../../../../services/graphql";
import { useWorkspace } from "../../../../contexts/WorkspaceContext";
import type { IntentField } from "../../../../utils/intentEditorUtils";
import type { UserEditableField } from "../../../../contexts/IntentContext";

export type DraftViewProps = {
  intent: string;
  intentPackage?: IntentPackage | null;
  workspaceId: string;
  workspaceName?: string;
  onTitleChange?: (newTitle: string) => void;
  // Chat messages passed from parent (same stream as interview)
  messages: ChatMessage[];
  isAgentWorking: boolean;
  // Chat input state controlled by parent
  chatValue: string;
  onChatValueChange: (value: string) => void;
  onChatSend: (message?: string) => void;
  chatSending: boolean;
  chatDisabled?: boolean;
  onContinue: () => void;
  currentStep?: number;
  totalSteps?: number;
  // NEW: Callback to register intent package getter for bidirectional sync
  onRegisterIntentPackageGetter?: (
    getter: (() => IntentPackage | null) | null,
  ) => void;
  // NEW: Recently updated fields from AI (for visual indicators)
  recentlyUpdatedFields?: IntentField[];
  // NEW: Callback when user edits fields (for tracking user_edited_fields)
  onFieldsEdited?: (fields: UserEditableField[]) => void;
};

// Create a default empty IntentPackage for when none is provided
const createDefaultIntentPackage = (): IntentPackage => ({
  schema_version: 1,
  title: "",
  summary: "",
  mission: {
    objective: "",
    why: "",
    success_looks_like: "",
  },
  team_guidance: {},
  confirmed: false,
});

export default function DraftView({
  intent,
  intentPackage,
  workspaceId,
  workspaceName,
  onTitleChange,
  messages,
  isAgentWorking,
  chatValue,
  onChatValueChange,
  onChatSend,
  chatSending,
  chatDisabled = false,
  onContinue,
  currentStep = 1,
  totalSteps = 4,
  onRegisterIntentPackageGetter,
  recentlyUpdatedFields = [],
  onFieldsEdited,
}: DraftViewProps) {
  const theme = useTheme();
  const { setCurrentWorkspace } = useWorkspace();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Props not used directly but kept for compatibility
  void intent; // Fallback for old workspaces - not needed with structured editor
  void chatValue;
  void onChatValueChange;
  void chatSending;

  // Local intent package state - initialized from prop
  const [localIntentPackage, setLocalIntentPackage] =
    useState<IntentPackage | null>(intentPackage || null);

  // Intent is ready if we have an intentPackage
  const [isIntentReady, setIsIntentReady] = useState(!!intentPackage);

  // Title editing state
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editableTitle, setEditableTitle] = useState(
    intentPackage?.title || workspaceName || "",
  );

  // Ref to structured editor
  const editorRef = useRef<StructuredIntentEditorRef>(null);

  // Get current intent package (merges editor content with metadata)
  const getCurrentIntentPackage = useCallback((): IntentPackage | null => {
    if (editorRef.current) {
      return editorRef.current.getIntentPackage();
    }
    return localIntentPackage;
  }, [localIntentPackage]);

  // Register the intent package getter with parent (for bidirectional sync)
  useEffect(() => {
    if (onRegisterIntentPackageGetter) {
      onRegisterIntentPackageGetter(getCurrentIntentPackage);
    }
    // Cleanup: unregister on unmount
    return () => {
      if (onRegisterIntentPackageGetter) {
        onRegisterIntentPackageGetter(null);
      }
    };
  }, [getCurrentIntentPackage, onRegisterIntentPackageGetter]);

  // Sync intent package from prop when it changes (e.g., AI updates)
  useEffect(() => {
    if (intentPackage) {
      setLocalIntentPackage(intentPackage);
      setIsIntentReady(true);
    }
  }, [intentPackage]);

  // Sync title when intentPackage arrives
  useEffect(() => {
    if (intentPackage?.title) {
      setEditableTitle(intentPackage.title);
    }
  }, [intentPackage?.title]);

  // Handle title save
  const handleTitleSave = () => {
    setIsEditingTitle(false);
    if (editableTitle.trim() && onTitleChange) {
      onTitleChange(editableTitle.trim());
    }
  };

  // Handle editor content changes
  const handleEditorChange = useCallback((pkg: IntentPackage) => {
    setLocalIntentPackage(pkg);
  }, []);

  // Handle continue - persist to setupIntentPackage and transition
  const handleContinue = async () => {
    const finalPackage = getCurrentIntentPackage();

    if (!finalPackage) {
      setSaveError(
        "No intent to save. Please wait for Theo to draft your mission.",
      );
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);

      // Mark as confirmed
      const confirmedPackage: IntentPackage = {
        ...finalPackage,
        confirmed: true,
      };

      // Persist to setupIntentPackage via the stage transition mutation
      // This saves the package AND transitions to data_scoping stage
      await confirmIntentAndStartDataScoping(workspaceId, confirmedPackage);

      // Reload workspace to get updated data
      const updatedWorkspace = await fetchWorkspaceById(workspaceId);
      if (updatedWorkspace) {
        setCurrentWorkspace(updatedWorkspace);
      }

      // Call parent's onContinue to handle phase transition
      onContinue();
    } catch (error) {
      console.error("Failed to save intent before continuing:", error);
      setSaveError("Failed to save intent. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  // Ensure we have a valid package for the editor
  const editorPackage = localIntentPackage || createDefaultIntentPackage();

  return (
    <Box sx={{ display: "flex", position: "relative", height: "100%" }}>
      {/* Main content - with dynamic right margin like Workspace */}
      <Box
        sx={{
          flexGrow: 1,
          mr: { xs: 0, sm: "26vw", md: "26vw" },
          transition: theme.transitions.create("margin", {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          px: 4,
          py: 3,
          pb: "90px",
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <Box sx={{ mb: 2, flexShrink: 0 }}>
          {/* Editable workspace title */}
          {isEditingTitle ? (
            <TextField
              value={editableTitle}
              onChange={(e) => setEditableTitle(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTitleSave();
                if (e.key === "Escape") {
                  setIsEditingTitle(false);
                  setEditableTitle(intentPackage?.title || workspaceName || "");
                }
              }}
              autoFocus
              fullWidth
              variant="standard"
              sx={{ mb: 1 }}
              InputProps={{
                sx: { fontSize: "1.5rem", fontWeight: 600 },
              }}
            />
          ) : (
            <Box
              onClick={() => setIsEditingTitle(true)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                cursor: "pointer",
                mb: 1,
                "&:hover .edit-icon": { opacity: 1 },
              }}
            >
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {editableTitle || intentPackage?.title || "Untitled Workspace"}
              </Typography>
              <IconButton
                size="small"
                className="edit-icon"
                sx={{ opacity: 0, transition: "opacity 0.2s" }}
              >
                <Edit size={32} />
              </IconButton>
            </Box>
          )}

          <Typography variant="h6" sx={{ fontWeight: 500, mb: 0.5 }}>
            Review Your Mission
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            Review and edit the workspace mission that Theo has drafted for you.
            Section headers are fixed; edit the content within each section.
          </Typography>
        </Box>

        {/* Structured Intent Editor */}
        <Box
          sx={{
            flex: 1,
            overflow: "auto",
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            mb: 2,
          }}
        >
          {localIntentPackage ? (
            <StructuredIntentEditor
              ref={editorRef}
              intentPackage={editorPackage}
              onChange={handleEditorChange}
              recentlyUpdatedFields={recentlyUpdatedFields}
              editable={true}
              height="100%"
              onFieldsEdited={onFieldsEdited}
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              Waiting for Theo to create your workspace intent...
            </Typography>
          )}
        </Box>

        {/* Error alert for save failures */}
        {saveError && (
          <Alert
            severity="error"
            onClose={() => setSaveError(null)}
            sx={{ mt: 2 }}
          >
            {saveError}
          </Alert>
        )}
      </Box>

      {/* ChatDock - same as Workspace, always open in setup */}
      <ChatDock
        open={true}
        fullScreen={false}
        isSetupMode={true}
        onClose={() => {}}
        onSubmit={onChatSend}
        workspaceId={workspaceId}
        initialMessages={messages}
        initialIsAgentWorking={isAgentWorking}
        inputDisabled={chatDisabled || chatSending}
      />

      {/* Footer with progress bar and Continue button */}
      <Box
        sx={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: { xs: 0, sm: "25vw", md: "25vw" },
          flexShrink: 0,
        }}
      >
        <SetupFooter
          currentStep={currentStep}
          totalSteps={totalSteps}
          onContinue={handleContinue}
          buttonText={saving ? "Saving..." : "Continue to Data Scoping"}
          buttonDisabled={saving || !isIntentReady}
        />
      </Box>
    </Box>
  );
}
