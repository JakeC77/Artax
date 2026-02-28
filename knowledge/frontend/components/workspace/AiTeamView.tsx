import { useEffect, useMemo, useState, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  Chip,
  keyframes,
  Tooltip,
  IconButton,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  Identification,
  Rotate,
  Star,
  DataBase,
  Chemistry,
  ChartLine,
  ArrowRight,
  UserAvatar,
} from "@carbon/icons-react";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import {
  fetchAiTeamMembers,
  type AiTeamMember,
  type TeamConfig,
} from "../../services/graphql";
import SetupFooter from "./setup/SetupFooter";

// Brand colors from design system
const colors = {
  white: "#FFFFFF",
  charcoal: "#1C1C1C",
  ivory: "#F4F0E6",
  gold: "#C6A664",
  emerald: "#0F5C4C",
  grayMedium: "#5E5E5E",
};

const shadowStack = (color: string) =>
  `1px 1px 0 0 ${color}, 2px 2px 0 0 ${color}, 3px 3px 0 0 ${color}, 4px 4px 0 0 ${color}, 5px 5px 0 0 ${color}`;

// Loading animation
const rotate = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

// Pulse glow animation for flip icon hint
const pulseGlow = keyframes`
  0%, 100% {
    box-shadow: 0 0 5px rgba(198, 166, 100, 0.5);
    transform: scale(1);
  }
  50% {
    box-shadow: 0 0 15px rgba(198, 166, 100, 0.8), 0 0 25px rgba(198, 166, 100, 0.4);
    transform: scale(1.1);
  }
`;

// Border glow animation for cards
const borderGlowGold = keyframes`
  0%, 100% { box-shadow: 0 0 10px rgba(198, 166, 100, 0.3), 0 4px 20px rgba(0,0,0,0.2); }
  50% { box-shadow: 0 0 20px rgba(198, 166, 100, 0.5), 0 0 30px rgba(198, 166, 100, 0.2), 0 4px 20px rgba(0,0,0,0.2); }
`;

const borderGlowEmerald = keyframes`
  0%, 100% { box-shadow: 0 0 8px rgba(15, 92, 76, 0.2), 0 4px 16px rgba(0,0,0,0.15); }
  50% { box-shadow: 0 0 15px rgba(15, 92, 76, 0.4), 0 0 25px rgba(15, 92, 76, 0.15), 0 4px 16px rgba(0,0,0,0.15); }
`;

// Fade in animation for staggered load
const fadeInUp = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

// Extended team member type with all available fields
type ExtendedTeamMember = {
  aiTeamMemberId: string;
  aiTeamId: string;
  agentId: string;
  name: string;
  role: string;
  type: "conductor" | "specialist";
  capabilities: string[];
  description?: string | null;
  expertise?: string[];
  tools?: string[];
  communicationStyle?: string | null;
  systemPrompt?: string | null;
  createdAt: string;
  updatedAt: string;
};

// Get specialist icon based on role/name
function getSpecialistIcon(role: string) {
  const roleLower = role.toLowerCase();
  if (
    roleLower.includes("data") ||
    roleLower.includes("etl") ||
    roleLower.includes("engineer")
  ) {
    return DataBase;
  }
  if (
    roleLower.includes("pharma") ||
    roleLower.includes("clinical") ||
    roleLower.includes("analyst")
  ) {
    return Chemistry;
  }
  if (
    roleLower.includes("report") ||
    roleLower.includes("visual") ||
    roleLower.includes("design")
  ) {
    return ChartLine;
  }
  return Identification;
}

// Parse sections from system prompt
function parseSystemPrompt(
  systemPrompt: string | null | undefined
): Record<string, string> {
  if (!systemPrompt) return {};

  const sections: Record<string, string> = {};
  const lines = systemPrompt.split("\n");
  let currentSection = "";
  let currentContent: string[] = [];

  for (const line of lines) {
    if (line.startsWith("## ")) {
      if (currentSection && currentContent.length > 0) {
        sections[currentSection] = currentContent.join("\n").trim();
      }
      currentSection = line.replace("## ", "").trim();
      currentContent = [];
    } else if (currentSection) {
      currentContent.push(line);
    }
  }

  if (currentSection && currentContent.length > 0) {
    sections[currentSection] = currentContent.join("\n").trim();
  }

  return sections;
}

