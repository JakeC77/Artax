import React, { useCallback, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'
import { Box, Typography, CircularProgress } from '@mui/material'
import PsychologyIcon from '@mui/icons-material/Psychology'
import { useStreamingReveal } from './useStreamingReveal'
import { STREAMING_CONFIG } from '../../../config/streaming'
import type { CsvAnalysisData } from './CsvAnalysisBlock'

// Attached event shown in collapsible section under messages
export type AttachedEvent = {
  eventType: string
  displayLabel: string // e.g., "Scope Updated"
  message: string
  timestamp: number
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'feedback' | 'feedback_received'
  content: string
  timestamp: number
  feedbackRequest?: any
  feedbackType?: 'feedback_received' | 'feedback_applied' | 'feedback_timeout'
  feedbackMessage?: string
  isComplete?: boolean
  dataLoadingProgress?: {
    type: 'nodes_created' | 'relationships_created'
    created: number
    total?: number
  }
  csvAnalysis?: CsvAnalysisData
  isError?: boolean
  attachedEvents?: AttachedEvent[]
}

export type ChatMessagesProps = {
  messages: ChatMessage[]
  isAgentWorking: boolean
  messagesEndRef?: React.RefObject<HTMLDivElement | null>
  onScroll?: () => void
  containerRef?: React.RefObject<HTMLDivElement | null>
}

export default function ChatMessages({
  messages,
  isAgentWorking,
  messagesEndRef,
  onScroll,
  containerRef,
}: ChatMessagesProps) {
  const handleStreamProgress = useCallback(() => {
    if (!messagesEndRef?.current || !containerRef?.current) return
    const container = containerRef.current
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight
    if (distanceFromBottom < 100) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      })
    }
  }, [messagesEndRef, containerRef])

  const { getDisplayedText, isStreaming, setCompleted, tick } = useStreamingReveal({
    onProgress: handleStreamProgress,
    revealCharsPerFrame: STREAMING_CONFIG.revealCharsPerFrame,
    settleDelayMs: STREAMING_CONFIG.settleDelayMs,
  })
  // tick is used implicitly to trigger re-renders during streaming animation
  void tick

  useEffect(() => {
    for (const m of messages) {
      if (m.role === 'assistant' && m.isComplete) {
        setCompleted(m.id)
      }
    }
  }, [messages, setCompleted])

  return (
    <Box
      ref={containerRef}
      onScroll={onScroll}
      sx={{
        flex: 1,
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
      }}
    >
      {[...messages].sort((a, b) => a.timestamp - b.timestamp).map((m) => {
        // Skip feedback messages for now (can be enhanced later)
        if (m.role === 'feedback' || m.role === 'feedback_received') {
          return null
        }

        const isAssistant = m.role === 'assistant'
        const streaming = isAssistant && isStreaming(m.id, m.content, m.timestamp)
        const displayedText = isAssistant
          ? getDisplayedText(m.id, m.content, m.timestamp)
          : m.content

        return (
          <Box key={m.id} sx={{ mb: 1 }}>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                color: m.role === 'user' ? 'text.secondary' : 'secondary.main',
              }}
            >
              {m.role === 'user' ? 'You' : 'Assistant'}
            </Typography>
            <Box
              sx={{
                '& p': { m: 0, mb: 0.5 },
                '& ul, & ol': { pl: 3, mb: 0.5 },
                '& li': { mb: 0.25 },
                '& pre': {
                  p: 1,
                  borderRadius: 1,
                  overflow: 'auto',
                  bgcolor: 'action.hover',
                  border: '1px solid',
                  borderColor: 'divider',
                  mb: 0.75,
                },
                '& code': {
                  bgcolor: 'action.hover',
                  px: 0.5,
                  py: 0.25,
                  borderRadius: 0.5,
                  border: '1px solid',
                  borderColor: 'divider',
                },
                '& h1, & h2, & h3, & h4, & h5, & h6': {
                  mt: 1,
                  mb: 0.5,
                  fontWeight: 700,
                },
                '& strong, & b': {
                  fontWeight: 700,
                  fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                },
                '& em, & i': {
                  fontStyle: 'italic',
                  fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                },
                '& a': { color: 'primary.main', textDecoration: 'underline' },
                color: 'text.primary',
                typography: 'body2',
              }}
            >
              {isAssistant && streaming ? (
                <Box component="span" sx={{ whiteSpace: 'pre-wrap' }}>
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
                          'strong',
                          'em',
                          'b',
                          'i',
                          'p',
                          'h1',
                          'h2',
                          'h3',
                          'h4',
                          'h5',
                          'h6',
                          'ul',
                          'ol',
                          'li',
                          'code',
                          'pre',
                          'a',
                        ],
                      },
                    ],
                  ]}
                >
                  {m.content}
                </ReactMarkdown>
              )}
            </Box>
          </Box>
        )
      })}

      {/* Agent Thinking Indicator - shown at bottom after messages */}
      {isAgentWorking && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            p: 1.5,
            borderRadius: 1,
            bgcolor: 'action.hover',
            border: '1px solid',
            borderColor: 'divider',
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': {
              '0%, 100%': {
                opacity: 1,
              },
              '50%': {
                opacity: 0.7,
              },
            },
          }}
        >
          <CircularProgress size={16} thickness={4} sx={{ color: 'secondary.main' }} />
          <PsychologyIcon fontSize="small" sx={{ color: 'secondary.main' }} />
          <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            Agents are thinking...
          </Typography>
        </Box>
      )}

      <div ref={messagesEndRef} />
    </Box>
  )
}

function StreamingCursor() {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-block',
        width: '0.5ch',
        height: '1em',
        bgcolor: 'secondary.main',
        ml: 0.5,
        animation: 'streaming-cursor-blink 0.8s steps(1) infinite',
        '@keyframes streaming-cursor-blink': {
          '0%, 50%': { opacity: 1 },
          '50.1%, 100%': { opacity: 0 },
        },
      }}
      aria-hidden="true"
    />
  )
}

