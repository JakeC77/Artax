import { Box, Typography, Paper } from '@mui/material'
import { Link } from 'react-router-dom'
import { Workspace } from '@carbon/icons-react';
import { FlowData } from '@carbon/icons-react';

export default function Home() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700 }}>
        Welcome to Geodesic
      </Typography>
      
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
        <Paper
          component={Link}
          to="/workspaces"
          elevation={0}  
          sx={{
            p: 3,
            border: '1px solid',
            borderColor: 'divider',
            textDecoration: 'none',
            display: 'block',
            transition: 'all 0.2s',
            '&:hover': {
              transform: 'translateY(-4px)',
            },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Workspace size="24" />
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              Workspaces
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Collaborate and manage your projects with AI-powered workspaces
          </Typography>
        </Paper>
        
        <Paper
          component={Link}
          to="/entities"
          elevation={0}  
          sx={{
            p: 3,
            textDecoration: 'none',
            border: '1px solid',
            borderColor: 'divider',
            display: 'block',
            transition: 'all 0.2s',
            '&:hover': {
              transform: 'translateY(-4px)',
            },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <FlowData size="24" />
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              Entities
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Explore and manage your knowledge entities
          </Typography>
        </Paper>
      </Box>
    </Box>
  )
}

