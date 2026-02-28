import { type ReactNode } from 'react';
import { Box, keyframes } from '@mui/material';

interface StarBorderProps {
  children: ReactNode;
  color?: string;
  speed?: string; // CSS duration like "3s"
  borderRadius?: number | string;
  borderWidth?: number;
  className?: string;
}

// Star/sparkle traveling around the border
const starMove = keyframes`
  0% {
    offset-distance: 0%;
  }
  100% {
    offset-distance: 100%;
  }
`;

// Pulsing glow effect
const pulse = keyframes`
  0%, 100% {
    opacity: 0.6;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
`;

export default function StarBorder({
  children,
  color = '#C6A664',
  speed = '4s',
  borderRadius = 4,
  borderWidth = 2,
  className = '',
}: StarBorderProps) {
  // Convert borderRadius to CSS value
  const radius = typeof borderRadius === 'number' ? `${borderRadius}px` : borderRadius;

  return (
    <Box
      className={className}
      sx={{
        position: 'relative',
        borderRadius: radius,
      }}
    >
      {/* SVG border path for the star to travel along */}
      <Box
        component="svg"
        sx={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          overflow: 'visible',
        }}
      >
        <defs>
          <filter id="star-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Border rectangle */}
        <rect
          x={borderWidth / 2}
          y={borderWidth / 2}
          width={`calc(100% - ${borderWidth}px)`}
          height={`calc(100% - ${borderWidth}px)`}
          rx={radius}
          ry={radius}
          fill="none"
          stroke={color}
          strokeWidth={borderWidth}
          strokeOpacity={0.3}
        />
      </Box>

      {/* Traveling star element */}
      <Box
        sx={{
          position: 'absolute',
          width: 8,
          height: 8,
          borderRadius: '50%',
          bgcolor: color,
          boxShadow: `0 0 12px ${color}, 0 0 24px ${color}`,
          pointerEvents: 'none',
          // Use CSS offset-path for smooth path following
          offsetPath: `path("M ${borderWidth} ${Number(radius.replace('px', '')) || 4}
            Q ${borderWidth} ${borderWidth} ${Number(radius.replace('px', '')) || 4} ${borderWidth}
            L calc(100% - ${Number(radius.replace('px', '')) || 4}px) ${borderWidth}
            Q calc(100% - ${borderWidth}px) ${borderWidth} calc(100% - ${borderWidth}px) ${Number(radius.replace('px', '')) || 4}px
            L calc(100% - ${borderWidth}px) calc(100% - ${Number(radius.replace('px', '')) || 4}px)
            Q calc(100% - ${borderWidth}px) calc(100% - ${borderWidth}px) calc(100% - ${Number(radius.replace('px', '')) || 4}px) calc(100% - ${borderWidth}px)
            L ${Number(radius.replace('px', '')) || 4}px calc(100% - ${borderWidth}px)
            Q ${borderWidth}px calc(100% - ${borderWidth}px) ${borderWidth}px calc(100% - ${Number(radius.replace('px', '')) || 4}px)
            Z")`,
          animation: `${starMove} ${speed} linear infinite, ${pulse} 2s ease-in-out infinite`,
          zIndex: 2,
        }}
      />

      {/* Main content */}
      <Box sx={{ position: 'relative', zIndex: 1 }}>
        {children}
      </Box>
    </Box>
  );
}
