import { useEffect } from 'react';

type ResizeCallback = () => void;

/**
 * Singleton manager for window resize events
 * Optimizes performance by using a single resize listener for all components
 */
class ResizeManager {
    private callbacks: Set<ResizeCallback> = new Set();
    private rafId: number | null = null;
    private isListening = false;

    /**
     * Register a callback to be called on window resize
     * @param callback Function to call on resize
     * @returns Cleanup function to unregister the callback
     */
    register(callback: ResizeCallback): () => void {
        this.callbacks.add(callback);

        if (!this.isListening) {
            this.startListening();
        }

        return () => {
            this.callbacks.delete(callback);
            if (this.callbacks.size === 0) {
                this.stopListening();
            }
        };
    }

    private startListening(): void {
        window.addEventListener('resize', this.handleResize, { passive: true });
        this.isListening = true;
    }

    private stopListening(): void {
        window.removeEventListener('resize', this.handleResize);
        this.isListening = false;
        if (this.rafId !== null) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    private handleResize = (): void => {
        // Throttle using requestAnimationFrame
        if (this.rafId !== null) return;

        this.rafId = requestAnimationFrame(() => {
            this.rafId = null;
            this.callbacks.forEach(callback => callback());
        });
    };
}

// Singleton instance
const resizeManager = new ResizeManager();

/**
 * Hook to register a callback for window resize events
 * Uses a centralized manager to optimize performance
 *
 * @param callback Function to call on window resize
 *
 * @example
 * ```tsx
 * const [width, setWidth] = useState(window.innerWidth);
 *
 * useResizeManager(() => {
 *   setWidth(window.innerWidth);
 * });
 * ```
 */
export function useResizeManager(callback: ResizeCallback): void {
    useEffect(() => {
        const unregister = resizeManager.register(callback);
        return unregister;
    }, [callback]);
}
