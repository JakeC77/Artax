import { useRef, useEffect, useCallback } from "react";
import { Box, Typography } from "@mui/material";
import ChatMessages from "../../chat/ChatMessages";
import ChatComposer from "../../chat/ChatComposer";
import { type ChatMessage } from "../../chat/ChatMessages";

export type InterviewViewProps = {
  messages: ChatMessage[];
  isAgentWorking: boolean;
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  disabled?: boolean;
};

export default function InterviewView({
  messages,
  isAgentWorking,
  value,
  onChange,
  onSend,
  sending,
  disabled = false,
}: InterviewViewProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef<boolean>(true);

  // Auto-scroll to bottom when messages change or agent starts/stops working
  useEffect(() => {
    if (shouldAutoScrollRef.current && messagesEndRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      });
    }
  }, [messages, isAgentWorking]);

  // Track scroll position to determine if we should auto-scroll
  const handleScroll = useCallback(() => {
    if (!messagesContainerRef.current) return;
    const container = messagesContainerRef.current;
    const { scrollTop, scrollHeight, clientHeight } = container;
    // If user is within 100px of bottom, enable auto-scroll
    shouldAutoScrollRef.current = scrollHeight - scrollTop - clientHeight < 100;
  }, []);

  // Reset auto-scroll when user sends a message
  const handleSend = useCallback(() => {
    shouldAutoScrollRef.current = true;
    onSend();
  }, [onSend]);

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        bgcolor: "background.default",
      }}
    >
      {/* Header - centered */}
      <Box
        sx={{
          py: 3,
          flexShrink: 0,
          display: "flex",
          justifyContent: "flex-start",
        }}
      >
        <Box sx={{ maxWidth: 720, width: "100%", px: 4 }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            Define your mission
          </Typography>
        </Box>
      </Box>

      {/* Messages area - centered chat */}
      <Box
        sx={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <Box
          sx={{
            maxWidth: 720,
            width: "100%",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            px: 4,
          }}
        >
          <ChatMessages
            messages={messages}
            isAgentWorking={isAgentWorking}
            messagesEndRef={messagesEndRef}
            onScroll={handleScroll}
            containerRef={messagesContainerRef}
          />
        </Box>
      </Box>

      {/* Input composer - centered */}
      <Box
        sx={{
          flexShrink: 0,
          py: 3,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <Box sx={{ maxWidth: 720, width: "100%", px: 4 }}>
          <ChatComposer
            value={value}
            onChange={onChange}
            onSend={handleSend}
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
    </Box>
  );
}
