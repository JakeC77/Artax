import { useState, useEffect, useRef } from 'react';
import { Box } from '@mui/material';

interface DecryptedTextProps {
  text: string;
  speed?: number; // ms per character
  maxIterations?: number; // iterations before settling
  characters?: string; // character pool for scrambling
  animateOn?: 'view' | 'hover' | 'always' | 'trigger';
  trigger?: boolean; // external trigger for animation when animateOn='trigger'
  className?: string;
  color?: string;
  fontSize?: number | string;
  fontFamily?: string;
}

const DEFAULT_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';

export default function DecryptedText({
  text,
  speed = 30,
  maxIterations = 10,
  characters = DEFAULT_CHARS,
  animateOn = 'view',
  trigger,
  className = '',
  color = 'text.secondary',
  fontSize = 10,
  fontFamily = 'inherit',
}: DecryptedTextProps) {
  const [displayText, setDisplayText] = useState(text);
  // isAnimating is set during animation but read access is reserved for future styling
  const [, setIsAnimating] = useState(false);
  const [hasAnimated, setHasAnimated] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const iterationsRef = useRef<number[]>([]);

  // Initialize iterations tracker
  useEffect(() => {
    iterationsRef.current = new Array(text.length).fill(0);
  }, [text]);

  const animate = () => {
    if (hasAnimated && animateOn === 'view') return;

    setIsAnimating(true);
    iterationsRef.current = new Array(text.length).fill(0);

    const interval = setInterval(() => {
      setDisplayText(() => {
        let allDone = true;
        const newText = text.split('').map((char, i) => {
          // Skip spaces
          if (char === ' ') return ' ';

          // If this character has completed iterations, show the real char
          if (iterationsRef.current[i] >= maxIterations) {
            return char;
          }

          // Increment iteration
          iterationsRef.current[i]++;
          allDone = false;

          // Return random character
          return characters[Math.floor(Math.random() * characters.length)];
        }).join('');

        if (allDone) {
          clearInterval(interval);
          setIsAnimating(false);
          setHasAnimated(true);
        }

        return newText;
      });
    }, speed);

    return () => clearInterval(interval);
  };

  // Trigger animation on view
  useEffect(() => {
    if (animateOn !== 'view') return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated) {
          animate();
        }
      },
      { threshold: 0.5 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [animateOn, hasAnimated, text]);

  // Trigger animation on mount for 'always'
  useEffect(() => {
    if (animateOn === 'always') {
      animate();
    }
  }, [animateOn]);

  // Trigger animation when external trigger changes to true
  useEffect(() => {
    if (animateOn === 'trigger' && trigger) {
      setHasAnimated(false);
      animate();
    }
  }, [animateOn, trigger]);

  const handleMouseEnter = () => {
    if (animateOn === 'hover') {
      setHasAnimated(false);
      animate();
    }
  };

  return (
    <Box
      component="span"
      ref={ref}
      onMouseEnter={handleMouseEnter}
      className={className}
      sx={{
        fontFamily,
        letterSpacing: '0.02em',
        color,
        fontSize,
        display: 'inline',
      }}
    >
      {displayText}
    </Box>
  );
}
