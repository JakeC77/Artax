import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { type Workspace, type WorkspaceStateValue, setTenantId } from '../services/graphql'

export type WorkspaceState = WorkspaceStateValue

type WorkspaceContextType = {
  currentWorkspace: Workspace | null
  setCurrentWorkspace: (ws: Workspace | null) => void
  chatOpen: boolean
  setChatOpen: (open: boolean) => void
  workspaceState: WorkspaceState
  setWorkspaceState: (state: WorkspaceState) => void
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [currentWorkspace, setCurrentWorkspaceState] = useState<Workspace | null>(() => {
    try {
      const raw = localStorage.getItem('workspace:selected')
      return raw ? (JSON.parse(raw) as Workspace) : null
    } catch {
      return null
    }
  })

  const [chatOpen, setChatOpenState] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem('workspace:chatOpen')
      // Default to true (open) if not set, or if value is 'true'
      return raw !== null ? raw === 'true' : true
    } catch {
      return true
    }
  })

  const [workspaceState, setWorkspaceStateInternal] = useState<WorkspaceState>(() => {
    try {
      const stored = localStorage.getItem('workspace:state')
      // Migrate old values to new schema
      if (stored === 'staging' || stored === 'data') return 'working'
      return (stored as WorkspaceState) || 'setup'
    } catch {
      return 'setup'
    }
  })

  const setChatOpen = (next: boolean) => {
    setChatOpenState(next)
    try {
      localStorage.setItem('workspace:chatOpen', String(next))
    } catch {}
  }

  const setWorkspaceState = (next: WorkspaceState) => {
    setWorkspaceStateInternal(next)
    try {
      localStorage.setItem('workspace:state', next)
    } catch {
      // Ignore localStorage errors (e.g., private mode, restricted iframes)
    }
  }

  const setCurrentWorkspace = (ws: Workspace | null) => {
    setCurrentWorkspaceState(ws)
    // Don't auto-open chat when workspace is null (during setup intro phase)
    if (ws) {
      setChatOpen(true)
    }
  }

  useEffect(() => {
    if (currentWorkspace) {
      try {
        localStorage.setItem('workspace:selected', JSON.stringify(currentWorkspace))
        setTenantId(currentWorkspace.tenantId || undefined)
      } catch {}
    } else {
      // During setup flow, we might have null workspace temporarily
      // Don't clear localStorage as we may want to restore after reload
      // Just ensure tenantId is not set when no workspace
    }
  }, [currentWorkspace])

  // Also need to initialize tenantId on mount
  useEffect(() => {
    if (currentWorkspace?.tenantId) {
      setTenantId(currentWorkspace.tenantId)
    }
  }, []) // Run once on mount

  const value = {
    currentWorkspace,
    setCurrentWorkspace,
    chatOpen,
    setChatOpen,
    workspaceState,
    setWorkspaceState,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider')
  }
  return context
}

