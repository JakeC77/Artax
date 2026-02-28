// Streaming Configuration
// Tunable parameters for the streaming text reveal animation

export const STREAMING_CONFIG = {
  // Characters revealed per animation frame (~60fps)
  // Lower = smoother typing effect, Higher = faster reveal
  // At 60fps: 3 chars/frame = ~180 chars/sec (natural typing feel)
  revealCharsPerFrame: 3,

  // Delay after last content update before hiding cursor (ms)
  // Keeps cursor visible briefly while waiting for more content
  settleDelayMs: 100,

  // Messages older than this are shown instantly without animation (ms)
  historicalCutoffMs: 5000,
} as const

export type StreamingConfig = typeof STREAMING_CONFIG
