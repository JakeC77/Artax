import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import {
  Box,
  ClickAwayListener,
  IconButton,
  Paper,
  Popper,
  Tooltip,
  Typography,
  Chip,
  Collapse,
  List,
  ListItem,
  Divider,
  CircularProgress,
  InputBase,
  Fab,
  Zoom,
} from "@mui/material";
import PsychologyIcon from "@mui/icons-material/Psychology";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import {
  Add,
  View,
  RecentlyViewed,
  // TODO: Uncomment when voice functionality is implemented
  // Microphone,
  RightPanelCloseFilled,
  Send,
  ArrowDown,
} from "@carbon/icons-react";
import {
  fetchUsers,
  fetchTenants,
  setTenantId,
  getTenantId,
  getApiBase,
  createScenario,
  createScenarioRun,
  getFeedbackHistory,
  appendScenarioRunLog,
  fetchScenarioRuns,
  updateWorkspace,
  fetchWorkspaceById,
  AuthenticatedEventSource,
  type FeedbackRequest,
  type FeedbackHistoryItem,
  type ScenarioRun,
  type IntentPackage,
  type DataScope,
  type ExecutionResult,
  type TeamConfig,
} from "../../services/graphql";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import ClarificationPanel, {
  type ClarificationQuestion,
  type ClarificationAnswer,
} from "./chat/ClarificationPanel";
import { useStreamingReveal } from "./chat/useStreamingReveal";
import { STREAMING_CONFIG } from "../../config/streaming";
import type { OntologyPackage } from "../../types/ontology";
import DataLoadingProgressBlock from "./chat/DataLoadingProgressBlock";
import { type CsvAnalysisData } from "./chat/CsvAnalysisBlock";

export type AttachedEvent = {
  eventType: string;
  displayLabel: string; // e.g., "Scope Updated"
  message: string;
  timestamp: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "feedback" | "feedback_received";
  content: string;
  timestamp: number;
  feedbackRequest?: FeedbackRequest;
  feedbackType?: "feedback_received" | "feedback_applied" | "feedback_timeout";
  feedbackMessage?: string;
  isComplete?: boolean;
  dataLoadingProgress?: {
    type: "nodes_created" | "relationships_created";
    created: number;
    total?: number;
  };
  csvAnalysis?: CsvAnalysisData;
  attachedEvents?: AttachedEvent[];
};

