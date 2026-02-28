import { useCallback, useState, useEffect, useRef, useMemo } from "react";
import { Box, Alert, Button as MuiButton } from "@mui/material";
import IntroView from "./setup/intent/IntroView";
import InterviewView from "./setup/intent/InterviewView";
import DraftView from "./setup/intent/DraftView";
import DataScopingView from "./setup/scoping/DataScopingView";
import LoadingView, { aiTeamLoadingEntities } from "./setup/team/LoadingView";
import AiTeamViewAnimated from "./AiTeamViewAnimated";
import AiTeamView from "./AiTeamView";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import {
  getTenantId,
  appendScenarioRunLog,
  updateWorkspace,
  type SetupStage,
  type IntentPackage,
  type DataScope,
  type ExecutionResult,
  type TeamConfig,
} from "../../services/graphql";
import type { ClarificationAnswer } from "./chat/ClarificationPanel";
import { useWorkspaceSetup } from "./setup/useWorkspaceSetup";
import { useChatStream } from "./chat/useChatStream";
import { diffPackages, type IntentField } from "../../utils/intentEditorUtils";
import type { EntityUpdate } from "./setup/scoping/EntityCard";
import type { ScopeState } from "../../types/scopeState";
import type { SetupProgressState, SetupTask } from "../../types/setupProgress";
import type { UserEditableField } from "../../contexts/IntentContext";

// Local type for execution progress tracking
export type EntityProgress = {
  entity_type?: string;
  entity?: string;
  status?: "pending" | "in_progress" | "complete" | "error";
  progress?: number;
  total?: number;
  message?: string;
};

export type SetupPhase =
  | "intro"
  | "interview"
  | "draft"
  | "dataScoping" // Unified scoping + loading + review experience
  | "dataLoading" // Loading screen while data is being fetched
  | "aiTeamLoading"
  | "aiTeam";

// Phase ordering for preventing backwards transitions (defined outside component for stable reference)
const PHASE_ORDER: Record<SetupPhase, number> = {
  intro: 0,
  interview: 1,
  draft: 2,
  dataScoping: 3, // Unified data scoping phase
  dataLoading: 4, // Data fetching loading screen
  aiTeamLoading: 5,
  aiTeam: 6,
};

export type WorkspaceSetupFlowProps = {
  onComplete: () => void;
};

