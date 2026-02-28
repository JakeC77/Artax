import { type ReactNode } from 'react';
import { keyframes } from '@mui/material/styles';
import { Box } from '@mui/material';

// Shine animation - sweeps from left to right
const shine = keyframes`
  0% {
    background-position: -200% center;
  }
  100% {
    background-position: 200% center;
  }
`;

interface ShinyTextProps {
  children: ReactNode;
  color?: string; // Base text color
  shineColor?: string; // Color of the shine effect
  duration?: number; // Animation duration in seconds
  className?: string;
}

export default function ShinyText({
  children,
  color = '#C6A664', // Gold by default
  shineColor = 'rgba(255, 255, 255, 0.8)',
  duration = 3,
  className = '',
}: ShinyTextProps) {
  return (
    <Box
      component="span"
      className={className}
      sx={{
        display: 'inline-block',
        background: `linear-gradient(
          90deg,
          ${color} 0%,
          ${color} 40%,
          ${shineColor} 50%,
          ${color} 60%,
          ${color} 100%
        )`,
        backgroundSize: '200% 100%',
        backgroundClip: 'text',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        animation: `${shine} ${duration}s linear infinite`,
      }}
    >
      {children}
    </Box>
  );
}
