'use client';

import { useEffect, useState } from 'react';

/**
 * Loading screen component that displays on initial page load
 *
 * Features:
 * - Full-screen white overlay with animated text
 * - Fades in from left with slide animation
 * - Fades out upward after 2.5 seconds
 * - Prevents scrolling while visible
 * - Uses React state for proper rendering
 */
export default function Loader() {
    const [isVisible, setIsVisible] = useState(true);
    const [isFadingOut, setIsFadingOut] = useState(false);

    useEffect(() => {
        // Prevent scrolling while loader is visible
        document.body.style.overflow = 'hidden';

        // Start fade out animation after 2.5 seconds
        const fadeTimer = setTimeout(() => {
            setIsFadingOut(true);
        }, 2500);

        // Remove loader completely after fade animation (1s)
        const removeTimer = setTimeout(() => {
            setIsVisible(false);
            document.body.style.overflow = 'auto';
        }, 3500); // 2500ms + 1000ms animation

        return () => {
            clearTimeout(fadeTimer);
            clearTimeout(removeTimer);
            document.body.style.overflow = 'auto';
        };
    }, []);

    if (!isVisible) return null;

    return (
        <>
            <style jsx global>{`
                @keyframes fadeInFromLeft {
                    from {
                        opacity: 0;
                        transform: translateX(-100%);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }

                @keyframes fadeOutUp {
                    0% {
                        opacity: 1;
                        transform: translateY(0%);
                    }
                    100% {
                        opacity: 0;
                        transform: translateY(-100%);
                    }
                }

                .fade-in-text {
                    animation: fadeInFromLeft 0.75s ease-out forwards;
                    opacity: 0;
                }
            `}</style>

            <div
                className="fixed top-0 left-0 w-screen h-screen bg-white flex items-center justify-center z-9999 font-sans text-black"
                style={isFadingOut ? { animation: 'fadeOutUp 1s ease-in-out forwards' } : {}}
            >
                <h1 className="text-black font-bold fade-in-text text-6xl">
                    STEV
                </h1>
                <h1 className="text-black font-bold fade-in-text delay text-6xl ml-2">
                    .LIU
                </h1>
            </div>
        </>
    );
}
