import { useRef, useState, type ReactNode, type MouseEvent } from 'react';

interface SpotlightCardProps {
  children: ReactNode;
  className?: string;
  spotlightColor?: string; // RGB values like "198, 166, 100"
  spotlightSize?: number;
  spotlightOpacity?: number;
}

export default function SpotlightCard({
  children,
  className = '',
  spotlightColor = '255, 255, 255',
  spotlightSize = 400,
  spotlightOpacity = 0.15,
}: SpotlightCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className={className}
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 'inherit',
      }}
    >
      {/* Spotlight overlay */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity,
          transition: 'opacity 400ms ease',
          background: `radial-gradient(${spotlightSize}px circle at ${position.x}px ${position.y}px, rgba(${spotlightColor}, ${spotlightOpacity}), transparent 40%)`,
          zIndex: 1,
          borderRadius: 'inherit',
        }}
      />
      {children}
    </div>
  );
}
