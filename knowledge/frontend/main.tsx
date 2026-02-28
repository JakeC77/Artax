import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MsalProvider } from '@azure/msal-react'
import './index.css'
import './styles/fonts.css'
import App from './App.tsx'
import { ThemeModeProvider } from './theme/ThemeModeProvider'
import { AuthProvider, msalInstance } from './contexts/AuthContext'

// Wrap initialization in try-catch to handle config errors
try {
  // Initialize MSAL before rendering
  msalInstance
    .initialize()
    .then(() => {
      const rootElement = document.getElementById('root')
      if (!rootElement) {
        throw new Error('Root element not found')
      }
      createRoot(rootElement).render(
        <StrictMode>
          <MsalProvider instance={msalInstance}>
            <AuthProvider>
              <ThemeModeProvider>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </ThemeModeProvider>
            </AuthProvider>
          </MsalProvider>
        </StrictMode>,
      )
    })
    .catch((error: unknown) => {
      console.error('MSAL initialization failed:', error)
      const rootElement = document.getElementById('root')
      if (rootElement) {
        rootElement.innerHTML = `
          <div style="padding: 20px; font-family: sans-serif; max-width: 600px; margin: 50px auto;">
            <h1 style="color: #d32f2f;">Application Error</h1>
            <p>Failed to initialize authentication. Please check the console for details.</p>
            <p style="color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 4px; margin-top: 10px;">
              ${error instanceof Error ? error.message : String(error)}
            </p>
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
              Make sure your .env.local file exists and contains all required VITE_* environment variables.
            </p>
          </div>
        `
      }
    })
} catch (error: unknown) {
  // Catch errors during module import (e.g., missing env vars)
  console.error('Failed to load application:', error)
  const rootElement = document.getElementById('root')
  if (rootElement) {
    rootElement.innerHTML = `
      <div style="padding: 20px; font-family: sans-serif; max-width: 600px; margin: 50px auto;">
        <h1 style="color: #d32f2f;">Configuration Error</h1>
        <p>Failed to load application configuration.</p>
        <p style="color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 4px; margin-top: 10px;">
          ${error instanceof Error ? error.message : String(error)}
        </p>
        <p style="margin-top: 20px; font-size: 14px; color: #666;">
          Please check your .env.local file and ensure all required environment variables are set.
          <br />Required variables: VITE_AZURE_CLIENT_ID, VITE_AZURE_AUTHORITY, VITE_AZURE_SCOPES
        </p>
      </div>
    `
  }
}