// Format event_type to display label: "scope_updated" -> "Scope Updated"
function formatEventTypeLabel(eventType: string): string {
  return eventType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Component to display attached events with expand/collapse
function AttachedEventsSection({ events }: { events: AttachedEvent[] }) {
  const [expanded, setExpanded] = React.useState(false);

  if (events.length === 0) return null;

  return (
    <Box sx={{ mt: 1 }}>
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.5,
          cursor: "pointer",
          color: "text.secondary",
          fontSize: "0.75rem",
          "&:hover": { color: "primary.main" },
        }}
      >
        <ExpandMoreIcon
          sx={{
            fontSize: 16,
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        />
        <Typography variant="caption" sx={{ fontWeight: 500 }}>
          {events.length} event{events.length > 1 ? "s" : ""}
        </Typography>
      </Box>
      <Collapse in={expanded}>
        <Box
          sx={{
            mt: 0.5,
            pl: 2,
            borderLeft: "2px solid",
            borderColor: "divider",
          }}
        >
          {events.map((event, idx) => (
            <Box key={idx} sx={{ mb: 0.5 }}>
              <Typography
                variant="caption"
                sx={{ fontWeight: 600, color: "primary.main" }}
              >
                {event.displayLabel}
              </Typography>
              <Typography
                variant="caption"
                sx={{ display: "block", color: "text.secondary" }}
              >
                {event.message}
              </Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export type ChatDockProps = {
  open: boolean;
  onClose: () => void;
  onSubmit: (value: string) => void;
  workspaceId?: string;
  setupRunId?: string;
  initialMessages?: ChatMessage[];
  initialIsAgentWorking?: boolean;
  inputDisabled?: boolean;
  onIntentUpdated?: (intent: string) => void;
  onIntentProposed?: () => void;
  onIntentPackageUpdated?: (
    intentPackage: IntentPackage,
    ready: boolean,
  ) => void;
  onIntentReady?: (intentPackage: IntentPackage) => void;
  onDataScopeUpdated?: (dataScope: DataScope, ready: boolean) => void;
  onScopeReady?: (dataScope: DataScope) => void;
  onExecutionProgress?: (
    entityType: string,
    status: string,
    message?: string,
  ) => void;
  onEntityComplete?: (
    entityType: string,
    nodeIds: string[],
    sampleData: any[],
  ) => void;
  onExecutionComplete?: (results: ExecutionResult[]) => void;
  onExecutionError?: (error: string) => void;
  onTeamBuildingProgress?: (status: string, message?: string) => void;
  onTeamComplete?: (teamConfig: TeamConfig) => void;
  isSetupMode?: boolean;
  fullScreen?: boolean;
  // External clarifications (from setup flow)
  externalClarifications?: ClarificationQuestion[];
  onExternalClarificationSubmit?: (answers: ClarificationAnswer[]) => void;
  // Ontology creation callbacks
  onOntologyProposed?: (ontologyPackage: OntologyPackage) => void;
  onOntologyUpdated?: (ontologyPackage: OntologyPackage, updateSummary?: string) => void;
  onOntologyFinalized?: (ontologyPackage: OntologyPackage) => void;
  // Staged rows context (for including selected data rows as evidence)
  stagedRowsContext?: {
    entityType: string;
    rowCount: number;
    rows: Record<string, unknown>[];
  } | null;
  onClearStagedRows?: () => void;
};

// Helper function to format relative time (e.g., "2d", "1w")
function formatTimeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}d`;
  if (diffWeeks < 4) return `${diffWeeks}w`;
  if (diffMonths < 12) return `${diffMonths}mo`;
  return `${Math.floor(diffDays / 365)}y`;
}

// Helper to parse evidence context from user messages for compact display
// Returns { prompt, evidence } where evidence contains metadata for badge display
// Full content remains in message for agent, this is display-only
type ParsedUserMessage = {
  prompt: string;
  evidence?: { entityType: string; rowCount: string };
};

function parseUserMessageForDisplay(content: string): ParsedUserMessage {
  // Match the evidence block pattern: \n\n---\n**Evidence from X** (Y rows):
  const evidencePattern = /\n\n---\n\*\*Evidence from ([^*]+)\*\* \(([^)]+) rows\):\n\n```[\s\S]*```(?:\n\n_[^_]+_)?$/;
  const match = content.match(evidencePattern);

  if (match) {
    const prompt = content.slice(0, match.index || 0);
    return {
      prompt,
      evidence: {
        entityType: match[1],
        rowCount: match[2],
      },
    };
  }

  return { prompt: content };
}

const TITLE_MAX_CHARS = 20;
const STOP_WORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "for",
  "from",
  "how",
  "i",
  "in",
  "is",
  "it",
  "me",
  "my",
  "of",
  "on",
  "or",
  "please",
  "the",
  "this",
  "to",
  "we",
  "what",
  "when",
  "where",
  "which",
  "with",
  "you",
  "your",
]);

function truncateTitle(value: string, maxChars = TITLE_MAX_CHARS): string {
  const trimmed = value.trim();
  if (trimmed.length <= maxChars) return trimmed;
  const suffix = "...";
  const sliceLength = Math.max(0, maxChars - suffix.length);
  return `${trimmed.slice(0, sliceLength).trimEnd()}${suffix}`;
}

function generateChatTitle(message: string): string {
  const cleaned = message.replace(/[^a-z0-9\s]/gi, " ");
  const tokens = cleaned.split(/\s+/).filter(Boolean);
  const meaningful = tokens.filter(
    (token) => !STOP_WORDS.has(token.toLowerCase()),
  );
  const base = meaningful.length > 0 ? meaningful.join(" ") : tokens.join(" ");
  const truncated = truncateTitle(base, TITLE_MAX_CHARS);
  return truncated || "Chat";
}

// Helper function to parse multiple JSON objects from a string
// Properly handles string boundaries to avoid counting braces/quotes inside strings
const parseJSONEvents = (
  text: string,
): Array<{ json: any; start: number; end: number }> => {
  const events: Array<{ json: any; start: number; end: number }> = [];
  let i = 0;
  let braceCount = 0;
  let start = -1;
  let inString = false;
  let escapeNext = false;

  while (i < text.length) {
    const char = text[i];

    // Handle escape sequences
    if (escapeNext) {
      escapeNext = false;
      i++;
      continue;
    }

    if (char === "\\" && inString) {
      escapeNext = true;
      i++;
      continue;
    }

    // Track string boundaries
    if (char === '"' && !escapeNext) {
      inString = !inString;
      i++;
      continue;
    }

    // Only count braces when not inside a string
    if (!inString) {
      if (char === "{") {
        if (braceCount === 0) {
          start = i;
        }
        braceCount++;
      } else if (char === "}") {
        braceCount--;
        if (braceCount === 0 && start !== -1) {
          try {
            const jsonStr = text.substring(start, i + 1);
            const json = JSON.parse(jsonStr);
            events.push({ json, start, end: i + 1 });
          } catch (e) {
            // Invalid JSON, skip but log for debugging
            const jsonStr = text.substring(start, i + 1);
            console.warn("Failed to parse JSON:", jsonStr.substring(0, 200), e);
          }
          start = -1;
        }
      }
    }

    i++;
  }

  return events;
};

const parseNdjsonWithRemainder = (
  text: string,
): { events: any[]; remainder: string } => {
  const normalized = text.replace(/}\s*{/g, "}\n{");
  const lines = normalized
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 1) {
    return { events: [], remainder: "" };
  }

  const events: any[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.startsWith("{") || !line.endsWith("}")) {
      return { events, remainder: lines.slice(i).join("\n") };
    }
    try {
      events.push(JSON.parse(line));
    } catch (e) {
      return { events, remainder: lines.slice(i).join("\n") };
    }
  }

  return { events, remainder: "" };
};

// Constants for resize
const MIN_WIDTH = 25; // percentage
const MAX_WIDTH = 75; // percentage
const DEFAULT_WIDTH = 25; // percentage
const STORAGE_KEY = "geodesic-chatdock-width";

export default function ChatDock({
  open,
  onClose,
  onSubmit,
  workspaceId,
  setupRunId,
  initialMessages,
  initialIsAgentWorking,
  inputDisabled = false,
  onIntentUpdated,
  onIntentProposed,
  onIntentPackageUpdated,
  onIntentReady,
  onDataScopeUpdated,
  onScopeReady,
  onExecutionProgress,
  onEntityComplete,
  onExecutionComplete,
  onExecutionError,
  onTeamBuildingProgress,
  onTeamComplete,
  onOntologyProposed,
  onOntologyUpdated,
  onOntologyFinalized,
  isSetupMode = false,
  fullScreen = false,
  externalClarifications,
  onExternalClarificationSubmit,
  stagedRowsContext,
  onClearStagedRows,
}: ChatDockProps) {
  const { currentWorkspace, setCurrentWorkspace } = useWorkspace();
  const [value, setValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    // Sort initial messages by timestamp to ensure correct order
    if (initialMessages && initialMessages.length > 0) {
      return [...initialMessages].sort((a, b) => a.timestamp - b.timestamp)
    }
    return []
  });
  const [agentActivity, setAgentActivity] = useState<Map<string, string>>(
    new Map(),
  );
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string>("");
  const [activeFeedbackRequest, setActiveFeedbackRequest] =
    useState<FeedbackRequest | null>(null);
  const [feedbackHistory, setFeedbackHistory] = useState<FeedbackHistoryItem[]>(
    [],
  );
  const [pendingClarifications, setPendingClarifications] = useState<
    ClarificationQuestion[]
  >([]);
  const [showFeedbackHistory, setShowFeedbackHistory] = useState(false);
  const [showAgentActivity, setShowAgentActivity] = useState(false);
  const [isAgentWorking, setIsAgentWorking] = useState(
    initialIsAgentWorking || false,
  );
  const [isTurnOpen, setIsTurnOpen] = useState(false);
  const [scenarioRuns, setScenarioRuns] = useState<ScenarioRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyAnchorRef = useRef<HTMLButtonElement | null>(null);
  const [chatTitles, setChatTitles] = useState<Record<string, string>>({});

  // Resize state
  const [width, setWidth] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? parseInt(saved, 10) : DEFAULT_WIDTH;
  });
  const [isResizing, setIsResizing] = useState(false);

  // Merge internal and external clarifications
  // External clarifications come from props (setup flow), internal from SSE events
  const allClarifications = React.useMemo(() => {
    const internal = pendingClarifications || [];
    const external = externalClarifications || [];

    // Combine and deduplicate by question_id
    const combined = [...external, ...internal];
    const seen = new Set<string>();
    return combined.filter((q) => {
      if (seen.has(q.question_id)) return false;
      seen.add(q.question_id);
      return true;
    });
  }, [pendingClarifications, externalClarifications]);

  const lastEventIdRef = useRef<string | null>(null);
  const esRef = useRef<AuthenticatedEventSource | null>(null);
  const streamBufferRef = useRef<string>("");
  const processedEventsRef = useRef<Set<string>>(new Set());
  const activeAgentsRef = useRef<Set<string>>(new Set());
  const eventSequenceRef = useRef<number>(0);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef<boolean>(true);
  const scrollRafRef = useRef<number | null>(null);
  const [showScrollFab, setShowScrollFab] = useState(false);
  const previousMessageCountRef = useRef<number>(0);
  const processedIntentEventsRef = useRef<Set<string>>(new Set());
  const isUpdatingIntentRef = useRef<boolean>(false);
  const closedMessageIdsRef = useRef<Set<string>>(new Set());
  const openMessageIdsRef = useRef<Set<string>>(new Set());
  const isInputDisabled = isSetupMode
    ? Boolean(sending || inputDisabled)
    : Boolean(sending || isTurnOpen || isAgentWorking || inputDisabled);
  // In setup mode, use initialMessages directly (parent is source of truth).
  // This avoids recreating message objects which breaks streaming animation state.
  const effectiveMessages = useMemo(
    () =>
      isSetupMode
        ? initialMessages || []
        : messages.length === 0 && initialMessages && initialMessages.length > 0
          ? initialMessages
          : messages,
    [isSetupMode, initialMessages, messages],
  );

  const handleToggleHistory = () => {
    setHistoryOpen((prev) => !prev);
  };

  const handleCloseHistory = () => {
    setHistoryOpen(false);
  };

  useEffect(() => {
    if (!historyOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setHistoryOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [historyOpen]);

  const renderPastChats = () => {
    if (loadingRuns) {
      return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 1 }}>
          <CircularProgress size={16} />
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontSize: 13 }}
          >
            Loading...
          </Typography>
        </Box>
      );
    }

    if (scenarioRuns.length === 0) {
      return (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ fontSize: 13, py: 1 }}
        >
          No past chats
        </Typography>
      );
    }

    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 0.75,
          maxHeight: 200,
          overflowY: "auto",
        }}
      >
        {scenarioRuns.map((run) => {
          const isSelected = selectedRunId === run.runId;
          const title =
            chatTitles[run.runId] || generateChatTitle(run.title || "");
          return (
            <Box
              key={run.runId}
              onClick={() => {
                handleSelectChat(run);
                setChatTitles((prev) => ({
                  ...prev,
                  [run.runId]: title,
                }));
                setHistoryOpen(false);
              }}
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: 13,
                cursor: "pointer",
                px: 1,
                py: 0.75,
                borderRadius: 0.5,
                bgcolor: isSelected ? "action.selected" : "transparent",
                "&:hover": {
                  bgcolor: isSelected ? "action.selected" : "action.hover",
                },
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontWeight: isSelected ? 600 : 400,
                  color: isSelected ? "primary.main" : "text.primary",
                }}
              >
                {title || `Run ${run.runId.slice(0, 8)}`}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatTimeAgo(run.startedAt)}
              </Typography>
            </Box>
          );
        })}
      </Box>
    );
  };
  const ndjsonRemainderRef = useRef<string>("");

  // Streaming reveal animation for smooth text appearance
  const { getDisplayedText, isStreaming, setCompleted, tick } =
    useStreamingReveal({
      onProgress: () => {
        // Trigger scroll on animation progress
        if (shouldAutoScrollRef.current && messagesEndRef.current) {
          if (scrollRafRef.current !== null) {
            cancelAnimationFrame(scrollRafRef.current);
          }
          scrollRafRef.current = requestAnimationFrame(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
            scrollRafRef.current = null;
          });
        }
      },
      revealCharsPerFrame: STREAMING_CONFIG.revealCharsPerFrame,
      settleDelayMs: STREAMING_CONFIG.settleDelayMs,
    });
  // tick is used implicitly to trigger re-renders during streaming animation
  void tick;

  const handleStreamProgress = useCallback(() => {
    if (!shouldAutoScrollRef.current || !messagesEndRef.current) return;
    // Debounce scroll - cancel any pending scroll and schedule a new one
    if (scrollRafRef.current !== null) {
      cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      scrollRafRef.current = null;
    });
  }, []);

  // Auto-scroll when messages update (text appears directly as SSE chunks arrive)
  // Only auto-scroll if:
  // 1. New messages were actually added (count increased)
  // 2. Agent is still working (streaming new content)
  // 3. User is near bottom (shouldAutoScrollRef is true)
  useEffect(() => {
    const currentCount = effectiveMessages.length;
    const hasNewMessages = currentCount > previousMessageCountRef.current;
    const shouldScroll = hasNewMessages || isAgentWorking;
    
    if (shouldScroll) {
      handleStreamProgress();
    }
    
    previousMessageCountRef.current = currentCount;
  }, [effectiveMessages, isAgentWorking, handleStreamProgress]);

  // Mark completed messages in the streaming reveal hook
  useEffect(() => {
    for (const m of effectiveMessages) {
      if (m.role === "assistant" && m.isComplete) {
        setCompleted(m.id);
      }
    }
  }, [effectiveMessages, setCompleted]);

  // Check if we're in the initial welcome state (no messages yet)
  const isInitialWelcome = isSetupMode && effectiveMessages.length === 0;

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (scrollRafRef.current !== null) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  // Save width to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, width.toString());
  }, [width]);

  // In setup mode, we use initialMessages directly via effectiveMessages (controlled component).
  // No sync needed - parent (useChatStream) is the source of truth.

  // In normal mode, initialize from `initialMessages` only once when empty.
  useEffect(() => {
    if (isSetupMode) return;
    if (
      initialMessages &&
      initialMessages.length > 0 &&
      messages.length === 0
    ) {
      console.log(
        "[ChatDock] Initializing messages from initialMessages:",
        initialMessages.length,
      );
      // Sort messages by timestamp to ensure correct order
      setMessages([...initialMessages].sort((a, b) => a.timestamp - b.timestamp));
    }
  }, [initialMessages, isSetupMode, messages.length]);

  // Sync initialIsAgentWorking when it changes
  useEffect(() => {
    if (initialIsAgentWorking !== undefined) {
      setIsAgentWorking(initialIsAgentWorking);
    }
  }, [initialIsAgentWorking]);

  // Load scenario runs when workspaceId changes
  useEffect(() => {
    if (!workspaceId) {
      setScenarioRuns([]);
      return;
    }

    const wsId = workspaceId; // TypeScript narrowing
    let mounted = true;
    async function loadRuns() {
      setLoadingRuns(true);
      try {
        const runs = await fetchScenarioRuns(wsId);
        if (!mounted) return;
        // Sort by startedAt descending (most recent first)
        const sorted = runs.sort(
          (a, b) =>
            new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
        );
        setScenarioRuns(sorted);
      } catch (e: any) {
        if (!mounted) return;
        console.error("Error loading scenario runs:", e);
      } finally {
        if (mounted) setLoadingRuns(false);
      }
    }
    loadRuns();
    return () => {
      mounted = false;
    };
  }, [workspaceId]);

  // Load feedback history when runId changes
  useEffect(() => {
    if (!runId) return;

    const loadHistory = async () => {
      try {
        const history = await getFeedbackHistory(runId);
        setFeedbackHistory(history);
      } catch (error) {
        console.error("Error loading feedback history:", error);
      }
    };

    loadHistory();
  }, [runId]);

  // Track scroll position to determine if we should auto-scroll and show FAB
  const handleScroll = useCallback(() => {
    if (!messagesContainerRef.current) return;
    const container = messagesContainerRef.current;
    const { scrollTop, scrollHeight, clientHeight } = container;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const isNearBottom = distanceFromBottom < 100;
    // If user is within 100px of bottom, enable auto-scroll and hide FAB
    shouldAutoScrollRef.current = isNearBottom;
    setShowScrollFab(!isNearBottom);
  }, []);

  // Scroll to bottom function (for FAB click)
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    setShowScrollFab(false);
    shouldAutoScrollRef.current = true;
  }, []);

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidthPx = window.innerWidth - e.clientX;
      const newWidthPercent = (newWidthPx / window.innerWidth) * 100;
      const constrainedWidth = Math.min(
        Math.max(newWidthPercent, MIN_WIDTH),
        MAX_WIDTH,
      );
      setWidth(constrainedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  const startStream = useCallback(
    (rid: string, tenantId: string, preserveMessages: boolean = false) => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      lastEventIdRef.current = null;
      streamBufferRef.current = "";
      processedEventsRef.current = new Set();
      processedIntentEventsRef.current = new Set();
      eventSequenceRef.current = 0; // Reset sequence counter for new stream
      setAgentActivity(new Map());
      closedMessageIdsRef.current = new Set();
      openMessageIdsRef.current = new Set();
      setIsTurnOpen(false);
      ndjsonRemainderRef.current = "";
      if (!preserveMessages) {
        setIsAgentWorking(false);
        activeAgentsRef.current = new Set();
        setMessages([]);
      }
      isUpdatingIntentRef.current = false;
      const apiBase = getApiBase().replace(/\/$/, "");
      const url = `${apiBase}/runs/${rid}/events?tid=${encodeURIComponent(
        tenantId,
      )}`;
      const es = new AuthenticatedEventSource(url);
      es.onmessage = (evt) => {
        if (evt.lastEventId && evt.lastEventId === lastEventIdRef.current)
          return;
        lastEventIdRef.current = evt.lastEventId || lastEventIdRef.current;
        let text = evt.data ?? "";
        if (!text) return;

        // Debug: log incoming data
        console.log("EventSource data received:", text);

        const timestamp = Date.now();

        // Parse all JSON events from the text
        const combinedText = `${ndjsonRemainderRef.current}${text}`;
        const { events: ndjsonEvents, remainder } =
          parseNdjsonWithRemainder(combinedText);
        ndjsonRemainderRef.current = remainder;
        let jsonEvents = ndjsonEvents;
        if (jsonEvents.length === 0) {
          jsonEvents = parseJSONEvents(combinedText);
          if (jsonEvents.length > 0) {
            ndjsonRemainderRef.current = "";
          }
        }
        console.log("Parsed JSON events:", jsonEvents.length, jsonEvents);

        // Process each JSON event
        if (jsonEvents.length > 0) {
          jsonEvents.forEach((event, index) => {
            // Handle both formats: direct object or { json: ... } wrapper
            const jsonData = event.json !== undefined ? event.json : event;
            if (!jsonData.event_type) {
              console.warn("JSON event missing event_type:", jsonData);
              return;
            }

            const eventType = jsonData.event_type;
            // Increment sequence counter for chronological ordering
            eventSequenceRef.current += 1;
            const sequence = eventSequenceRef.current;
            // Make event ID more unique by including index and sequence
            const eventId = `${eventType}-${jsonData.agent_id || "unknown"}-${
              jsonData.subtask_id || "main"
            }-${timestamp}-${index}-${sequence}`;

            // Skip if we've already processed this event
            if (processedEventsRef.current.has(eventId)) {
              console.log("Skipping duplicate event:", eventId);
              return;
            }
            processedEventsRef.current.add(eventId);
            console.log("Processing event:", eventType, jsonData);

            // Handle different event types
            // Use base timestamp + sequence for stable, chronological ordering
            const eventTimestamp = timestamp + sequence / 1000000; // Add sequence as microsecond offset for stable ordering

            if (
              eventType === "task_decomposed" ||
              eventType === "subtask_assigned"
            ) {
              // Show these events as assistant messages in chat
              setMessages((prev) => {
                const messageId = `event-${eventId}`;
                if (prev.some((m) => m.id === messageId)) return prev;

                return [
                  ...prev,
                  {
                    id: messageId,
                    role: "assistant" as const,
                    content: jsonData.message || "",
                    timestamp: eventTimestamp,
                  },
                ].sort((a, b) => a.timestamp - b.timestamp);
              });
            } else if (
              eventType === "feedback_r" ||
              eventType === "feedback_requested"
            ) {
              // Parse feedback request message to extract subtasks if present
              const message = jsonData.message || "";
              const subtasks: Array<{
                id: string;
                description: string;
                agent_id: string;
              }> = [];

              // Try to extract subtasks from message (format: "agent_id: description")
              const lines = message.split("\n");
              for (const line of lines) {
                const match = line.match(/^([^:]+):\s*(.+)$/);
                if (match) {
                  subtasks.push({
                    id: `subtask-${subtasks.length}`,
                    description: match[2].trim(),
                    agent_id: match[1].trim(),
                  });
                }
              }

              const feedbackRequest: FeedbackRequest = {
                id: jsonData.id || `fb-${eventTimestamp}`,
                runId: rid,
                checkpoint: jsonData.checkpoint || "unknown",
                message: message,
                options: jsonData.options,
                metadata: {
                  subtasks: subtasks.length > 0 ? subtasks : undefined,
                  ...jsonData.metadata,
                },
              };
              setActiveFeedbackRequest(feedbackRequest);

              // Add feedback requested message to chat
              setMessages((prev) => {
                const messageId = `event-${eventId}`;
                if (prev.some((m) => m.id === messageId)) return prev;

                return [
                  ...prev,
                  {
                    id: messageId,
                    role: "assistant" as const,
                    content: message || "Feedback requested",
                    timestamp: eventTimestamp,
                  },
                ].sort((a, b) => a.timestamp - b.timestamp);
              });
            } else if (eventType === "task_completed") {
              // Skip task_completed messages - do not display in chat
              // Clear active agents when task is completed
              activeAgentsRef.current.clear();
              setIsAgentWorking(false);
            } else if (eventType === "feedback_received") {
              // Insert feedback received card
              setMessages((prev) => {
                const feedbackId = `feedback-received-${eventTimestamp}`;
                if (prev.some((m) => m.id === feedbackId)) return prev;

                return [
                  ...prev,
                  {
                    id: feedbackId,
                    role: "feedback_received" as const,
                    content: "",
                    timestamp: eventTimestamp,
                    feedbackType: "feedback_received" as const,
                    feedbackMessage: jsonData.message || "",
                  },
                ].sort((a, b) => a.timestamp - b.timestamp);
              });
            } else if (eventType === "user_message") {
              // Add user message to chat
              setMessages((prev) => {
                const messageId = `event-${eventId}`;
                if (prev.some((m) => m.id === messageId)) return prev;

                // Also check for duplicate content (handles optimistic updates)
                const content = jsonData.message || "";
                const alreadyExists = prev.some(
                  (m) => m.role === "user" && m.content === content,
                );
                if (alreadyExists) {
                  return prev;
                }

                return [
                  ...prev,
                  {
                    id: messageId,
                    role: "user" as const,
                    content,
                    timestamp: eventTimestamp,
                  },
                ].sort((a, b) => a.timestamp - b.timestamp);
              });
            } else if (eventType === "agent_message") {
              // Handle multipart agent messages - group by message_id and append content
              setMessages((prev) => {
                const serverMessageId = jsonData.message_id;
                const isComplete = jsonData.completed === true;
                // Use message_id from server if available, otherwise fallback to eventId for backward compatibility
                const messageId = serverMessageId
                  ? `agent-message-${serverMessageId}`
                  : `event-${eventId}`;

                if (closedMessageIdsRef.current.has(messageId) && !isComplete) {
                  return prev;
                }

                openMessageIdsRef.current.add(messageId);
                setIsTurnOpen(openMessageIdsRef.current.size > 0);

                const existingIndex = prev.findIndex((m) => m.id === messageId);
                if (existingIndex >= 0) {
                  // Append to existing message
                  const updated = [...prev];
                  updated[existingIndex] = {
                    ...updated[existingIndex],
                    content:
                      updated[existingIndex].content + (jsonData.message || ""),
                    isComplete: updated[existingIndex].isComplete || isComplete,
                  };

                  if (isComplete) {
                    closedMessageIdsRef.current.add(messageId);
                    openMessageIdsRef.current.delete(messageId);
                    setIsTurnOpen(openMessageIdsRef.current.size > 0);
                  }

                  return updated.sort((a, b) => a.timestamp - b.timestamp);
                } else {
                  // Create new message
                  if (isComplete) {
                    closedMessageIdsRef.current.add(messageId);
                    openMessageIdsRef.current.delete(messageId);
                    setIsTurnOpen(openMessageIdsRef.current.size > 0);
                  }

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message || "",
                      timestamp: eventTimestamp,
                      isComplete: isComplete,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                }
              });
            } else if (eventType === "workflow_stage") {
              // Skip workflow_stage messages - do not display in chat
            } else if (
              eventType === "agent_thinking" ||
              eventType === "tool_called" ||
              eventType === "agent_completed" ||
              eventType === "memory_retrieved"
            ) {
              // Update agent activity
              const agentId = jsonData.agent_id || "unknown";
              setAgentActivity((prev) => {
                const updated = new Map(prev);
                const current = updated.get(agentId) || "";
                const newContent = jsonData.message || "";
                updated.set(
                  agentId,
                  current ? `${current}\n${newContent}` : newContent,
                );
                return updated;
              });

              // Track active agents for thinking indicator
              if (
                eventType === "agent_thinking" ||
                eventType === "tool_called"
              ) {
                activeAgentsRef.current.add(agentId);
                setIsAgentWorking(true);
              } else if (eventType === "agent_completed") {
                activeAgentsRef.current.delete(agentId);
                // Only set to false if no other agents are active
                if (activeAgentsRef.current.size === 0) {
                  setIsAgentWorking(false);
                }
              }
            } else if (
              eventType === "intent_proposed" ||
              eventType === "intent_finalized"
            ) {
              // Handle intent events from Theo
              if (
                jsonData.agent_id === "theo" &&
                jsonData.intent_text &&
                workspaceId
              ) {
                // Turn off agent working indicator when intent is proposed
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);

                // Create a unique key for this intent event (using intent_text hash to avoid duplicates)
                const intentHash = `${eventType}-${jsonData.intent_text.substring(
                  0,
                  50,
                )}-${timestamp}`;

                // Skip if we've already processed this exact intent update
                if (processedIntentEventsRef.current.has(intentHash)) {
                  console.log("Skipping duplicate intent event:", intentHash);
                  return;
                }

                // Skip if we're already updating the intent
                if (isUpdatingIntentRef.current) {
                  console.log("Intent update already in progress, skipping");
                  return;
                }

                // Check if intent has actually changed
                const currentIntent = currentWorkspace?.intent || "";
                const intentText = jsonData.intent_text;

                if (currentIntent.trim() === intentText.trim()) {
                  console.log("Intent unchanged, skipping update");
                  processedIntentEventsRef.current.add(intentHash);
                  return;
                }

                // Mark as processing
                isUpdatingIntentRef.current = true;
                processedIntentEventsRef.current.add(intentHash);

                // Notify parent about intent_proposed event
                if (eventType === "intent_proposed" && onIntentProposed) {
                  onIntentProposed();
                }

                // Update workspace intent via GraphQL
                updateWorkspace({
                  workspaceId,
                  intent: intentText,
                })
                  .then(() => {
                    // Reload workspace to get updated data
                    return fetchWorkspaceById(workspaceId);
                  })
                  .then((updatedWorkspace) => {
                    if (updatedWorkspace) {
                      // Only update if intent actually changed
                      if (updatedWorkspace.intent !== currentIntent) {
                        // Update workspace context
                        setCurrentWorkspace(updatedWorkspace);
                        // Notify parent component if callback provided
                        if (onIntentUpdated) {
                          onIntentUpdated(intentText);
                        }
                      }
                    }
                  })
                  .catch((error) => {
                    console.error("Failed to update workspace intent:", error);
                    // Remove from processed set on error so we can retry
                    processedIntentEventsRef.current.delete(intentHash);
                  })
                  .finally(() => {
                    isUpdatingIntentRef.current = false;
                  });

                // Also add message to chat
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content:
                        jsonData.message ||
                        `Intent ${
                          eventType === "intent_finalized"
                            ? "finalized"
                            : "proposed"
                        }`,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "intent_updated") {
              // Handle intent_updated event (workspace setup flow)
              if (jsonData.intent_package && onIntentPackageUpdated) {
                const ready = jsonData.ready || false;
                onIntentPackageUpdated(jsonData.intent_package, ready);
                console.log("[ChatDock] Intent package updated, ready:", ready);
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "intent_ready") {
              // Handle intent_ready event (workspace setup flow)
              if (jsonData.intent_package && onIntentReady) {
                onIntentReady(jsonData.intent_package);
                console.log("[ChatDock] Intent is ready!");

                // Turn off agent working indicator
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "scope_updated" || eventType === "scope_update") {
              // Handle scope_updated/scope_update events (data scoping stage)
              // ready flag indicates scope is finalized and user can proceed
              if (jsonData.data_scope && onDataScopeUpdated) {
                const ready = jsonData.ready === true;
                onDataScopeUpdated(jsonData.data_scope, ready);
                console.log("[ChatDock] Data scope updated, ready:", ready);

                // If ready, also call onScopeReady for backward compatibility
                if (ready && onScopeReady) {
                  onScopeReady(jsonData.data_scope);
                  activeAgentsRef.current.clear();
                  setIsAgentWorking(false);
                }
              }
              // Attach event to the most recent assistant message (expandable display)
              if (jsonData.message) {
                setMessages((prev) => {
                  // Find the last assistant message
                  const lastAssistantIdx = [...prev]
                    .reverse()
                    .findIndex((m) => m.role === "assistant");
                  if (lastAssistantIdx === -1) return prev;
                  const actualIdx = prev.length - 1 - lastAssistantIdx;

                  const attachedEvent: AttachedEvent = {
                    eventType,
                    displayLabel: formatEventTypeLabel(eventType),
                    message: jsonData.message,
                    timestamp: eventTimestamp,
                  };

                  const updated = [...prev];
                  updated[actualIdx] = {
                    ...updated[actualIdx],
                    attachedEvents: [
                      ...(updated[actualIdx].attachedEvents || []),
                      attachedEvent,
                    ],
                  };
                  return updated;
                });
              }
            } else if (eventType === "scope_ready") {
              // Handle scope_ready event (data scoping stage)
              if (jsonData.data_scope && onScopeReady) {
                onScopeReady(jsonData.data_scope);
                console.log("[ChatDock] Data scope is ready!");

                // Turn off agent working indicator
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);
              }
              // Attach event to the most recent assistant message (expandable display)
              if (jsonData.message) {
                setMessages((prev) => {
                  // Find the last assistant message
                  const lastAssistantIdx = [...prev]
                    .reverse()
                    .findIndex((m) => m.role === "assistant");
                  if (lastAssistantIdx === -1) return prev;
                  const actualIdx = prev.length - 1 - lastAssistantIdx;

                  const attachedEvent: AttachedEvent = {
                    eventType,
                    displayLabel: formatEventTypeLabel(eventType),
                    message: jsonData.message,
                    timestamp: eventTimestamp,
                  };

                  const updated = [...prev];
                  updated[actualIdx] = {
                    ...updated[actualIdx],
                    attachedEvents: [
                      ...(updated[actualIdx].attachedEvents || []),
                      attachedEvent,
                    ],
                  };
                  return updated;
                });
              }
            } else if (eventType === "execution_progress") {
              // Handle execution_progress event (data review stage)
              if (onExecutionProgress && jsonData.entity_type) {
                onExecutionProgress(
                  jsonData.entity_type,
                  jsonData.status || "in_progress",
                  jsonData.message,
                );
                console.log(
                  "[ChatDock] Execution progress:",
                  jsonData.entity_type,
                  jsonData.status,
                );
              }
            } else if (eventType === "entity_complete") {
              // Handle entity_complete event (data review stage)
              if (onEntityComplete && jsonData.entity_type) {
                onEntityComplete(
                  jsonData.entity_type,
                  jsonData.node_ids || [],
                  jsonData.sample_data || [],
                );
                console.log(
                  "[ChatDock] Entity complete:",
                  jsonData.entity_type,
                  "nodes:",
                  jsonData.node_ids?.length,
                );
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "execution_complete") {
              // Handle execution_complete event (data review stage)
              if (onExecutionComplete && jsonData.results) {
                onExecutionComplete(jsonData.results);
                console.log(
                  "[ChatDock] Execution complete! Results:",
                  jsonData.results.length,
                );

                // Turn off agent working indicator
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "execution_error") {
              // Handle execution_error event (data review stage)
              if (onExecutionError && jsonData.error) {
                onExecutionError(jsonData.error);
                console.error("[ChatDock] Execution error:", jsonData.error);

                // Turn off agent working indicator
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);
              }
              // Add error message to chat
              if (jsonData.error || jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message || `Error: ${jsonData.error}`,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "team_building_progress") {
              // Handle team_building_progress event (team building stage)
              if (onTeamBuildingProgress) {
                onTeamBuildingProgress(
                  jsonData.status || "in_progress",
                  jsonData.message,
                );
                console.log(
                  "[ChatDock] Team building progress:",
                  jsonData.status,
                );
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "team_complete") {
              // Handle team_complete event (team building stage)
              if (onTeamComplete && jsonData.team_config) {
                onTeamComplete(jsonData.team_config);
                console.log(
                  "[ChatDock] Team building complete! Agents:",
                  jsonData.team_config.agents?.length,
                );

                // Turn off agent working indicator
                activeAgentsRef.current.clear();
                setIsAgentWorking(false);
              }
              // Add message to chat if provided
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (eventType === "clarification_needed") {
              // Handle clarification_needed event (data scoping stage)
              console.log("[ChatDock] Clarification needed:", jsonData);

              // Turn off agent working indicator while waiting for user input
              activeAgentsRef.current.clear();
              setIsAgentWorking(false);

              // Build the clarification question from the event
              const clarificationQuestion: ClarificationQuestion = {
                question_id:
                  jsonData.question_id || `clarification-${eventTimestamp}`,
                question:
                  jsonData.question || jsonData.message || "Please clarify",
                context: jsonData.context,
                options: jsonData.options || [],
                affects_entities: jsonData.affects_entities,
                agent_id: jsonData.agent_id,
                stage: jsonData.stage,
              };

              // Add to pending clarifications (queue multiple questions)
              setPendingClarifications((prev) => {
                // Avoid duplicate questions
                if (
                  prev.some(
                    (q) => q.question_id === clarificationQuestion.question_id,
                  )
                ) {
                  return prev;
                }
                return [...prev, clarificationQuestion];
              });

              // Add message to chat showing the clarification request
              if (jsonData.message) {
                setMessages((prev) => {
                  const messageId = `event-${eventId}`;
                  if (prev.some((m) => m.id === messageId)) return prev;

                  return [
                    ...prev,
                    {
                      id: messageId,
                      role: "assistant" as const,
                      content: jsonData.message,
                      timestamp: eventTimestamp,
                    },
                  ].sort((a, b) => a.timestamp - b.timestamp);
                });
              }
            } else if (
              eventType === "ontology_proposed" ||
              eventType === "ontology_updated" ||
              eventType === "ontology_finalized"
            ) {
              // Handle ontology events
              console.log("[ChatDock] Ontology event:", eventType, jsonData);
              // ontology_package can be at top level or in metadata
              const ontologyPackage = jsonData.ontology_package || jsonData.metadata?.ontology_package;
              
              if (ontologyPackage) {
                if (eventType === "ontology_proposed" && onOntologyProposed) {
                  onOntologyProposed(ontologyPackage);
                  activeAgentsRef.current.clear();
                  setIsAgentWorking(false);
                } else if (eventType === "ontology_updated" && onOntologyUpdated) {
                  const updateSummary = jsonData.update_summary || jsonData.metadata?.update_summary;
                  onOntologyUpdated(ontologyPackage, updateSummary);
                } else if (eventType === "ontology_finalized" && onOntologyFinalized) {
                  onOntologyFinalized(ontologyPackage);
                  activeAgentsRef.current.clear();
                  setIsAgentWorking(false);
                }
              }
            } else if (eventType === "workflow_started") {
              // Handle workflow_started event (for ontology creation workflow)
              console.log("[ChatDock] Workflow started:", jsonData);
              setIsAgentWorking(true);
            } else if (eventType === "workflow_complete") {
              // Handle workflow_complete event
              console.log("[ChatDock] Workflow complete:", jsonData);
              activeAgentsRef.current.clear();
              setIsAgentWorking(false);
            } else if (eventType === "workflow_error") {
              // Handle workflow_error event
              console.error("[ChatDock] Workflow error:", jsonData);
              const errorMessage = jsonData.message || jsonData.error || "An error occurred in the workflow";
              activeAgentsRef.current.clear();
              setIsAgentWorking(false);
              setIsTurnOpen(false);
              // Add error message to chat
              setMessages((prev) => {
                const messageId = `workflow-error-${eventId}`;
                if (prev.some((m) => m.id === messageId)) return prev;
                return [
                  ...prev,
                  {
                    id: messageId,
                    role: "assistant" as const,
                    content: `**Error:** ${errorMessage}`,
                    timestamp: eventTimestamp,
                  },
                ].sort((a, b) => a.timestamp - b.timestamp);
              });
            }
            // Continue processing other events...
          });
        } else {
          // No JSON events found - try parsing as single JSON object
          console.log(
            "No JSON events found in text, trying single parse:",
            text.substring(0, 100),
          );
          try {
            const singleJson = JSON.parse(text);
            if (singleJson.event_type) {
              console.log("Found single JSON event:", singleJson.event_type);
              const eventType = singleJson.event_type;
              // Increment sequence counter for chronological ordering
              eventSequenceRef.current += 1;
              const sequence = eventSequenceRef.current;
              const eventId = `${eventType}-${
                singleJson.agent_id || "unknown"
              }-${
                singleJson.subtask_id || "main"
              }-${timestamp}-single-${sequence}`;

              if (!processedEventsRef.current.has(eventId)) {
                processedEventsRef.current.add(eventId);
                // Use base timestamp + sequence for stable, chronological ordering
                const eventTimestamp = timestamp + sequence / 1000000; // Add sequence as microsecond offset for stable ordering

                // Handle event types inline (same logic as in forEach above)
                if (
                  eventType === "task_decomposed" ||
                  eventType === "subtask_assigned"
                ) {
                  setMessages((prev) => {
                    const messageId = `event-${eventId}`;
                    if (prev.some((m) => m.id === messageId)) return prev;

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "assistant" as const,
                        content: singleJson.message || "",
                        timestamp: eventTimestamp,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (eventType === "feedback_requested") {
                  const message = singleJson.message || "";
                  const subtasks: Array<{
                    id: string;
                    description: string;
                    agent_id: string;
                  }> = [];
                  const lines = message.split("\n");
                  for (const line of lines) {
                    const match = line.match(/^([^:]+):\s*(.+)$/);
                    if (match) {
                      subtasks.push({
                        id: `subtask-${subtasks.length}`,
                        description: match[2].trim(),
                        agent_id: match[1].trim(),
                      });
                    }
                  }
                  const feedbackRequest: FeedbackRequest = {
                    id: singleJson.id || `fb-${eventTimestamp}`,
                    runId: rid,
                    checkpoint: singleJson.checkpoint || "unknown",
                    message: message,
                    options: singleJson.options,
                    metadata: {
                      subtasks: subtasks.length > 0 ? subtasks : undefined,
                      ...singleJson.metadata,
                    },
                  };
                  setActiveFeedbackRequest(feedbackRequest);

                  // Add feedback requested message to chat
                  setMessages((prev) => {
                    const messageId = `event-${eventId}`;
                    if (prev.some((m) => m.id === messageId)) return prev;

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "assistant" as const,
                        content: message || "Feedback requested",
                        timestamp: eventTimestamp,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (eventType === "task_completed") {
                  // Add task completed message to chat - show result if available, otherwise message
                  setMessages((prev) => {
                    const messageId = `event-${eventId}`;
                    if (prev.some((m) => m.id === messageId)) return prev;

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "assistant" as const,
                        content:
                          singleJson.result ||
                          singleJson.message ||
                          "Task completed",
                        timestamp: eventTimestamp,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                  // Clear active agents when task is completed
                  activeAgentsRef.current.clear();
                  setIsAgentWorking(false);
                } else if (eventType === "feedback_received") {
                  setMessages((prev) => {
                    const feedbackId = `feedback-received-${eventTimestamp}`;
                    if (prev.some((m) => m.id === feedbackId)) return prev;

                    return [
                      ...prev,
                      {
                        id: feedbackId,
                        role: "feedback_received" as const,
                        content: "",
                        timestamp: eventTimestamp,
                        feedbackType: "feedback_received" as const,
                        feedbackMessage: singleJson.message || "",
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (eventType === "user_message") {
                  // Add user message to chat
                  setMessages((prev) => {
                    const messageId = `event-${eventId}`;
                    if (prev.some((m) => m.id === messageId)) return prev;

                    // Also check for duplicate content (handles optimistic updates)
                    const content = singleJson.message || "";
                    const alreadyExists = prev.some(
                      (m) => m.role === "user" && m.content === content,
                    );
                    if (alreadyExists) {
                      return prev;
                    }

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "user" as const,
                        content,
                        timestamp: eventTimestamp,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (eventType === "agent_message") {
                  // Handle multipart agent messages - group by message_id and append content
                  setMessages((prev) => {
                    const serverMessageId = singleJson.message_id;
                    const newContent = singleJson.message || "";
                    const isComplete = singleJson.completed === true;
                    // Use message_id from server if available, otherwise fallback to eventId for backward compatibility
                    const messageId = serverMessageId
                      ? `agent-message-${serverMessageId}`
                      : `event-${eventId}`;

                    if (
                      closedMessageIdsRef.current.has(messageId) &&
                      !isComplete
                    ) {
                      return prev;
                    }

                    openMessageIdsRef.current.add(messageId);
                    setIsTurnOpen(openMessageIdsRef.current.size > 0);

                    const existingIndex = prev.findIndex(
                      (m) => m.id === messageId,
                    );
                    if (existingIndex >= 0) {
                      // Append to existing message
                      const updated = [...prev];
                      updated[existingIndex] = {
                        ...updated[existingIndex],
                        content: updated[existingIndex].content + newContent,
                        isComplete:
                          updated[existingIndex].isComplete || isComplete,
                      };

                      if (isComplete) {
                        closedMessageIdsRef.current.add(messageId);
                        openMessageIdsRef.current.delete(messageId);
                        setIsTurnOpen(openMessageIdsRef.current.size > 0);
                      }

                      return updated.sort((a, b) => a.timestamp - b.timestamp);
                    }

                    // Otherwise, create a new message
                    if (prev.some((m) => m.id === messageId)) return prev;

                    if (isComplete) {
                      closedMessageIdsRef.current.add(messageId);
                      openMessageIdsRef.current.delete(messageId);
                      setIsTurnOpen(openMessageIdsRef.current.size > 0);
                    }

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "assistant" as const,
                        content: newContent,
                        timestamp: eventTimestamp,
                        isComplete: isComplete,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (eventType === "workflow_stage") {
                  // Add workflow stage message to chat
                  setMessages((prev) => {
                    const messageId = `event-${eventId}`;
                    if (prev.some((m) => m.id === messageId)) return prev;

                    return [
                      ...prev,
                      {
                        id: messageId,
                        role: "assistant" as const,
                        content: singleJson.message || "",
                        timestamp: eventTimestamp,
                      },
                    ].sort((a, b) => a.timestamp - b.timestamp);
                  });
                } else if (
                  eventType === "agent_thinking" ||
                  eventType === "tool_called" ||
                  eventType === "agent_completed" ||
                  eventType === "memory_retrieved"
                ) {
                  const agentId = singleJson.agent_id || "unknown";
                  setAgentActivity((prev) => {
                    const updated = new Map(prev);
                    const current = updated.get(agentId) || "";
                    const newContent = singleJson.message || "";
                    updated.set(
                      agentId,
                      current ? `${current}\n${newContent}` : newContent,
                    );
                    return updated;
                  });

                  // Track active agents for thinking indicator
                  if (
                    eventType === "agent_thinking" ||
                    eventType === "tool_called"
                  ) {
                    activeAgentsRef.current.add(agentId);
                    setIsAgentWorking(true);
                  } else if (eventType === "agent_completed") {
                    activeAgentsRef.current.delete(agentId);
                    // Only set to false if no other agents are active
                    if (activeAgentsRef.current.size === 0) {
                      setIsAgentWorking(false);
                    }
                  }
                } else if (
                  eventType === "intent_proposed" ||
                  eventType === "intent_finalized"
                ) {
                  // Handle intent events from Theo
                  if (
                    singleJson.agent_id === "theo" &&
                    singleJson.intent_text &&
                    workspaceId
                  ) {
                    // Turn off agent working indicator when intent is proposed
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);

                    // Create a unique key for this intent event (using intent_text hash to avoid duplicates)
                    const intentHash = `${eventType}-${singleJson.intent_text.substring(
                      0,
                      50,
                    )}-${timestamp}`;

                    // Skip if we've already processed this exact intent update
                    if (processedIntentEventsRef.current.has(intentHash)) {
                      console.log(
                        "Skipping duplicate intent event:",
                        intentHash,
                      );
                      return;
                    }

                    // Skip if we're already updating the intent
                    if (isUpdatingIntentRef.current) {
                      console.log(
                        "Intent update already in progress, skipping",
                      );
                      return;
                    }

                    // Check if intent has actually changed
                    const currentIntent = currentWorkspace?.intent || "";
                    const intentText = singleJson.intent_text;

                    if (currentIntent.trim() === intentText.trim()) {
                      console.log("Intent unchanged, skipping update");
                      processedIntentEventsRef.current.add(intentHash);
                      return;
                    }

                    // Mark as processing
                    isUpdatingIntentRef.current = true;
                    processedIntentEventsRef.current.add(intentHash);

                    // Notify parent about intent_proposed event
                    if (eventType === "intent_proposed" && onIntentProposed) {
                      onIntentProposed();
                    }

                    // Update workspace intent via GraphQL
                    updateWorkspace({
                      workspaceId,
                      intent: intentText,
                    })
                      .then(() => {
                        // Reload workspace to get updated data
                        return fetchWorkspaceById(workspaceId);
                      })
                      .then((updatedWorkspace) => {
                        if (updatedWorkspace) {
                          // Only update if intent actually changed
                          if (updatedWorkspace.intent !== currentIntent) {
                            // Update workspace context
                            setCurrentWorkspace(updatedWorkspace);
                            // Notify parent component if callback provided
                            if (onIntentUpdated) {
                              onIntentUpdated(intentText);
                            }
                          }
                        }
                      })
                      .catch((error) => {
                        console.error(
                          "Failed to update workspace intent:",
                          error,
                        );
                        // Remove from processed set on error so we can retry
                        processedIntentEventsRef.current.delete(intentHash);
                      })
                      .finally(() => {
                        isUpdatingIntentRef.current = false;
                      });

                    // Also add message to chat
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content:
                            singleJson.message ||
                            `Intent ${
                              eventType === "intent_finalized"
                                ? "finalized"
                                : "proposed"
                            }`,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "intent_updated") {
                  // Handle intent_updated event (workspace setup flow)
                  if (singleJson.intent_package && onIntentPackageUpdated) {
                    const ready = singleJson.ready || false;
                    onIntentPackageUpdated(singleJson.intent_package, ready);
                    console.log(
                      "[ChatDock] Intent package updated, ready:",
                      ready,
                    );
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "intent_ready") {
                  // Handle intent_ready event (workspace setup flow)
                  if (singleJson.intent_package && onIntentReady) {
                    onIntentReady(singleJson.intent_package);
                    console.log("[ChatDock] Intent is ready!");

                    // Turn off agent working indicator
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "scope_updated" || eventType === "scope_update") {
                  // Handle scope_updated/scope_update events (data scoping stage)
                  // ready flag indicates scope is finalized and user can proceed
                  if (singleJson.data_scope && onDataScopeUpdated) {
                    const ready = singleJson.ready === true;
                    onDataScopeUpdated(singleJson.data_scope, ready);
                    console.log("[ChatDock] Data scope updated, ready:", ready);

                    // If ready, also call onScopeReady for backward compatibility
                    if (ready && onScopeReady) {
                      onScopeReady(singleJson.data_scope);
                      activeAgentsRef.current.clear();
                      setIsAgentWorking(false);
                    }
                  }
                  // Attach event to the most recent assistant message (expandable display)
                  if (singleJson.message) {
                    setMessages((prev) => {
                      // Find the last assistant message
                      const lastAssistantIdx = [...prev]
                        .reverse()
                        .findIndex((m) => m.role === "assistant");
                      if (lastAssistantIdx === -1) return prev;
                      const actualIdx = prev.length - 1 - lastAssistantIdx;

                      const attachedEvent: AttachedEvent = {
                        eventType,
                        displayLabel: formatEventTypeLabel(eventType),
                        message: singleJson.message,
                        timestamp: eventTimestamp,
                      };

                      const updated = [...prev];
                      updated[actualIdx] = {
                        ...updated[actualIdx],
                        attachedEvents: [
                          ...(updated[actualIdx].attachedEvents || []),
                          attachedEvent,
                        ],
                      };
                      return updated;
                    });
                  }
                } else if (eventType === "scope_ready") {
                  // Handle scope_ready event (data scoping stage)
                  if (singleJson.data_scope && onScopeReady) {
                    onScopeReady(singleJson.data_scope);
                    console.log("[ChatDock] Data scope is ready!");

                    // Turn off agent working indicator
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);
                  }
                  // Attach event to the most recent assistant message (expandable display)
                  if (singleJson.message) {
                    setMessages((prev) => {
                      // Find the last assistant message
                      const lastAssistantIdx = [...prev]
                        .reverse()
                        .findIndex((m) => m.role === "assistant");
                      if (lastAssistantIdx === -1) return prev;
                      const actualIdx = prev.length - 1 - lastAssistantIdx;

                      const attachedEvent: AttachedEvent = {
                        eventType,
                        displayLabel: formatEventTypeLabel(eventType),
                        message: singleJson.message,
                        timestamp: eventTimestamp,
                      };

                      const updated = [...prev];
                      updated[actualIdx] = {
                        ...updated[actualIdx],
                        attachedEvents: [
                          ...(updated[actualIdx].attachedEvents || []),
                          attachedEvent,
                        ],
                      };
                      return updated;
                    });
                  }
                } else if (eventType === "execution_progress") {
                  // Handle execution_progress event (data review stage)
                  if (onExecutionProgress && singleJson.entity_type) {
                    onExecutionProgress(
                      singleJson.entity_type,
                      singleJson.status || "in_progress",
                      singleJson.message,
                    );
                    console.log(
                      "[ChatDock] Execution progress:",
                      singleJson.entity_type,
                      singleJson.status,
                    );
                  }
                } else if (eventType === "entity_complete") {
                  // Handle entity_complete event (data review stage)
                  if (onEntityComplete && singleJson.entity_type) {
                    onEntityComplete(
                      singleJson.entity_type,
                      singleJson.node_ids || [],
                      singleJson.sample_data || [],
                    );
                    console.log(
                      "[ChatDock] Entity complete:",
                      singleJson.entity_type,
                      "nodes:",
                      singleJson.node_ids?.length,
                    );
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "execution_complete") {
                  // Handle execution_complete event (data review stage)
                  if (onExecutionComplete && singleJson.results) {
                    onExecutionComplete(singleJson.results);
                    console.log(
                      "[ChatDock] Execution complete! Results:",
                      singleJson.results.length,
                    );

                    // Turn off agent working indicator
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "execution_error") {
                  // Handle execution_error event (data review stage)
                  if (onExecutionError && singleJson.error) {
                    onExecutionError(singleJson.error);
                    console.error(
                      "[ChatDock] Execution error:",
                      singleJson.error,
                    );

                    // Turn off agent working indicator
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);
                  }
                  // Add error message to chat
                  if (singleJson.error || singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content:
                            singleJson.message || `Error: ${singleJson.error}`,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "team_building_progress") {
                  // Handle team_building_progress event (team building stage)
                  if (onTeamBuildingProgress) {
                    onTeamBuildingProgress(
                      singleJson.status || "in_progress",
                      singleJson.message,
                    );
                    console.log(
                      "[ChatDock] Team building progress:",
                      singleJson.status,
                    );
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "team_complete") {
                  // Handle team_complete event (team building stage)
                  if (onTeamComplete && singleJson.team_config) {
                    onTeamComplete(singleJson.team_config);
                    console.log(
                      "[ChatDock] Team building complete! Agents:",
                      singleJson.team_config.agents?.length,
                    );

                    // Turn off agent working indicator
                    activeAgentsRef.current.clear();
                    setIsAgentWorking(false);
                  }
                  // Add message to chat if provided
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                } else if (eventType === "clarification_needed") {
                  // Handle clarification_needed event (data scoping stage)
                  console.log("[ChatDock] Clarification needed:", singleJson);

                  // Turn off agent working indicator while waiting for user input
                  activeAgentsRef.current.clear();
                  setIsAgentWorking(false);

                  // Build the clarification question from the event
                  const clarificationQuestion: ClarificationQuestion = {
                    question_id:
                      singleJson.question_id ||
                      `clarification-${eventTimestamp}`,
                    question:
                      singleJson.question ||
                      singleJson.message ||
                      "Please clarify",
                    context: singleJson.context,
                    options: singleJson.options || [],
                    affects_entities: singleJson.affects_entities,
                    agent_id: singleJson.agent_id,
                    stage: singleJson.stage,
                  };

                  // Add to pending clarifications (queue multiple questions)
                  setPendingClarifications((prev) => {
                    // Avoid duplicate questions
                    if (
                      prev.some(
                        (q) =>
                          q.question_id === clarificationQuestion.question_id,
                      )
                    ) {
                      return prev;
                    }
                    return [...prev, clarificationQuestion];
                  });

                  // Add message to chat showing the clarification request
                  if (singleJson.message) {
                    setMessages((prev) => {
                      const messageId = `event-${eventId}`;
                      if (prev.some((m) => m.id === messageId)) return prev;

                      return [
                        ...prev,
                        {
                          id: messageId,
                          role: "assistant" as const,
                          content: singleJson.message,
                          timestamp: eventTimestamp,
                        },
                      ].sort((a, b) => a.timestamp - b.timestamp);
                    });
                  }
                }
              }
              return; // Skip further processing if we handled JSON
            }
          } catch (e) {
            // Not JSON, skip processing
            console.log("Text is not JSON:", e);
          }
        }
      };
      es.onerror = () => {};
      esRef.current = es;
    },
    [
      workspaceId,
      setCurrentWorkspace,
      onIntentUpdated,
      onIntentProposed,
      onIntentPackageUpdated,
      onIntentReady,
      onDataScopeUpdated,
      onScopeReady,
    ],
  );

  const handleSend = useCallback(async () => {
    const prompt = value.trim();
    if (!prompt) return;
    if (!isSetupMode && isTurnOpen) return;

    // Build the message with staged rows context if available
    let messageToSend = prompt;
    if (stagedRowsContext && stagedRowsContext.rowCount > 0) {
      // Limit to 100 rows max for context
      const MAX_CONTEXT_ROWS = 100;
      const rows = stagedRowsContext.rows.slice(0, MAX_CONTEXT_ROWS);

      if (rows.length > 0) {
        const columns = Object.keys(rows[0]).filter(k => k !== 'id');

        // Format as comma-separated list for agent reasoning
        const csvHeader = columns.join(', ');
        const csvRows = rows.map(row =>
          columns.map(col => String(row[col] ?? '')).join(', ')
        ).join('\n');

        const truncated = stagedRowsContext.rowCount > MAX_CONTEXT_ROWS;
        const rowCountLabel = truncated
          ? `${rows.length} of ${stagedRowsContext.rowCount}`
          : `${rows.length}`;

        const contextBlock = `\n\n---\n**Evidence from ${stagedRowsContext.entityType}** (${rowCountLabel} rows):\n\n\`\`\`\n${csvHeader}\n${csvRows}\n\`\`\`${truncated ? `\n\n_Limited to ${MAX_CONTEXT_ROWS} rows for context._` : ''}`;
        messageToSend = prompt + contextBlock;
      }
      onClearStagedRows?.(); // Clear after including in message
    }

    onSubmit?.(messageToSend);
    setValue("");
    setError(null);

    // In setup mode, the parent (WorkspaceSetupFlow) handles all submission logic
    // via the onSubmit callback - we just need to clear the input and return
    if (isSetupMode) {
      return;
    }

    setIsTurnOpen(true);
    setSending(true);
    setIsAgentWorking(true); // Show thinking indicator when sending
    // Always scroll to bottom when user sends a message
    shouldAutoScrollRef.current = true;

    // Use runId or setupRunId for existing conversations
    const activeRunId = runId || setupRunId;

    try {
      // If we have an existing runId, continue the conversation by appending user message
      if (activeRunId) {
        // Create user_message event JSON
        const userMessageEvent = {
          event_type: "user_message",
          message: prompt,
        };
        // Append to scenario run log
        await appendScenarioRunLog(
          activeRunId,
          JSON.stringify(userMessageEvent),
        );
        // Clear the active feedback request if it exists
        if (activeFeedbackRequest) {
          setActiveFeedbackRequest(null);
        }
        // Reload feedback history
        const history = await getFeedbackHistory(activeRunId);
        setFeedbackHistory(history);
      } else {
        // First message: create new scenario run
        if (!workspaceId) throw new Error("Select a workspace to analyze.");

        const wsId = workspaceId; // TypeScript narrowing
        let tid = getTenantId() || "";
        if (!tid) {
          const tenants = await fetchTenants();
          if (!tenants.length) throw new Error("No tenants available");
          tid = tenants[0].tenantId;
          setTenantId(tid);
        }

        const users = await fetchUsers();
        if (!users.length) throw new Error("No users available");
        const createdBy = users[0].userId;

        const scenarioName = `Workspace Chat - ${new Date().toISOString()}`;
        const scenarioId = await createScenario({
          workspaceId: wsId,
          name: scenarioName,
          createdBy,
        });
        const newRunId = await createScenarioRun(scenarioId, {}, prompt);
        setRunId(newRunId);
        setSelectedRunId(newRunId);
        setChatTitles((prev) => ({
          ...prev,
          [newRunId]: generateChatTitle(prompt),
        }));
        setActiveFeedbackRequest(null);
        setFeedbackHistory([]);

        // Append user_message event to ensure it's in the log
        const userMessageEvent = {
          event_type: "user_message",
          message: prompt,
        };
        await appendScenarioRunLog(newRunId, JSON.stringify(userMessageEvent));
        setIsAgentWorking(true); // Show thinking indicator when starting stream
        startStream(newRunId, tid);
        // Reload scenario runs to include the new one
        const runs = await fetchScenarioRuns(wsId);
        const sorted = runs.sort(
          (a, b) =>
            new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
        );
        setScenarioRuns(sorted);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to start analysis");
    } finally {
      setSending(false);
    }
  }, [
    value,
    onSubmit,
    isSetupMode,
    workspaceId,
    startStream,
    activeFeedbackRequest,
    runId,
    setupRunId,
    isTurnOpen,
    stagedRowsContext,
    onClearStagedRows,
  ]);

  const handleClarificationSubmit = useCallback(
    async (answers: ClarificationAnswer[]) => {
      const activeRunId = runId || setupRunId;
      if (!activeRunId) return;

      try {
        setSending(true);
        setIsAgentWorking(true);

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
        await appendScenarioRunLog(
          activeRunId,
          JSON.stringify(userMessageEvent),
        );

        // Add user message to chat display
        const timestamp = Date.now();
        setMessages((prev) =>
          [
            ...prev,
            {
              id: `clarification-response-${timestamp}`,
              role: "user" as const,
              content: clarificationResponseMessage,
              timestamp,
            },
          ].sort((a, b) => a.timestamp - b.timestamp),
        );

        // Clear pending clarifications
        setPendingClarifications([]);

        // Scroll to bottom
        shouldAutoScrollRef.current = true;
      } catch (error: any) {
        setError(error?.message || "Failed to submit clarification responses");
        setIsAgentWorking(false);
      } finally {
        setSending(false);
      }
    },
    [runId, setupRunId],
  );

  // Unified handler that routes to internal or external handler
  const handleUnifiedClarificationSubmit = useCallback(
    async (answers: ClarificationAnswer[]) => {
      // Split answers into external and internal based on question source
      const externalQuestionIds = new Set(
        (externalClarifications || []).map((q) => q.question_id),
      );

      const externalAnswers = answers.filter((a) =>
        externalQuestionIds.has(a.question_id),
      );
      const internalAnswers = answers.filter(
        (a) => !externalQuestionIds.has(a.question_id),
      );

      // Send external answers to external handler (setup flow)
      if (externalAnswers.length > 0 && onExternalClarificationSubmit) {
        onExternalClarificationSubmit(externalAnswers);
      }

      // Send internal answers to internal handler (SSE flow)
      if (internalAnswers.length > 0) {
        await handleClarificationSubmit(internalAnswers);
      }
    },
    [
      externalClarifications,
      onExternalClarificationSubmit,
      handleClarificationSubmit,
    ],
  );

  const handleNewChat = useCallback(() => {
    // Close existing stream
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    // Reset all state
    setRunId("");
    setSelectedRunId("");
    setMessages([]);
    setActiveFeedbackRequest(null);
    setFeedbackHistory([]);
    setPendingClarifications([]);
    setAgentActivity(new Map());
    setIsAgentWorking(false);
    setError(null);
    setValue("");
    lastEventIdRef.current = null;
    streamBufferRef.current = "";
    processedEventsRef.current = new Set();
    activeAgentsRef.current = new Set();
  }, []);

  const handleSelectChat = useCallback(
    async (selectedRun: ScenarioRun) => {
      // Close existing stream
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      // Get tenantId
      let tid = currentWorkspace?.tenantId || getTenantId() || "";
      if (!tid) {
        try {
          const tenants = await fetchTenants();
          if (tenants.length > 0) {
            tid = tenants[0].tenantId;
            setTenantId(tid);
          } else {
            setError("No tenant available");
            return;
          }
        } catch (e: any) {
          setError(e?.message || "Failed to get tenant");
          return;
        }
      }

      // Set selected run
      setSelectedRunId(selectedRun.runId);
      setRunId(selectedRun.runId);
      if (selectedRun.title) {
        setChatTitles((prev) => ({
          ...prev,
          [selectedRun.runId]: generateChatTitle(selectedRun.title || ""),
        }));
      }
      setMessages([]);
      setActiveFeedbackRequest(null);
      setFeedbackHistory([]);
      setPendingClarifications([]);
      setAgentActivity(new Map());
      setIsAgentWorking(false);
      setError(null);

      // Start stream for the selected run
      startStream(selectedRun.runId, tid);
    },
    [currentWorkspace, startStream],
  );

  // Auto-connect to SetupRunId when provided
  useEffect(() => {
    if (isSetupMode) return;
    if (!setupRunId || !open || selectedRunId === setupRunId) return;

    // If we have initialMessages, we're transitioning from interview to draft
    // Just set the runId and connect to the stream without clearing messages
    const hasInitialData = initialMessages && initialMessages.length > 0;

    // If we already have the run in scenarioRuns and no initial data, use handleSelectChat
    if (!hasInitialData && scenarioRuns.length > 0 && !loadingRuns) {
      const matchingRun = scenarioRuns.find((run) => run.runId === setupRunId);
      if (matchingRun) {
        handleSelectChat(matchingRun);
        return;
      }
    }

    // Otherwise, connect directly to the runId
    // This handles the case where the run was just created and might not be in scenarioRuns yet
    const connectDirectly = async () => {
      // Close existing stream
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      // Get tenantId
      let tid = currentWorkspace?.tenantId || getTenantId() || "";
      if (!tid) {
        try {
          const tenants = await fetchTenants();
          if (tenants.length > 0) {
            tid = tenants[0].tenantId;
            setTenantId(tid);
          } else {
            setError("No tenant available");
            return;
          }
        } catch (e: any) {
          setError(e?.message || "Failed to get tenant");
          return;
        }
      }

      // Set selected run
      setSelectedRunId(setupRunId);
      setRunId(setupRunId);

      // Only clear state if we don't have initial data from a phase transition
      if (!hasInitialData) {
        setMessages([]);
        setActiveFeedbackRequest(null);
        setFeedbackHistory([]);
        setAgentActivity(new Map());
        setIsAgentWorking(false);
      }
      setError(null);

      // Start stream for the setupRunId (but don't clear messages if we have initial data)
      startStream(setupRunId, tid, hasInitialData);
    };

    connectDirectly();
  }, [
    setupRunId,
    open,
    scenarioRuns,
    loadingRuns,
    selectedRunId,
    handleSelectChat,
    currentWorkspace,
    initialMessages,
    startStream,
  ]);

  if (!open) {
    return null;
  }

  return (
    <Box
      sx={
        fullScreen
          ? {
              position: "relative",
              width: "100%",
              height: "100%",
              bgcolor: isSetupMode ? "background.default" : "background.paper",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              justifyContent: isInitialWelcome ? "center" : "flex-start",
            }
          : {
              position: "fixed",
              right: 0,
              top: 0,
              bottom: 0,
              width: { xs: "100vw", sm: `${width}%`, md: `${width}%` },
              minWidth: `${MIN_WIDTH}%`,
              maxWidth: `${MAX_WIDTH}%`,
              transform: open ? "translateX(0)" : "translateX(100%)",
              transition: "transform 0.3s ease",
              zIndex: 1200,
              bgcolor: "background.paper",
              borderLeft: "1px solid",
              borderColor: "divider",
              boxSizing: "border-box",
              display: "grid",
              gridTemplateRows: isSetupMode
                ? "1fr auto" // In setup mode: messages + input (no top bar)
                : "auto 1fr auto",
            }
      }
    >
      {/* Resize handle - only in dock mode */}
      {!fullScreen && (
        <Box
          onMouseDown={handleResizeStart}
          sx={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: "4px",
            cursor: "col-resize",
            bgcolor: "transparent",
            zIndex: 1000,
            transition: "width 0.2s, background-color 0.2s",
            "&:hover": {
              width: "8px",
              bgcolor: "divider",
            },
          }}
        />
      )}
      {/* Top bar: New Chat + icons - hide in fullScreen mode or setup mode */}
      {!fullScreen && !isSetupMode && (
        <Box
          sx={{
            order: 1,
            px: 2,
            pt: 2,
            pb: 1.25,
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 1,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            {!isSetupMode && (
              <Tooltip title="New Chat" placement="bottom">
                <IconButton
                  size="small"
                  onClick={handleNewChat}
                  sx={{ color: "secondary.main" }}
                >
                  <Add size="24" />
                </IconButton>
              </Tooltip>
            )}
            {!isSetupMode && (
              <IconButton
                ref={historyAnchorRef}
                size="small"
                sx={{ color: "secondary.main" }}
                onClick={handleToggleHistory}
                aria-label="toggle chat history"
              >
                <RecentlyViewed size="20" />
              </IconButton>
            )}
            {!isSetupMode && agentActivity.size > 0 && (
              <Tooltip
                title={
                  showAgentActivity
                    ? "Hide agent activity"
                    : "Show agent activity"
                }
                placement="bottom"
              >
                <IconButton
                  size="small"
                  aria-label="toggle agent activity"
                  onClick={() => setShowAgentActivity(!showAgentActivity)}
                  sx={{ color: "secondary.main" }}
                >
                  <AccountTreeIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            {!isSetupMode && feedbackHistory.length > 0 && (
              <Tooltip
                title={
                  showFeedbackHistory
                    ? "Hide feedback history"
                    : "Show feedback history"
                }
                placement="bottom"
              >
                <IconButton
                  size="small"
                  aria-label="toggle feedback history"
                  onClick={() => setShowFeedbackHistory(!showFeedbackHistory)}
                  sx={{ color: "secondary.main" }}
                >
                  <View size="20" />
                </IconButton>
              </Tooltip>
            )}
            {!isSetupMode && (
              <Tooltip title="Collapse" placement="bottom">
                <IconButton
                  size="small"
                  onClick={onClose}
                  sx={{ color: "secondary.main" }}
                >
                  <RightPanelCloseFilled size="20" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>
      )}

      {!isSetupMode && historyAnchorRef.current && (
        <Popper
          open={historyOpen}
          anchorEl={historyAnchorRef.current}
          placement="bottom-start"
          modifiers={[{ name: "offset", options: { offset: [0, 8] } }]}
          sx={{ zIndex: 1300 }}
        >
          <ClickAwayListener onClickAway={handleCloseHistory}>
            <Paper
              elevation={3}
              sx={{
                width: 320,
                maxWidth: "90vw",
                bgcolor: (theme) =>
                  theme.palette.mode === "dark"
                    ? theme.palette.background.paper
                    : theme.palette.common.white,
                borderRadius: 1,
                p: 2,
                border: "1px solid",
                borderColor: "divider",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Past Chats
                </Typography>
              </Box>
              {renderPastChats()}
            </Paper>
          </ClickAwayListener>
        </Popper>
      )}

      <Box
        ref={messagesContainerRef}
        onScroll={handleScroll}
        sx={{
          ...(fullScreen
            ? {
                flex: isInitialWelcome ? "0 0 auto" : 1,
                overflow: isInitialWelcome ? "visible" : "auto",
                display: "flex",
                flexDirection: "column",
                alignItems: isInitialWelcome ? "center" : "stretch",
                justifyContent: isInitialWelcome ? "center" : "flex-start",
                px: 2,
                pb: 1,
                gap: 1,
                maxWidth: isInitialWelcome ? 600 : "100%",
                mx: isInitialWelcome ? "auto" : 0,
              }
            : {
                order: isSetupMode ? 1 : 2, // Setup mode: messages first
                px: 2,
                pt: isSetupMode ? 2 : 0, // Add top margin in setup mode
                pb: 1,
                overflow: "auto",
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
                gap: 1,
              }),
        }}
      >
        {/* Feedback History - Collapsible */}
        {feedbackHistory.length > 0 && (
          <Collapse in={showFeedbackHistory}>
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid",
                borderColor: "divider",
                p: 1.25,
                bgcolor: "action.hover",
                flexShrink: 0,
                mb: 1,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 700,
                  color: "text.secondary",
                  mb: 1,
                  display: "block",
                }}
              >
                Feedback History
              </Typography>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 1,
                  maxHeight: 180,
                  overflowY: "auto",
                }}
              >
                <List dense sx={{ p: 0 }}>
                  {feedbackHistory.map((feedback, idx) => (
                    <React.Fragment key={feedback.id}>
                      <ListItem
                        sx={{
                          flexDirection: "column",
                          alignItems: "flex-start",
                          py: 1,
                          px: 0,
                        }}
                      >
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            width: "100%",
                            mb: 0.5,
                          }}
                        >
                          <Chip
                            label={feedback.action}
                            size="small"
                            sx={{
                              fontWeight: 600,
                              bgcolor: "background.paper",
                              border: "1px solid",
                              borderColor: "divider",
                            }}
                          />
                          {feedback.applied && (
                            <Chip
                              label="Applied"
                              size="small"
                              sx={{
                                bgcolor: "#28a745",
                                color: "#fff",
                                fontWeight: 600,
                              }}
                            />
                          )}
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: "auto", fontSize: "0.7rem" }}
                          >
                            {new Date(feedback.timestamp).toLocaleString()}
                          </Typography>
                        </Box>
                        <Typography
                          variant="body2"
                          sx={{ fontSize: "0.75rem", color: "text.secondary" }}
                        >
                          {feedback.feedback_text}
                        </Typography>
                      </ListItem>
                      {idx < feedbackHistory.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              </Box>
            </Box>
          </Collapse>
        )}

        {/* Agent Activity - Collapsible */}
        {agentActivity.size > 0 && (
          <Collapse in={showAgentActivity}>
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid",
                borderColor: "divider",
                p: 1.25,
                bgcolor: "action.hover",
                flexShrink: 0,
                mb: 1,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 700,
                  color: "text.secondary",
                  mb: 1,
                  display: "block",
                }}
              >
                Agent Activity
              </Typography>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 1,
                  maxHeight: 180,
                  overflowY: "auto",
                }}
              >
                {Array.from(agentActivity.entries()).map(
                  ([agentName, content]) => (
                    <Box
                      key={agentName}
                      sx={{ mb: 1.5, "&:last-child": { mb: 0 } }}
                    >
                      <Chip
                        label={agentName}
                        size="small"
                        sx={{
                          mb: 0.75,
                          fontWeight: 600,
                          bgcolor: "background.paper",
                          border: "1px solid",
                          borderColor: "divider",
                        }}
                      />
                      <Typography
                        variant="body2"
                        sx={{
                          color: "text.secondary",
                          fontSize: "0.75rem",
                          fontFamily: "monospace",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                        }}
                      >
                        {content}
                      </Typography>
                    </Box>
                  ),
                )}
              </Box>
            </Box>
          </Collapse>
        )}

        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 1.5,
          }}
        >
          {error && (
            <Typography variant="body2" color="error" sx={{ mb: 1 }}>
              {error}
            </Typography>
          )}

          {(() => {
            const sorted = [...effectiveMessages].sort(
              (a, b) => a.timestamp - b.timestamp,
            );

            return sorted.map((m) => {
              const isAssistant = m.role === "assistant";
              const isUser = m.role === "user";
              // Call streaming functions directly (component re-renders via forceUpdate in onProgress)
              const streaming =
                isAssistant && isStreaming(m.id, m.content, m.timestamp);

              // For user messages, parse out evidence for compact display
              const parsedUserMessage = isUser ? parseUserMessageForDisplay(m.content) : null;
              const displayedText = isAssistant
                ? getDisplayedText(m.id, m.content, m.timestamp)
                : parsedUserMessage?.prompt || m.content;

              return (
                <Box
                  key={m.id}
                  sx={{
                    mb: 1,
                    textAlign:
                      m.id === "welcome" && isInitialWelcome
                        ? "center"
                        : "left",
                  }}
                >
                  {m.id !== "welcome" && (
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 700,
                        color:
                          m.role === "user"
                            ? "text.secondary"
                            : "secondary.main",
                      }}
                    >
                      {m.role === "user" ? "You" : "Assistant"}
                    </Typography>
                  )}
                  {m.dataLoadingProgress ? (
                    <DataLoadingProgressBlock message={m} />
                  ) : (
                    <Box
                      sx={{
                        "& p": { m: 0, mb: 0.5 },
                        "& ul, & ol": { pl: 3, mb: 0.5 },
                        "& li": { mb: 0.25 },
                        "& pre": {
                          p: 1,
                          borderRadius: 1,
                          overflow: "auto",
                          bgcolor: "action.hover",
                          border: "1px solid",
                          borderColor: "divider",
                          mb: 0.75,
                        },
                        "& code": {
                          bgcolor: "action.hover",
                          px: 0.5,
                          py: 0.25,
                          borderRadius: 0.5,
                          border: "1px solid",
                          borderColor: "divider",
                        },
                        "& h1, & h2, & h3, & h4, & h5, & h6": {
                          mt: 1,
                          mb: 0.5,
                          fontWeight: 700,
                        },
                        "& strong, & b": {
                          fontWeight: 700,
                          fontFamily:
                            "Inter, system-ui, -apple-system, sans-serif",
                        },
                        "& em, & i": {
                          fontStyle: "italic",
                          fontFamily:
                            "Inter, system-ui, -apple-system, sans-serif",
                        },
                        "& a": {
                          color: "primary.main",
                          textDecoration: "underline",
                        },
                        color: "text.primary",
                        typography: "body2",
                      }}
                    >
                      {isAssistant && streaming ? (
                        <Box component="span" sx={{ whiteSpace: "pre-wrap" }}>
                          {displayedText}
                          <StreamingCursor />
                        </Box>
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[
                            rehypeRaw,
                            [
                              rehypeSanitize,
                              {
                                tagNames: [
                                  "strong",
                                  "em",
                                  "b",
                                  "i",
                                  "p",
                                  "h1",
                                  "h2",
                                  "h3",
                                  "h4",
                                  "h5",
                                  "h6",
                                  "ul",
                                  "ol",
                                  "li",
                                  "code",
                                  "pre",
                                  "a",
                                ],
                              },
                            ],
                          ]}
                        >
                          {m.content}
                        </ReactMarkdown>
                      )}
                    </Box>
                  )}
                  {m.attachedEvents && m.attachedEvents.length > 0 && (
                    <AttachedEventsSection events={m.attachedEvents} />
                  )}
                </Box>
              );
            });
          })()}

          {/* Agent Thinking Indicator */}
          {isAgentWorking && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                p: 1.5,
                borderRadius: 1,
                bgcolor: "action.hover",
                border: "1px solid",
                borderColor: "divider",
                animation: "pulse 2s ease-in-out infinite",
                "@keyframes pulse": {
                  "0%, 100%": {
                    opacity: 1,
                  },
                  "50%": {
                    opacity: 0.7,
                  },
                },
              }}
            >
              <CircularProgress
                size={16}
                thickness={4}
                sx={{ color: "secondary.main" }}
              />
              <PsychologyIcon
                fontSize="small"
                sx={{ color: "secondary.main" }}
              />
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", fontStyle: "italic" }}
              >
                Agents are thinking...
              </Typography>
            </Box>
          )}

          <div ref={messagesEndRef} />

          {/* Scroll to bottom FAB */}
          <Zoom in={showScrollFab}>
            <Fab
              size="small"
              onClick={scrollToBottom}
              sx={{
                position: "sticky",
                bottom: 16,
                left: "50%",
                transform: "translateX(-50%)",
                bgcolor: "primary.main",
                color: "primary.contrastText",
                "&:hover": {
                  bgcolor: "primary.dark",
                },
                zIndex: 10,
              }}
              aria-label="Scroll to bottom"
            >
              <ArrowDown size={20} />
            </Fab>
          </Zoom>
        </Box>
      </Box>

      {/* input card - replaced by ClarificationPanel when clarifications are pending */}
      <Box
        sx={
          fullScreen
            ? {
                flex: "0 0 auto",
                px: 2,
                pb: 1,
                maxWidth: isInitialWelcome ? 600 : "100%",
                width: isInitialWelcome ? "100%" : "auto",
                mx: isInitialWelcome ? "auto" : 0,
              }
            : {
                order: isSetupMode ? 2 : 3, // In setup mode, always order 2 (after messages)
                px: 2,
                pb: 1,
              }
        }
      >
        {allClarifications.length > 0 ? (
          <ClarificationPanel
            questions={allClarifications}
            onSubmit={handleUnifiedClarificationSubmit}
          />
        ) : (
          <>
            {isInputDisabled && (
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  mb: 0.75,
                  color: "text.secondary",
                  bgcolor: "action.hover",
                  border: "1px solid",
                  borderColor: "divider",
                  px: 1,
                  py: 0.5,
                  borderRadius: 0.5,
                }}
              >
                Chat disabled while agents are at work
              </Typography>
            )}
            {!effectiveMessages.length && !error && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 0.75 }}
              >
                Analyze your workspace or ask a question.
              </Typography>
            )}
            <Box
              sx={{
                borderRadius: 0.5,
                px: 1.5,
                py: 1,
                minHeight: 80,
                display: "flex",
                alignItems: "center",
                gap: 1,
                bgcolor: (theme) =>
                  theme.palette.mode === "dark"
                    ? theme.palette.background.paper
                    : theme.palette.common.white,
                border: "1px solid",
                borderColor: "divider",
                opacity: isInputDisabled ? 0.65 : 1,
              }}
            >
              {/* TODO: Uncomment when attach functionality is implemented
              <IconButton size="small" sx={{ color: "text.secondary" }}>
                <AttachFileRoundedIcon sx={{ fontSize: 18 }} />
              </IconButton>
              */}

              {/* Staged rows indicator */}
              {stagedRowsContext && stagedRowsContext.rowCount > 0 && (
                <Chip
                  size="small"
                  label={`${stagedRowsContext.rowCount} ${stagedRowsContext.entityType} rows`}
                  onDelete={onClearStagedRows}
                  sx={{
                    bgcolor: (theme) => theme.palette.primary.main,
                    color: "white",
                    fontWeight: 500,
                    fontSize: "0.75rem",
                    height: 24,
                    "& .MuiChip-deleteIcon": {
                      color: "rgba(255,255,255,0.7)",
                      "&:hover": { color: "white" },
                    },
                  }}
                />
              )}

              <InputBase
                fullWidth
                placeholder={
                  isInputDisabled
                    ? "Please wait for the current response..."
                    : activeFeedbackRequest
                      ? "Type your response..."
                      : "Ask anything"
                }
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    if (!isInputDisabled) {
                      handleSend();
                    }
                  }
                }}
                disabled={isInputDisabled}
                sx={(theme) => ({
                  fontSize: 14,
                  color: theme.palette.text.primary,
                  "& input, & textarea": {
                    color: theme.palette.text.primary,
                    WebkitTextFillColor: theme.palette.text.primary,
                    opacity: 1,
                    caretColor: theme.palette.text.primary,
                  },
                  "& input::placeholder, & textarea::placeholder": {
                    color: theme.palette.text.secondary,
                    WebkitTextFillColor: theme.palette.text.secondary,
                    opacity: 0.7,
                  },
                })}
              />
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                {/* TODO: Uncomment when voice functionality is implemented
                <IconButton size="small">
                  <Microphone size="20" />
                </IconButton>
                */}
                <IconButton
                  size="small"
                  color="primary"
                  aria-label="send"
                  disabled={isInputDisabled}
                  onClick={handleSend}
                >
                  <Send size="20" />
                </IconButton>
              </Box>
            </Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 0.75, display: "block" }}
            >
              {activeFeedbackRequest
                ? "Press Enter to send"
                : "Press Enter to run"}
            </Typography>
          </>
        )}
      </Box>
    </Box>
  );
}

function StreamingCursor() {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-block",
        width: "0.5ch",
        height: "1em",
        bgcolor: "secondary.main",
        ml: 0.5,
        animation: "streaming-cursor-blink 0.8s steps(1) infinite",
        "@keyframes streaming-cursor-blink": {
          "0%, 50%": { opacity: 1 },
          "50.1%, 100%": { opacity: 0 },
        },
      }}
      aria-hidden="true"
    />
  );
}
