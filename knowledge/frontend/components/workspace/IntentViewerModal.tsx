import { Modal, Paper, Box, Typography, IconButton, Chip } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { Close } from "@carbon/icons-react";
import type { IntentPackage } from "../../services/graphql";

export interface IntentViewerModalProps {
  open: boolean;
  onClose: () => void;
  intentPackage: IntentPackage | null;
  /** Legacy intent text for older workspaces without structured intentPackage */
  legacyIntent?: string;
}

export default function IntentViewerModal({
  open,
  onClose,
  intentPackage,
  legacyIntent,
}: IntentViewerModalProps) {
  const theme = useTheme();

  // Check if we have meaningful structured content in intentPackage
  const hasStructuredContent =
    intentPackage &&
    (intentPackage.mission?.objective ||
      intentPackage.mission?.why ||
      intentPackage.mission?.success_looks_like ||
      intentPackage.summary);

  // Only show legacy fallback if there's NO structured content
  // Always prefer structured data when available
  const showLegacyFallback = !hasStructuredContent && !!legacyIntent;

  return (
    <Modal
      open={open}
      onClose={onClose}
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
          bgcolor: theme.palette.mode === "light" ? "#FFFFFF" : "#1C1C1C",
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
            bgcolor: theme.palette.mode === "light" ? "#1C1C1C" : "#F4F0E6",
            zIndex: 1,
          }}
        >
          <Typography
            id="intent-modal-title"
            variant="h6"
            sx={{
              fontWeight: 600,
              color: theme.palette.mode === "light" ? "#F4F0E6" : "#1C1C1C",
            }}
          >
            Workspace Intent
          </Typography>
          <IconButton
            size="small"
            onClick={onClose}
            sx={{
              color: theme.palette.mode === "light" ? "#F4F0E6" : "#1C1C1C",
            }}
          >
            <Close size={20} />
          </IconButton>
        </Box>

        {/* Modal Content */}
        {showLegacyFallback ? (
          /* Legacy intent fallback - plain text display */
          <Box sx={{ p: 3 }}>
            <Typography
              variant="body2"
              sx={{
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                color: theme.palette.mode === "light" ? "#1C1C1C" : "#F4F0E6",
              }}
            >
              {legacyIntent}
            </Typography>
          </Box>
        ) : hasStructuredContent && intentPackage ? (
          <Box sx={{ p: 3 }}>
            {/* Primary Objective */}
            {intentPackage.mission?.objective && (
              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle2"
                  sx={{ fontWeight: 600, mb: 1, color: "#0F5C4C" }}
                >
                  Primary Objective
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    lineHeight: 1.6,
                    color:
                      theme.palette.mode === "light" ? "#1C1C1C" : "#F4F0E6",
                  }}
                >
                  {intentPackage.mission.objective}
                </Typography>
              </Box>
            )}

            {/* Business Context */}
            {intentPackage.mission?.why && (
              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle2"
                  sx={{ fontWeight: 600, mb: 1, color: "#0F5C4C" }}
                >
                  Business Context
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    color:
                      theme.palette.mode === "light" ? "#1C1C1C" : "#F4F0E6",
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
                  sx={{ fontWeight: 600, mb: 1, color: "#0F5C4C" }}
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
                                ? "#5E5E5E"
                                : "#D6D6D6",
                          }}
                        >
                          •
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            color:
                              theme.palette.mode === "light"
                                ? "#1C1C1C"
                                : "#F4F0E6",
                          }}
                        >
                          {item.trim()}
                        </Typography>
                      </Box>
                    ))}
                </Typography>
              </Box>
            )}

            {/* Summary (show if no mission objective/why but has summary) */}
            {!intentPackage.mission?.objective &&
              !intentPackage.mission?.why &&
              intentPackage.summary && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{ fontWeight: 600, mb: 1, color: "#0F5C4C" }}
                  >
                    Summary
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      lineHeight: 1.6,
                      whiteSpace: "pre-wrap",
                      color:
                        theme.palette.mode === "light" ? "#1C1C1C" : "#F4F0E6",
                    }}
                  >
                    {intentPackage.summary}
                  </Typography>
                </Box>
              )}

            {/* Team Guidance (if available) */}
            {intentPackage.team_guidance &&
              Object.keys(intentPackage.team_guidance).length > 0 && (
                <Box
                  sx={{
                    mt: 2,
                    pt: 2,
                    borderTop: "1px solid",
                    borderColor:
                      theme.palette.mode === "light" ? "#D6D6D6" : "#2B2B2B",
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 600,
                      mb: 1.5,
                      color:
                        theme.palette.mode === "light" ? "#5E5E5E" : "#D6D6D6",
                    }}
                  >
                    Team Guidance
                  </Typography>

                  {intentPackage.team_guidance.expertise_needed &&
                    intentPackage.team_guidance.expertise_needed.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 600,
                            color:
                              theme.palette.mode === "light"
                                ? "#5E5E5E"
                                : "#D6D6D6",
                            display: "block",
                            mb: 0.5,
                          }}
                        >
                          Expertise Needed
                        </Typography>
                        <Box
                          sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}
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
                                  borderColor: "#0F5C4C",
                                  color:
                                    theme.palette.mode === "light"
                                      ? "#1C1C1C"
                                      : "#F4F0E6",
                                }}
                              />
                            )
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
                              ? "#5E5E5E"
                              : "#D6D6D6",
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
                                ? "#5E5E5E"
                                : "#D6D6D6",
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
        ) : (
          <Box sx={{ p: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Intent is not available for this workspace yet.
            </Typography>
          </Box>
        )}
      </Paper>
    </Modal>
  );
}
