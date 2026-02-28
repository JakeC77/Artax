import { useCallback, useEffect, useRef, useState } from 'react'

type RevealEntry = {
  revealedLen: number
  lastFullLen: number
  lastUpdateTs: number
  completed: boolean
}

type StreamingRevealOptions = {
  /** Characters to reveal per animation frame. Default: 3 */
  revealCharsPerFrame?: number
  /** Ms after last content update before message is considered "settled". Default: 100 */
  settleDelayMs?: number
  /** Messages older than this (ms) show instantly. Default: 5000 */
  historicalCutoffMs?: number
  /** Callback fired on each reveal step (for auto-scroll). */
  onProgress?: () => void
}

export function useStreamingReveal(options: StreamingRevealOptions = {}) {
  const {
    revealCharsPerFrame = 3,
    settleDelayMs = 100,
    historicalCutoffMs = 5000,
    onProgress,
  } = options

  const entriesRef = useRef<Map<string, RevealEntry>>(new Map())
  const rafRef = useRef<number | null>(null)
  const [tick, setTick] = useState(0)

  // Store options in refs to avoid recreating step callback
  const optionsRef = useRef({ revealCharsPerFrame, settleDelayMs, onProgress })
  optionsRef.current = { revealCharsPerFrame, settleDelayMs, onProgress }

  // Animation step - reveal characters and trigger re-render
  // Using a ref-based pattern to avoid stale closure issues with RAF
  const stepRef = useRef<(() => void) | undefined>(undefined)
  stepRef.current = () => {
    const { revealCharsPerFrame: chars, settleDelayMs: settle, onProgress: progress } = optionsRef.current
    const now = Date.now()
    let hasMoreWork = false

    entriesRef.current.forEach((entry) => {
      // Reveal more characters if needed (even if marked complete, finish the animation)
      if (entry.revealedLen < entry.lastFullLen) {
        entry.revealedLen = Math.min(
          entry.revealedLen + chars,
          entry.lastFullLen
        )
        hasMoreWork = true
      } else if (!entry.completed && now - entry.lastUpdateTs < settle) {
        // Keep animating during settle period (cursor stays visible)
        // But only if not marked complete (more content might come)
        hasMoreWork = true
      }
    })

    // Always re-render when we have work
    if (hasMoreWork) {
      setTick((t) => t + 1)
      progress?.()
      rafRef.current = requestAnimationFrame(() => stepRef.current?.())
    } else {
      rafRef.current = null
    }
  }

  // Stable step function that delegates to ref
  const step = useCallback(() => {
    stepRef.current?.()
  }, [])

  // Start RAF loop if not running
  const startRaf = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(step)
    }
  }, [step])

  // Get or create entry for a message
  const ensureEntry = useCallback(
    (messageId: string, fullText: string, messageTimestamp?: number): RevealEntry => {
      const now = Date.now()
      const entries = entriesRef.current
      let entry = entries.get(messageId)

      if (!entry) {
        // New message - check if historical
        const isHistorical =
          typeof messageTimestamp === 'number' &&
          now - messageTimestamp > historicalCutoffMs

        entry = {
          revealedLen: isHistorical ? fullText.length : 0,
          lastFullLen: fullText.length,
          lastUpdateTs: isHistorical ? 0 : now,
          completed: isHistorical,
        }
        entries.set(messageId, entry)

        // Start animation if needed
        if (!isHistorical && entry.revealedLen < entry.lastFullLen) {
          startRaf()
        }
        return entry
      }

      // Existing entry - check for new content
      if (fullText.length > entry.lastFullLen) {
        entry.lastFullLen = fullText.length
        entry.lastUpdateTs = now
      }

      // Always try to start RAF if there's unrevealed content
      // startRaf() is a no-op if already running, so this is safe
      // Note: We start even if completed=true because we want to animate to the end
      if (entry.revealedLen < entry.lastFullLen) {
        startRaf()
      }

      return entry
    },
    [historicalCutoffMs, startRaf]
  )

  // Get the revealed portion of text
  const getDisplayedText = useCallback(
    (messageId: string, fullText: string, messageTimestamp?: number): string => {
      const entry = ensureEntry(messageId, fullText, messageTimestamp)
      if (entry.completed) {
        return fullText
      }
      return fullText.slice(0, entry.revealedLen)
    },
    [ensureEntry]
  )

  // Check if message is still streaming (for cursor display)
  const isStreaming = useCallback(
    (messageId: string, fullText: string, messageTimestamp?: number): boolean => {
      const entry = ensureEntry(messageId, fullText, messageTimestamp)
      if (entry.completed) {
        return false
      }
      const now = Date.now()
      // Streaming if: still revealing OR within settle window after last update
      return entry.revealedLen < entry.lastFullLen ||
             (entry.lastUpdateTs > 0 && now - entry.lastUpdateTs < settleDelayMs)
    },
    [ensureEntry, settleDelayMs]
  )

  // Mark message as complete (no more content coming, but let animation finish)
  const setCompleted = useCallback((messageId: string) => {
    const entry = entriesRef.current.get(messageId)
    if (entry && !entry.completed) {
      // Mark that no more content is coming, but DON'T skip to the end
      // The RAF loop will continue animating until revealedLen catches up
      entry.completed = true
      // Ensure animation continues if there's unrevealed content
      if (entry.revealedLen < entry.lastFullLen) {
        startRaf()
      }
    }
  }, [startRaf])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [])

  return {
    getDisplayedText,
    isStreaming,
    setCompleted,
    tick, // Expose tick so consumers can depend on it for re-renders
  }
}
