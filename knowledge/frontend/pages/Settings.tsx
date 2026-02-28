import { Box, Typography, Paper, CircularProgress, List, ListItem, ListItemText, Button, Switch, FormControlLabel } from '@mui/material'
import { User, Logout } from '@carbon/icons-react'
import { useAuth } from '../contexts/AuthContext'
import { useThemeMode } from '../theme/ThemeModeProvider'

export default function Settings() {
  const { account, isLoading, logout } = useAuth()
  const { mode, setMode } = useThemeMode()

  if (isLoading) {
    return (
      <Box sx={{ p: 3, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700 }}>
        User settings
      </Typography>

      <Paper
        elevation={0}
        sx={{
          p: 3,
          mb: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <User size={24} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Profile
          </Typography>
        </Box>
        <List dense disablePadding>
          {account?.name != null && (
            <ListItem disablePadding sx={{ py: 0.5 }}>
              <ListItemText primary="Name" secondary={account.name} />
            </ListItem>
          )}
          {account?.username != null && (
            <ListItem disablePadding sx={{ py: 0.5 }}>
              <ListItemText primary="Email" secondary={account.username} />
            </ListItem>
          )}
        </List>
      </Paper>

      <Paper
        elevation={0}
        sx={{
          p: 3,
          mb: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Appearance
        </Typography>
        <FormControlLabel
          control={
            <Switch
              checked={mode === 'dark'}
              onChange={(_, checked) => setMode(checked ? 'dark' : 'light')}
              color="primary"
            />
          }
          label="Dark mode"
        />
      </Paper>

      <Paper
        elevation={0}
        sx={{
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Account
        </Typography>
        <Button
          variant="outlined"
          color="primary"
          startIcon={<Logout size={20} />}
          onClick={() => logout()}
        >
          Sign out
        </Button>
      </Paper>
    </Box>
  )
}
