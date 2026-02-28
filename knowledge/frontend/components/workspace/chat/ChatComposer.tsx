import { Box, IconButton, Typography, InputBase } from "@mui/material";
import type { SxProps, Theme } from "@mui/material";
import AttachFileRoundedIcon from "@mui/icons-material/AttachFileRounded";
import { Microphone, Send } from "@carbon/icons-react";

export type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  disabled?: boolean;
  disabledBannerText?: string;
  placeholder?: string;
  helperText?: string;
  showAttach?: boolean;
  showMicrophone?: boolean;
  maxRows?: number;
  sx?: SxProps<Theme>;
  paperSx?: SxProps<Theme>;
};

export default function ChatComposer({
  value,
  onChange,
  onSend,
  sending,
  disabled = false,
  disabledBannerText = "Chat disabled while agents are at work",
  placeholder = "Ask anything",
  helperText = "Press Enter to run",
  showAttach = true,
  showMicrophone = true,
  maxRows,
  sx,
  paperSx,
}: ChatComposerProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled) {
        onSend();
      }
    }
  };

  return (
    <Box sx={{ width: "100%", ...sx }}>
      {disabled && (
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
          {disabledBannerText}
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
          opacity: disabled ? 0.65 : 1,
          ...paperSx,
        }}
      >
        {showAttach && (
          <IconButton size="small" sx={{ color: "text.secondary" }}>
            <AttachFileRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        )}

        <InputBase
          fullWidth
          placeholder={
            disabled ? "Please wait for the current response..." : placeholder
          }
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          sx={{
            fontSize: 14,
            color: "text.primary",
            // '& input, & textarea': {
            //   color:  'text.primary',
            //   opacity: 1,
            // },
            "& input::placeholder, & textarea::placeholder": {
              color: (theme) =>
                disabled
                  ? theme.palette.text.disabled
                  : theme.palette.text.secondary,
              opacity: 1,
            },
            "& input, & textarea": {
              color: "text.primary",
              WebkitTextFillColor: "currentColor",
              opacity: 1,
            },
          }}
          multiline
          maxRows={maxRows}
        />
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          {showMicrophone && (
            <IconButton size="small">
              <Microphone size={20} />
            </IconButton>
          )}
          <IconButton
            size="small"
            color="primary"
            aria-label="send"
            disabled={disabled || sending || !value.trim()}
            onClick={() => onSend()}
          >
            <Send size={20} />
          </IconButton>
        </Box>
      </Box>
      {helperText && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 0.75, display: "block" }}
        >
          {helperText}
        </Typography>
      )}
    </Box>
  );
}