// Flip Button Component with tooltip always shown
function FlipButton({
  onClick,
  showHint,
  isConductor,
}: {
  onClick: () => void;
  showHint: boolean;
  isConductor?: boolean;
}) {
  const accentColor = isConductor ? colors.gold : colors.emerald;

  return (
    <Tooltip title="Flip card to see more" placement="top" arrow>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        <Typography
          sx={{ fontSize: 11, color: "text.secondary", fontWeight: 500 }}
        >
          Flip
        </Typography>
        <IconButton
          onClick={onClick}
          sx={{
            width: 32,
            height: 32,
            bgcolor: "transparent",
            border: `1px solid ${accentColor}`,
            color: accentColor,
            borderRadius: "50%",
            animation: showHint
              ? `${pulseGlow} 2s ease-in-out infinite`
              : "none",
            "&:hover": {
              bgcolor: alpha(accentColor, 0.1),
            },
          }}
        >
          <Rotate size={16} />
        </IconButton>
      </Box>
    </Tooltip>
  );
}

// Card Front Face - Character Portrait
function CardFront({
  member,
  isConductor,
  showHint,
  onFlip,
  animationDelay,
}: {
  member: ExtendedTeamMember;
  isConductor?: boolean;
  showHint: boolean;
  onFlip: () => void;
  animationDelay?: number;
}) {
  const accentColor = isConductor ? colors.gold : colors.emerald;
  const expertise = member.expertise?.slice(0, isConductor ? 4 : 3) || [];
  const parsedSections = useMemo(
    () => parseSystemPrompt(member.systemPrompt),
    [member.systemPrompt]
  );
  const SpecialistIcon = !isConductor ? getSpecialistIcon(member.role) : null;

  return (
    <Paper
      variant="outlined"
      className="card-border"
      sx={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        borderRadius: 1,
        overflow: "hidden",
        borderColor: accentColor,
        borderWidth: isConductor ? 2 : 1,
        bgcolor: colors.white,
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.08)",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        animation:
          animationDelay !== undefined
            ? `${fadeInUp} 0.5s ease-out ${animationDelay}s both, ${
                isConductor ? borderGlowGold : borderGlowEmerald
              } 3s ease-in-out infinite`
            : `${
                isConductor ? borderGlowGold : borderGlowEmerald
              } 3s ease-in-out infinite`,
      }}
    >
      {/* Star badge for conductor */}
      {isConductor && (
        <Box
          sx={{
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 3,
            bgcolor: colors.gold,
            borderRadius: 0.5,
            p: 0.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Star size={18} color={colors.white} />
        </Box>
      )}

      {/* Avatar */}
      <Box
        sx={{
          position: "absolute",
          top: 15,
          left: 15,
          width: isConductor ? 56 : 44,
          height: isConductor ? 56 : 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: accentColor,
          border: "2px solid",
          borderColor: alpha(accentColor, 0.55),
          borderRadius: isConductor ? "50%" : 0.5,
          boxShadow: shadowStack(accentColor),
          zIndex: 2,
        }}
      >
        {isConductor ? (
          <UserAvatar size={28} color={colors.white} />
        ) : (
          SpecialistIcon && <SpecialistIcon size={24} color={colors.white} />
        )}
      </Box>

      {/* Header */}
      <Box
        sx={{
          pl: isConductor ? 11 : 9,
          pr: 2,
          py: 1.5,
          bgcolor: alpha(accentColor, 0.15),
          borderBottom: `1px solid ${alpha(accentColor, 0.3)}`,
          display: "flex",
          flexDirection: "column",
          minHeight: isConductor ? 56 : 48,
        }}
      >
        <Typography
          sx={{
            fontWeight: 600,
            fontSize: isConductor ? 16 : 14,
            fontFamily: "TiemposHeadline, Georgia, serif",
            lineHeight: 1.2,
            color: "text.primary",
          }}
        >
          {member.name}
        </Typography>
        <Typography
          sx={{
            fontSize: 11,
            color: "text.secondary",
            fontStyle: "italic",
          }}
        >
          {member.role}
        </Typography>
      </Box>

      {/* Body */}
      <Box sx={{ px: 2, pt: 1.5, pb: 6 }}>
        {/* Mission/Description */}
        {member.description && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 11,
              }}
            >
              Mission
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                lineHeight: 1.5,
                fontSize: 11,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {member.description}
            </Typography>
          </Box>
        )}

        {/* Communication Style for Conductor */}
        {isConductor && member.communicationStyle && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 11,
              }}
            >
              Communication Style
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                lineHeight: 1.5,
                fontSize: 11,
              }}
            >
              {member.communicationStyle}
            </Typography>
          </Box>
        )}

        {/* Focus and Called When for Specialists */}
        {!isConductor && parsedSections["Called When"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 11,
              }}
            >
              Called When
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                lineHeight: 1.5,
                fontSize: 11,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {parsedSections["Called When"]}
            </Typography>
          </Box>
        )}

        {/* Expertise Tags */}
        {expertise.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 11,
              }}
            >
              Expertise
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {expertise.map((exp, i) => (
                <Chip
                  key={i}
                  label={exp}
                  size="small"
                  sx={{
                    bgcolor: colors.ivory,
                    color: "text.primary",
                    fontSize: 10,
                    height: 20,
                    maxWidth: "200px",
                    textOverflow: "ellipsis",
                    border: `1px solid ${alpha(accentColor, 0.4)}`,
                    "& .MuiChip-label": { px: 1 },
                  }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Flip Button */}
        <Box
          sx={{
            position: "absolute",
            bottom: 10,
            right: 10,
          }}
        >
          <FlipButton
            onClick={onFlip}
            showHint={showHint}
            isConductor={isConductor}
          />
        </Box>
      </Box>
    </Paper>
  );
}

// Card Back Face - Character Stats
function CardBack({
  member,
  isConductor,
  onFlip,
}: {
  member: ExtendedTeamMember;
  isConductor?: boolean;
  onFlip: () => void;
}) {
  const accentColor = isConductor ? colors.gold : colors.emerald;
  const parsedSections = useMemo(
    () => parseSystemPrompt(member.systemPrompt),
    [member.systemPrompt]
  );
  const tools = member.tools?.filter((t) => t && t !== "{}") || [];

  return (
    <Paper
      variant="outlined"
      sx={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        borderRadius: 1,
        overflow: "hidden",
        borderColor: accentColor,
        borderWidth: isConductor ? 2 : 1,
        bgcolor: colors.white,
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.08)",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        transform: "rotateY(180deg)",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2,
          py: 1,
          bgcolor: accentColor,
          color: colors.white,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Typography
          sx={{
            fontWeight: 600,
            fontSize: 13,
            fontFamily: "TiemposHeadline, Georgia, serif",
          }}
        >
          Stats & Abilities
        </Typography>
        <Typography sx={{ fontSize: 11, opacity: 0.9 }}>
          {member.name}
        </Typography>
      </Box>

      {/* Body - Scrollable */}
      <Box
        sx={{
          px: 2,
          pt: 1.5,
          pb: 5,
          height: "calc(100% - 40px)",
          overflow: "auto",
          "&::-webkit-scrollbar": { width: 4 },
          "&::-webkit-scrollbar-thumb": {
            bgcolor: alpha(accentColor, 0.3),
            borderRadius: 2,
          },
        }}
      >
        {/* Problem-Solving Approach */}
        {parsedSections["Problem-Solving Approach"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 10,
              }}
            >
              Problem-Solving
            </Typography>
            <Typography
              variant="body2"
              sx={{ color: "text.secondary", lineHeight: 1.4, fontSize: 10 }}
            >
              {parsedSections["Problem-Solving Approach"]}
            </Typography>
          </Box>
        )}

        {/* Guiding Principles */}
        {parsedSections["Guiding Principles"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 10,
              }}
            >
              Guiding Principles
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{
                color: "text.secondary",
                lineHeight: 1.4,
                fontSize: 10,
                whiteSpace: "pre-wrap",
              }}
            >
              {parsedSections["Guiding Principles"]}
            </Typography>
          </Box>
        )}

        {/* Tools */}
        {tools.length > 0 && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 10,
              }}
            >
              Tools
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {tools.map((tool, i) => (
                <Chip
                  key={i}
                  label={tool}
                  size="small"
                  variant="outlined"
                  sx={{
                    fontSize: 9,
                    height: 18,
                    borderColor: alpha(accentColor, 0.5),
                    color: "text.secondary",
                    "& .MuiChip-label": { px: 0.75 },
                  }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Conductor-specific sections */}
        {isConductor && (
          <>
            {parsedSections["Solo Handling"] && (
              <Box sx={{ mb: 1.5 }}>
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 600,
                    color: colors.grayMedium,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    mb: 0.5,
                    fontSize: 10,
                  }}
                >
                  Works Solo When
                </Typography>
                <Typography
                  variant="body2"
                  component="div"
                  sx={{
                    color: "text.secondary",
                    lineHeight: 1.4,
                    fontSize: 10,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {parsedSections["Solo Handling"]}
                </Typography>
              </Box>
            )}

            {parsedSections["Delegation Triggers"] && (
              <Box sx={{ mb: 1.5 }}>
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 600,
                    color: colors.grayMedium,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    mb: 0.5,
                    fontSize: 10,
                  }}
                >
                  Delegates When
                </Typography>
                <Typography
                  variant="body2"
                  component="div"
                  sx={{
                    color: "text.secondary",
                    lineHeight: 1.4,
                    fontSize: 10,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {parsedSections["Delegation Triggers"]}
                </Typography>
              </Box>
            )}
          </>
        )}

        {/* Specialist boundaries */}
        {!isConductor && parsedSections["Background"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.grayMedium,
                textTransform: "uppercase",
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 10,
              }}
            >
              Background
            </Typography>
            <Typography
              variant="body2"
              sx={{ color: "text.secondary", lineHeight: 1.4, fontSize: 10 }}
            >
              {parsedSections["Background"]}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Flip Button */}
      <Box
        sx={{
          position: "absolute",
          bottom: 10,
          right: 10,
        }}
      >
        <FlipButton
          onClick={onFlip}
          showHint={false}
          isConductor={isConductor}
        />
      </Box>
    </Paper>
  );
}

