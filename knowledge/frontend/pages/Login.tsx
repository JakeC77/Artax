import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Paper, Typography } from '@mui/material'
import Button from '../components/common/Button'
import { useAuth } from '../contexts/AuthContext'
import { msalInstance } from '../contexts/AuthContext'

export default function Login() {
  const { isAuthenticated, login, isLoading } = useAuth()
  const navigate = useNavigate()
  const [loginInProgress, setLoginInProgress] = useState(false)

  useEffect(() => {
    // If already authenticated, redirect to home
    if (isAuthenticated) {
      console.log('User is authenticated, redirecting to home')
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const handleLogin = async () => {
    if (loginInProgress) return
    
    try {
      setLoginInProgress(true)
      console.log('Starting login...')
      await login()
      console.log('Login popup completed, checking for accounts...')
      
      // Wait for MSAL to update its state - check the instance directly
      for (let i = 0; i < 15; i++) {
        await new Promise((resolve) => setTimeout(resolve, 200))
        const accounts = msalInstance.getAllAccounts()
        console.log(`Check ${i + 1}: Found ${accounts.length} account(s)`)
        if (accounts.length > 0) {
          console.log('Account found, authentication successful')
          // Force a navigation - the useEffect should handle it, but this ensures it happens
          navigate('/', { replace: true })
          break
        }
      }
      
      const finalAccounts = msalInstance.getAllAccounts()
      if (finalAccounts.length === 0) {
        console.error('No accounts found after login - authentication may have failed')
        alert('Login completed but authentication state was not updated. Please try refreshing the page.')
      }
    } catch (error: any) {
      console.error('Login error:', error)
      alert(`Login failed: ${error.message || 'Unknown error'}`)
    } finally {
      setLoginInProgress(false)
    }
  }

  if (isAuthenticated) {
    return null // Will redirect via useEffect
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <Paper sx={{ p: 4, width: 360 }} elevation={1}>
        <Typography variant="h5" sx={{ mb: 2 }}>
          Sign in
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Sign in with your Azure account to continue
        </Typography>
        <Button
          onClick={handleLogin}
          fullWidth
          size="md"
          disabled={isLoading || loginInProgress}
        >
          {isLoading || loginInProgress ? 'Signing in...' : 'Sign in with Azure'}
        </Button>
      </Paper>
    </Box>
  )
}

