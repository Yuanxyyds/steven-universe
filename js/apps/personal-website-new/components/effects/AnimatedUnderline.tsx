'use client';

import { ReactNode, useRef } from 'react';
import { useScrollManager } from '@/hooks/useScrollManager';

interface AnimatedUnderlineProps {
  children: ReactNode;
  className?: string;
  /** Scroll ratio when the underline starts appearing (default: 0.2) */
  startThreshold?: number;
  /** Scroll ratio when the underline is fully visible (default: 0.5) */
  endThreshold?: number;
}

/**
 * Wrapper component that adds an animated underline below its content
 * The underline width animates from 0% to 100% based on scroll position
 *
 * @example
 * <AnimatedUnderline>
 *   <h2>WHO AM I</h2>
 * </AnimatedUnderline>
 */
export default function AnimatedUnderline({
  children,
  className = '',
  startThreshold = 0.2,
  endThreshold = 0.5,
}: AnimatedUnderlineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lineRef = useRef<HTMLDivElement>(null);

  useScrollManager(() => {
    const container = containerRef.current;
    const line = lineRef.current;

    if (!container || !line) return;

    const viewportHeight = window.innerHeight;
    const rect = container.getBoundingClientRect();
    const distanceFromBottom = viewportHeight - rect.top;
    const scrollRatio = distanceFromBottom / viewportHeight;

    let widthPercent = 0;
    if (scrollRatio < startThreshold) {
      widthPercent = 0;
    } else if (scrollRatio >= endThreshold) {
      widthPercent = 100;
    } else {
      widthPercent =
        ((scrollRatio - startThreshold) / (endThreshold - startThreshold)) * 100;
    }

    widthPercent = Math.min(Math.max(widthPercent, 0), 100);
    line.style.width = `${widthPercent}%`;
  });

  return (
    <div className={className}>
      <div ref={containerRef}>
        {children}
      </div>
      <div
        ref={lineRef}
        className="h-1 bg-primary rounded-full transition-all duration-300"
        style={{ width: '0%' }}
      />
    </div>
  );
}
