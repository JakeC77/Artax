import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  CircularProgress,
  Link,
  Paper,
  Typography,
} from '@mui/material'
import { getApiBase, getTenantId } from '../services/graphql'
import { msalInstance } from '../contexts/AuthContext'
import { loginRequest } from '../config/msalConfig'

interface FilePreviewProps {
  attachmentId: string
  fileType: string | null
  title: string | null
}

export default function FilePreview({ attachmentId, fileType, title }: FilePreviewProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [textContent, setTextContent] = useState<string | null>(null)

  useEffect(() => {
    if (!attachmentId) {
      setBlobUrl(null)
      setTextContent(null)
      return
    }

    let active = true
    async function loadFile() {
      setLoading(true)
      setError(null)
      try {
        const apiBase = getApiBase().replace(/\/$/, '')
        const tenantId = getTenantId() || ''
        const url = `${apiBase}/scratchpad/attachments/${attachmentId}/download` + (tenantId ? `?tid=${encodeURIComponent(tenantId)}` : '')
        
        // Get access token using MSAL (same pattern as openFileInNewWindow)
        let accessToken: string | null = null
        try {
          const accounts = msalInstance.getAllAccounts()
          if (accounts.length > 0) {
            const response = await msalInstance.acquireTokenSilent({
              ...loginRequest,
              account: accounts[0],
            })
            accessToken = response.accessToken
          }
        } catch (error) {
          console.warn('Failed to get access token:', error)
        }
        
        const headers: Record<string, string> = {
          ...(tenantId ? { 'X-Tenant-Id': tenantId } : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        }

        const response = await fetch(url, {
          method: 'GET',
          headers,
          mode: 'cors',
        })

        if (!response.ok) {
          throw new Error(`Failed to load file: ${response.status} ${response.statusText}`)
        }

        const blob = await response.blob()
        
        if (!active) {
          URL.revokeObjectURL(URL.createObjectURL(blob))
          return
        }

        // Handle text-based files
        const normalizedFileType = fileType?.toLowerCase() || ''
        const textTypes = ['text/plain', 'text/markdown', 'text/html', 'application/json', 'text/csv']
        const isTextFile = textTypes.some(type => normalizedFileType.includes(type)) || 
                          normalizedFileType.includes('text') ||
                          normalizedFileType.includes('json') ||
                          normalizedFileType.includes('csv') ||
                          normalizedFileType.includes('markdown') ||
                          normalizedFileType.includes('md')

        if (isTextFile) {
          const text = await blob.text()
          setTextContent(text)
          setBlobUrl(null)
        } else {
          // For binary files (PDF, images, etc.), create blob URL
          const url = URL.createObjectURL(blob)
          setBlobUrl(url)
          setTextContent(null)
        }
      } catch (e: any) {
        if (!active) return
        setError(e?.message || 'Failed to load file')
      } finally {
        if (active) setLoading(false)
      }
    }

    loadFile()

    return () => {
      active = false
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl)
      }
    }
  }, [attachmentId, fileType])

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl)
      }
    }
  }, [blobUrl])

  if (!attachmentId) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 3,
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 2,
        }}
      >
        <Typography color="text.secondary">
          Select a document to preview
        </Typography>
      </Paper>
    )
  }

  if (loading) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 3,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading preview...
        </Typography>
      </Paper>
    )
  }

  if (error) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 3,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 2,
        }}
      >
        <Alert severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Paper>
    )
  }

  const normalizedFileType = fileType?.toLowerCase() || ''
  const isImage = normalizedFileType.startsWith('image/') || 
                  ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].some(ext => normalizedFileType.includes(ext))
  const isPdf = normalizedFileType.includes('pdf') || normalizedFileType.includes('application/pdf')

  return (
    <Paper
      variant="outlined"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.default',
        }}
      >
        <Typography variant="subtitle1" fontWeight={600}>
          {title || 'Document Preview'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {fileType || 'Unknown file type'}
        </Typography>
      </Box>

      {/* Content */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 2,
        }}
      >
        {textContent !== null ? (
          // Text content
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 2,
              bgcolor: 'background.default',
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'divider',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              overflow: 'auto',
            }}
          >
            {textContent}
          </Box>
        ) : blobUrl && isImage ? (
          // Image preview
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              maxHeight: '100%',
            }}
          >
            <Box
              component="img"
              src={blobUrl}
              alt={title || 'Preview'}
              sx={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
              }}
            />
          </Box>
        ) : blobUrl && isPdf ? (
          // PDF preview
          <Box
            component="iframe"
            src={blobUrl}
            sx={{
              width: '100%',
              height: '100%',
              minHeight: 600,
              border: 'none',
            }}
            title={title || 'PDF Preview'}
          />
        ) : blobUrl ? (
          // Other file types - show download link
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 2,
            }}
          >
            <Typography color="text.secondary">
              Preview not available for this file type
            </Typography>
            <Link
              href={blobUrl}
              download
              sx={{
                textDecoration: 'none',
              }}
            >
              Download File
            </Link>
          </Box>
        ) : (
          <Typography color="text.secondary">
            Unable to load preview
          </Typography>
        )}
      </Box>
    </Paper>
  )
}
