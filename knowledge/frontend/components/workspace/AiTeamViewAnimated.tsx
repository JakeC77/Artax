import { useEffect, useMemo, useState, useRef, useCallback } from "react";
import {
  Box,
  Paper,
  Typography,
  Chip,
  keyframes,
  Tooltip,
  IconButton,
  Alert,
  Modal,
  Button,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import {
  Identification,
  Rotate,
  Star,
  DataBase,
  Chemistry,
  ChartLine,
  ArrowRight,
  UserAvatar,
  View,
  Close,
} from "@carbon/icons-react";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import {
  fetchAiTeamMembers,
  type AiTeamMember,
  type TeamConfig,
  type IntentPackage,
} from "../../services/graphql";
import SetupFooter from "./setup/SetupFooter";
// React Bits components for enhanced interactivity
import TiltedCard from "../common/TiltedCard";
import ClickSpark from "../common/ClickSpark";
import DecryptedText from "../common/DecryptedText";

// Brand colors from design system
const colors = {
  white: "#FFFFFF",
  charcoal: "#1C1C1C",
  ivory: "#F4F0E6",
  gold: "#C6A664",
  emerald: "#0F5C4C",
  grayLight: "#D6D6D6",
  grayMedium: "#5E5E5E",
  grayDark: "#2B2B2B",
};

const shadowStack = (color: string) =>
  `1px 1px 0 0 ${color}, 2px 2px 0 0 ${color}, 3px 3px 0 0 ${color}, 4px 4px 0 0 ${color}, 5px 5px 0 0 ${color}`;

// Loading animation
const rotate = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

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
  0%, 100% { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  50% { box-shadow: 0 3px 10px rgba(0,0,0,0.12); }
`;

const borderGlowEmerald = keyframes`
  0%, 100% { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  50% { box-shadow: 0 3px 10px rgba(0,0,0,0.12); }
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
  systemPrompt: string | null | undefined,
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

function inferConductorId(members: AiTeamMember[]): string | null {
  if (!members.length) return null;

  const hasConductorSignals = (member: AiTeamMember) => {
    const haystack = `${member.role ?? ""} ${member.name ?? ""}`;
    if (
      /\b(conductor|orchestrator|lead|manager|director|coordinator|chief|head)\b/i.test(
        haystack,
      )
    ) {
      return true;
    }
    if (member.communicationStyle) {
      return true;
    }
    if (
      member.systemPrompt &&
      /##\s*(solo handling|delegation triggers|communication style)/i.test(
        member.systemPrompt,
      )
    ) {
      return true;
    }
    return false;
  };

  const explicit = members.find(hasConductorSignals);
  return explicit?.aiTeamMemberId ?? null;
}

// Custom hook for drag-to-scroll with momentum
function useDragScroll(ref: React.RefObject<HTMLElement | null>) {
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartY = useRef(0);
  const scrollStartX = useRef(0);
  const velocityX = useRef(0);
  const lastX = useRef(0);
  const lastTime = useRef(0);
  const animationFrame = useRef<number | undefined>(undefined);
  const isDragHorizontal = useRef<boolean | null>(null);

  const applyMomentum = useCallback((): void => {
    if (!ref.current || Math.abs(velocityX.current) < 0.5) {
      velocityX.current = 0;
      return;
    }

    ref.current.scrollLeft -= velocityX.current;
    velocityX.current *= 0.95; // Friction coefficient

    animationFrame.current = requestAnimationFrame(applyMomentum);
  }, [ref]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!ref.current) return;
    
    // Check if click is on a scrollable element
    const target = e.target as HTMLElement;
    const isScrollable = target.closest('[data-scrollable="true"]');
    if (isScrollable) return;
    
    setIsDragging(true);
    dragStartX.current = e.pageX;
    dragStartY.current = e.pageY;
    scrollStartX.current = ref.current.scrollLeft;
    velocityX.current = 0;
    lastX.current = e.pageX;
    lastTime.current = Date.now();
    isDragHorizontal.current = null;
    
    // Cancel any ongoing momentum
    if (animationFrame.current) {
      cancelAnimationFrame(animationFrame.current);
    }
  }, [ref]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging || !ref.current) return;

    const currentX = e.pageX;
    const currentY = e.pageY;
    const deltaX = Math.abs(currentX - dragStartX.current);
    const deltaY = Math.abs(currentY - dragStartY.current);

    // Determine drag direction on first significant move
    if (isDragHorizontal.current === null && (deltaX > 5 || deltaY > 5)) {
      isDragHorizontal.current = deltaX > deltaY;
    }

    // Only proceed if horizontal drag
    if (isDragHorizontal.current === false) return;

    const currentTime = Date.now();
    const scrollDelta = dragStartX.current - currentX;
    const deltaTime = currentTime - lastTime.current;

    // Calculate velocity for momentum
    if (deltaTime > 0) {
      velocityX.current = (lastX.current - currentX) / deltaTime * 16; // Normalize to 60fps
    }

    ref.current.scrollLeft = scrollStartX.current + scrollDelta;
    
    lastX.current = currentX;
    lastTime.current = currentTime;

    // Prevent text selection during horizontal drag
    if (isDragHorizontal.current) {
      e.preventDefault();
    }
  }, [isDragging, ref]);

  const handleMouseUp = useCallback(() => {
    if (!isDragging) return;
    
    setIsDragging(false);
    
    // Apply momentum scrolling only if it was a horizontal drag
    if (isDragHorizontal.current && Math.abs(velocityX.current) > 0.5) {
      animationFrame.current = requestAnimationFrame(applyMomentum);
    }
    
    isDragHorizontal.current = null;
  }, [isDragging, applyMomentum]);

  const handleMouseLeave = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      velocityX.current = 0;
      isDragHorizontal.current = null;
    }
  }, [isDragging]);

  // Touch events for mobile
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (!ref.current || e.touches.length !== 1) return;
    
    // Check if touch is on a scrollable element
    const target = e.target as HTMLElement;
    const isScrollable = target.closest('[data-scrollable="true"]');
    if (isScrollable) return;
    
    const touch = e.touches[0];
    setIsDragging(true);
    dragStartX.current = touch.pageX;
    dragStartY.current = touch.pageY;
    scrollStartX.current = ref.current.scrollLeft;
    velocityX.current = 0;
    lastX.current = touch.pageX;
    lastTime.current = Date.now();
    isDragHorizontal.current = null;
    
    if (animationFrame.current) {
      cancelAnimationFrame(animationFrame.current);
    }
  }, [ref]);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging || !ref.current || e.touches.length !== 1) return;

    const touch = e.touches[0];
    const currentX = touch.pageX;
    const currentY = touch.pageY;
    const deltaX = Math.abs(currentX - dragStartX.current);
    const deltaY = Math.abs(currentY - dragStartY.current);

    // Determine drag direction on first significant move
    if (isDragHorizontal.current === null && (deltaX > 5 || deltaY > 5)) {
      isDragHorizontal.current = deltaX > deltaY;
    }

    // Only proceed if horizontal drag
    if (isDragHorizontal.current === false) return;

    const currentTime = Date.now();
    const scrollDelta = dragStartX.current - currentX;
    const deltaTime = currentTime - lastTime.current;

    if (deltaTime > 0) {
      velocityX.current = (lastX.current - currentX) / deltaTime * 16;
    }

    ref.current.scrollLeft = scrollStartX.current + scrollDelta;
    
    lastX.current = currentX;
    lastTime.current = currentTime;

    // Prevent default only for horizontal drag
    if (isDragHorizontal.current) {
      e.preventDefault();
    }
  }, [isDragging, ref]);

  const handleTouchEnd = useCallback(() => {
    if (!isDragging) return;
    
    setIsDragging(false);
    
    // Apply momentum scrolling only if it was a horizontal drag
    if (isDragHorizontal.current && Math.abs(velocityX.current) > 0.5) {
      animationFrame.current = requestAnimationFrame(applyMomentum);
    }
    
    isDragHorizontal.current = null;
  }, [isDragging, applyMomentum]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (animationFrame.current) {
        cancelAnimationFrame(animationFrame.current);
      }
    };
  }, []);

  return {
    isDragging,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onMouseLeave: handleMouseLeave,
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
    },
  };
}

