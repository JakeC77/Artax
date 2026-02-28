import { Box, Typography } from '@mui/material'
import Button from '../../common/Button'

interface SetupFooterProps {
  currentStep: number
  totalSteps: number
  onContinue: () => void
  buttonText?: string
  buttonDisabled?: boolean
}

export default function SetupFooter({
  currentStep,
  totalSteps,
  onContinue,
  buttonText = 'Continue',
  buttonDisabled = false,
}: SetupFooterProps) {
  const progressPercentage = (currentStep / totalSteps) * 100

  return (
    <Box
      sx={{
        position: 'sticky',
        bottom: 0,
        left: 0,
        right: 0,
        bgcolor: 'background.default',
        borderTop: '1px solid',
        borderColor: 'divider',
        zIndex: 10,
      }}
    >
      {/* Progress bar */}
      <Box
        sx={{
          height: 4,
          width: `${progressPercentage}%`,
          bgcolor: 'primary.main',
          transition: 'width 0.3s ease',
        }}
      />

      {/* Footer content */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 3,
          py: 2,
        }}
      >
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
            Step {currentStep} of {totalSteps}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Workspace Setup
          </Typography>
        </Box>
        <Button size="md" onClick={onContinue} disabled={buttonDisabled}>
          {buttonText}
        </Button>
      </Box>
    </Box>
  )
}

