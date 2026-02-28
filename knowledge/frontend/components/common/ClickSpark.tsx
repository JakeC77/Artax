import { useState, type ReactNode, type MouseEvent } from 'react';
import { Box, keyframes } from '@mui/material';

interface Spark {
  id: number;
  x: number;
  y: number;
  angle: number;
}

interface ClickSparkProps {
  children: ReactNode;
  sparkColor?: string;
  sparkCount?: number;
  sparkSize?: number;
  sparkDuration?: number;
  className?: string;
}

// Spark animation - shoots outward and fades
const sparkAnimation = keyframes`
  0% {
    transform: translate(0, 0) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(var(--tx), var(--ty)) scale(0);
    opacity: 0;
  }
`;

export default function ClickSpark({
  children,
  sparkColor = '#C6A664',
  sparkCount = 8,
  sparkSize = 6,
  sparkDuration = 400,
  className = '',
}: ClickSparkProps) {
  const [sparks, setSparks] = useState<Spark[]>([]);

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Generate sparks in a circular pattern
    const newSparks: Spark[] = [];
    for (let i = 0; i < sparkCount; i++) {
      const angle = (360 / sparkCount) * i + Math.random() * 30 - 15;
      newSparks.push({
        id: Date.now() + i,
        x,
        y,
        angle,
      });
    }

    setSparks(prev => [...prev, ...newSparks]);

    // Clean up sparks after animation
    setTimeout(() => {
      setSparks(prev => prev.filter(s => !newSparks.find(ns => ns.id === s.id)));
    }, sparkDuration + 50);
  };

  return (
    <Box
      onClick={handleClick}
      className={className}
      sx={{
        position: 'relative',
        display: 'inline-block',
        cursor: 'pointer',
      }}
    >
      {children}

      {/* Spark elements */}
      {sparks.map(spark => {
        const distance = 30 + Math.random() * 20;
        const tx = Math.cos((spark.angle * Math.PI) / 180) * distance;
        const ty = Math.sin((spark.angle * Math.PI) / 180) * distance;

        return (
          <Box
            key={spark.id}
            sx={{
              position: 'absolute',
              left: spark.x,
              top: spark.y,
              width: sparkSize,
              height: sparkSize,
              borderRadius: '50%',
              bgcolor: sparkColor,
              pointerEvents: 'none',
              '--tx': `${tx}px`,
              '--ty': `${ty}px`,
              animation: `${sparkAnimation} ${sparkDuration}ms ease-out forwards`,
              boxShadow: `0 0 ${sparkSize}px ${sparkColor}`,
            } as any}
          />
        );
      })}
    </Box>
  );
}
