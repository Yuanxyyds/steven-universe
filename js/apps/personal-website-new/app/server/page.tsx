'use client';

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { FiArrowUp, FiArrowDown } from "react-icons/fi";
import clsx from "clsx";
import { useResizeManager } from "@/hooks/useResizeManager";

// Dynamic import to prevent SSR issues with Three.js
const ModelCanvas = dynamic(() => import("@/components/server/ModelCanvas"), {
    ssr: false,
    loading: () => (
        <div className="w-full h-full flex items-center justify-center">
            <div className="text-white text-xl">Loading 3D Scene...</div>
        </div>
    ),
});

/**
 * Server page - Interactive 3D server room experience
 *
 * Features:
 * - Responsive hero section (vertical on mobile, horizontal on desktop)
 * - Full-screen 3D canvas with Three.js
 * - Scroll toggle button with pulse animation
 * - Video background with overlay
 */
export default function Server() {
    const [atTop, setAtTop] = useState(true);
    const [isVertical, setIsVertical] = useState(false);

    const checkLayout = useCallback(() => {
        setIsVertical(window.innerWidth < 764);
    }, []);

    useResizeManager(checkLayout);

    // Check layout on mount
    useEffect(() => {
        checkLayout();
    }, [checkLayout]);

    const handleClick = () => {
        if (atTop) {
            window.scrollTo({
                top: window.innerHeight,
                behavior: "smooth"
            });
        } else {
            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });
        }
    };

    useEffect(() => {
        const preventScroll = (e: Event) => {
            e.preventDefault();
        };

        const preventKeys = (e: KeyboardEvent) => {
            const keys = ['Space', 'PageUp', 'PageDown', 'End', 'Home', 'ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown'];
            if (keys.includes(e.code)) {
                e.preventDefault();
            }
        };

        const handleScroll = () => {
            const isNowTop = window.scrollY < window.innerHeight;
            setAtTop(isNowTop);
        };

        // Prevent scrolling initially
        window.addEventListener("keydown", preventKeys);
        window.addEventListener("wheel", preventScroll, { passive: false });
        window.addEventListener("touchmove", preventScroll, { passive: false });
        window.addEventListener("scroll", handleScroll);

        return () => {
            window.removeEventListener("scroll", handleScroll);
            window.removeEventListener("wheel", preventScroll);
            window.removeEventListener("touchmove", preventScroll);
            window.removeEventListener("keydown", preventKeys);
        };
    }, []);

    return (
        <section>
            {/* Scroll Toggle Button */}
            <button
                className={clsx(
                    "fixed bottom-10 right-10 w-16 h-16",
                    "bg-[rgba(107,76,76,0.08)] text-white/90",
                    "border border-white/20 rounded-full",
                    "flex items-center justify-center text-2xl cursor-pointer",
                    "backdrop-blur-sm transition-all duration-300",
                    "hover:bg-white/15 hover:border-white/30",
                    "animate-[pulse-scale_2s_ease-in-out_infinite]",
                    "z-9999",
                    "max-sm:bottom-5 max-sm:right-5 max-sm:w-12 max-sm:h-12",
                    "max-h-[600px]:bottom-5 max-h-[600px]:right-5 max-h-[600px]:w-12 max-h-[600px]:h-12",
                    "max-h-[500px]:bottom-4 max-h-[500px]:right-4 max-h-[500px]:w-9 max-h-[500px]:h-9"
                )}
                onClick={handleClick}
            >
                {atTop ? <FiArrowDown /> : <FiArrowUp />}
            </button>

            {/* Hero Section */}
            {isVertical ? (
                // Vertical (Mobile) Layout
                <div className="h-screen m-0 p-0 text-white">
                    <div className="pt-[20vh] px-[5vw]">
                        <h1 className={clsx(
                            "font-light mb-0 flex items-center",
                            "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:0ms]",
                            "after:content-[''] after:w-20 after:h-1 after:bg-primary after:ml-5"
                        )}>
                            ENTER MY
                        </h1>
                        <h1 className={clsx(
                            "mb-2 text-primary",
                            "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:300ms]"
                        )}>
                            3D SERVER ROOM
                        </h1>
                        <h5 className={clsx(
                            "mb-6 font-bold",
                            "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:500ms]"
                        )}>
                            Discover how I manage, automate, and deploy projects from my custom-built home server.
                        </h5>
                    </div>

                    <div className="p-0 m-0 bg-black/60 opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:700ms]">
                        <video
                            src="/server/server.mp4"
                            className="w-full"
                            autoPlay
                            muted
                            loop
                            playsInline
                        />
                    </div>

                    <div className="pt-4 px-[5vw]">
                        <h4
                            className="underline cursor-pointer opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:700ms]"
                            onClick={handleClick}
                        >
                            Let's Go
                        </h4>
                    </div>
                </div>
            ) : (
                // Horizontal (Desktop) Layout
                <div className="relative h-screen m-0 p-0 text-white bg-black/60">
                    <video
                        className="absolute top-0 left-0 w-full h-full object-fill -z-10 pointer-events-none"
                        src="/server/server.mp4"
                        autoPlay
                        muted
                        loop
                        playsInline
                    />

                    <div className="px-[8vw] pb-[15vh] h-full flex items-center">
                        <div className="w-full md:w-2/3 lg:w-7/12 xl:w-1/2">
                            <h1 className={clsx(
                                "font-light mb-0 flex items-center",
                                "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:0ms]",
                                "after:content-[''] after:w-20 after:h-1 after:bg-primary after:ml-5"
                            )}>
                                ENTER MY
                            </h1>
                            <h2 className={clsx(
                                "mb-2 text-primary font-bold",
                                "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:300ms]"
                            )}>
                                3D SERVER ROOM
                            </h2>
                            <p className={clsx(
                                "mb-0 font-bold",
                                "opacity-0 animate-[fadeIn_0.6s_ease-in-out_forwards] [animation-delay:500ms]"
                            )}>
                                Discover how I manage, automate, and deploy projects from my custom-built home server.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* 3D Canvas Section */}
            <div className="relative w-full h-screen m-0 p-0">
                <ModelCanvas />
            </div>
        </section>
    );
}
