import { useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  ListSubheader,
  IconButton,
} from '@mui/material'
import { useTheme } from '@mui/material/styles'
import {
  LightModeOutlined as LightModeOutlinedIcon,
  DarkModeOutlined as DarkModeOutlinedIcon,
} from '@mui/icons-material'
import logoUrl from '../assets/logo.svg'
import WorkspaceToolbar from '../components/WorkspaceToolbar'
import { useThemeMode } from '../theme/ThemeModeProvider'
import { useWorkspace } from '../contexts/WorkspaceContext'
import { Home } from '@carbon/icons-react';
import { Workspace } from '@carbon/icons-react';
import { FlowData } from '@carbon/icons-react';
import { AppConnectivity } from '@carbon/icons-react';
import { Notification } from '@carbon/icons-react';
import { Settings } from '@carbon/icons-react';
import { Document } from '@carbon/icons-react';
import { Book } from '@carbon/icons-react';
import { Task } from '@carbon/icons-react';
import { UserMultiple } from '@carbon/icons-react';
import { SidePanelCloseFilled } from '@carbon/icons-react';
import { SidePanelOpenFilled } from '@carbon/icons-react';
const navSections = [
  {
    header: 'MAIN',
    items: [
      { label: 'Home', to: '/', icon: <Home size="24" /> },
      { label: 'Workspaces', to: '/workspaces', icon: <Workspace size="24" /> },
      { label: 'Data', to: '/entities', icon: <FlowData size="24" /> },
      { label: 'Ontology', to: '/knowledge/ontologies', icon: <AppConnectivity size="24" /> },
      { label: 'Knowledge', to: '/knowledge', icon: <Book size="24" /> },
      { label: 'Intents', to: '/intents', icon: <Task size="24" /> },
      { label: 'Agent Roles', to: '/agent-roles', icon: <UserMultiple size="24" /> },
      { label: 'Reports', to: '/reports', icon: <Document size="24" /> },
    ],
  },
  {
    header: 'SETTINGS',
    items: [
      { label: 'Notifications', to: '/notification', icon: <Notification size="24" /> },
      { label: 'Settings', to: '/settings', icon: <Settings size="24" /> },
    ],
  },
]

