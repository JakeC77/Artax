/**
 * useEntityFieldMetadata Hook
 *
 * Fetches available fields for an entity type from the graph schema.
 * Falls back to mock data when API is unavailable.
 * Caches results to avoid redundant API calls.
 */

import { useState, useEffect, useRef } from 'react'
import { fetchGraphNodePropertyMetadata } from '../services/graphql'
import { mockFieldMetadata } from '../components/workspace/setup/scoping/__mocks__/mockScopeState'

export interface FieldMetadata {
  name: string
  dataType: 'string' | 'number' | 'date' | 'boolean'
  description?: string
}

interface CacheEntry {
  fields: FieldMetadata[]
  timestamp: number
}

// Module-level cache shared across all hook instances
const fieldCache = new Map<string, CacheEntry>()
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

function normalizeDataType(apiType: string): FieldMetadata['dataType'] {
  const lower = apiType.toLowerCase()

  if (lower.includes('int') || lower.includes('float') || lower.includes('double') || lower.includes('number') || lower.includes('decimal')) {
    return 'number'
  }
  if (lower.includes('date') || lower.includes('time') || lower.includes('timestamp')) {
    return 'date'
  }
  if (lower.includes('bool')) {
    return 'boolean'
  }
  return 'string'
}

function getMockFields(entityType: string): FieldMetadata[] {
  const mockFields = mockFieldMetadata[entityType]
  if (mockFields) {
    return mockFields.map((f) => ({
      name: f.name,
      dataType: f.dataType,
    }))
  }
  // Return generic fields if entity type not in mock data
  return [
    { name: 'id', dataType: 'string' },
    { name: 'name', dataType: 'string' },
    { name: 'created_at', dataType: 'date' },
    { name: 'updated_at', dataType: 'date' },
    { name: 'is_active', dataType: 'boolean' },
  ]
}

export function useEntityFieldMetadata(entityType: string | null): {
  fields: FieldMetadata[]
  loading: boolean
  error: Error | null
} {
  const [fields, setFields] = useState<FieldMetadata[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!entityType) {
      setFields([])
      setLoading(false)
      setError(null)
      return
    }

    // Check cache first
    const cached = fieldCache.get(entityType)
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      setFields(cached.fields)
      setLoading(false)
      setError(null)
      return
    }

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    setLoading(true)
    setError(null)

    fetchGraphNodePropertyMetadata(entityType)
      .then((apiFields) => {
        let normalized: FieldMetadata[]

        if (apiFields && apiFields.length > 0) {
          normalized = apiFields.map((f) => ({
            name: f.name,
            dataType: normalizeDataType(f.dataType),
          }))
        } else {
          // API returned empty - use mock data
          normalized = getMockFields(entityType)
        }

        // Update cache
        fieldCache.set(entityType, {
          fields: normalized,
          timestamp: Date.now(),
        })

        setFields(normalized)
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return

        // On error, fall back to mock data
        const mockFields = getMockFields(entityType)

        // Cache the mock data too
        fieldCache.set(entityType, {
          fields: mockFields,
          timestamp: Date.now(),
        })

        setFields(mockFields)
        setError(null) // Clear error since we have fallback data
        setLoading(false)
      })

    return () => {
      abortControllerRef.current?.abort()
    }
  }, [entityType])

  return { fields, loading, error }
}