export default function WorkspaceSetupFlow({
  onComplete,
}: WorkspaceSetupFlowProps) {
  const useAnimationComponents = true;
  const { currentWorkspace, setCurrentWorkspace } = useWorkspace();
  const [phase, setPhase] = useState<SetupPhase>("intro");
  const [chatValue, setChatValue] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [localIntentPackage, setLocalIntentPackage] =
    useState<IntentPackage | null>(null);
  const [isIntentReady, setIsIntentReady] = useState(false);
  // isIntentReady is used indirectly via setIsIntentReady callbacks
  void isIntentReady;
  const [localDataScope, setLocalDataScope] = useState<
    import("../../services/graphql").DataScope | null
  >(null);
  const [isScopeReady, setIsScopeReady] = useState(false);
  // Local scope state for when chatStream handles SSE (in dataScoping phase)
  const [localScopeState, setLocalScopeState] = useState<ScopeState | null>(
    null,
  );
  // Setup tasks state for data staging loading screen (from setup_task SSE events)
  const [setupTasks, setSetupTasks] = useState<
    Map<
      string,
      {
        taskId: string;
        taskType: "entity" | "agent" | "other";
        title: string;
        status: "pending" | "running" | "completed" | "failed";
        taskIndex: number;
        taskTotal: number;
        progress?: { current: number; total: number };
      }
    >
  >(new Map());
  const [localExecutionResults, setLocalExecutionResults] = useState<
    import("../../services/graphql").ExecutionResult[] | null
  >(null);
  const [teamBuildingStatus, setTeamBuildingStatus] = useState<string>("");
  const [localTeamConfig, setLocalTeamConfig] = useState<
    import("../../services/graphql").TeamConfig | null
  >(null);
  const [hasRestoredState, setHasRestoredState] = useState(false);

  // Error state for displaying errors in loading views
  const [executionError, setExecutionError] = useState<string | null>(null);
  // executionError is set but not displayed in unified view - kept for future use
  void executionError;
  const [teamBuildingError, setTeamBuildingError] = useState<string | null>(
    null,
  );
  const restoredWorkspaceIdRef = useRef<string | null>(null);

  // Track recently updated fields for UI badges (shows which fields AI updated)
  const [recentlyUpdatedFields, setRecentlyUpdatedFields] = useState<
    IntentField[]
  >([]);

  // Track entity updates from scope events (for "Theo Updated" badges in scoping)
  const [entityUpdates, setEntityUpdates] = useState<
    Record<string, EntityUpdate>
  >({});

  // Track whether we've received the initial scope state
  // We only show "Theo Updated" badges AFTER the initial scope is set
  const hasReceivedInitialScopeRef = useRef(false);

  // Track whether user has seen the draft view at least once
  // We only show "Theo updated" badges AFTER the user has first viewed the draft
  const hasSeenDraftRef = useRef(false);

  // Ref to get current intent package from editor (for sending with chat messages)
  // This will be set by DraftView when it has an editor with user edits
  const getCurrentIntentPackageRef = useRef<
    (() => IntentPackage | null) | null
  >(null);

  // Track which fields the user has edited since last AI update
  // Reset when intent_updated event is received
  const userEditedFieldsRef = useRef<Set<UserEditableField>>(new Set());

  // Track user-initiated phase transitions to prevent SSE from overriding them
  const userInitiatedPhaseRef = useRef<SetupPhase | null>(null);
  const userPhaseTimestampRef = useRef<number>(0);

  // Wrapper to set phase that marks it as user-initiated
  const setPhaseUserInitiated = useCallback((newPhase: SetupPhase) => {
    userInitiatedPhaseRef.current = newPhase;
    userPhaseTimestampRef.current = Date.now();
    setPhase(newPhase);
  }, []);

  // Stable callbacks for useWorkspaceSetup (prevent infinite loops)
  const handleStageChange = useCallback(
    (stage: SetupStage) => {
      // Only block stage changes on intro if we're truly fresh (no setupRunId yet)
      // Once setup starts (setupRunId exists), allow stage changes even from intro
      // This prevents auto-transition on mount but allows SSE-driven transitions after user starts setup
      if (phase === "intro" && !currentWorkspace?.setupRunId) {
        return;
      }

      // If user recently initiated a phase transition (within 5 seconds), don't override it
      // This prevents SSE stage events from reverting user-initiated transitions
      const timeSinceUserAction = Date.now() - userPhaseTimestampRef.current;
      if (userInitiatedPhaseRef.current && timeSinceUserAction < 5000) {
        return;
      }

      // Map stage to phase - intent_discovery goes to interview (not draft)
      // since we're still chatting until intent is ready
      // IMPORTANT: Stage changes should NOT auto-advance the user through phases.
      // Events can unlock the continue button, but only user clicks should advance phases.
      // Note: data_scoping stays on dataScoping, data_review goes to dataLoading
      // Note: team_building maps to aiTeamLoading (loading screen), NOT aiTeam directly
      const phaseMap: Record<SetupStage, SetupPhase> = {
        intent_discovery: "interview",
        data_scoping: "dataScoping",
        data_review: "dataLoading", // Show data loading screen during execution
        team_building: "aiTeamLoading", // Show team building loading screen
        complete: "aiTeam",
      };
      const newPhase = phaseMap[stage];

      // CRITICAL: Certain phase transitions MUST be user-initiated (via Continue button).
      // SSE stage events can unlock the Continue button but should NOT auto-advance the phase.
      // This prevents events like scope_ready from automatically moving the user forward.
      // NOTE: dataLoading -> aiTeamLoading is NOT blocked - we want auto-transition when data loads
      const userInitiatedOnlyTransitions: Array<[SetupPhase, SetupPhase]> = [
        ["dataScoping", "dataLoading"], // User must click "Stage Data" to start data loading
        ["dataScoping", "aiTeamLoading"], // Block skipping data loading
        ["dataScoping", "aiTeam"], // Block skipping to final view
        ["dataLoading", "aiTeam"], // Block skipping team loading (but allow dataLoading -> aiTeamLoading)
        ["aiTeamLoading", "aiTeam"], // User must click Continue on team loading screen
      ];

      const isUserInitiatedOnly = userInitiatedOnlyTransitions.some(
        ([from, to]) => phase === from && newPhase === to,
      );

      if (isUserInitiatedOnly) {
        return;
      }

      // Only transition if moving forward (prevent backwards navigation from delayed SSE events)
      const currentOrder = PHASE_ORDER[phase] ?? 0;
      const newOrder = PHASE_ORDER[newPhase] ?? 0;

      if (newPhase && newPhase !== phase && newOrder >= currentOrder) {
        setPhase(newPhase);
      }
    },
    [phase, currentWorkspace?.setupRunId],
  );

  const handleIntentReady = useCallback((intentPackage: IntentPackage) => {
    setLocalIntentPackage(intentPackage);
    setIsIntentReady(true);
    // Transition to draft view when intent is ready (from interview phase)
    // Only navigate if user hasn't recently initiated a phase change
    const timeSinceUserAction = Date.now() - userPhaseTimestampRef.current;
    if (userInitiatedPhaseRef.current && timeSinceUserAction < 5000) {
      return;
    }
    // Only transition to draft if we're in interview phase
    // When resuming, SSE replays events - don't regress from later phases
    setPhase((currentPhase) => {
      if (currentPhase === "interview" || currentPhase === "intro") {
        return "draft";
      }
      return currentPhase;
    });
  }, []);

  const handleScopeReady = useCallback((dataScope: DataScope) => {
    setLocalDataScope(dataScope);
    setIsScopeReady(true);
  }, []);

  const handleExecutionComplete = useCallback((results: ExecutionResult[]) => {
    setLocalExecutionResults(results);
    // In the unified dataScoping phase, execution results are merged into ScopeState
    // No phase transition needed - user stays in dataScoping until they click "Stage Data"
  }, []);

  const handleTeamComplete = useCallback(
    (teamConfig: TeamConfig) => {
      // If the incoming team config has empty agents but we have agent tasks,
      // construct agents from the setup_task events
      let finalConfig = teamConfig;

      if (
        (!teamConfig.agents || teamConfig.agents.length === 0) &&
        setupTasks.size > 0
      ) {
        const agentTasks = Array.from(setupTasks.values()).filter(
          (t) => t.taskType === "agent",
        );
        if (agentTasks.length > 0) {
          finalConfig = {
            ...teamConfig,
            agents: agentTasks.map((task) => ({
              agent_id: task.taskId,
              name: task.title,
              role: task.title,
              capabilities: [], // Will be populated from API fetch in AiTeamViewAnimated
            })),
          };
        }
      }

      setLocalTeamConfig(finalConfig);

      // Event-driven transition: setup_complete/team_complete event means team building is done
      // Transition directly to aiTeam phase
      setPhase("aiTeam");
    },
    [setupTasks],
  );

  const handleIntentProposed = useCallback(
    async (intentPackage: IntentPackage | null) => {
      // When intent_proposed event arrives, switch to draft phase and enable continue button
      if (intentPackage) {
        setLocalIntentPackage(intentPackage);

        // Auto-update workspace name only if still "New Workspace"
        if (currentWorkspace?.name === "New Workspace" && intentPackage.title) {
          try {
            await updateWorkspace({
              workspaceId: currentWorkspace.workspaceId,
              name: intentPackage.title,
            });
            setCurrentWorkspace({
              ...currentWorkspace,
              name: intentPackage.title,
            });
          } catch (e) {
            console.error(
              "[WorkspaceSetupFlow] Failed to auto-update workspace name:",
              e,
            );
          }
        }
      }
      // Only navigate if user hasn't recently initiated a phase change
      const timeSinceUserAction = Date.now() - userPhaseTimestampRef.current;
      if (userInitiatedPhaseRef.current && timeSinceUserAction < 5000) {
        setIsIntentReady(true);
        return;
      }
      // Only transition to draft if we're in interview phase
      // When resuming, SSE replays events - don't regress from later phases
      setPhase((currentPhase) => {
        if (currentPhase === "interview" || currentPhase === "intro") {
          return "draft";
        }
        // Don't regress from later phases (scoping, loading, review, aiTeam, etc.)
        return currentPhase;
      });
      setIsIntentReady(true);
    },
    [currentWorkspace, setCurrentWorkspace],
  );

  // Handle title change from DraftView
  const handleTitleChange = useCallback(
    async (newTitle: string) => {
      if (!currentWorkspace?.workspaceId) return;
      try {
        await updateWorkspace({
          workspaceId: currentWorkspace.workspaceId,
          name: newTitle,
        });
        setCurrentWorkspace({ ...currentWorkspace, name: newTitle });
      } catch (e) {
        console.error(
          "[WorkspaceSetupFlow] Failed to update workspace name:",
          e,
        );
      }
    },
    [currentWorkspace, setCurrentWorkspace],
  );

  // Use the workspace setup hook
  const setupHook = useWorkspaceSetup({
    workspaceId: currentWorkspace?.workspaceId || "",
    onStageChange: handleStageChange,
    onIntentReady: handleIntentReady,
    onScopeReady: handleScopeReady,
    onExecutionComplete: handleExecutionComplete,
    onTeamComplete: handleTeamComplete,
    onExecutionError: (error) => {
      console.error("[WorkspaceSetupFlow] Execution error:", error);
      setExecutionError(error);
    },
    onTeamBuildingError: (error) => {
      console.error("[WorkspaceSetupFlow] Team building error:", error);
      setTeamBuildingError(error);
    },
  });

  // Handle intent_updated event from AI (bidirectional sync)
  const handleIntentPackageUpdated = useCallback(
    (newIntentPackage: IntentPackage, _updateSummary?: string) => {
      // Clear user-edited fields tracking when AI updates (reset tracking)
      userEditedFieldsRef.current = new Set();

      // Calculate which fields changed for UI badges
      // Only show "updated" badges when:
      // 1. AI modifies an EXISTING intent (not on first proposal)
      // 2. User has already seen the draft view at least once
      setLocalIntentPackage((prevPackage) => {
        // Only show "Theo updated" badges if user has already seen the draft
        // This prevents showing badges on the initial view when intent is first proposed
        if (prevPackage && hasSeenDraftRef.current) {
          const changedFields = diffPackages(prevPackage, newIntentPackage);
          if (changedFields.length > 0) {
            setRecentlyUpdatedFields(changedFields);
          }
        }
        return newIntentPackage;
      });
    },
    [],
  );

  // Handle user editing fields in the intent editor
  const handleFieldsEdited = useCallback((fields: UserEditableField[]) => {
    fields.forEach((field) => userEditedFieldsRef.current.add(field));
  }, []);

  // Use the chat stream hook for real-time chat
  // Now handles ALL setup events - scope, execution, and team building
  const chatStream = useChatStream({
    workspaceId: currentWorkspace?.workspaceId,
    currentWorkspace,
    setCurrentWorkspace,
    onIntentProposed: handleIntentProposed,
    // NEW: Handle intent_updated events (bidirectional sync)
    onIntentPackageUpdated: handleIntentPackageUpdated,
    // Scope callbacks - handle scope events from SSE
    onScopeUpdated: (dataScope, ready) => {
      setLocalDataScope(dataScope);
      setIsScopeReady(ready);
    },
    onScopeReady: handleScopeReady,
    // Handle scope state updates with entity update info (for "Theo Updated" badges)
    // The ready flag is on the scope_update event, not a separate event
    // Also update localScopeState since chatStream handles SSE during dataScoping phase
    onScopeStateUpdated: (scopeState, entityUpdateInfo) => {
      const previousScopeState = localScopeState;

      // Update local scope state for rendering
      setLocalScopeState(scopeState);

      // Skip "Theo Updated" badges on the first scope update - everything is new
      if (!hasReceivedInitialScopeRef.current) {
        hasReceivedInitialScopeRef.current = true;
        return;
      }

      // Handle entity updates for "Theo Updated" badges (only after initial scope)
      const timestamp = Date.now();
      const newUpdates: Record<string, EntityUpdate> = {};

      if (entityUpdateInfo && entityUpdateInfo.changedEntities.length > 0) {
        // Use changed_entities from the event if available
        for (const entityType of entityUpdateInfo.changedEntities) {
          newUpdates[entityType] = {
            summary: entityUpdateInfo.updateSummary,
            changedFields: entityUpdateInfo.isNewEntity
              ? ["entity", "fields"]
              : ["filters"],
            timestamp,
            isNew: entityUpdateInfo.isNewEntity,
            addedFilterIds: entityUpdateInfo.addedFilterIds,
            changedFilterIds: entityUpdateInfo.changedFilterIds,
            addedFieldNames: entityUpdateInfo.addedFieldNames,
            changedFieldNames: entityUpdateInfo.changedFieldNames,
          };
        }
      } else if (previousScopeState && scopeState) {
        // Fallback: detect changes by comparing previous and new scope state
        const prevEntityTypes = new Set(
          previousScopeState.entities.map((e) => e.entity_type),
        );

        for (const entity of scopeState.entities) {
          const prevEntity = previousScopeState.entities.find(
            (e) => e.entity_type === entity.entity_type,
          );

          if (!prevEntityTypes.has(entity.entity_type)) {
            // New entity added
            newUpdates[entity.entity_type] = {
              summary: "Added to scope",
              changedFields: ["entity", "fields"],
              timestamp,
              isNew: true,
            };
          } else if (prevEntity) {
            // Check if filters or fields changed
            const filtersChanged =
              JSON.stringify(prevEntity.filters) !==
              JSON.stringify(entity.filters);
            const fieldsChanged =
              JSON.stringify(prevEntity.fields_of_interest) !==
              JSON.stringify(entity.fields_of_interest);

            if (filtersChanged || fieldsChanged) {
              newUpdates[entity.entity_type] = {
                summary: filtersChanged ? "Filters updated" : "Fields updated",
                changedFields: filtersChanged ? ["filters"] : ["fields"],
                timestamp,
                isNew: false,
              };
            }
          }
        }
      }

      // Only update if there are actual changes
      if (Object.keys(newUpdates).length > 0) {
        setEntityUpdates(newUpdates);
      }
    },
    // Execution complete callback
    onExecutionComplete: handleExecutionComplete,
    // Setup task callbacks (for data staging loading screen)
    onSetupTask: (task) => {
      setSetupTasks((prev) => {
        const updated = new Map(prev);
        updated.set(task.taskId, {
          taskId: task.taskId,
          taskType: task.taskType,
          title: task.title,
          status: task.status,
          taskIndex: task.taskIndex,
          taskTotal: task.taskTotal,
          progress: task.progress,
        });
        return updated;
      });
    },
    // Team building callbacks
    onTeamBuildingStatus: (message) => {
      setTeamBuildingStatus(message);
    },
    onTeamComplete: handleTeamComplete,
  });

  // Ref to track current stream state
  const activeStreamRunIdRef = useRef<string | null>(null);
  // Ref to store pending initial message when starting setup (for optimistic display)
  const pendingInitialMessageRef = useRef<string | null>(null);

  const isChatLocked = chatSending || chatStream.isTurnOpen;

  // Start chat stream when we have a runId
  // Stream stays active through ALL setup phases - not just chat phases
  // This ensures we receive execution_complete, team_complete, and other events during loading/review
  useEffect(() => {
    const runId = setupHook.status?.runId || currentWorkspace?.setupRunId;
    const tenantId = getTenantId();

    // Only restart if runId actually changed
    if (runId && tenantId && runId !== activeStreamRunIdRef.current) {
      activeStreamRunIdRef.current = runId;
      // Pass initial message and thinking flag if we have a pending message
      const initialMessage = pendingInitialMessageRef.current;
      pendingInitialMessageRef.current = null; // Clear after use
      chatStream.startStream(runId, tenantId, {
        initialMessage: initialMessage || undefined,
        showThinking: !!initialMessage, // Show thinking if there's an initial message
      });
    }
    // NO cleanup function - we want the stream to stay open even when dependencies change
    // Stream will be cleaned up by useChatStream's own useEffect cleanup on component unmount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setupHook.status?.runId, currentWorkspace?.setupRunId, phase]);

  // Separate cleanup effect that ONLY runs on unmount
  useEffect(() => {
    return () => {
      // This cleanup ONLY runs when WorkspaceSetupFlow unmounts
      chatStream.stopStream();
      activeStreamRunIdRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps = only on mount/unmount

  // Mark that user has seen the draft view (for "Theo updated" badge logic)
  // We only show update badges AFTER the user has first viewed the draft
  useEffect(() => {
    if (phase === "draft") {
      // Small delay to let the initial render complete before enabling badges
      const timer = setTimeout(() => {
        hasSeenDraftRef.current = true;
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [phase]);

  // Sync localIntentPackage from workspace when transitioning TO dataScoping phase
  // This ensures we use the confirmed intent from the database (with user edits)
  useEffect(() => {
    if (phase === "dataScoping" && currentWorkspace?.setupIntentPackage) {
      // Only sync if the workspace has a newer/different intent than what we have locally
      const dbIntent = currentWorkspace.setupIntentPackage;
      const localIntent = localIntentPackage;

      // Check if they differ (simplified check on key fields)
      const needsSync =
        !localIntent ||
        dbIntent.mission?.objective !== localIntent.mission?.objective ||
        dbIntent.mission?.why !== localIntent.mission?.why ||
        dbIntent.mission?.success_looks_like !==
          localIntent.mission?.success_looks_like;

      if (needsSync) {
        setLocalIntentPackage(dbIntent);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, currentWorkspace?.setupIntentPackage]);

  // Handle chat send - accepts optional message param from ChatDock, falls back to chatValue
  const handleChatSend = useCallback(
    async (messageFromChatDock?: string) => {
      const message = (messageFromChatDock ?? chatValue).trim();
      if (!message) return;
      if (chatStream.isTurnOpen) return;

      // Clear "updated" badges when user sends a new message
      setRecentlyUpdatedFields([]);

      chatStream.setIsTurnOpen(true);
      setChatSending(true);

      try {
        if (phase === "intro") {
          // Starting fresh setup from intro screen
          // Store the message for optimistic display when stream starts
          // The useEffect that calls startStream will pass this to show the message
          // immediately with the thinking indicator
          pendingInitialMessageRef.current = message;
          setPhase("interview"); // Eagerly transition BEFORE async call
          await setupHook.startSetup(message);
          // handleStageChange will handle further phase transitions based on SSE events
        } else if (
          phase === "interview" ||
          phase === "draft" ||
          phase === "dataScoping"
        ) {
          // Sending follow-up message to existing conversation
          // Works across interview, draft, and dataScoping phases (same stream)
          // Show thinking indicator immediately for follow-up messages
          chatStream.setIsAgentWorking(true);
          chatStream.addOptimisticMessage({ role: "user", content: message });
          // Try multiple sources for runId: ref (most reliable), setupHook, workspace
          const runId =
            activeStreamRunIdRef.current ||
            setupHook.status?.runId ||
            currentWorkspace?.setupRunId;

          if (!runId) {
            chatStream.setIsAgentWorking(false);
            return;
          }

          // Get current intent package from editor (if available) for bidirectional sync
          // This ensures AI sees user's latest edits before processing
          const currentIntentPackage =
            getCurrentIntentPackageRef.current?.() || localIntentPackage;

          const userMessageEvent: {
            event_type: string;
            message: string;
            current_intent_package?: IntentPackage | null;
            user_edited_fields?: string[];
          } = {
            event_type: "user_message",
            message: message,
          };

          // Include current_intent_package when in draft or dataScoping phases
          // (during interview, the intent hasn't been established yet)
          if (
            (phase === "draft" || phase === "dataScoping") &&
            currentIntentPackage
          ) {
            userMessageEvent.current_intent_package = currentIntentPackage;
            // Include which fields the user has edited since last AI update
            const editedFields = Array.from(userEditedFieldsRef.current);
            userMessageEvent.user_edited_fields = editedFields;
          }

          const { appendScenarioRunLog } =
            await import("../../services/graphql");
          await appendScenarioRunLog(runId, JSON.stringify(userMessageEvent));
        }
      } catch (error) {
        console.error("[WorkspaceSetupFlow] Failed to send message:", error);
        chatStream.setIsAgentWorking(false);
        if (phase === "intro") {
          setPhase("intro"); // Revert to intro on error
        }
      } finally {
        // Clear input
        setChatValue("");
        setChatSending(false);
      }
    },
    [chatValue, phase, setupHook, currentWorkspace?.setupRunId, chatStream],
  );

  // Handle clarification submission
  const handleClarificationSubmit = useCallback(
    async (answers: ClarificationAnswer[]) => {
      const runId =
        activeStreamRunIdRef.current ||
        setupHook.status?.runId ||
        currentWorkspace?.setupRunId;
      if (!runId) {
        return;
      }

      try {
        setChatSending(true);
        chatStream.setIsAgentWorking(true);

        // Format the answers as a user_message with all Q&A pairs
        const formattedAnswers = answers
          .map(
            (a) =>
              `${a.question}: ${a.selected_option}${
                a.selected_description ? ` (${a.selected_description})` : ""
              }`,
          )
          .join("\n\n");

        const clarificationResponseMessage = `**Clarification responses**\n\n${formattedAnswers}`;

        // Create user_message event with the formatted responses
        const userMessageEvent = {
          event_type: "user_message",
          message: clarificationResponseMessage,
          clarification_responses: answers.map((a) => ({
            question_id: a.question_id,
            selected_option: a.selected_option,
          })),
        };

        // Append to scenario run log
        await appendScenarioRunLog(runId, JSON.stringify(userMessageEvent));
        // Add user message to chat display so it appears in the conversation
        chatStream.addOptimisticMessage({
          role: "user",
          content: clarificationResponseMessage,
        });

        // Clear pending clarifications
        chatStream.clearClarifications();
      } catch (error) {
        console.error(
          "[WorkspaceSetupFlow] Failed to submit clarification responses:",
          error,
        );
        chatStream.setIsAgentWorking(false);
      } finally {
        setChatSending(false);
      }
    },
    [setupHook.status?.runId, currentWorkspace?.setupRunId, chatStream],
  );

  // Note: Setup is now started when user sends first message from intro screen
  // No auto-start needed - user initiates the workflow

  // Restore state from workspace on mount (Resume Flow Support)
  useEffect(() => {
    if (!currentWorkspace) {
      return;
    }

    // If switching to a different workspace, reset restoration state
    if (
      restoredWorkspaceIdRef.current &&
      restoredWorkspaceIdRef.current !== currentWorkspace.workspaceId
    ) {
      setHasRestoredState(false);
      activeStreamRunIdRef.current = null;
    }

    // Only restore once per workspace (prevent re-running when workspace updates mid-setup)
    if (restoredWorkspaceIdRef.current === currentWorkspace.workspaceId) {
      return;
    }

    // Restore artifacts from workspace
    if (currentWorkspace.setupIntentPackage) {
      setLocalIntentPackage(currentWorkspace.setupIntentPackage);
      setIsIntentReady(true);
    }

    if (currentWorkspace.setupDataScope) {
      setLocalDataScope(currentWorkspace.setupDataScope);
      setIsScopeReady(true);
    }

    if (currentWorkspace.setupExecutionResults) {
      setLocalExecutionResults(currentWorkspace.setupExecutionResults);
    }

    if (currentWorkspace.setupTeamConfig) {
      setLocalTeamConfig(currentWorkspace.setupTeamConfig);
    }

    // Mark this workspace as restored to prevent re-running
    restoredWorkspaceIdRef.current = currentWorkspace.workspaceId;

    // Restore phase based on setupStage with edge case handling
    // For fresh workspaces (no setupStage or no setupRunId), stay on intro
    if (!currentWorkspace.setupStage || !currentWorkspace.setupRunId) {
      setHasRestoredState(true);
      return;
    }

    const stage = currentWorkspace.setupStage as SetupStage;
    let restoredPhase: SetupPhase = "intro";

    // Edge case: Check if artifacts indicate completion beyond the current stage
    // This handles cases where the backend completed a stage while user was away
    const hasIntent = !!currentWorkspace.setupIntentPackage;
    const hasScope = !!currentWorkspace.setupDataScope;
    const hasResults = !!currentWorkspace.setupExecutionResults;
    const hasTeam = !!currentWorkspace.setupTeamConfig;

    switch (stage) {
      case "intent_discovery":
        // If intent is ready, show draft; otherwise show interview (in-progress chat)
        restoredPhase = hasIntent ? "draft" : "interview";

        // Edge case: If we have scope/results/team, stage is further ahead
        if (hasTeam) {
          restoredPhase = "aiTeam";
        } else if (hasScope || hasResults) {
          // Unified dataScoping phase handles both scoping and review
          restoredPhase = "dataScoping";
        }
        break;

      case "data_scoping":
        // Data scoping phase - user is still refining scope
        restoredPhase = "dataScoping";

        // Edge case: If we have results, data loading completed while away
        if (hasResults) {
          restoredPhase = hasTeam ? "aiTeam" : "aiTeamLoading";
        } else if (hasTeam) {
          restoredPhase = "aiTeam";
        }
        break;

      case "data_review":
        // Data review = data loading in progress
        restoredPhase = hasResults ? "aiTeamLoading" : "dataLoading";

        // Edge case: If we have team, team building completed while away
        if (hasTeam) {
          restoredPhase = "aiTeam";
        }
        break;

      case "team_building":
        // Show loading screen if team building is in progress, aiTeam if complete
        restoredPhase = hasTeam ? "aiTeam" : "aiTeamLoading";
        break;

      case "complete":
        restoredPhase = "aiTeam";
        break;
    }

    setPhase(restoredPhase);
    setHasRestoredState(true);
  }, [currentWorkspace?.workspaceId]);

  // Auto-reconnect to SSE stream when resuming (Resume Flow Support)
  // Only use setupHook's SSE for non-chat phases (loading, review, aiTeam)
  // Chat phases (intro, interview, draft, scoping) use chatStream's SSE connection
  useEffect(() => {
    if (!hasRestoredState) return; // Wait until state is restored

    const runId = setupHook.status?.runId || currentWorkspace?.setupRunId;
    const tenantId = getTenantId();
    const stage = currentWorkspace?.setupStage;

    // Only connect via setupHook if we're NOT in a chat phase
    // (chat phases use chatStream which has its own SSE connection)
    // Extended to include 'dataScoping' - chat stream stays active through unified data scoping phase
    const isChatPhase =
      phase === "intro" ||
      phase === "interview" ||
      phase === "draft" ||
      phase === "dataScoping";

    if (
      !isChatPhase &&
      runId &&
      tenantId &&
      stage &&
      stage !== "complete" &&
      !setupHook.isStreaming
    ) {
      setupHook.connectToStage(runId, tenantId);
    } else if (isChatPhase && setupHook.isStreaming) {
      // If we're in a chat phase and setupHook is still streaming, disconnect it
      // (chatStream will handle the connection)
      setupHook.disconnectStream();
    }

    return () => {
      // Cleanup on unmount (only if not in chat phase)
      if (!isChatPhase) {
        setupHook.disconnectStream();
      }
    };
  }, [
    hasRestoredState,
    setupHook.status?.runId,
    currentWorkspace?.setupRunId,
    currentWorkspace?.setupStage,
    phase,
  ]);

  // Navigation guard - warn user if they try to leave during setup
  const isSetupComplete =
    phase === "aiTeam" && setupHook.status?.stage === "complete";

  // Use browser's beforeunload event to warn about leaving mid-setup
  useEffect(() => {
    if (isSetupComplete) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Modern browsers require returnValue to be set
      e.returnValue = "";
      return "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isSetupComplete]);

  // Handle transition from draft phase to data scoping
  // NOTE: DraftView.handleContinue already calls confirmIntentAndStartDataScoping mutation
  // So this callback just needs to:
  // 1. Send end_intent event to stop Theo
  // 2. Sync localIntentPackage from workspace context
  // 3. Transition the UI phase
  const handleDraftContinue = useCallback(async () => {
    // Send end_intent event to stop Theo
    const runId = setupHook.status?.runId || currentWorkspace?.setupRunId;
    if (runId) {
      const endIntentEvent = {
        event_type: "end_intent",
        message: "User confirmed intent",
        metadata: {
          action: "confirm",
        },
      };
      await appendScenarioRunLog(runId, JSON.stringify(endIntentEvent));
    }

    // Sync localIntentPackage from workspace context
    // DraftView.handleContinue already updated currentWorkspace.setupIntentPackage
    if (currentWorkspace?.setupIntentPackage) {
      setLocalIntentPackage(currentWorkspace.setupIntentPackage);
    }

    // Transition UI to data scoping phase
    setPhaseUserInitiated("dataScoping");
  }, [
    setupHook.status?.runId,
    currentWorkspace?.setupRunId,
    currentWorkspace?.setupIntentPackage,
    setPhaseUserInitiated,
  ]);

  // Handle "Stage Data" from unified DataScopingView - confirms scope and starts data loading
  const handleStageData = useCallback(async () => {
    // Use the hook's dataScope or localDataScope if available
    const scope = localDataScope || setupHook.dataScope;

    // IMPORTANT: Transition to data loading screen FIRST, before async calls
    // This ensures user sees the loading screen immediately
    setPhaseUserInitiated("dataLoading");

    try {
      // Confirm scope - this starts data execution on backend
      if (scope) {
        await setupHook.confirmScope(scope);
      }
      // Data loading will complete when execution_complete event arrives
      // Then we auto-transition to aiTeamLoading via handleExecutionComplete
    } catch (error) {
      console.error("[WorkspaceSetupFlow] Error in handleStageData:", error);
      // Go back to dataScoping page on error - user can retry
      setPhaseUserInitiated("dataScoping");
    }
  }, [setupHook, localDataScope, setPhaseUserInitiated]);

  // Handle data loading complete - transition to AI team loading
  // Backend automatically transitions from data_review to team_building after data execution
  // No frontend mutation needed - just update the UI phase
  const handleDataLoadingContinue = useCallback(() => {
    // Clear agent tasks from setupTasks to start fresh for team building
    // (keep entity tasks for reference, but agent tasks need a clean slate)
    setSetupTasks((prev) => {
      const filtered = new Map<
        string,
        typeof prev extends Map<string, infer V> ? V : never
      >();
      prev.forEach((task, key) => {
        if (task.taskType !== "agent") {
          filtered.set(key, task);
        }
      });
      return filtered;
    });

    // Transition to AI team loading screen
    // Backend has already started team building after data execution completed
    setPhaseUserInitiated("aiTeamLoading");
  }, [setPhaseUserInitiated]);

  const handleAiTeamLoadingContinue = useCallback(() => {
    setPhase("aiTeam");
  }, []);

  // Assemble workflow inputs from workspace context
  const handleAiTeamContinue = useCallback(async () => {
    const teamConfig = localTeamConfig || setupHook.teamConfig;
    const intentPkg = localIntentPackage || setupHook.intentPackage;
    const dataScope = localDataScope || setupHook.dataScope;
    const execResults = localExecutionResults || setupHook.executionResults;

    if (teamConfig && currentWorkspace?.workspaceId) {
      try {
        // Complete setup - this now triggers the workflow and returns runId
        const runId = await setupHook.completeSetup(teamConfig);

        // Update workspace context with ALL setup artifacts so they persist
        // after transitioning to the working workspace view
        setCurrentWorkspace({
          ...currentWorkspace,
          analysisRunId: runId || currentWorkspace.analysisRunId,
          setupIntentPackage: intentPkg || currentWorkspace.setupIntentPackage,
          setupDataScope: dataScope || currentWorkspace.setupDataScope,
          setupExecutionResults:
            execResults || currentWorkspace.setupExecutionResults,
          setupTeamConfig: teamConfig,
        });
      } catch (e) {
        console.error("[WorkspaceSetupFlow] Failed to complete setup:", e);
        // Still update context with artifacts even on error
        setCurrentWorkspace({
          ...currentWorkspace,
          setupIntentPackage: intentPkg || currentWorkspace.setupIntentPackage,
          setupDataScope: dataScope || currentWorkspace.setupDataScope,
          setupExecutionResults:
            execResults || currentWorkspace.setupExecutionResults,
          setupTeamConfig: teamConfig,
        });
      }
    }

    // Navigate to workspace page
    onComplete();
  }, [
    localTeamConfig,
    localIntentPackage,
    localDataScope,
    localExecutionResults,
    setupHook,
    currentWorkspace,
    setCurrentWorkspace,
    onComplete,
  ]);

  // These handlers are kept for future use when we wire up real-time execution progress
  const handleRetry = useCallback(async () => {
    // Clear the workflow error before retrying
    chatStream.clearWorkflowError();

    // Determine which action to retry based on current stage
    const stage = currentWorkspace?.setupStage as SetupStage;

    try {
      switch (stage) {
        case "intent_discovery":
          // Restart intent discovery
          await setupHook.startSetup();
          setPhase("interview");
          break;

        case "data_scoping":
          // Retry confirming intent to restart data scoping
          if (localIntentPackage || setupHook.intentPackage) {
            await setupHook.confirmIntent(
              localIntentPackage || setupHook.intentPackage!,
            );
            setPhase("dataScoping");
          }
          break;

        case "data_review":
          // Retry confirming scope to restart execution
          if (localDataScope || setupHook.dataScope) {
            await setupHook.confirmScope(
              localDataScope || setupHook.dataScope!,
            );
            setPhase("dataScoping");
          }
          break;

        case "team_building":
          // Retry confirming review to restart team building
          // Go back to dataScoping so user can click Stage Data again
          console.warn(
            "[WorkspaceSetupFlow] Team building retry requires going back to dataScoping",
          );
          setPhase("dataScoping");
          break;

        default:
          console.warn(
            "[WorkspaceSetupFlow] No retry action for stage:",
            stage,
          );
          // Fallback: refetch status
          await setupHook.refetchStatus();
      }
    } catch (error) {
      console.error("[WorkspaceSetupFlow] Retry failed:", error);
    }
  }, [
    currentWorkspace?.setupStage,
    setupHook,
    localIntentPackage,
    localDataScope,
  ]);

  // Convert setupTasks map to SetupProgressState for LoadingView
  // NOTE: This useMemo MUST be before any early returns to satisfy React hooks rules
  const dataLoadingProgressState: SetupProgressState = useMemo(() => {
    // Filter for entity tasks only (data staging)
    const tasks: SetupTask[] = Array.from(setupTasks.values())
      .filter((t) => t.taskType === "entity")
      .map((t) => ({
        id: t.taskId,
        type: "entity" as const,
        title: t.title,
        index: t.taskIndex,
        total: t.taskTotal,
        status: t.status,
        progress: t.progress,
      }));

    const isComplete =
      tasks.length > 0 && tasks.every((t) => t.status === "completed");

    return {
      phase: {
        name: "staging_data" as const,
        index: 0,
        total: 1,
        status: isComplete ? "completed" : "started",
      },
      tasks,
      messages: [],
      isComplete,
      error: executionError,
      summary: {},
    };
  }, [setupTasks, executionError]);

  // Convert setupTasks to SetupProgressState for team building LoadingView
  const teamBuildingProgressState: SetupProgressState = useMemo(() => {
    // Filter for agent tasks only (team building)
    const tasks: SetupTask[] = Array.from(setupTasks.values())
      .filter((t) => t.taskType === "agent")
      .map((t) => ({
        id: t.taskId,
        type: "agent" as const,
        title: t.title,
        index: t.taskIndex,
        total: t.taskTotal,
        status: t.status,
        progress: t.progress,
      }));

    const isComplete =
      tasks.length > 0 && tasks.every((t) => t.status === "completed");

    return {
      phase: {
        name: "building_team" as const,
        index: 0,
        total: 1,
        status: isComplete ? "completed" : "started",
      },
      tasks,
      messages: [],
      isComplete,
      error: teamBuildingError,
      summary: {},
    };
  }, [setupTasks, teamBuildingError]);

  // Show AI Team view
  if (phase === "aiTeam" && currentWorkspace) {
    return (
      <>
        {useAnimationComponents ? (
          <AiTeamViewAnimated
            isSetupMode={true}
            onContinue={handleAiTeamContinue}
            currentStep={3}
            totalSteps={3}
            teamConfig={localTeamConfig || setupHook.teamConfig}
            workspaceName={currentWorkspace.name}
            error={teamBuildingError}
            intentPackage={localIntentPackage || setupHook.intentPackage}
          />
        ) : (
          <AiTeamView
            isSetupMode={true}
            onContinue={handleAiTeamContinue}
            currentStep={3}
            totalSteps={3}
            teamConfig={localTeamConfig || setupHook.teamConfig}
            workspaceName={currentWorkspace.name}
          />
        )}
      </>
    );
  }

  // Show data loading view (fetching data from database)
  if (phase === "dataLoading") {
    return (
      <LoadingView
        key="data-staging-loader"
        onContinue={handleDataLoadingContinue}
        currentStep={2}
        totalSteps={3}
        mode="data_staging"
        progressState={dataLoadingProgressState}
        autoProgress={true}
        isReady={!!localExecutionResults || !!setupHook.executionResults}
        error={executionError}
      />
    );
  }

  // Show AI Team loading view
  // Transition to aiTeam is event-driven via handleTeamComplete (setup_complete event)
  if (phase === "aiTeamLoading") {
    return (
      <LoadingView
        key="team-building-loader"
        onContinue={handleAiTeamLoadingContinue}
        currentStep={3}
        totalSteps={3}
        mode="team_building"
        subtitle={teamBuildingStatus || undefined}
        progressState={teamBuildingProgressState}
        // Fallback to hardcoded entities if no SSE tasks received yet
        entities={
          teamBuildingProgressState.tasks.length === 0
            ? aiTeamLoadingEntities
            : undefined
        }
        error={teamBuildingError}
      />
    );
  }

  // Show unified data scoping view (merges previous scoping, loading, and review phases)
  if (phase === "dataScoping" && currentWorkspace) {
    return (
      <DataScopingView
        workspaceId={currentWorkspace.workspaceId}
        workspaceName={currentWorkspace.name}
        scopeState={localScopeState || setupHook.scopeState}
        isScopeReady={isScopeReady}
        onStageData={handleStageData}
        currentStep={2}
        totalSteps={3}
        // Chat props
        setupRunId={currentWorkspace.setupRunId || undefined}
        onChatSubmit={handleChatSend}
        chatDisabled={isChatLocked}
        messages={chatStream.messages}
        isAgentWorking={chatStream.isAgentWorking}
        // Clarification props
        pendingClarifications={chatStream.pendingClarifications}
        onClarificationSubmit={handleClarificationSubmit}
        // Intent props for View Intent modal
        intentPackage={localIntentPackage || setupHook.intentPackage}
        // Entity updates for "Theo Updated" badges
        entityUpdates={entityUpdates}
        // Error handling
        workflowError={chatStream.workflowError}
        onRetry={handleRetry}
      />
    );
  }

  // Show draft view when intent is ready (80% intent, 20% inline chat - same stream as interview)
  if (phase === "draft" && currentWorkspace) {
    return (
      <DraftView
        intent={currentWorkspace.intent || ""}
        intentPackage={localIntentPackage || setupHook.intentPackage}
        workspaceId={currentWorkspace.workspaceId}
        workspaceName={currentWorkspace.name}
        onTitleChange={handleTitleChange}
        messages={chatStream.messages}
        isAgentWorking={chatStream.isAgentWorking}
        chatValue={chatValue}
        onChatValueChange={setChatValue}
        onChatSend={handleChatSend}
        chatSending={isChatLocked}
        chatDisabled={isChatLocked}
        onContinue={handleDraftContinue}
        currentStep={1}
        totalSteps={3}
        onRegisterIntentPackageGetter={(getter) => {
          getCurrentIntentPackageRef.current = getter;
        }}
        recentlyUpdatedFields={recentlyUpdatedFields}
        onFieldsEdited={handleFieldsEdited}
      />
    );
  }

  // Show interview view (full chat) after first message until intent is ready
  if (phase === "interview" && currentWorkspace) {
    return (
      <Box
        sx={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          bgcolor: "background.default",
        }}
      >
        {/* Error Alert */}
        {setupHook.error && (
          <Alert
            severity="error"
            sx={{ mx: 2, mt: 2 }}
            action={
              <MuiButton color="inherit" size="small" onClick={handleRetry}>
                Retry
              </MuiButton>
            }
          >
            {setupHook.error}
          </Alert>
        )}

        <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
          <InterviewView
            messages={chatStream.messages}
            isAgentWorking={chatStream.isAgentWorking}
            value={chatValue}
            onChange={setChatValue}
            onSend={handleChatSend}
            sending={isChatLocked}
            disabled={isChatLocked}
          />
        </Box>
      </Box>
    );
  }

  // Intro phase shows the initial greeting with centered input
  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        bgcolor: "background.default",
      }}
    >
      {/* Error Alert */}
      {setupHook.error && (
        <Alert
          severity="error"
          sx={{ mx: 2, mt: 2 }}
          action={
            <MuiButton color="inherit" size="small" onClick={handleRetry}>
              Retry
            </MuiButton>
          }
        >
          {setupHook.error}
        </Alert>
      )}

      <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
        <IntroView
          value={chatValue}
          onChange={setChatValue}
          onSend={handleChatSend}
          sending={isChatLocked}
          disabled={isChatLocked}
        />
      </Box>
    </Box>
  );
}