export default function AppLayout() {
  const location = useLocation()
  const theme = useTheme()
  const { mode, setMode } = useThemeMode()
  const { workspaceState } = useWorkspace()
  const isDark = mode === 'dark'

  const [collapsed, setCollapsed] = useState(false)

  const expandedWidth = 200
  const collapsedWidth = 72
  const drawerWidth = collapsed ? collapsedWidth : expandedWidth
  
  // Hide sidebar and toolbar during setup
  const isSetupMode = workspaceState === 'setup' || workspaceState === 'draft'

  return (
    <Box sx={{ display: 'flex' }}>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            borderRight: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
            display: 'flex',
            flexDirection: 'column',
            transition: theme.transitions.create('width', {
              duration: theme.transitions.duration.shortest,
            }),
            // Ensure sidebar is above ChatDock (which uses zIndex: 1200)
            zIndex: 1300,
          },
        }}
      >
        {/* Top logo + collapse toggle */}
        <Toolbar
          sx={{
            minHeight: 64,
            px: collapsed ? 1 : 1,
            gap: 1.5,
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
          }}
        >
          <Box
            component={Link}
            to="/"
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <Box
              component="img"
              src={logoUrl}
              alt="logo"
              sx={{ height: collapsed ? 24 : 28 }}
            />
          </Box>

          {!collapsed && (
            <IconButton
              size="small"
              onClick={() => setCollapsed((prev) => !prev)}
              color="secondary"
              sx={{
                borderRadius: 1,
                padding: 0.5,
                color: 'secondary.main',
              }}
              aria-label="Collapse sidebar"
            >
              <SidePanelCloseFilled size="20" />
            </IconButton>
          )}
        </Toolbar>
        {collapsed && (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              justifyContent: 'center',
              mb: 1,
            }}
          >
            <IconButton
              size="small"
              onClick={() => setCollapsed(false)}
              sx={{
                borderRadius: 1,
                padding: 0.5,
                color: 'secondary.main',
              }}
              aria-label="Expand sidebar"
            >
              <SidePanelOpenFilled size="20" />
            </IconButton>
          </Box>
        )}

        {/* Navigation sections */}
        <Box sx={{ flex: 1, overflowY: 'auto', pb: 2 }}>
          {navSections.map((section) => (
            <List
              key={section.header}
              disablePadding
              subheader={
                <ListSubheader
                  component="div"
                  disableSticky
                  sx={{
                    bgcolor: 'transparent',
                    color: 'text.secondary',
                    fontWeight: 600,
                    fontSize: 11,
                    textTransform: 'uppercase',
                    letterSpacing: 0.8,
                    px: collapsed ? 0 : 2,
                    pt: collapsed ? 1.5 : 2,
                    pb: collapsed ? 1 : 0.5,
                    textAlign: collapsed ? 'center' : 'left',
                  }}
                >
                  {section.header}
                </ListSubheader>
              }
            >
              {section.items.map((item) => {
                const selected =
                  item.to === '/'
                    ? location.pathname === '/'
                    : location.pathname === item.to ||
                      location.pathname.startsWith(`${item.to}/`) ||
                      (item.to === '/workspaces' && location.pathname === '/workspace') ||
                      (item.to === '/intents' && location.pathname.startsWith('/intent')) ||
                      (item.to === '/agent-roles' && location.pathname.startsWith('/agent-role')) ||
                      (item.to === '/knowledge/ontologies' && (location.pathname === '/knowledge/ontologies' || location.pathname.startsWith('/knowledge/ontology/')))

                const selectedBg = theme.palette.background.default

                return (
                  <ListItemButton
                    key={item.to}
                    component={Link}
                    to={item.to}
                    selected={selected}
                    sx={{
                      mx: collapsed ? 1 : 1.5,
                      my: 0.25,
                      borderRadius: 0.5,
                      py: 0.75,
                      px: collapsed ? 0 : 1.5,
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      transition:
                        'background-color 120ms ease-out, box-shadow 120ms ease-out',
                      '&.Mui-selected': {
                        bgcolor: selectedBg,
                        boxShadow: isDark
                          ? '0 0 0 1px rgba(255,255,255,0.08)'
                          : '0 0 0 1px rgba(0,0,0,0.04)',
                      },
                      '&.Mui-selected:hover': {
                        bgcolor: selectedBg,
                      },
                      '&:hover': {
                        bgcolor: isDark
                          ? 'rgba(255,255,255,0.04)'
                          : 'rgba(255,255,255,0.7)',
                      },
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        minWidth: collapsed ? 0 : 32,
                        mr: collapsed ? 0 : 1,
                        display: 'flex',
                        justifyContent: 'center',
                        color: selected
                          ? theme.palette.text.primary
                          : theme.palette.text.secondary,
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>

                    {!collapsed && (
                      <ListItemText
                        primary={item.label}
                        primaryTypographyProps={{
                          fontWeight: selected ? 700 : 500,
                          fontSize: 14,
                        }}
                      />
                    )}
                  </ListItemButton>
                )
              })}
            </List>
          ))}
        </Box>

        {/* Bottom light/dark selector */}
<Box
  sx={{
    borderTop: '1px solid',
    borderColor: 'divider',
    px: collapsed ? 1 : 1,
    py: 1.25,
    bgcolor: isDark ? 'background.default' : 'common.white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: collapsed ? 'center' : 'flex-start',
  }}
>
  {!collapsed ? (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      {/* Light pill (active) */}
      <Box
        onClick={() => setMode('light')}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 1,
          px: 1.75,
          py: 0.75,
          borderRadius: 0.5,
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: !isDark ? 600 : 400,
          bgcolor: !isDark ? 'background.default' : 'transparent',
          color: !isDark ? 'text.primary' : 'text.secondary',
          border: '1px solid',
          borderColor: !isDark ? 'divider' : 'transparent',
          boxShadow: !isDark ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
        }}
      >
        <LightModeOutlinedIcon sx={{ fontSize: 16 }} />
        <Box component="span">Light</Box>
      </Box>

      {/* Dark option */}
      <Box
        onClick={() => setMode('dark')}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 1,
          px: 1.75,
          py: 0.75,
          borderRadius: 0.5,
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: isDark ? 600 : 400,
          bgcolor: isDark ? 'background.paper' : 'transparent',
          color: isDark ? 'text.primary' : 'text.secondary',
          border: '1px solid',
          borderColor: isDark ? 'divider' : 'transparent',
          boxShadow: isDark ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
        }}
      >
        <DarkModeOutlinedIcon sx={{ fontSize: 16 }} />
        <Box component="span">Dark</Box>
      </Box>
    </Box>
  ) : (
    // Compact version when collapsed: single icon button that toggles the mode
    <IconButton
      size="small"
      onClick={() => setMode(isDark ? 'light' : 'dark')}
      sx={{
        borderRadius: 999,
        padding: 0.5,
      }}
      aria-label="Toggle color mode"
    >
      {isDark ? (
        <DarkModeOutlinedIcon sx={{ fontSize: 18 }} />
      ) : (
        <LightModeOutlinedIcon sx={{ fontSize: 18 }} />
      )}
    </IconButton>
  )}
</Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0 }}>
        {/* Only show the workspace toolbar on the /workspace route (singular), not /workspaces, and not in setup mode */}
        {location.pathname.startsWith('/workspace') &&
          !location.pathname.startsWith('/workspaces') && 
          !isSetupMode && <WorkspaceToolbar />}
        <Outlet />
      </Box>
    </Box>
  )
}
