import type { Configuration, PopupRequest } from '@azure/msal-browser'

// Get configuration from environment variables with defaults
const getEnvVar = (key: string, defaultValue?: string): string => {
  // Vite exposes env variables on import.meta.env
  const value = import.meta.env[key] || defaultValue
  if (!value) {
    const error = new Error(`Missing required environment variable: ${key}`)
    console.error(error.message)
    console.error('Available env vars:', Object.keys(import.meta.env).filter(k => k.startsWith('VITE_')))
    console.error('Make sure you have a .env.local file with the required variables.')
    throw error
  }
  return value
}

// Default values for Azure Entra External IDs (CIAM) configuration
// These are used as fallbacks if environment variables are not set during build
const DEFAULT_AZURE_CLIENT_ID = '2b0deb9a-619c-45eb-88a7-a5e5ca2a0bce'
const DEFAULT_AZURE_AUTHORITY = 'https://geodesicexternal.ciamlogin.com/602b0bbc-14f5-41be-83e5-9eac403b66f1/v2.0'
const DEFAULT_AZURE_SCOPES = 'api://402454db-6c18-4a13-9415-abf75a85f973/access_as_user,openid,profile,email'

// Azure Entra External IDs (CIAM) configuration
const authority = getEnvVar('VITE_AZURE_AUTHORITY', DEFAULT_AZURE_AUTHORITY)
// Extract the base domain for knownAuthorities (e.g., "geodesicexternal.ciamlogin.com")
const authorityUrl = new URL(authority)
const knownAuthority = authorityUrl.hostname

export const msalConfig: Configuration = {
  auth: {
    clientId: getEnvVar('VITE_AZURE_CLIENT_ID', DEFAULT_AZURE_CLIENT_ID),
    authority: authority,
    redirectUri: getEnvVar('VITE_AZURE_REDIRECT_URI', window.location.origin),
    knownAuthorities: [knownAuthority], // Required for B2C/Entra External IDs
  },
  cache: {
    cacheLocation: 'sessionStorage', // This configures where your cache will be stored
    storeAuthStateInCookie: false, // Set this to "true" if you are having issues on IE11 or Edge
  },
  system: {
    loggerOptions: {
      loggerCallback: (level: number, message: string, containsPii: boolean) => {
        if (containsPii) {
          return
        }
        switch (level) {
          case 0: // LogLevel.Error
            console.error(message)
            return
          case 1: // LogLevel.Warning
            console.warn(message)
            return
          case 2: // LogLevel.Info
            console.info(message)
            return
          case 3: // LogLevel.Verbose
            console.debug(message)
            return
        }
      },
      piiLoggingEnabled: false,
      logLevel: 1, // LogLevel.Warning
    },
  },
}

// Scopes for API access
const getScopes = (): string[] => {
  const scopesEnv = getEnvVar('VITE_AZURE_SCOPES', DEFAULT_AZURE_SCOPES)
  if (!scopesEnv) {
    return ['openid', 'profile', 'email']
  }
  return scopesEnv.split(',').map((s) => s.trim()).filter(Boolean)
}

// Add your scopes here for ID token to be used at Microsoft identity platform endpoints.
export const loginRequest: PopupRequest = {
  scopes: getScopes(),
}

// Add the endpoints here for Microsoft Graph API services you'd like to use.
export const graphConfig = {
  graphMeEndpoint: 'https://graph.microsoft.com/v1.0/me',
}

