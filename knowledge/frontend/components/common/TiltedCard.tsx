import { useRef, useState, useEffect, type ReactNode, type MouseEvent } from 'react';

interface TiltedCardProps {
  children: ReactNode;
  className?: string;
  tiltMaxAngle?: number;
  scale?: number;
  transitionSpeed?: number;
  disabled?: boolean; // Disable tilt effect (e.g., during flip animation)
}

export default function TiltedCard({
  children,
  className = '',
  tiltMaxAngle = 10,
  scale = 1.02,
  transitionSpeed = 300,
  disabled = false,
}: TiltedCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState('perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)');

  // Reset transform when disabled
  useEffect(() => {
    if (disabled) {
      setTransform('perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)');
    }
  }, [disabled]);

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (disabled || !ref.current) return;

    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -tiltMaxAngle;
    const rotateY = ((x - centerX) / centerX) * tiltMaxAngle;

    setTransform(`perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${scale})`);
  };

  const handleMouseLeave = () => {
    setTransform('perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)');
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        transform,
        transition: `transform ${transitionSpeed}ms ease-out`,
        transformStyle: 'preserve-3d',
      }}
    >
      {children}
    </div>
  );
}
