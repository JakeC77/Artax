/**
 * useEntityPreview Hook
 *
 * Fetches and manages preview data for a scope entity.
 * Executes Cypher query from entity.query field with pagination support.
 * Falls back to mock data when API is unavailable (for development/testing).
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { fetchGraphNodesByCypher, type GraphNode } from '../services/graphql'
import type { ScopeEntity } from '../types/scopeState'
import { mockSamples } from '../components/workspace/setup/scoping/__mocks__/mockScopeState'

const DEFAULT_LIMIT = 1000
const MOCK_LIMIT = 50 // Smaller limit for mock data to test pagination
const MOCK_TOTAL = 150 // Total mock records available
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

interface CacheEntry {
  data: GraphNode[]
  timestamp: number
  hasMore: boolean
}

// Module-level cache shared across hook instances
const previewCache = new Map<string, CacheEntry>()

export interface UseEntityPreviewResult {
  data: GraphNode[]
  loading: boolean
  error: Error | null
  hasMore: boolean
  totalLoaded: number
  loadMore: () => Promise<void>
  refresh: () => Promise<void>
}

/**
 * Generates a cache key from entity type and query
 */
function getCacheKey(entity: ScopeEntity): string {
  return `${entity.entity_type}:${entity.query || ''}`
}

/**
 * Appends LIMIT and SKIP clauses to a Cypher query for pagination.
 */
function applyPagination(baseQuery: string, skip: number, limit: number): string {
  // Remove any existing LIMIT/SKIP to avoid conflicts
  let query = baseQuery
    .replace(/\s+LIMIT\s+\d+/gi, '')
    .replace(/\s+SKIP\s+\d+/gi, '')
    .trim()

  // Add SKIP if needed
  if (skip > 0) {
    query += ` SKIP ${skip}`
  }

  // Add LIMIT
  query += ` LIMIT ${limit}`

  return query
}

/**
 * Convert mock sample data to GraphNode format for testing.
 * Returns { nodes, hasMore } to properly simulate pagination.
 */
function getMockNodes(entityType: string, skip: number): { nodes: GraphNode[]; hasMore: boolean } {
  const samples = mockSamples[entityType]
  if (!samples || samples.length === 0) {
    return { nodes: [], hasMore: false }
  }

  // Generate mock data by repeating samples with unique IDs
  const expandedData: GraphNode[] = []

  for (let i = 0; i < MOCK_TOTAL; i++) {
    const sample = samples[i % samples.length]
    const properties = Object.entries(sample).map(([key, value]) => ({
      key,
      value: String(value),
    }))

    expandedData.push({
      id: `${entityType.toLowerCase()}-${i + 1}`,
      labels: [entityType],
      properties,
    })
  }

  // Apply skip and limit (use MOCK_LIMIT for testing pagination)
  const nodes = expandedData.slice(skip, skip + MOCK_LIMIT)
  const hasMore = skip + MOCK_LIMIT < MOCK_TOTAL

  return { nodes, hasMore }
}

export function useEntityPreview(entity: ScopeEntity | null): UseEntityPreviewResult {
  const [data, setData] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [hasMore, setHasMore] = useState(true)

  const abortControllerRef = useRef<AbortController | null>(null)

  // Fetch data for the entity
  const fetchData = useCallback(
    async (skipCount: number, append: boolean = false) => {
      if (!entity || !entity.query) {
        setData([])
        setLoading(false)
        setError(null)
        setHasMore(false)
        return
      }

      // Check cache for initial load
      if (skipCount === 0 && !append) {
        const cacheKey = getCacheKey(entity)
        const cached = previewCache.get(cacheKey)
        if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
          setData(cached.data)
          setHasMore(cached.hasMore)
          setLoading(false)
          setError(null)
          return
        }
      }

      // Cancel any in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      abortControllerRef.current = new AbortController()

      setLoading(true)
      if (!append) {
        setError(null)
      }

      try {
        const paginatedQuery = applyPagination(entity.query, skipCount, DEFAULT_LIMIT)
        const nodes = await fetchGraphNodesByCypher(paginatedQuery)

        // Determine if there are more records
        const moreAvailable = nodes.length === DEFAULT_LIMIT

        if (append) {
          setData((prev) => [...prev, ...nodes])
        } else {
          setData(nodes)
          // Cache initial load
          const cacheKey = getCacheKey(entity)
          previewCache.set(cacheKey, {
            data: nodes,
            timestamp: Date.now(),
            hasMore: moreAvailable,
          })
        }

        setHasMore(moreAvailable)
        setLoading(false)
      } catch (err) {
        if ((err as Error).name === 'AbortError') return

        // Fall back to mock data when API is unavailable (for development/testing)
        const { nodes: mockNodes, hasMore: mockHasMore } = getMockNodes(entity.entity_type, skipCount)

        if (mockNodes.length > 0) {
          // Use mock data as fallback
          if (append) {
            setData((prev) => [...prev, ...mockNodes])
          } else {
            setData(mockNodes)
            // Cache mock data too
            const cacheKey = getCacheKey(entity)
            previewCache.set(cacheKey, {
              data: mockNodes,
              timestamp: Date.now(),
              hasMore: mockHasMore,
            })
          }

          setHasMore(mockHasMore)
          setError(null) // Clear error since we have fallback data
          setLoading(false)
        } else {
          // No mock data available, show error
          setError(err instanceof Error ? err : new Error('Failed to fetch preview data'))
          setLoading(false)
        }
      }
    },
    [entity]
  )

  // Initial load when entity changes
  useEffect(() => {
    if (entity && entity.query) {
      fetchData(0, false)
    } else {
      setData([])
      setHasMore(false)
      setError(null)
    }

    return () => {
      abortControllerRef.current?.abort()
    }
  }, [entity?.entity_type, entity?.query, fetchData])

  // Load more records
  const loadMore = useCallback(async () => {
    if (!hasMore || loading) return
    await fetchData(data.length, true)
  }, [fetchData, data.length, hasMore, loading])

  // Force refresh (clears cache)
  const refresh = useCallback(async () => {
    if (!entity) return
    const cacheKey = getCacheKey(entity)
    previewCache.delete(cacheKey)
    setData([])
    setHasMore(true)
    await fetchData(0, false)
  }, [entity, fetchData])

  return {
    data,
    loading,
    error,
    hasMore,
    totalLoaded: data.length,
    loadMore,
    refresh,
  }
}

/**
 * Clears all cached preview data.
 * Call this when scope changes significantly.
 */
export function clearPreviewCache(): void {
  previewCache.clear()
}
