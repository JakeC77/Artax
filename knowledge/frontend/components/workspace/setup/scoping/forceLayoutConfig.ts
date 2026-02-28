/**
 * Force-Directed Graph Layout Configuration
 *
 * Physics parameters for the force simulation, optimized for different graph sizes.
 * These settings control repulsion, attraction, and simulation behavior.
 */

// ============================================================================
// Types
// ============================================================================

export interface ForceLayoutParams {
  /** How strongly nodes push apart. Higher = more spread. */
  repulsion: number
  /** Extra padding between nodes beyond their size. */
  minDist: number
  /** How aggressively overlapping nodes separate. */
  collision: number
  /** How strongly connected nodes pull together. */
  spring: number
  /** Ideal distance from primary to related nodes. */
  distPrimaryRelated: number
  /** Ideal distance from primary to contextual nodes. */
  distPrimaryContextual: number
  /** Ideal distance for non-primary connections. */
  distOther: number
  /** Number of simulation iterations. More = better convergence, slower. */
  iterations: number
  /** Velocity decay per step. Higher = smoother but slower settling. */
  damping: number
  /** Pull toward center. Higher = tighter cluster. */
  gravity: number
}

export type GraphSize = 'small' | 'medium' | 'large' | 'xlarge'

// ============================================================================
// Size Thresholds
// ============================================================================

/**
 * Determine graph size category based on node count.
 */
export function getGraphSize(nodeCount: number): GraphSize {
  if (nodeCount <= 5) return 'small'
  if (nodeCount <= 10) return 'medium'
  if (nodeCount <= 15) return 'large'
  return 'xlarge'
}

// ============================================================================
// Preset Configurations
// ============================================================================

/**
 * Optimized layout parameters for small graphs (1-5 nodes).
 * Wide spread for clear label visibility.
 */
const SMALL_CONFIG: ForceLayoutParams = {
  repulsion: 80000,
  minDist: 60,
  collision: 12,
  spring: 0.04,
  distPrimaryRelated: 240,
  distPrimaryContextual: 340,
  distOther: 200,
  iterations: 300,
  damping: 0.85,
  gravity: 0.008,
}

/**
 * Optimized layout parameters for medium graphs (6-10 nodes).
 * Balanced spread with room for labels.
 */
const MEDIUM_CONFIG: ForceLayoutParams = {
  repulsion: 100000,
  minDist: 70,
  collision: 14,
  spring: 0.035,
  distPrimaryRelated: 280,
  distPrimaryContextual: 400,
  distOther: 220,
  iterations: 350,
  damping: 0.85,
  gravity: 0.006,
}

/**
 * Optimized layout parameters for large graphs (11-15 nodes).
 * More spread to avoid overlap, stronger repulsion.
 */
const LARGE_CONFIG: ForceLayoutParams = {
  repulsion: 130000,
  minDist: 80,
  collision: 16,
  spring: 0.03,
  distPrimaryRelated: 320,
  distPrimaryContextual: 460,
  distOther: 250,
  iterations: 450,
  damping: 0.82,
  gravity: 0.005,
}

/**
 * Optimized layout parameters for extra-large graphs (16+ nodes).
 * Maximum spread, strong repulsion, more iterations.
 */
const XLARGE_CONFIG: ForceLayoutParams = {
  repulsion: 160000,
  minDist: 90,
  collision: 18,
  spring: 0.025,
  distPrimaryRelated: 360,
  distPrimaryContextual: 520,
  distOther: 280,
  iterations: 550,
  damping: 0.8,
  gravity: 0.004,
}

// ============================================================================
// Config Map
// ============================================================================

export const FORCE_LAYOUT_PRESETS: Record<GraphSize, ForceLayoutParams> = {
  small: SMALL_CONFIG,
  medium: MEDIUM_CONFIG,
  large: LARGE_CONFIG,
  xlarge: XLARGE_CONFIG,
}

/**
 * Get the appropriate layout configuration for a given node count.
 */
export function getLayoutConfig(nodeCount: number): ForceLayoutParams {
  const size = getGraphSize(nodeCount)
  return FORCE_LAYOUT_PRESETS[size]
}

// ============================================================================
// Node Dimensions
// ============================================================================

export const NODE_DIMENSIONS = {
  primary: { width: 180, height: 90 },
  related: { width: 160, height: 80 },
  contextual: { width: 144, height: 70 },
} as const

// ============================================================================
// Edge Style Configuration
// ============================================================================

export interface EdgeStyle {
  color: string
  width: number
  dash: number[] | null
}

export const EDGE_STYLES: Record<string, EdgeStyle> = {
  /** Edge from primary to related entity */
  primaryToRelated: {
    color: '#C6A664', // gold
    width: 2.5,
    dash: null,
  },
  /** Edge from primary to contextual entity */
  primaryToContextual: {
    color: '#B0B0B0', // gray
    width: 1.5,
    dash: [6, 4],
  },
  /** Edge between non-primary entities */
  other: {
    color: '#D6D6D6', // light gray
    width: 1.5,
    dash: null,
  },
  /** Highlighted edge (on hover/select) */
  highlighted: {
    color: '#0F5C4C', // emerald
    width: 2.5,
    dash: null,
  },
}
