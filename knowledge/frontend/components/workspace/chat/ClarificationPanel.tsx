import { useState, useCallback } from 'react'
import {
  Box,
  Typography,
  Radio,
  RadioGroup,
  FormControlLabel,
  Button,
  IconButton,
  Chip,
  TextField,
  Collapse,
} from '@mui/material'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { ChevronLeft, ChevronRight } from '@carbon/icons-react'

const OTHER_OPTION_LABEL = '__other__'

export type ClarificationOption = {
  label: string
  description: string
  recommended?: boolean
}

export type ClarificationQuestion = {
  question_id: string
  question: string
  context?: string
  options: ClarificationOption[]
  affects_entities?: string[]
  agent_id?: string
  stage?: string
}

export type ClarificationAnswer = {
  question_id: string
  question: string
  selected_option: string
  selected_description: string
}

export type ClarificationPanelProps = {
  questions: ClarificationQuestion[]
  onSubmit: (answers: ClarificationAnswer[]) => void
  onCancel?: () => void
}

export default function ClarificationPanel({
  questions,
  onSubmit,
  onCancel: _onCancel,
}: ClarificationPanelProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Map<string, ClarificationAnswer>>(new Map())
  const [otherTexts, setOtherTexts] = useState<Map<string, string>>(new Map())
  const [selectedOther, setSelectedOther] = useState<Set<string>>(new Set())

  const currentQuestion = questions[currentIndex]
  const isLastQuestion = currentIndex === questions.length - 1
  const isFirstQuestion = currentIndex === 0
  const totalQuestions = questions.length

  const currentAnswer = answers.get(currentQuestion?.question_id)
  const isOtherSelected = selectedOther.has(currentQuestion?.question_id)
  const currentOtherText = otherTexts.get(currentQuestion?.question_id) || ''

  const handleOptionChange = useCallback(
    (optionLabel: string) => {
      if (!currentQuestion) return

      // Handle "Other" option selection
      if (optionLabel === OTHER_OPTION_LABEL) {
        setSelectedOther((prev) => {
          const updated = new Set(prev)
          updated.add(currentQuestion.question_id)
          return updated
        })
        // Set answer with current other text (or empty placeholder)
        const otherText = otherTexts.get(currentQuestion.question_id) || ''
        setAnswers((prev) => {
          const updated = new Map(prev)
          updated.set(currentQuestion.question_id, {
            question_id: currentQuestion.question_id,
            question: currentQuestion.question,
            selected_option: 'Other',
            selected_description: otherText,
          })
          return updated
        })
        return
      }

      // Clear "Other" selection when choosing a predefined option
      setSelectedOther((prev) => {
        const updated = new Set(prev)
        updated.delete(currentQuestion.question_id)
        return updated
      })

      const option = currentQuestion.options.find((o) => o.label === optionLabel)
      if (!option) return

      setAnswers((prev) => {
        const updated = new Map(prev)
        updated.set(currentQuestion.question_id, {
          question_id: currentQuestion.question_id,
          question: currentQuestion.question,
          selected_option: option.label,
          selected_description: option.description,
        })
        return updated
      })
    },
    [currentQuestion, otherTexts]
  )

  const handleOtherTextChange = useCallback(
    (text: string) => {
      if (!currentQuestion) return

      setOtherTexts((prev) => {
        const updated = new Map(prev)
        updated.set(currentQuestion.question_id, text)
        return updated
      })

      // Update the answer with the new text
      setAnswers((prev) => {
        const updated = new Map(prev)
        updated.set(currentQuestion.question_id, {
          question_id: currentQuestion.question_id,
          question: currentQuestion.question,
          selected_option: 'Other',
          selected_description: text,
        })
        return updated
      })
    },
    [currentQuestion]
  )

  const handleContinue = useCallback(() => {
    if (!currentAnswer) return
    // If "Other" is selected, require text input
    if (isOtherSelected && !currentOtherText.trim()) return

    if (isLastQuestion) {
      // Submit all answers
      const allAnswers = Array.from(answers.values())
      onSubmit(allAnswers)
    } else {
      // Go to next question
      setCurrentIndex((prev) => prev + 1)
    }
  }, [currentAnswer, isLastQuestion, answers, onSubmit, isOtherSelected, currentOtherText])

  // Check if the continue button should be enabled
  const canContinue = currentAnswer && (!isOtherSelected || currentOtherText.trim())

  const handleBack = useCallback(() => {
    if (!isFirstQuestion) {
      setCurrentIndex((prev) => prev - 1)
    }
  }, [isFirstQuestion])

  if (!currentQuestion) return null

  return (
    <Box
      sx={{
        width: '100%',
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 2,
          py: 1.5,
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'action.hover',
        }}
      >
        <HelpOutlineIcon sx={{ fontSize: 20, color: 'warning.main' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 600, flex: 1 }}>
          Clarification Needed
        </Typography>
        {totalQuestions > 1 && (
          <Chip
            label={`${currentIndex + 1} of ${totalQuestions}`}
            size="small"
            sx={{
              height: 22,
              fontSize: '0.75rem',
              bgcolor: 'background.default',
            }}
          />
        )}
      </Box>

      {/* Question Content - Scrollable */}
      <Box
        sx={{
          maxHeight: { xs: '50vh', sm: '60vh' },
          overflowY: 'auto',
          px: 2,
          py: 2,
        }}
      >
        <Typography variant="body1" sx={{ fontWeight: 600, mb: 1 }}>
          {currentQuestion.question}
        </Typography>
        {currentQuestion.context && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 2, fontSize: '0.85rem' }}
          >
            {currentQuestion.context}
          </Typography>
        )}

        {/* Options */}
        <RadioGroup
          value={isOtherSelected ? OTHER_OPTION_LABEL : (currentAnswer?.selected_option || '')}
          onChange={(e) => handleOptionChange(e.target.value)}
        >
          {currentQuestion.options.map((option, idx) => (
            <Box
              key={idx}
              sx={{
                border: '1px solid',
                borderColor:
                  !isOtherSelected && currentAnswer?.selected_option === option.label
                    ? 'primary.main'
                    : 'divider',
                borderRadius: 1,
                mb: 1,
                px: 1.5,
                py: 1,
                cursor: 'pointer',
                bgcolor:
                  !isOtherSelected && currentAnswer?.selected_option === option.label
                    ? 'action.selected'
                    : 'transparent',
                transition: 'all 0.15s ease',
                '&:hover': {
                  borderColor: 'primary.light',
                  bgcolor: 'action.hover',
                },
              }}
              onClick={() => handleOptionChange(option.label)}
            >
              <FormControlLabel
                value={option.label}
                control={
                  <Radio
                    size="small"
                    sx={{
                      py: 0,
                      color:
                        !isOtherSelected && currentAnswer?.selected_option === option.label
                          ? 'primary.main'
                          : 'text.secondary',
                    }}
                  />
                }
                label={
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 600, color: 'text.primary' }}
                      >
                        {option.label}
                      </Typography>
                      {option.recommended && (
                        <Chip
                          label="Recommended"
                          size="small"
                          color="success"
                          sx={{
                            height: 18,
                            fontSize: '0.65rem',
                            fontWeight: 600,
                          }}
                        />
                      )}
                    </Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mt: 0.25 }}
                    >
                      {option.description}
                    </Typography>
                  </Box>
                }
                sx={{
                  m: 0,
                  width: '100%',
                  alignItems: 'flex-start',
                  '& .MuiFormControlLabel-label': {
                    flex: 1,
                  },
                }}
              />
            </Box>
          ))}

          {/* Other option - always shown */}
          <Box
            sx={{
              border: '1px solid',
              borderColor: isOtherSelected ? 'primary.main' : 'divider',
              borderRadius: 1,
              mb: 1,
              px: 1.5,
              py: 1,
              cursor: 'pointer',
              bgcolor: isOtherSelected ? 'action.selected' : 'transparent',
              transition: 'all 0.15s ease',
              '&:hover': {
                borderColor: 'primary.light',
                bgcolor: 'action.hover',
              },
            }}
            onClick={() => handleOptionChange(OTHER_OPTION_LABEL)}
          >
            <FormControlLabel
              value={OTHER_OPTION_LABEL}
              control={
                <Radio
                  size="small"
                  sx={{
                    py: 0,
                    color: isOtherSelected ? 'primary.main' : 'text.secondary',
                  }}
                />
              }
              label={
                <Box sx={{ width: '100%' }}>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, color: 'text.primary' }}
                  >
                    Other
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mt: 0.25 }}
                  >
                    Provide your own response
                  </Typography>
                </Box>
              }
              sx={{
                m: 0,
                width: '100%',
                alignItems: 'flex-start',
                '& .MuiFormControlLabel-label': {
                  flex: 1,
                },
              }}
            />
          </Box>

          {/* Other text input - shown when Other is selected */}
          <Collapse in={isOtherSelected}>
            <Box sx={{ pl: 4, pr: 1, pb: 1 }}>
              <TextField
                fullWidth
                multiline
                minRows={2}
                maxRows={4}
                placeholder="Enter your response..."
                value={currentOtherText}
                onChange={(e) => handleOtherTextChange(e.target.value)}
                variant="outlined"
                size="small"
                autoFocus={isOtherSelected}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    fontSize: '0.875rem',
                  },
                }}
              />
            </Box>
          </Collapse>
        </RadioGroup>

        {/* Affected entities */}
        {currentQuestion.affects_entities &&
          currentQuestion.affects_entities.length > 0 && (
            <Box sx={{ mt: 1.5, display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography variant="caption" color="text.secondary">
                Affects:
              </Typography>
              {currentQuestion.affects_entities.map((entity) => (
                <Chip
                  key={entity}
                  label={entity}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.7rem' }}
                />
              ))}
            </Box>
          )}
      </Box>

      {/* Footer with navigation */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          borderTop: '1px solid',
          borderColor: 'divider',
          bgcolor: 'action.hover',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {totalQuestions > 1 && (
            <IconButton
              size="small"
              onClick={handleBack}
              disabled={isFirstQuestion}
              sx={{ color: 'text.secondary' }}
            >
              <ChevronLeft size={20} />
            </IconButton>
          )}
          {totalQuestions > 1 && (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {questions.map((_, idx) => (
                <Box
                  key={idx}
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor:
                      idx === currentIndex
                        ? 'primary.main'
                        : answers.has(questions[idx].question_id)
                        ? 'success.main'
                        : 'divider',
                    transition: 'all 0.15s ease',
                  }}
                />
              ))}
            </Box>
          )}
          {totalQuestions > 1 && (
            <IconButton
              size="small"
              onClick={handleContinue}
              disabled={!canContinue || isLastQuestion}
              sx={{ color: 'text.secondary' }}
            >
              <ChevronRight size={20} />
            </IconButton>
          )}
        </Box>

        <Button
          variant="contained"
          size="small"
          onClick={handleContinue}
          disabled={!canContinue}
          sx={{
            textTransform: 'none',
            fontWeight: 600,
            px: 2.5,
          }}
        >
          {isLastQuestion ? 'Send' : 'Continue'}
        </Button>
      </Box>
    </Box>
  )
}
