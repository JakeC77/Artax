import React from 'react'
import styled from '@emotion/styled'
import { css } from '@emotion/react'
import { useTheme } from '@mui/material/styles'
import type { SxProps, Theme } from '@mui/material/styles'
import Box from '@mui/material/Box'

type Variant = 'primary' | 'outline' | 'secondary' | 'accent'
type Size = 'sm' | 'md' | 'lg'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  fullWidth?: boolean
  sx?: SxProps<Theme>
}

const COLORS = {
  primary: '#C6A664',
  secondary: '#0F5C4C',
  accent: '#C6A664',
  dark: '#1C1C1C',
}

const shadowStack = (color: string) =>
  `1px 1px 0 0 ${color}, 2px 2px 0 0 ${color}, 3px 3px 0 0 ${color}, 4px 4px 0 0 ${color}, 5px 5px 0 0 ${color}`

const baseStyles = css`
  font-family: inherit;
  transition: all 200ms ease-in-out;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-transform: uppercase;
  letter-spacing: 2px;
  position: relative;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
  touch-action: manipulation;
  border-radius: 0; /* square like the marketing site */
  border-width: 3px;
  border-style: solid;
`

const sizeStyles: Record<Size, ReturnType<typeof css>> = {
  sm: css`
    padding: 4px 12px;
    font-size: 0.875rem;
    line-height: 1.25rem;
  `,
  md: css`
    padding: 8px 16px;
    font-size: 0.95rem;
    line-height: 1.5rem;
  `,
  lg: css`
    padding: 12px 20px;
    font-size: 1.05rem;
    line-height: 1.75rem;
  `,
}

const variantStyles = {
  primary: css`
    background: ${COLORS.primary};
    color: ${COLORS.dark};
    border-color: ${COLORS.primary};
     box-shadow: ${shadowStack(COLORS.dark)};
    top: 0;
    left: 0;
    &:hover {
      box-shadow: none;
      top: 5px;
      left: 5px;
    }
    &:active {
      box-shadow: none;
      top: 5px;
      left: 5px;
    }
  `,
  outline: css`
    background: transparent;
    color: ${COLORS.primary};
    border-color: ${COLORS.primary};
    box-shadow: ${shadowStack(COLORS.primary)};
    top: 0;
    left: 0;
    &:hover {
      box-shadow: none;
      top: 5px;
      left: 5px;
    }
    &:active {
      box-shadow: none;
      top: 5px;
      left: 5px;
    }
  `,
  secondary: css`
    background: ${COLORS.secondary};
    color: white;
    border-color: ${COLORS.secondary};
  `,
  accent: css`
    background: ${COLORS.accent};
    color: white;
    border-color: ${COLORS.accent};
  `,
}

const disabledStyles = css`
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    box-shadow: none;
    top: 0;
    left: 0;
    &:hover {
      box-shadow: none;
      top: 0;
      left: 0;
    }
  }
`

const StyledButton = styled.button<{
  $variant: Variant
  $size: Size
  $fullWidth?: boolean
}>`
  ${baseStyles};
  ${(p) => sizeStyles[p.$size]};
  ${(p) => variantStyles[p.$variant]};
  ${(p) => (p.$fullWidth ? 'width: 100%; display: inline-flex;' : '')}
  ${disabledStyles};
`

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth,
  sx,
  ...rest
}: ButtonProps) {
  const theme = useTheme()
  
  // If we are in dark mode, change 'primary' variant to 'outline' automatically
  const finalVariant = theme.palette.mode === 'dark' && variant === 'primary' 
    ? 'outline' 
    : variant

  const button = (
    <StyledButton $variant={finalVariant} $size={size} $fullWidth={fullWidth} {...rest}>
      {children}
    </StyledButton>
  )

  if (sx != null) {
    return <Box component="span" sx={sx}>{button}</Box>
  }
  return button
}

