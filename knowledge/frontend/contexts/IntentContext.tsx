/* eslint-disable react-refresh/only-export-components */
// Disabling react-refresh rule: Context files commonly export both provider components and hooks
import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
  type RefObject,
} from 'react'
import type { Editor } from '@tiptap/react'
import type { IntentPackage } from '../services/graphql'
import {
  editorToIntentPackage,
  diffPackages,
  type IntentField,
  type TiptapDocNode,
} from '../utils/intentEditorUtils'

// Re-export IntentField for consumers
export type { IntentField }

// Field names for tracking user edits (matches backend expectations)
export type UserEditableField =
  | 'title'
  | 'summary'
  | 'mission.objective'
  | 'mission.why'
  | 'mission.success_looks_like'

export interface IntentContextValue {
  // Current package (source of truth for AI metadata)
  intentPackage: IntentPackage | null
  setIntentPackage: (pkg: IntentPackage | null) => void

  // Editor reference for extracting current content
  editorRef: RefObject<Editor | null> | null
  setEditorRef: (ref: RefObject<Editor | null>) => void

  // Get current state (editor content merged with metadata)
  getCurrentIntentPackage: () => IntentPackage | null

  // Recently updated fields (for UI badges)
  recentlyUpdatedFields: IntentField[]
  setRecentlyUpdatedFields: (fields: IntentField[]) => void
  clearRecentlyUpdatedFields: () => void

  // Track when AI updates the package
  handleIntentUpdated: (newPackage: IntentPackage, updateSummary?: string) => void

  // Track user-edited fields (for sending with chat messages)
  userEditedFields: Set<UserEditableField>
  trackUserEdit: (field: UserEditableField) => void
  clearUserEditedFields: () => void
  getUserEditedFieldsArray: () => UserEditableField[]
}

const IntentContext = createContext<IntentContextValue | null>(null)

export interface IntentProviderProps {
  children: ReactNode
  initialPackage?: IntentPackage | null
  onIntentChange?: (pkg: IntentPackage) => void
}

export function IntentProvider({
  children,
  initialPackage = null,
  onIntentChange,
}: IntentProviderProps) {
  const [intentPackage, setIntentPackageState] = useState<IntentPackage | null>(initialPackage)
  const [editorRefState, setEditorRefState] = useState<RefObject<Editor | null> | null>(null)
  const [recentlyUpdatedFields, setRecentlyUpdatedFieldsState] = useState<IntentField[]>([])
  const clearTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Track which fields the user has edited since last AI update
  const userEditedFieldsRef = useRef<Set<UserEditableField>>(new Set())

  const setIntentPackage = useCallback((pkg: IntentPackage | null) => {
    setIntentPackageState(pkg)
    if (pkg && onIntentChange) {
      onIntentChange(pkg)
    }
  }, [onIntentChange])

  const setEditorRef = useCallback((ref: RefObject<Editor | null>) => {
    setEditorRefState(ref)
  }, [])

  const getCurrentIntentPackage = useCallback((): IntentPackage | null => {
    if (!intentPackage) return null
    if (!editorRefState?.current) return intentPackage

    // Merge current editor content with existing package
    const editorJSON = editorRefState.current.getJSON() as TiptapDocNode
    return editorToIntentPackage(editorJSON, intentPackage)
  }, [intentPackage, editorRefState])

  const setRecentlyUpdatedFields = useCallback((fields: IntentField[]) => {
    setRecentlyUpdatedFieldsState(fields)
  }, [])

  const clearRecentlyUpdatedFields = useCallback(() => {
    setRecentlyUpdatedFieldsState([])
  }, [])

  const handleIntentUpdated = useCallback((
    newPackage: IntentPackage,
    updateSummary?: string
  ) => {
    // Calculate changed fields for UI indicators
    if (intentPackage) {
      const changedFields = diffPackages(intentPackage, newPackage)
      setRecentlyUpdatedFieldsState(changedFields)

      // Clear indicators after 3 seconds
      if (clearTimeoutRef.current) {
        clearTimeout(clearTimeoutRef.current)
      }
      clearTimeoutRef.current = setTimeout(() => {
        setRecentlyUpdatedFieldsState([])
      }, 3000)
    }

    // Clear user-edited fields when AI updates (reset tracking)
    userEditedFieldsRef.current = new Set()

    // Update the package
    setIntentPackage(newPackage)

    // Log update summary for debugging
    if (updateSummary) {
      console.log('[IntentContext] Intent updated:', updateSummary)
    }
  }, [intentPackage, setIntentPackage])

  // Track a user edit to a specific field
  const trackUserEdit = useCallback((field: UserEditableField) => {
    userEditedFieldsRef.current.add(field)
  }, [])

  // Clear all tracked user edits
  const clearUserEditedFields = useCallback(() => {
    userEditedFieldsRef.current = new Set()
  }, [])

  // Get array of user-edited fields (for sending with messages)
  const getUserEditedFieldsArray = useCallback((): UserEditableField[] => {
    return Array.from(userEditedFieldsRef.current)
  }, [])

  return (
    <IntentContext.Provider
      value={{
        intentPackage,
        setIntentPackage,
        editorRef: editorRefState,
        setEditorRef,
        getCurrentIntentPackage,
        recentlyUpdatedFields,
        setRecentlyUpdatedFields,
        clearRecentlyUpdatedFields,
        handleIntentUpdated,
        userEditedFields: userEditedFieldsRef.current,
        trackUserEdit,
        clearUserEditedFields,
        getUserEditedFieldsArray,
      }}
    >
      {children}
    </IntentContext.Provider>
  )
}

export function useIntentContext(): IntentContextValue {
  const context = useContext(IntentContext)
  if (!context) {
    throw new Error('useIntentContext must be used within an IntentProvider')
  }
  return context
}

// Optional hook that doesn't throw if context is missing (for components that may be outside provider)
export function useIntentContextOptional(): IntentContextValue | null {
  return useContext(IntentContext)
}
