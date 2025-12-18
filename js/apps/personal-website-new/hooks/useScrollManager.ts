import { useEffect } from 'react';

type ScrollCallback = () => void;

/**
 * Global scroll manager that maintains a single scroll event listener
 * All scroll-based hooks register their callbacks here
 */
class ScrollManager {
  private callbacks: Set<ScrollCallback> = new Set();
  private rafId: number | null = null;
  private isListening = false;

  /**
   * Register a callback to be called on scroll/resize
   */
  register(callback: ScrollCallback) {
    this.callbacks.add(callback);

    if (!this.isListening) {
      this.startListening();
    }

    // Return unregister function
    return () => {
      this.callbacks.delete(callback);

      if (this.callbacks.size === 0) {
        this.stopListening();
      }
    };
  }

  private startListening() {
    this.isListening = true;
    window.addEventListener('scroll', this.handleScroll, { passive: true });
    window.addEventListener('resize', this.handleScroll, { passive: true });
    // Initial call
    this.handleScroll();
  }

  private stopListening() {
    this.isListening = false;
    window.removeEventListener('scroll', this.handleScroll);
    window.removeEventListener('resize', this.handleScroll);

    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  private handleScroll = () => {
    // Use requestAnimationFrame to throttle updates and batch DOM reads
    if (this.rafId !== null) {
      return;
    }

    this.rafId = requestAnimationFrame(() => {
      this.rafId = null;
      this.callbacks.forEach(callback => callback());
    });
  };
}

// Global singleton instance
const scrollManager = new ScrollManager();

/**
 * Hook that registers a callback with the global scroll manager
 * Much more efficient than adding individual scroll listeners
 *
 * @param callback - Function to call on scroll/resize
 *
 * @example
 * useScrollManager(() => {
 *   console.log('Page scrolled');
 * });
 */
export function useScrollManager(callback: ScrollCallback) {
  useEffect(() => {
    return scrollManager.register(callback);
  }, [callback]);
}
