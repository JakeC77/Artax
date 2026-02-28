import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { PublicClientApplication, InteractionStatus } from '@azure/msal-browser'
import type { AccountInfo } from '@azure/msal-browser'
import { useMsal, useIsAuthenticated, useAccount } from '@azure/msal-react'
import { msalConfig, loginRequest } from '../config/msalConfig'

// Create MSAL instance
export const msalInstance = new PublicClientApplication(msalConfig)

// Auth Context Type
type AuthContextType = {
  isAuthenticated: boolean
  account: AccountInfo | null
  login: () => Promise<void>
  logout: () => Promise<void>
  getAccessToken: () => Promise<string | null>
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Auth Provider Component
export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const msalIsAuthenticated = useIsAuthenticated()
  const account = useAccount(accounts[0] || null)
  const [isLoading, setIsLoading] = useState(true)

  // Use accounts.length as a more reliable check for authentication
  // This ensures we detect authentication even if useIsAuthenticated() is delayed
  const isAuthenticated = accounts.length > 0 || msalIsAuthenticated

  useEffect(() => {
    // Check if we're still initializing
    if (inProgress === InteractionStatus.None) {
      setIsLoading(false)
    }
  }, [inProgress])

  const login = async () => {
    try {
      const response = await instance.loginPopup(loginRequest)
      console.log('Login successful, account:', response.account?.username)
      // Force a check for accounts after login
      const updatedAccounts = instance.getAllAccounts()
      console.log('Accounts after login:', updatedAccounts.length)
      if (updatedAccounts.length === 0) {
        console.warn('No accounts found after login - this may indicate an issue')
      }
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  const logout = async () => {
    try {
      await instance.logoutPopup({
        account: account || undefined,
      })
    } catch (error) {
      console.error('Logout failed:', error)
      throw error
    }
  }

  const getAccessToken = async (): Promise<string | null> => {
    if (!account) {
      return null
    }

    try {
      // Try to get token silently first
      const response = await instance.acquireTokenSilent({
        ...loginRequest,
        account: account,
      })
      return response.accessToken
    } catch (error: any) {
      // If silent token acquisition fails, try popup
      if (error.errorCode === 'interaction_required' || error.errorCode === 'consent_required') {
        try {
          const response = await instance.acquireTokenPopup({
            ...loginRequest,
            account: account,
          })
          return response.accessToken
        } catch (popupError) {
          console.error('Token acquisition failed:', popupError)
          return null
        }
      }
      console.error('Silent token acquisition failed:', error)
      return null
    }
  }

  const value: AuthContextType = {
    isAuthenticated,
    account,
    login,
    logout,
    getAccessToken,
    isLoading,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Custom hook to use auth context
export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