// FlipCard Component - Container with 3D perspective and hover effects
function FlipCard({
  member,
  isConductor,
  showHint,
  onFirstFlip,
  animationDelay,
}: {
  member: ExtendedTeamMember;
  isConductor?: boolean;
  showHint: boolean;
  onFirstFlip: () => void;
  animationDelay?: number;
}) {
  const [isFlipped, setIsFlipped] = useState(false);

  const handleFlip = () => {
    if (showHint && !isFlipped) {
      onFirstFlip();
    }
    setIsFlipped(!isFlipped);
  };

  const cardWidth = isConductor
    ? { xs: "100%", md: 500 }
    : { xs: "100%", sm: 300 };
  const cardHeight = isConductor ? 340 : 300;

  return (
    <Box
      sx={{
        perspective: "1000px",
        width: cardWidth,
        height: cardHeight,
        maxWidth: "100%",
        minWidth: isConductor ? undefined : { sm: 280 },
        flex: isConductor ? undefined : { sm: "1 1 300px" },
        transition: "transform 0.2s ease-out",
        "&:hover": {
          transform: "translateY(-4px)",
        },
      }}
    >
      <Box
        sx={{
          position: "relative",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transition: "transform 0.6s ease-in-out",
          transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        <CardFront
          member={member}
          isConductor={isConductor}
          showHint={showHint}
          onFlip={handleFlip}
          animationDelay={animationDelay}
        />
        <CardBack
          member={member}
          isConductor={isConductor}
          onFlip={handleFlip}
        />
      </Box>
    </Box>
  );
}

// Delegation Flow Visualization Component
function DelegationFlowSection({
  specialists,
}: {
  specialists: ExtendedTeamMember[];
}) {
  if (specialists.length === 0) return null;

  return (
    <Box
      sx={{
        mt: 4,
        pt: 3,
        borderTop: "1px solid",
        borderColor: "divider",
        textAlign: "center",
      }}
    >
      <Typography
        sx={{
          fontSize: 13,
          fontWeight: 600,
          color: colors.grayMedium,
          mb: 2,
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        Delegation Flow Visualization
      </Typography>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 1,
          flexWrap: "wrap",
        }}
      >
        {/* Conductor receives task */}
        <Box
          sx={{
            px: 2,
            py: 1,
            bgcolor: alpha(colors.gold, 0.15),
            border: `1px solid ${alpha(colors.gold, 0.3)}`,
            borderRadius: 1,
          }}
        >
          <Typography sx={{ fontSize: 11, color: "text.primary" }}>
            Conductor receives task
          </Typography>
        </Box>

        <ArrowRight size={16} style={{ opacity: 0.5, color: "inherit" }} />

        {/* Delegates to specialist */}
        <Box
          sx={{
            px: 2,
            py: 1,
            bgcolor: alpha(colors.emerald, 0.15),
            border: `1px solid ${alpha(colors.emerald, 0.3)}`,
            borderRadius: 1,
          }}
        >
          <Typography sx={{ fontSize: 11, color: "text.primary" }}>
            Delegates to [Specialist] with condition
          </Typography>
        </Box>

        <ArrowRight size={16} style={{ opacity: 0.5, color: "inherit" }} />

        {/* Specialist returns */}
        <Box
          sx={{
            px: 2,
            py: 1,
            bgcolor: alpha(colors.emerald, 0.15),
            border: `1px solid ${alpha(colors.emerald, 0.3)}`,
            borderRadius: 1,
          }}
        >
          <Typography sx={{ fontSize: 11, color: "text.primary" }}>
            Specialist returns [deliverable]
          </Typography>
        </Box>

        <ArrowRight size={16} style={{ opacity: 0.5, color: "inherit" }} />

        {/* Conductor synthesizes */}
        <Box
          sx={{
            px: 2,
            py: 1,
            bgcolor: alpha(colors.gold, 0.15),
            border: `1px solid ${alpha(colors.gold, 0.3)}`,
            borderRadius: 1,
          }}
        >
          <Typography sx={{ fontSize: 11, color: "text.primary" }}>
            Conductor synthesizes final output
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export type AiTeamViewProps = {
  onLoadingChange?: (loading: boolean) => void;
  isSetupMode?: boolean;
  onContinue?: () => void;
  currentStep?: number;
  totalSteps?: number;
  teamConfig?: TeamConfig | null;
  workspaceName?: string;
};

export default function AiTeamView({
  onLoadingChange,
  isSetupMode = false,
  onContinue,
  currentStep = 4,
  totalSteps = 4,
  teamConfig,
  workspaceName,
}: AiTeamViewProps) {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace?.workspaceId ?? null;

  const [members, setMembers] = useState<AiTeamMember[]>([]);
  const [hasSeenFlipHint, setHasSeenFlipHint] = useState(() => {
    return localStorage.getItem("aiTeamFlipHintSeen") === "true";
  });
  const [animationPhase, setAnimationPhase] = useState(0);
  const teamRowRef = useRef<HTMLDivElement>(null);

  const handleFirstFlip = () => {
    setHasSeenFlipHint(true);
    localStorage.setItem("aiTeamFlipHintSeen", "true");
  };

  // Animation sequence on mount
  useEffect(() => {
    const timers = [
      setTimeout(() => setAnimationPhase(1), 100), // Conductor fades in
      setTimeout(() => setAnimationPhase(2), 400), // Lines draw
      setTimeout(() => setAnimationPhase(3), 800), // Specialists fade in
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  // Fetch full team member data from API
  useEffect(() => {
    if (!workspaceId) return;

    let mounted = true;
    async function load() {
      if (!workspaceId) return;
      if (!isSetupMode) {
        onLoadingChange?.(true);
      }
      try {
        const data = await fetchAiTeamMembers(workspaceId);
        if (!mounted) return;
        setMembers(data);
      } catch (e: unknown) {
        if (!mounted) return;
        console.error("Failed to load AI team members:", e);
      } finally {
        if (mounted && !isSetupMode) {
          onLoadingChange?.(false);
        }
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [workspaceId, onLoadingChange, isSetupMode]);

  // Merge TeamConfig agents with full API data
  const teamMembers: ExtendedTeamMember[] = useMemo(() => {
    if (teamConfig?.agents) {
      return teamConfig.agents.map((agent) => {
        const fullData = members.find(
          (m) => m.agentId === agent.agent_id || m.name === agent.name
        );

        return {
          aiTeamMemberId: fullData?.aiTeamMemberId || agent.agent_id,
          aiTeamId: fullData?.aiTeamId || teamConfig.team_id,
          agentId: agent.agent_id,
          name: fullData?.name || agent.name || agent.role,
          role: fullData?.role || agent.role,
          type: (agent.type || "specialist") as "conductor" | "specialist",
          capabilities: agent.capabilities,
          description: fullData?.description,
          expertise: fullData?.expertise,
          tools: fullData?.tools,
          communicationStyle: fullData?.communicationStyle,
          systemPrompt: fullData?.systemPrompt,
          createdAt: fullData?.createdAt || new Date().toISOString(),
          updatedAt: fullData?.updatedAt || new Date().toISOString(),
        };
      });
    }

    return members.map((m) => ({
      ...m,
      type: "specialist" as const,
      capabilities: m.description
        ? m.description
            .split(/\n|;|[•\u2022]|-/)
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    }));
  }, [teamConfig, members]);

  // Separate conductor from specialists
  const { conductor, specialists } = useMemo(() => {
    const conductor = teamMembers.find((m) => m.type === "conductor");
    const specialists = teamMembers.filter((m) => m.type !== "conductor");
    return { conductor, specialists };
  }, [teamMembers]);

  // Determine if team is ready
  const isTeamReady = !!(teamConfig?.agents && teamConfig.agents.length > 0);

  // Setup mode: full height with footer
  if (isSetupMode) {
    // Show loading animation if team is not ready
    if (!isTeamReady) {
      return (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            height: "100vh",
            bgcolor: "background.default",
          }}
        >
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 3,
            }}
          >
            <Box sx={{ position: "relative", width: 264, height: 286 }}>
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
                    stroke={colors.gold}
                    strokeWidth="0.5"
                  />
                  <circle
                    opacity="0.8"
                    cx="130.961"
                    cy="141.961"
                    r="112.711"
                    stroke={colors.gold}
                    strokeWidth="0.5"
                  />
                  <circle
                    cx="130.256"
                    cy="142.256"
                    r="68.7559"
                    fill={colors.gold}
                    fillOpacity="0.2"
                    stroke={colors.ivory}
                  />
                </svg>
              </Box>
            </Box>

            <Typography
              variant="h6"
              sx={{ color: "text.primary", fontWeight: 500 }}
            >
              Building Your AI Team...
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Assembling team members based on your workspace requirements
            </Typography>
          </Box>

          <SetupFooter
            currentStep={currentStep}
            totalSteps={totalSteps}
            onContinue={onContinue || (() => {})}
            buttonDisabled={true}
          />
        </Box>
      );
    }

    // Team is ready - show Command Center view
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          bgcolor: "background.default",
          backgroundImage: `
            radial-gradient(circle at 20% 80%, ${alpha(
              colors.gold,
              0.05
            )} 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, ${alpha(
              colors.emerald,
              0.05
            )} 0%, transparent 50%)
          `,
        }}
      >
        <Box
          sx={{
            flex: 1,
            overflow: "auto",
            p: 0,
          }}
        >
          <Box component="main" sx={{ maxWidth: "100%", px: 0 }}>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 0, p: 4 }}
            >
              {/* Header with decorative elements */}
              <Box sx={{ mb: 4, textAlign: "center" }}>
                {workspaceName && (
                  <Typography
                    variant="h4"
                    sx={{
                      fontWeight: 600,
                      mb: 1,
                      color: "text.primary",
                      fontFamily: "TiemposHeadline, Georgia, serif",
                    }}
                  >
                    {workspaceName}
                  </Typography>
                )}
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 1,
                  }}
                >
                  <Box
                    sx={{
                      width: 40,
                      height: 1,
                      bgcolor: alpha(colors.gold, 0.3),
                    }}
                  />
                  <Typography
                    variant="subtitle1"
                    sx={{
                      fontWeight: 500,
                      color: "text.secondary",
                      fontSize: 14,
                    }}
                  >
                    Your AI Team
                  </Typography>
                  <Box
                    sx={{
                      width: 40,
                      height: 1,
                      bgcolor: alpha(colors.gold, 0.3),
                    }}
                  />
                </Box>
              </Box>

              {/* Hierarchical Tree Layout */}
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 0,
                }}
              >
                {/* Conductor Card (Top) */}
                {conductor && animationPhase >= 1 && (
                  <FlipCard
                    member={conductor}
                    isConductor
                    showHint={!hasSeenFlipHint}
                    onFirstFlip={handleFirstFlip}
                    animationDelay={0}
                  />
                )}

                {/* Spacer between conductor and specialists */}
                {specialists.length > 0 && <Box sx={{ height: 24 }} />}

                {/* Team Members Row */}
                <Box
                  ref={teamRowRef}
                  sx={{
                    display: "flex",
                    justifyContent: "center",
                    gap: 3,
                    flexWrap: { xs: "wrap", lg: "nowrap" },
                    width: "100%",
                    maxWidth: 1100,
                  }}
                >
                  {animationPhase >= 3 &&
                    specialists.map((m, index) => (
                      <FlipCard
                        key={m.aiTeamMemberId}
                        member={m}
                        showHint={!hasSeenFlipHint}
                        onFirstFlip={handleFirstFlip}
                        animationDelay={index * 0.15}
                      />
                    ))}
                </Box>

                {/* Delegation Flow */}
                {animationPhase >= 3 && (
                  <DelegationFlowSection specialists={specialists} />
                )}
              </Box>
            </Box>
          </Box>
        </Box>

        <SetupFooter
          currentStep={currentStep}
          totalSteps={totalSteps}
          buttonText="Go to Workspace"
          onContinue={onContinue || (() => {})}
        />
      </Box>
    );
  }

  // Normal mode: show loading or tree view
  if (members.length === 0) {
    return (
      <Box sx={{ p: 0, bgcolor: "background.default", minHeight: 400 }}>
        <Box component="main" sx={{ maxWidth: "100%", px: 0 }}>
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 3,
              minHeight: 400,
              py: 4,
            }}
          >
            <Box sx={{ position: "relative", width: 264, height: 286 }}>
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
                    stroke={colors.gold}
                    strokeWidth="0.5"
                  />
                  <circle
                    opacity="0.8"
                    cx="130.961"
                    cy="141.961"
                    r="112.711"
                    stroke={colors.gold}
                    strokeWidth="0.5"
                  />
                  <circle
                    cx="130.256"
                    cy="142.256"
                    r="68.7559"
                    fill={colors.gold}
                    fillOpacity="0.2"
                    stroke={colors.ivory}
                  />
                </svg>
              </Box>
            </Box>

            <Typography
              variant="h6"
              sx={{ color: "text.primary", fontWeight: 500 }}
            >
              Your team is being created...
            </Typography>
          </Box>
        </Box>
      </Box>
    );
  }

  // Normal mode with team data - show Command Center view
  return (
    <Box
      sx={{
        p: 4,
        bgcolor: "background.default",
        backgroundImage: `
          radial-gradient(circle at 20% 80%, ${alpha(
            colors.gold,
            0.05
          )} 0%, transparent 50%),
          radial-gradient(circle at 80% 20%, ${alpha(
            colors.emerald,
            0.05
          )} 0%, transparent 50%)
        `,
        minHeight: "100%",
      }}
    >
      <Box component="main" sx={{ maxWidth: "100%", px: 0 }}>
        {/* Hierarchical Tree Layout */}
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 0,
          }}
        >
          {/* Conductor Card (Top) */}
          {conductor && (
            <FlipCard
              member={conductor}
              isConductor
              showHint={!hasSeenFlipHint}
              onFirstFlip={handleFirstFlip}
            />
          )}

          {/* Spacer between conductor and specialists */}
          {specialists.length > 0 && <Box sx={{ height: 24 }} />}

          {/* Team Members Row */}
          <Box
            ref={teamRowRef}
            sx={{
              display: "flex",
              justifyContent: "center",
              gap: 3,
              flexWrap: { xs: "wrap", lg: "nowrap" },
              width: "100%",
              maxWidth: 1100,
            }}
          >
            {specialists.map((m) => (
              <FlipCard
                key={m.aiTeamMemberId}
                member={m}
                showHint={!hasSeenFlipHint}
                onFirstFlip={handleFirstFlip}
              />
            ))}
          </Box>

          {/* Delegation Flow */}
          <DelegationFlowSection specialists={specialists} />
        </Box>
      </Box>
    </Box>
  );
}
