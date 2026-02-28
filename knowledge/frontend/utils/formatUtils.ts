/**
 * Shared formatting utilities for dates and strings.
 */

/**
 * Format an ISO date string for display (e.g. "Jan 1, 2025, 3:30 PM").
 * @param isoString - ISO 8601 date string or null
 * @param fallback - Value to return when isoString is null/empty (default: '—')
 */
export function formatDateTime(isoString: string | null, fallback: string = '—'): string {
  if (!isoString) return fallback
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

/**
 * Truncate a string to a maximum length, appending "..." if truncated.
 * @param s - String or null
 * @param max - Maximum length before truncation
 * @param fallback - Value to return when s is null/empty (default: '—')
 */
export function truncate(s: string | null, max: number, fallback: string = '—'): string {
  if (!s) return fallback
  return s.length <= max ? s : s.slice(0, max) + '...'
}
