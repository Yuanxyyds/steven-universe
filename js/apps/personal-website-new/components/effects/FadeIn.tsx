'use client';

import { ReactNode, useRef, useState, useCallback } from 'react';
import { useScrollManager } from '@/hooks/useScrollManager';

interface FadeInProps {
  children: ReactNode;
  className?: string;
}

/**
 * FadeIn component that wraps content with scroll-based fade effect
 * Exact replica of old website's continuous opacity behavior
 * Opacity is calculated based on element's position in viewport
 *
 * @example
 * <FadeIn>
 *   <h2>WHO AM I</h2>
 * </FadeIn>
 */
export default function FadeIn({ children, className = '' }: FadeInProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [opacity, setOpacity] = useState(0);

  const updateOpacity = useCallback(() => {
    const element = ref.current;
    if (!element) return;

    const position = element.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    const elementTopToViewBottom = windowHeight - position.top;
    const ViewTopToElementBottom = position.bottom;

    let newOpacity = 0;
    const transitionDistance = windowHeight / 4;

    if (elementTopToViewBottom >= 0 && ViewTopToElementBottom >= 0) {
      if (elementTopToViewBottom <= transitionDistance) {
        newOpacity = Math.pow(elementTopToViewBottom / transitionDistance, 2);
      } else if (ViewTopToElementBottom <= transitionDistance) {
        newOpacity = Math.pow(ViewTopToElementBottom / transitionDistance, 2);
      } else {
        newOpacity = 1;
      }
    }

    setOpacity(newOpacity);
  }, []);

  // Use shared scroll manager for better performance
  useScrollManager(updateOpacity);

  return (
    <div
      ref={ref}
      style={{ opacity }}
      className={className}
    >
      {children}
    </div>
  );
}