// Custom hook for calculating card scale and opacity based on position
function useCardScaleEffect(
  containerRef: React.RefObject<HTMLElement | null>,
  cardRefs: React.RefObject<(HTMLElement | null)[]>
) {
  const [cardStyles, setCardStyles] = useState<{ scale: number; opacity: number }[]>([]);

  const updateCardStyles = useCallback(() => {
    if (!containerRef.current || !cardRefs.current) return;

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const containerCenter = containerRect.left + containerRect.width / 2;
    
    // Responsive scale values
    const isMobile = window.innerWidth < 768;
    const isTablet = window.innerWidth >= 768 && window.innerWidth < 1200;
    
    // Scale ranges based on screen size
    const maxScale = isMobile ? 1.015 : isTablet ? 1.03 : 1.06;
    const minScale = isMobile ? 0.97 : isTablet ? 0.94 : 0.92;
    const minOpacity = isMobile ? 0.82 : isTablet ? 0.78 : 0.72;

    const newStyles = cardRefs.current.map((cardEl) => {
      if (!cardEl) return { scale: 1, opacity: 1 };

      const cardRect = cardEl.getBoundingClientRect();
      const cardCenter = cardRect.left + cardRect.width / 2;
      
      // Calculate distance from container center
      const distance = Math.abs(cardCenter - containerCenter);
      const maxDistance = containerRect.width / 2;
      const normalizedDistance = Math.min(distance / maxDistance, 1);

      // Linear interpolation for scale and opacity
      const scale = maxScale - normalizedDistance * (maxScale - minScale);
      const opacity = 1 - normalizedDistance * (1 - minOpacity);

      return { scale, opacity };
    });

    setCardStyles(newStyles);
  }, [containerRef, cardRefs]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Update on scroll
    const handleScroll = () => {
      requestAnimationFrame(updateCardStyles);
    };

    // Initial update
    updateCardStyles();

    container.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', updateCardStyles);

    return () => {
      container.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', updateCardStyles);
    };
  }, [containerRef, updateCardStyles]);

  return cardStyles;
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
          variant="caption"
          sx={{ color: colors.grayMedium, fontWeight: 600, lineHeight: 1 }}
        >
          More info
        </Typography>
        <ClickSpark sparkColor={accentColor} sparkCount={6} sparkSize={4}>
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
        </ClickSpark>
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
  const theme = useTheme();
  const accentColor = isConductor ? colors.gold : colors.emerald;
  const expertise = member.expertise?.slice(0, isConductor ? 4 : 3) || [];
  const parsedSections = useMemo(
    () => parseSystemPrompt(member.systemPrompt),
    [member.systemPrompt],
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
        borderRadius: 0.5,
        overflow: "hidden",
        borderColor: accentColor,
        borderWidth: 1,
        bgcolor:
          theme.palette.mode === "light" ? colors.white : colors.charcoal,
        boxShadow:
          theme.palette.mode === "light"
            ? "0 2px 8px rgba(0, 0, 0, 0.08)"
            : "0 2px 8px rgba(0, 0, 0, 0.3)",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        transition: "box-shadow 0.2s ease",
        "&:hover": {
          boxShadow:
            theme.palette.mode === "light"
              ? "0 4px 12px rgba(0, 0, 0, 0.12)"
              : "0 4px 12px rgba(0, 0, 0, 0.4)",
        },
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

      {/* Header */}
      <Box
        sx={{
          px: 2,
          py: 1.5,
          bgcolor: alpha(accentColor, 0.15),
          borderBottom: `1px solid ${alpha(accentColor, 0.3)}`,
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          minHeight: 64,
        }}
      >
        {/* Avatar */}
        <Box
          sx={{
            width: isConductor ? 56 : 44,
            height: isConductor ? 56 : 44,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: alpha(accentColor, 0.75),
            border: "2px solid",
            borderColor: accentColor,
            borderRadius: isConductor ? "50%" : 0.5,
            boxShadow: shadowStack(accentColor),
          }}
        >
          {isConductor ? (
            <UserAvatar size={28} color={colors.white} />
          ) : (
            SpecialistIcon && <SpecialistIcon size={24} color={colors.white} />
          )}
        </Box>

        {/* Name and Role */}
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            minWidth: 0,
          }}
        >
          <Typography
            variant="h6"
            sx={{
              fontWeight: 600,
              fontFamily: "TiemposHeadline, Georgia, serif",
              lineHeight: 1.2,
              color:
                theme.palette.mode === "light" ? colors.charcoal : colors.ivory,
            }}
          >
            {member.name}
          </Typography>
          <Typography
            variant="subtitle2"
            sx={{
              fontSize: 11,
              color:
                theme.palette.mode === "light"
                  ? colors.grayMedium
                  : colors.grayLight,
              fontStyle: "italic",
            }}
          >
            {member.role}
          </Typography>
        </Box>
      </Box>

      {/* Body */}
      <Box 
        sx={{ 
          px: 2, 
          pt: 1.5, 
          pb: 6,
          height: "calc(100% - 64px)", // Height minus header
          overflow: "auto",
          "&::-webkit-scrollbar": { width: 4 },
          "&::-webkit-scrollbar-thumb": {
            bgcolor: theme.palette.mode === "light" 
              ? alpha(accentColor, 0.3)
              : alpha(accentColor, 0.5),
            borderRadius: 2,
          },
        }}
      >
        {/* Mission/Description */}
        {member.description && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              Mission
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.5,
                fontSize: 12,
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
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              Communication Style
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.5,
                fontSize: 12,
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
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              Called When
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.5,
                fontSize: 12,
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
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
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
                    bgcolor:
                      theme.palette.mode === "light"
                        ? colors.ivory
                        : colors.grayDark,
                    color:
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory,
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
  isFlipped,
}: {
  member: ExtendedTeamMember;
  isConductor?: boolean;
  onFlip: () => void;
  isFlipped: boolean;
}) {
  const theme = useTheme();
  const accentColor = isConductor ? colors.gold : colors.emerald;
  const parsedSections = useMemo(
    () => parseSystemPrompt(member.systemPrompt),
    [member.systemPrompt],
  );
  const tools = member.tools?.filter((t) => t && t !== "{}") || [];

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
        bgcolor:
          theme.palette.mode === "light" ? colors.white : colors.charcoal,
        boxShadow:
          theme.palette.mode === "light"
            ? "0 2px 8px rgba(0, 0, 0, 0.08)"
            : "0 2px 8px rgba(0, 0, 0, 0.3)",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        transform: "rotateY(180deg)",
        transition: "box-shadow 0.2s ease",
        "&:hover": {
          boxShadow:
            theme.palette.mode === "light"
              ? "0 4px 12px rgba(0, 0, 0, 0.12)"
              : "0 4px 12px rgba(0, 0, 0, 0.4)",
        },
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
          variant="h6"
          sx={{
            fontWeight: 600,
            fontSize: 16,
            fontFamily: "TiemposHeadline, Georgia, serif",
          }}
        >
          Stats & Abilities
        </Typography>
        <Typography sx={{ fontSize: 14, opacity: 0.9 }}>
          {member.name}
        </Typography>
      </Box>

      {/* Body - Scrollable */}
      <Box
        data-scrollable="true"
        sx={{
          px: 2,
          pt: 1.5,
          pb: 5,
          height: "calc(100% - 40px)",
          overflow: "auto",
          "&::-webkit-scrollbar": { width: 4 },
          "&::-webkit-scrollbar-thumb": {
            bgcolor:
              theme.palette.mode === "light"
                ? alpha(accentColor, 0.3)
                : alpha(accentColor, 0.5),
            borderRadius: 2,
          },
        }}
      >
        {/* Problem-Solving Approach */}
        {parsedSections["Problem-Solving Approach"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              <DecryptedText
                text="Problem-Solving"
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight
                }
                fontSize={16}
              />
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.4,
              }}
            >
              <DecryptedText
                text={parsedSections["Problem-Solving Approach"]}
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory
                }
                fontSize={12}
                fontFamily="inherit"
              />
            </Typography>
          </Box>
        )}

        {/* Guiding Principles */}
        {parsedSections["Guiding Principles"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              <DecryptedText
                text="Guiding Principles"
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight
                }
                fontSize={16}
              />
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.4,
                whiteSpace: "pre-wrap",
              }}
            >
              <DecryptedText
                text={parsedSections["Guiding Principles"]}
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory
                }
                fontSize={12}
                fontFamily="inherit"
              />
            </Typography>
          </Box>
        )}

        {/* Tools */}
        {tools.length > 0 && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              <DecryptedText
                text="Tools"
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight
                }
                fontSize={16}
              />
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
                    color:
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory,
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
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    color:
                      theme.palette.mode === "light"
                        ? colors.grayMedium
                        : colors.grayLight,
                    letterSpacing: 0.5,
                    mb: 0.5,
                    fontSize: 16,
                  }}
                >
                  <DecryptedText
                    text="Works Solo When"
                    speed={60}
                    maxIterations={12}
                    animateOn="trigger"
                    trigger={isFlipped}
                    color={
                      theme.palette.mode === "light"
                        ? colors.grayMedium
                        : colors.grayLight
                    }
                    fontSize={16}
                  />
                </Typography>
                <Typography
                  variant="body2"
                  component="div"
                  sx={{
                    color:
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory,
                    lineHeight: 1.4,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  <DecryptedText
                    text={parsedSections["Solo Handling"]}
                    speed={60}
                    maxIterations={12}
                    animateOn="trigger"
                    trigger={isFlipped}
                    color={
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory
                    }
                    fontSize={12}
                    fontFamily="inherit"
                  />
                </Typography>
              </Box>
            )}

            {parsedSections["Delegation Triggers"] && (
              <Box sx={{ mb: 1.5 }}>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    color:
                      theme.palette.mode === "light"
                        ? colors.grayMedium
                        : colors.grayLight,

                    letterSpacing: 0.5,
                    mb: 0.5,
                    fontSize: 16,
                  }}
                >
                  <DecryptedText
                    text="Delegates When"
                    speed={60}
                    maxIterations={12}
                    animateOn="trigger"
                    trigger={isFlipped}
                    color={
                      theme.palette.mode === "light"
                        ? colors.grayMedium
                        : colors.grayLight
                    }
                    fontSize={16}
                  />
                </Typography>
                <Typography
                  variant="body2"
                  component="div"
                  sx={{
                    color:
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory,
                    lineHeight: 1.4,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  <DecryptedText
                    text={parsedSections["Delegation Triggers"]}
                    speed={60}
                    maxIterations={12}
                    animateOn="trigger"
                    trigger={isFlipped}
                    color={
                      theme.palette.mode === "light"
                        ? colors.charcoal
                        : colors.ivory
                    }
                    fontSize={12}
                    fontFamily="inherit"
                  />
                </Typography>
              </Box>
            )}
          </>
        )}

        {/* Specialist boundaries */}
        {!isConductor && parsedSections["Background"] && (
          <Box sx={{ mb: 1.5 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color:
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight,
                letterSpacing: 0.5,
                mb: 0.5,
                fontSize: 16,
              }}
            >
              <DecryptedText
                text="Background"
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.grayMedium
                    : colors.grayLight
                }
                fontSize={16}
              />
            </Typography>
            <Typography
              variant="body2"
              component="div"
              sx={{
                color:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                lineHeight: 1.4,
              }}
            >
              <DecryptedText
                text={parsedSections["Background"]}
                speed={60}
                maxIterations={12}
                animateOn="trigger"
                trigger={isFlipped}
                color={
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory
                }
                fontSize={12}
                fontFamily="inherit"
              />
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
  scale = 1,
  fadeOpacity = 1,
}: {
  member: ExtendedTeamMember;
  isConductor?: boolean;
  showHint: boolean;
  onFirstFlip: () => void;
  animationDelay?: number;
  scale?: number;
  fadeOpacity?: number;
}) {
  const [isFlipped, setIsFlipped] = useState(false);
  const [isFlippedForDecrypt, setIsFlippedForDecrypt] = useState(false);

  const handleFlip = () => {
    if (showHint && !isFlipped) {
      onFirstFlip();
    }
    const newFlipped = !isFlipped;
    setIsFlipped(newFlipped);

    // Delay decrypt trigger until after flip animation completes (0.6s)
    if (newFlipped) {
      setTimeout(() => {
        setIsFlippedForDecrypt(true);
      }, 600);
    } else {
      setIsFlippedForDecrypt(false);
    }
  };

  const cardWidth = isConductor
    ? { xs: "100%", sm: "100%", md: 560 }
    : { xs: "100%", sm: 360, md: 380, lg: 420 };
  const cardHeight = isConductor ? { xs: 340, sm: 360, md: 380 } : { xs: 320, sm: 340, md: 340 };

  // Card content wrapped with interactive effects
  return (
    <Box
      sx={{
        width: cardWidth,
        height: cardHeight,
        maxWidth: "100%",
        minWidth: isConductor ? undefined : { xs: 280, sm: 340, md: 360 },
        flex: isConductor ? undefined : { sm: "0 1 450px" },
        position: "relative",
        zIndex: 1,
        flexShrink: 0,
        transform: `scale(${scale})`,
        opacity: fadeOpacity,
        transition:
          "transform 0.42s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.36s ease-out",
        willChange: "transform, opacity",
        "&:hover": {
          zIndex: 10,
        },
      }}
    >
      <Box sx={{ width: "100%", height: "100%" }}>
        <TiltedCard tiltMaxAngle={3} scale={1.08}>
          <Box
            sx={{
              perspective: "1000px",
              width: "100%",
              height: "100%",
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
                isFlipped={isFlippedForDecrypt}
              />
            </Box>
          </Box>
        </TiltedCard>
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

export type AiTeamViewAnimatedProps = {
  onLoadingChange?: (loading: boolean) => void;
  isSetupMode?: boolean;
  onContinue?: () => void;
  currentStep?: number;
  totalSteps?: number;
  teamConfig?: TeamConfig | null;
  workspaceName?: string;
  /** Error message to display if team building fails */
  error?: string | null;
  intentPackage?: IntentPackage | null;
};

export default function AiTeamViewAnimated({
  onLoadingChange,
  isSetupMode = false,
  onContinue,
  currentStep = 4,
  totalSteps = 4,
  teamConfig,
  workspaceName,
  error = null,
  intentPackage,
}: AiTeamViewAnimatedProps) {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace?.workspaceId ?? null;
  const theme = useTheme();

  const [members, setMembers] = useState<AiTeamMember[]>([]);
  const [hasSeenFlipHint, setHasSeenFlipHint] = useState(() => {
    return localStorage.getItem("aiTeamFlipHintSeen") === "true";
  });
  const [animationPhase, setAnimationPhase] = useState(0);
  const teamRowRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const hasAppliedInitialRosterScroll = useRef(false);
  const [intentModalOpen, setIntentModalOpen] = useState(false);

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
  // In setup mode, retry if empty (team may not be persisted yet)
  useEffect(() => {
    if (!workspaceId) return;

    let mounted = true;
    let retryCount = 0;
    const maxRetries = 10;
    const retryDelay = 1000; // 1 second between retries

    async function load() {
      if (!workspaceId || !mounted) return;
      if (!isSetupMode) {
        onLoadingChange?.(true);
      }
      try {
        const data = await fetchAiTeamMembers(workspaceId);
        if (!mounted) return;

        // In setup mode, if no data and we have teamConfig, retry
        if (
          isSetupMode &&
          data.length === 0 &&
          teamConfig?.agents?.length &&
          retryCount < maxRetries
        ) {
          retryCount++;
          setTimeout(load, retryDelay);
          return;
        }

        setMembers(data);
      } catch (e: unknown) {
        if (!mounted) return;
        console.error("Failed to load AI team members:", e);

        // In setup mode, retry on error too
        if (isSetupMode && retryCount < maxRetries) {
          retryCount++;
          setTimeout(load, retryDelay);
          return;
        }
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
  }, [workspaceId, onLoadingChange, isSetupMode, teamConfig?.agents?.length]);

  // Merge TeamConfig agents with full API data
  const inferredConductorId = useMemo(() => {
    if (teamConfig?.agents?.length) return null;
    return inferConductorId(members);
  }, [teamConfig?.agents?.length, members]);

  const teamMembers: ExtendedTeamMember[] = useMemo(() => {
    // Only use teamConfig.agents if it has entries, otherwise fall back to members from API
    if (teamConfig?.agents && teamConfig.agents.length > 0) {
      return teamConfig.agents.map((agent) => {
        const fullData = members.find(
          (m) => m.agentId === agent.agent_id || m.name === agent.name,
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
      type:
        inferredConductorId && m.aiTeamMemberId === inferredConductorId
          ? ("conductor" as const)
          : ("specialist" as const),
      capabilities: m.description
        ? m.description
            .split(/\n|;|[•\u2022]|-/)
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    }));
  }, [teamConfig, members, inferredConductorId]);

  // Separate conductor from specialists
  const { conductor, specialists } = useMemo(() => {
    const conductor = teamMembers.find((m) => m.type === "conductor");
    const specialists = teamMembers.filter((m) => m.type !== "conductor");
    return { conductor, specialists };
  }, [teamMembers]);
  const specialistsSignature = useMemo(
    () => specialists.map((m) => m.aiTeamMemberId).join("|"),
    [specialists],
  );

  // Carousel hooks for drag-to-scroll and scale effects
  const { isDragging, handlers } = useDragScroll(teamRowRef as React.RefObject<HTMLElement | null>);
  const cardStyles = useCardScaleEffect(teamRowRef as React.RefObject<HTMLElement | null>, cardRefs);

  // Reset initial-scroll flag when roster composition changes
  useEffect(() => {
    hasAppliedInitialRosterScroll.current = false;
  }, [specialistsSignature]);

  // Initial roster position: center second specialist when 3+ members exist
  useEffect(() => {
    if (specialists.length < 3) return;
    if (hasAppliedInitialRosterScroll.current) return;
    if (isSetupMode && animationPhase < 3) return;

    const container = teamRowRef.current;
    const secondCard = cardRefs.current[1];
    if (!container || !secondCard) return;

    const timer = setTimeout(() => {
      secondCard.scrollIntoView({
        behavior: "auto",
        block: "nearest",
        inline: "center",
      });
      hasAppliedInitialRosterScroll.current = true;
    }, 0);

    return () => clearTimeout(timer);
  }, [specialists.length, isSetupMode, animationPhase, specialistsSignature]);

  // Determine if team is ready - need API data loaded (members)
  // teamConfig.agents may be empty if constructed from setup_complete event,
  // but members from fetchAiTeamMembers() has the full data we need to render
  const isTeamReady = members.length > 0;

  // Setup mode: full height with footer
  if (isSetupMode) {
    // Show loading animation if team is not ready (or error state)
    if (!isTeamReady || error) {
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
            {/* Show error state or loading animation */}
            {error ? (
              <>
                <Typography
                  variant="h5"
                  sx={{ color: "error.main", fontWeight: 600 }}
                >
                  Team Building Failed
                </Typography>
                <Alert severity="error" sx={{ maxWidth: 500 }}>
                  {error}
                </Alert>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  Please create a new workspace to try again.
                </Typography>
              </>
            ) : (
              <>
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
                        fill={colors.ivory}
                        fillOpacity="0.85"
                      />
                      <circle
                        cx="87.2722"
                        cy="114.641"
                        r="1.37004"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <circle
                        cx="91.1082"
                        cy="114.641"
                        r="1.37004"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <circle
                        cx="94.9444"
                        cy="114.641"
                        r="1.37004"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <rect
                        x="86.4501"
                        y="119.3"
                        width="87.6824"
                        height="23.0166"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <rect
                        x="130.839"
                        y="145.604"
                        width="43.2932"
                        height="9.31626"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <rect
                        x="86.4501"
                        y="158.757"
                        width="87.6824"
                        height="9.31626"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <rect
                        x="86.4501"
                        y="146.7"
                        width="26.8527"
                        height="2.74008"
                        rx="1.37004"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />
                      <rect
                        x="86.4501"
                        y="151.084"
                        width="38.9091"
                        height="2.74008"
                        rx="1.37004"
                        fill={colors.gold}
                        fillOpacity="0.5"
                      />

                      {/* Top icon with line */}
                      <path
                        d="M133.507 39.0052C134.979 39.0052 136.173 37.8113 136.173 36.3386C136.173 34.8658 134.979 33.6719 133.507 33.6719C132.034 33.6719 130.84 34.8658 130.84 36.3386C130.84 37.8113 132.034 39.0052 133.507 39.0052ZM133.507 110.597L134.007 110.597L134.007 36.3386L133.507 36.3386L133.007 36.3386L133.007 110.597L133.507 110.597Z"
                        fill={colors.emerald}
                      />

                      {/* Bottom icon with line */}
                      <path
                        d="M133.507 244.597C132.034 244.597 130.84 245.791 130.84 247.264C130.84 248.737 132.034 249.931 133.507 249.931C134.979 249.931 136.173 248.737 136.173 247.264C136.173 245.791 134.979 244.597 133.507 244.597ZM133.507 175.376L133.007 175.376L133.007 247.264L133.507 247.264L134.007 247.264L134.007 175.376L133.507 175.376Z"
                        fill={colors.emerald}
                      />

                      {/* Right icon with line */}
                      <path
                        d="M231.167 139.036C231.167 140.509 232.361 141.703 233.834 141.703C235.307 141.703 236.501 140.509 236.501 139.036C236.501 137.563 235.307 136.369 233.834 136.369C232.361 136.369 231.167 137.563 231.167 139.036ZM177.746 139.036V139.536H233.834V139.036V138.536H177.746V139.036Z"
                        fill={colors.emerald}
                      />

                      {/* Left icon with line */}
                      <path
                        d="M31.8959 139.036C31.8959 137.563 30.702 136.369 29.2292 136.369C27.7565 136.369 26.5626 137.563 26.5626 139.036C26.5626 140.509 27.7565 141.703 29.2292 141.703C30.702 141.703 31.8959 140.509 31.8959 139.036ZM82.9479 139.036L82.9479 138.536L29.2292 138.536L29.2292 139.036L29.2292 139.536L82.9479 139.536L82.9479 139.036Z"
                        fill={colors.emerald}
                      />

                      {/* Diagonal icons with lines */}
                      <path
                        d="M194.954 69.9492C196.065 70.9161 197.75 70.7994 198.716 69.6885C199.683 68.5776 199.567 66.8932 198.456 65.9263C197.345 64.9594 195.66 65.0761 194.694 66.187C193.727 67.2979 193.843 68.9823 194.954 69.9492ZM159.576 110.597L159.953 110.925L197.082 68.266L196.705 67.9378L196.328 67.6095L159.199 110.268L159.576 110.597Z"
                        fill={colors.emerald}
                      />
                      <path
                        d="M57.629 61.4247C58.8312 60.5739 59.116 58.9097 58.2653 57.7075C57.4145 56.5054 55.7503 56.2205 54.5481 57.0713C53.3459 57.922 53.061 59.5863 53.9118 60.7884C54.7626 61.9906 56.4268 62.2755 57.629 61.4247ZM92.4276 110.597L92.8357 110.308L56.4967 58.9591L56.0885 59.248L55.6804 59.5368L92.0195 110.886L92.4276 110.597Z"
                        fill={colors.emerald}
                      />
                      <path
                        d="M61.4895 210.268C60.2538 209.466 58.6025 209.818 57.8011 211.054C56.9998 212.29 57.3519 213.941 58.5876 214.742C59.8232 215.544 61.4745 215.192 62.2759 213.956C63.0772 212.72 62.7251 211.069 61.4895 210.268ZM84.1169 175.376L83.6974 175.104L59.619 212.233L60.0385 212.505L60.458 212.777L84.5364 175.648L84.1169 175.376Z"
                        fill={colors.emerald}
                      />
                      <path
                        d="M199.913 210.323C198.707 211.169 198.416 212.832 199.262 214.037C200.109 215.243 201.772 215.534 202.977 214.687C204.183 213.841 204.474 212.178 203.627 210.973C202.781 209.767 201.118 209.476 199.913 210.323ZM175.376 175.376L174.966 175.663L201.036 212.792L201.445 212.505L201.854 212.218L175.785 175.089L175.376 175.376Z"
                        fill={colors.emerald}
                      />

                      {/* Corner icons with circles */}
                      <circle
                        cx="133.255"
                        cy="18.4213"
                        r="17.4213"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="133.388"
                        cy="263.734"
                        r="16.2605"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="206.304"
                        cy="56.2078"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="55.4177"
                        cy="45.1482"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="53.8378"
                        cy="225.263"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="211.044"
                        cy="223.683"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="248.173"
                        cy="137.638"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
                      />
                      <circle
                        cx="15.1287"
                        cy="137.638"
                        r="14.1287"
                        stroke={colors.emerald}
                        strokeWidth="2"
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
              </>
            )}
          </Box>

          <SetupFooter
            currentStep={currentStep}
            totalSteps={totalSteps}
            onContinue={onContinue || (() => {})}
            buttonDisabled={!error}
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
          p: 0,
          bgcolor: "background.default",
        }}
      >
        <Box
          sx={{
            flex: 1,
            overflow: "visible",
            p: 0,
            overflowY: "auto",
          }}
        >
          <Box component="main" sx={{ maxWidth: "100%", px: 0 }}>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 0, p: 4 }}
            >
              {/* Header with decorative elements */}
              <Box sx={{ mb: 4 }}>
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
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    gap: 1.5,
                  }}
                >
                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 500,
                      color: "text.main",
                    }}
                  >
                    Your team
                  </Typography>
                  {intentPackage && (
                    <Button
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
                          color: colors.emerald,
                          bgcolor: alpha(colors.emerald, 0.08),
                        },
                      }}
                    >
                      View Intent
                    </Button>
                  )}
                </Box>
              </Box>

              {/* Hierarchical Tree Layout */}
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 0,
                  width: "100%",
                  overflow: "visible",
                }}
              >
                {/* Conductor Card (Top) */}
                {conductor && animationPhase >= 1 && (
                  <Box 
                    sx={{ 
                      mb: { xs: 3, sm: 4 }, 
                      mt: { xs: 3, sm: 4 },
                      px: { xs: 2, sm: 3, md: 0 },
                      width: "100%",
                      display: "flex",
                      justifyContent: "center",
                    }}
                  >
                    <Box sx={{ 
                      width: "100%",
                      maxWidth: { xs: "100%", sm: 500, md: 560 }
                    }}>
                      <FlipCard
                        member={conductor}
                        isConductor
                        showHint={!hasSeenFlipHint}
                        onFirstFlip={handleFirstFlip}
                        animationDelay={0}
                      />
                    </Box>
                  </Box>
                )}

                {/* Spacer between conductor and specialists */}
                {specialists.length > 0 && animationPhase >= 1 && (
                  <Box sx={{ height: 0 }} />
                )}

                {/* Team Members Row */}
                <Box
                  sx={{
                    position: "relative",
                    width: "100%",
                    maxWidth: "100vw",
                    overflow: "visible", // Changed from hidden to visible
                    py: 2, // Add vertical padding for hover expansion
                  }}
                >
                  {/* Gradient masks */}
                  <Box
                    sx={{
                      position: "absolute",
                      left: 0,
                      top: "32px",
                      bottom: "32px",
                      width: { xs: 40, sm: 60, md: 80, lg: 120 },
                      background: `linear-gradient(to right, ${theme.palette.background.default} 0%, transparent 100%)`,
                      zIndex: 2,
                      pointerEvents: "none",
                    }}
                  />
                  <Box
                    sx={{
                      position: "absolute",
                      right: 0,
                      top: "32px",
                      bottom: "32px",
                      width: { xs: 40, sm: 60, md: 80, lg: 120 },
                      background: `linear-gradient(to left, ${theme.palette.background.default} 0%, transparent 100%)`,
                      zIndex: 2,
                      pointerEvents: "none",
                    }}
                  />
                  
                  {/* Carousel container */}
                  <Box
                    ref={teamRowRef}
                    {...handlers}
                    sx={{
                      display: "flex",
                      gap: { xs: 2, sm: 3, md: 4, lg: 5 },
                      px: { xs: 1, sm: 2, md: 0 },
                      py: { xs: 4, sm: 5, md: 6 }, // Reduced padding on mobile
                      overflowX: "auto",
                      overflowY: "visible", // Allow vertical overflow for hover effects
                      scrollBehavior: "smooth",
                      cursor: isDragging ? "grabbing" : "grab",
                      userSelect: "none",
                      WebkitOverflowScrolling: "touch",
                      // Hide scrollbar
                      scrollbarWidth: "none",
                      msOverflowStyle: "none",
                      "&::-webkit-scrollbar": {
                        display: "none",
                      },
                      // Snap scrolling to center cards
                      scrollSnapType: { xs: "x mandatory", md: "x mandatory" },
                      // Center alignment - show 1 card centered with 0.5 cards on each side
                      "&::before, &::after": {
                        content: '""',
                        flexShrink: 0,
                        width: {
                          xs: "max(20px, calc((100vw - 280px) / 2 - 8px))", // Mobile: prevent negative values
                          sm: "max(30px, calc((100vw - 340px) / 2 - 12px))", // Small tablets
                          md: "calc((100vw - 380px) / 2 - 16px)", // Tablet
                          lg: "calc((100vw - 450px) / 2 - 20px)", // Desktop
                        },
                      },
                    }}
                  >
                    {animationPhase >= 3 &&
                      specialists.map((m, index) => (
                        <Box
                          key={m.aiTeamMemberId}
                          ref={(el: HTMLDivElement | null) => {
                            if (cardRefs.current) {
                              cardRefs.current[index] = el;
                            }
                          }}
                          sx={{
                            scrollSnapAlign: "center",
                            scrollSnapStop: "always",
                            flexShrink: 0,
                          }}
                        >
                          <FlipCard
                            member={m}
                            showHint={!hasSeenFlipHint}
                            onFirstFlip={handleFirstFlip}
                            animationDelay={index * 0.15}
                            scale={cardStyles[index]?.scale || 1}
                            fadeOpacity={cardStyles[index]?.opacity || 1}
                          />
                        </Box>
                      ))}
                  </Box>
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

        {/* Intent Modal */}
        <Modal
          open={intentModalOpen}
          onClose={() => setIntentModalOpen(false)}
          aria-labelledby="intent-modal-title"
        >
          <Paper
            sx={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "90%",
              maxWidth: 600,
              maxHeight: "85vh",
              overflow: "auto",
              p: 0,
              borderRadius: 1,
              outline: "none",
              bgcolor:
                theme.palette.mode === "light" ? colors.white : colors.charcoal,
            }}
          >
            {/* Modal Header */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                px: 3,
                py: 2,
                borderBottom: "1px solid",
                borderColor: "divider",
                position: "sticky",
                top: 0,
                bgcolor:
                  theme.palette.mode === "light"
                    ? colors.charcoal
                    : colors.ivory,
                zIndex: 1,
              }}
            >
              <Typography
                id="intent-modal-title"
                variant="h6"
                sx={{
                  fontWeight: 600,
                  color:
                    theme.palette.mode === "light"
                      ? colors.ivory
                      : colors.charcoal,
                }}
              >
                Workspace Intent
              </Typography>
              <IconButton
                size="small"
                onClick={() => setIntentModalOpen(false)}
                sx={{
                  color:
                    theme.palette.mode === "light"
                      ? colors.ivory
                      : colors.charcoal,
                }}
              >
                <Close size={20} />
              </IconButton>
            </Box>

            {/* Modal Content */}
            {intentPackage && (
              <Box sx={{ p: 3 }}>
                {/* Primary Objective */}
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{ fontWeight: 600, mb: 1, color: colors.emerald }}
                  >
                    Primary Objective
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      lineHeight: 1.6,
                      color:
                        theme.palette.mode === "light"
                          ? colors.charcoal
                          : colors.ivory,
                    }}
                  >
                    {intentPackage.mission?.objective ||
                      intentPackage.summary ||
                      "No objective defined"}
                  </Typography>
                </Box>

                {/* Business Context */}
                {intentPackage.mission?.why && (
                  <Box sx={{ mb: 3 }}>
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 600, mb: 1, color: colors.emerald }}
                    >
                      Business Context
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        lineHeight: 1.6,
                        whiteSpace: "pre-wrap",
                        color:
                          theme.palette.mode === "light"
                            ? colors.charcoal
                            : colors.ivory,
                      }}
                    >
                      {intentPackage.mission.why}
                    </Typography>
                  </Box>
                )}

                {/* Success Criteria */}
                {intentPackage.mission?.success_looks_like && (
                  <Box sx={{ mb: 3 }}>
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 600, mb: 1, color: colors.emerald }}
                    >
                      Success Criteria
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{ lineHeight: 1.6, whiteSpace: "pre-wrap" }}
                      component="div"
                    >
                      {intentPackage.mission.success_looks_like
                        .split(/[-•]/g)
                        .filter(Boolean)
                        .map((item, idx) => (
                          <Box
                            key={idx}
                            sx={{ display: "flex", gap: 1, mb: 0.5 }}
                          >
                            <Typography
                              variant="body2"
                              sx={{
                                color:
                                  theme.palette.mode === "light"
                                    ? colors.grayMedium
                                    : colors.grayLight,
                              }}
                            >
                              •
                            </Typography>
                            <Typography
                              variant="body2"
                              sx={{
                                color:
                                  theme.palette.mode === "light"
                                    ? colors.charcoal
                                    : colors.ivory,
                              }}
                            >
                              {item.trim()}
                            </Typography>
                          </Box>
                        ))}
                    </Typography>
                  </Box>
                )}

                {/* Team Guidance (if available) */}
                {intentPackage.team_guidance && (
                  <Box
                    sx={{
                      mt: 2,
                      pt: 2,
                      borderTop: "1px solid",
                      borderColor:
                        theme.palette.mode === "light"
                          ? colors.grayLight
                          : colors.grayDark,
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 600,
                        mb: 1.5,
                        color:
                          theme.palette.mode === "light"
                            ? colors.grayMedium
                            : colors.grayLight,
                      }}
                    >
                      Team Guidance
                    </Typography>

                    {intentPackage.team_guidance.expertise_needed &&
                      intentPackage.team_guidance.expertise_needed.length >
                        0 && (
                        <Box sx={{ mb: 2 }}>
                          <Typography
                            variant="caption"
                            sx={{
                              fontWeight: 600,
                              color:
                                theme.palette.mode === "light"
                                  ? colors.grayMedium
                                  : colors.grayLight,
                              display: "block",
                              mb: 0.5,
                            }}
                          >
                            Expertise Needed
                          </Typography>
                          <Box
                            sx={{
                              display: "flex",
                              flexWrap: "wrap",
                              gap: 0.5,
                            }}
                          >
                            {intentPackage.team_guidance.expertise_needed.map(
                              (skill: string, idx: number) => (
                                <Chip
                                  key={idx}
                                  label={skill}
                                  size="small"
                                  variant="outlined"
                                  sx={{
                                    fontSize: "0.75rem",
                                    borderColor: colors.emerald,
                                    color:
                                      theme.palette.mode === "light"
                                        ? colors.charcoal
                                        : colors.ivory,
                                  }}
                                />
                              ),
                            )}
                          </Box>
                        </Box>
                      )}

                    {intentPackage.team_guidance.complexity_level && (
                      <Box sx={{ mb: 2 }}>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 600,
                            color:
                              theme.palette.mode === "light"
                                ? colors.grayMedium
                                : colors.grayLight,
                            display: "block",
                            mb: 0.5,
                          }}
                        >
                          Complexity
                        </Typography>
                        <Chip
                          label={intentPackage.team_guidance.complexity_level}
                          size="small"
                          color={
                            intentPackage.team_guidance.complexity_level ===
                            "Simple"
                              ? "success"
                              : intentPackage.team_guidance.complexity_level ===
                                  "Moderate"
                                ? "warning"
                                : "error"
                          }
                          sx={{ fontSize: "0.75rem" }}
                        />
                        {intentPackage.team_guidance.complexity_notes && (
                          <Typography
                            variant="caption"
                            sx={{
                              display: "block",
                              mt: 0.5,
                              color:
                                theme.palette.mode === "light"
                                  ? colors.grayMedium
                                  : colors.grayLight,
                            }}
                          >
                            {intentPackage.team_guidance.complexity_notes}
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                )}
              </Box>
            )}
          </Paper>
        </Modal>
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
        p: 0,
        bgcolor: "background.default",
        minHeight: "100%",
        mb: 4,
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
            width: "100%",
              overflow: "visible",
          }}
        >
          {/* Conductor Card (Top) */}
          {conductor && (
            <Box 
              sx={{ 
                mb: { xs: 3, sm: 4 }, 
                mt: { xs: 3, sm: 4 },
                px: { xs: 2, sm: 3, md: 0 },
                width: "100%",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <Box sx={{ 
                width: "100%",
                maxWidth: { xs: "100%", sm: 500, md: 560 }
              }}>
                <FlipCard
                  member={conductor}
                  isConductor
                  showHint={!hasSeenFlipHint}
                  onFirstFlip={handleFirstFlip}
                />
              </Box>
            </Box>
          )}

          {/* Team Members Row */}
          <Box
            sx={{
              position: "relative",
              width: "100%",
              maxWidth: "100vw",
              overflow: "visible", // Changed from hidden to visible
              py: 2, // Add vertical padding for hover expansion
            }}
          >
            {/* Gradient masks */}
            <Box
              sx={{
                position: "absolute",
                left: 0,
                top: "32px",
                bottom: "32px",
                width: { xs: 40, sm: 60, md: 80, lg: 120 },
                background: `linear-gradient(to right, ${theme.palette.background.default} 0%, transparent 100%)`,
                zIndex: 2,
                pointerEvents: "none",
              }}
            />
            <Box
              sx={{
                position: "absolute",
                right: 0,
                top: "32px",
                bottom: "32px",
                width: { xs: 40, sm: 60, md: 80, lg: 120 },
                background: `linear-gradient(to left, ${theme.palette.background.default} 0%, transparent 100%)`,
                zIndex: 2,
                pointerEvents: "none",
              }}
            />
            
            {/* Carousel container */}
            <Box
              ref={teamRowRef}
              {...handlers}
              sx={{
                display: "flex",
                gap: { xs: 2, sm: 3, md: 4, lg: 5 },
                px: { xs: 1, sm: 2, md: 0 },
                py: { xs: 4, sm: 5, md: 6 },
                overflowX: "auto",
                overflowY: "visible",
                scrollBehavior: "smooth",
                cursor: isDragging ? "grabbing" : "grab",
                userSelect: "none",
                WebkitOverflowScrolling: "touch",
                // Hide scrollbar
                scrollbarWidth: "none",
                msOverflowStyle: "none",
                "&::-webkit-scrollbar": {
                  display: "none",
                },
                // Snap scrolling to center cards
                scrollSnapType: { xs: "x mandatory", md: "x mandatory" },
                // Center alignment - show 1 card centered with 0.5 cards on each side
                "&::before, &::after": {
                  content: '""',
                  flexShrink: 0,
                  width: {
                    xs: "max(20px, calc((100vw - 280px) / 2 - 8px))",
                    sm: "max(30px, calc((100vw - 340px) / 2 - 12px))",
                    md: "calc((100vw - 380px) / 2 - 16px)",
                    lg: "calc((100vw - 450px) / 2 - 20px)",
                  },
                },
              }}
            >
              {specialists.map((m, index) => (
                <Box
                  key={m.aiTeamMemberId}
                  ref={(el: HTMLDivElement | null) => {
                    if (cardRefs.current) {
                      cardRefs.current[index] = el;
                    }
                  }}
                  sx={{
                    scrollSnapAlign: "center",
                    scrollSnapStop: "always",
                    flexShrink: 0,
                  }}
                >
                  <FlipCard
                    member={m}
                    showHint={!hasSeenFlipHint}
                    onFirstFlip={handleFirstFlip}
                    scale={cardStyles[index]?.scale || 1}
                    fadeOpacity={cardStyles[index]?.opacity || 1}
                  />
                </Box>
              ))}
            </Box>
          </Box>

          {/* Delegation Flow */}
          <DelegationFlowSection specialists={specialists} />
        </Box>
      </Box>
    </Box>
  );
}
