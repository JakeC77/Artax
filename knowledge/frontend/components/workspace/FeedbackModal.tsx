import React, { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  FormLabel,
  TextField,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
  Paper,
  Collapse,
} from '@mui/material'

export interface FeedbackRequest {
  id: string
  runId: string
  checkpoint: string
  message: string
  options?: string[]
  metadata: {
    subtasks?: Array<{
      id: string
      description: string
      agent_id: string
    }>
  }
}

export interface FeedbackSubmission {
  runId: string
  feedback_text: string
  action: string
  subtask_id?: string | null
  target?: any
}

interface FeedbackModalProps {
  request: FeedbackRequest
  runId: string
  onSubmit: (feedback: FeedbackSubmission) => void
  onClose: () => void
  open: boolean
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  request,
  runId,
  onSubmit,
  onClose,
  open,
}) => {
  const [action, setAction] = useState<string>('approve')
  const [feedbackText, setFeedbackText] = useState('')

  const handleSubmit = () => {
    onSubmit({
      runId: runId,
      feedback_text: feedbackText || `Action: ${action}`,
      action: action,
      subtask_id: null,
      target: action === 'modify' || action === 'add_subtask' ? { feedback: feedbackText } : undefined,
    })
    setFeedbackText('')
    setAction('approve')
    onClose()
  }

  const handleClose = () => {
    setFeedbackText('')
    setAction('approve')
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Review Workflow Plan
          </Typography>
          <Chip
            label="Feedback Requested"
            size="small"
            sx={{
              bgcolor: '#ffc107',
              color: '#000',
              fontWeight: 600,
            }}
          />
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" sx={{ mb: 2 }}>
            {request.message}
          </Typography>

          {request.metadata.subtasks && request.metadata.subtasks.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                Planned Subtasks:
              </Typography>
              <List
                sx={{
                  bgcolor: 'action.hover',
                  borderRadius: 1,
                  p: 1,
                  maxHeight: 200,
                  overflow: 'auto',
                }}
              >
                {request.metadata.subtasks.map((st) => (
                  <ListItem key={st.id} sx={{ py: 0.5, px: 1 }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            label={st.agent_id}
                            size="small"
                            sx={{
                              fontWeight: 600,
                              bgcolor: 'background.paper',
                              border: '1px solid',
                              borderColor: 'divider',
                            }}
                          />
                          <Typography variant="body2">{st.description}</Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          <FormControl component="fieldset" sx={{ mb: 3 }}>
            <FormLabel component="legend" sx={{ fontWeight: 700, mb: 1 }}>
              Select Action
            </FormLabel>
            <RadioGroup
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              <FormControlLabel
                value="approve"
                control={<Radio />}
                label="Approve & Continue"
              />
              <FormControlLabel
                value="modify"
                control={<Radio />}
                label="Modify Plan"
              />
              <FormControlLabel
                value="add_subtask"
                control={<Radio />}
                label="Add Subtask"
              />
              <FormControlLabel
                value="cancel"
                control={<Radio />}
                label="Cancel Workflow"
              />
            </RadioGroup>
          </FormControl>

          {(action === 'modify' || action === 'add_subtask') && (
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Feedback / Instructions"
              placeholder="Describe what you'd like to change..."
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              sx={{ mb: 2 }}
            />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
        <Button onClick={handleSubmit} variant="contained" color="primary">
          Submit Feedback
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// Inline feedback card component for chat
interface FeedbackCardProps {
  request: FeedbackRequest
  runId: string
  onSubmit: (feedback: FeedbackSubmission) => void
  onDismiss?: () => void
}

export const FeedbackCard: React.FC<FeedbackCardProps> = ({
  request,
  runId,
  onSubmit,
  onDismiss,
}) => {
  const [action, setAction] = useState<string>('approve')
  const [feedbackText, setFeedbackText] = useState('')
  const [expanded, setExpanded] = useState(true)

  const handleSubmit = () => {
    onSubmit({
      runId: runId,
      feedback_text: feedbackText || `Action: ${action}`,
      action: action,
      subtask_id: null,
      target: action === 'modify' || action === 'add_subtask' ? { feedback: feedbackText } : undefined,
    })
    setFeedbackText('')
    setAction('approve')
    setExpanded(false)
    onDismiss?.()
  }

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        mb: 1.5,
        borderRadius: 2,
        borderLeft: '4px solid',
        borderColor: '#ffc107',
        bgcolor: '#fff3cd',
        position: 'relative',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <Chip
          label="Feedback Requested"
          size="small"
          sx={{
            bgcolor: '#ffc107',
            color: '#000',
            fontWeight: 600,
          }}
        />
        <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary' }}>
          Review Required
        </Typography>
      </Box>

      <Collapse in={expanded}>
        <Box>
          <Typography variant="body2" sx={{ mb: 2, fontWeight: 500 }}>
            {request.message}
          </Typography>

          {request.metadata.subtasks && request.metadata.subtasks.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" sx={{ fontWeight: 700, mb: 1, display: 'block' }}>
                Planned Subtasks:
              </Typography>
              <List
                dense
                sx={{
                  bgcolor: 'background.paper',
                  borderRadius: 1,
                  p: 0.5,
                  maxHeight: 150,
                  overflow: 'auto',
                }}
              >
                {request.metadata.subtasks.map((st) => (
                  <ListItem key={st.id} sx={{ py: 0.25, px: 1 }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            label={st.agent_id}
                            size="small"
                            sx={{
                              fontWeight: 600,
                              bgcolor: 'action.hover',
                              border: '1px solid',
                              borderColor: 'divider',
                              fontSize: '0.65rem',
                              height: 20,
                            }}
                          />
                          <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                            {st.description}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          <FormControl component="fieldset" sx={{ mb: 2, width: '100%' }}>
            <FormLabel component="legend" sx={{ fontWeight: 700, mb: 1, fontSize: '0.875rem' }}>
              Select Action
            </FormLabel>
            <RadioGroup
              value={action}
              onChange={(e) => setAction(e.target.value)}
              sx={{ gap: 0.5 }}
            >
              <FormControlLabel
                value="approve"
                control={<Radio size="small" />}
                label={<Typography variant="body2">Approve & Continue</Typography>}
              />
              <FormControlLabel
                value="modify"
                control={<Radio size="small" />}
                label={<Typography variant="body2">Modify Plan</Typography>}
              />
              <FormControlLabel
                value="add_subtask"
                control={<Radio size="small" />}
                label={<Typography variant="body2">Add Subtask</Typography>}
              />
              <FormControlLabel
                value="cancel"
                control={<Radio size="small" />}
                label={<Typography variant="body2">Cancel Workflow</Typography>}
              />
            </RadioGroup>
          </FormControl>

          {(action === 'modify' || action === 'add_subtask') && (
            <TextField
              fullWidth
              multiline
              rows={3}
              size="small"
              label="Feedback / Instructions"
              placeholder="Describe what you'd like to change..."
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              sx={{ mb: 2 }}
            />
          )}

          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
            {onDismiss && (
              <Button size="small" onClick={onDismiss}>
                Dismiss
              </Button>
            )}
            <Button size="small" onClick={handleSubmit} variant="contained" color="primary">
              Submit Feedback
            </Button>
          </Box>
        </Box>
      </Collapse>
    </Paper>
  )
}

// Inline feedback received/applied card component for chat
interface FeedbackReceivedCardProps {
  type: 'feedback_received' | 'feedback_applied' | 'feedback_timeout'
  message: string
  timestamp?: number
}

export const FeedbackReceivedCard: React.FC<FeedbackReceivedCardProps> = ({
  type,
  message,
  timestamp,
}) => {
  const getCardStyles = () => {
    switch (type) {
      case 'feedback_applied':
        return {
          borderColor: '#28a745',
          bgcolor: '#d4edda',
          chipColor: '#28a745',
          chipLabel: 'Feedback Applied',
        }
      case 'feedback_timeout':
        return {
          borderColor: '#6c757d',
          bgcolor: '#e9ecef',
          chipColor: '#6c757d',
          chipLabel: 'No Feedback, Continuing',
        }
      case 'feedback_received':
      default:
        return {
          borderColor: '#17a2b8',
          bgcolor: '#d1ecf1',
          chipColor: '#17a2b8',
          chipLabel: 'Feedback Received',
        }
    }
  }

  const styles = getCardStyles()

  return (
    <Paper
      elevation={0}
      sx={{
        p: 1.5,
        mb: 1.5,
        borderRadius: 2,
        borderLeft: '4px solid',
        borderColor: styles.borderColor,
        bgcolor: styles.bgcolor,
        position: 'relative',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        <Chip
          label={styles.chipLabel}
          size="small"
          sx={{
            bgcolor: styles.chipColor,
            color: '#fff',
            fontWeight: 600,
          }}
        />
        {timestamp && (
          <Typography
            variant="caption"
            sx={{ ml: 'auto', color: 'text.secondary', fontSize: '0.7rem' }}
          >
            {new Date(timestamp).toLocaleTimeString()}
          </Typography>
        )}
      </Box>
      <Typography variant="body2" sx={{ fontSize: '0.875rem', color: 'text.primary' }}>
        {message}
      </Typography>
    </Paper>
  )
}

