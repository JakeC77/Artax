import { useEffect, useState } from 'react'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { CloseOutline } from '@carbon/icons-react'
import IconButton from '@mui/material/IconButton'
import {
  createWorkspace,
  listCompanies,
  fetchOntologies,
  getTenantId,
  setTenantId,
  fetchTenants,
  type Company,
  type Ontology,
} from '../services/graphql'
import Button from './common/Button'

export type CreateWorkspaceModalProps = {
  open: boolean
  onClose: () => void
  onCreated: (workspaceId: string) => void
}

export default function CreateWorkspaceModal({ open, onClose, onCreated }: CreateWorkspaceModalProps) {
  const theme = useTheme()
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [ontologies, setOntologies] = useState<Ontology[]>([])
  const [name, setName] = useState('New Workspace')
  const [companyId, setCompanyId] = useState<string>('')
  const [ontologyId, setOntologyId] = useState<string>('')

  useEffect(() => {
    if (!open) return
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [companiesData, ontologiesData] = await Promise.all([listCompanies(), fetchOntologies()])
        if (!active) return
        setCompanies(companiesData)
        setOntologies(ontologiesData)
      } catch (e: unknown) {
        if (!active) return
        setError(e instanceof Error ? e.message : 'Failed to load companies and ontologies')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [open])

  const handleSubmit = async () => {
    try {
      setSubmitting(true)
      setError(null)

      // Ensure tenant is set for createWorkspace (backend requires X-Tenant-Id or valid tenant context)
      let tenantId = getTenantId()
      if (companyId) {
        const company = companies.find((c) => c.companyId === companyId)
        if (company?.tenantId) {
          tenantId = company.tenantId
          setTenantId(tenantId)
        }
      }
      if (!tenantId) {
        const tenants = await fetchTenants()
        if (tenants.length > 0) {
          tenantId = tenants[0].tenantId
          setTenantId(tenantId)
        }
      }
      if (!tenantId) {
        setError('Unable to determine tenant. Please select a company or ensure tenant is configured.')
        return
      }

      const id = await createWorkspace({
        name: name.trim() || 'New Workspace',
        companyId: companyId || null,
        ontologyId: ontologyId || null,
      })
      onCreated(id)
      onClose()
      setName('New Workspace')
      setCompanyId('')
      setOntologyId('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create workspace')
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!submitting) {
      onClose()
      setError(null)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          boxShadow: `0 8px 24px ${alpha(theme.palette.common.black, 0.15)}`,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Create Workspace
        </Typography>
        <IconButton onClick={handleClose} aria-label="Close" size="small" disabled={submitting}>
          <CloseOutline size={24} />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={22} />
          </Box>
        ) : (
          <>
            <TextField
              label="Name"
              size="small"
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="New Workspace"
              autoFocus
            />
            <FormControl size="small" fullWidth>
              <InputLabel id="create-workspace-company-label">Company (optional)</InputLabel>
              <Select
                labelId="create-workspace-company-label"
                value={companyId}
                label="Company (optional)"
                onChange={(e) => setCompanyId(e.target.value)}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {companies.map((c) => (
                  <MenuItem key={c.companyId} value={c.companyId}>
                    {c.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" fullWidth>
              <InputLabel id="create-workspace-ontology-label">Ontology (optional)</InputLabel>
              <Select
                labelId="create-workspace-ontology-label"
                value={ontologyId}
                label="Ontology (optional)"
                onChange={(e) => setOntologyId(e.target.value)}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {ontologies.map((o) => (
                  <MenuItem key={o.ontologyId} value={o.ontologyId}>
                    {o.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {error && (
              <Typography color="error" variant="body2">
                {error}
              </Typography>
            )}
          </>
        )}
      </DialogContent>
      {!loading && (
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button size="sm" variant="outline" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={submitting}>
            Create
          </Button>
        </DialogActions>
      )}
    </Dialog>
  )
}
