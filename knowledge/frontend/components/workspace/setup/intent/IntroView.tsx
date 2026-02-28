import { Box, Typography } from "@mui/material";
import ChatComposer from "../../chat/ChatComposer";

export type IntroViewProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  disabled?: boolean;
};

export default function IntroView({
  value,
  onChange,
  onSend,
  sending,
  disabled = false,
}: IntroViewProps) {
  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        px: 3,
        bgcolor: "background.default",
      }}
    >
      {/* Centered content container */}
      <Box
        sx={{
          textAlign: "center",
          maxWidth: 520,
          width: "100%",
          pt: 20,
        }}
      >
        {/* Greeting */}
        <Typography
          variant="h4"
          sx={{
            fontWeight: 400,
            mb: 1.5,
            fontSize: { xs: "1.5rem", sm: "1.75rem" },
            lineHeight: 1.3,
          }}
        >
          <Box component="span" sx={{ display: "inline" }}>
            <Box component="span" role="img" aria-label="wave">
              👋
            </Box>{" "}
            Hi! I'm Theo,
          </Box>
          <br />
          <Box component="span" sx={{ fontWeight: 600 }}>
            your workspace assistant.
          </Box>
        </Typography>

        {/* Description */}
        <Typography
          variant="body1"
          sx={{
            color: "text.secondary",
            fontSize: "0.9375rem",
            mb: 3,
            lineHeight: 1.6,
          }}
        >
          I'll help you set up this workspace so it's tailored to what you're
          trying to accomplish. Let's start with the basics:
        </Typography>

        {/* Question prompt */}
        <Typography
          variant="h5"
          sx={{
            fontWeight: 600,
            mb: 4,
          }}
        >
          What brings you here today?
        </Typography>

        {/* Input composer */}
        <ChatComposer
          value={value}
          onChange={onChange}
          onSend={onSend}
          sending={sending}
          disabled={disabled}
          disabledBannerText="Chat disabled while agents are at work"
          placeholder="What problem are you trying to solve?"
          helperText=""
          showAttach={true}
          showMicrophone={true}
          paperSx={{
            bgcolor: "background.default",
            backgroundImage: "none",
            border: "1px solid",
            borderColor: "divider",
          }}
        />
      </Box>
    </Box>
  );
}
