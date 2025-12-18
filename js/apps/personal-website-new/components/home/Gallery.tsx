'use client';

import { useRef, useEffect, useState, CSSProperties, useCallback } from "react";
import { useScrollManager } from '@/hooks/useScrollManager';
import clsx from 'clsx';

const XS_BREAKPOINT = 767;

/**
 * Props for the ScrollImage component
 * A parallax image component that animates based on scroll position
 */
interface ScrollImageProps {
    /** Image source URL */
    src: string;
    /** Parallax speed multiplier (default: 1). Higher values = faster scroll effect */
    speed?: number;
    /** Additional CSS classes to apply to the wrapper */
    className?: string;
    /** Width of the image wrapper (default: "80%") */
    wrapperWidth?: string;
    /** Initial vertical offset in pixels for parallax calculation (default: 0) */
    initialOffset?: number;
    /** Z-index for stacking context (default: 0) */
    z?: number;
    /** Text to display on hover overlay (optional) */
    overlayText?: string;
    /** Callback function when overlay is clicked */
    overlayAction?: () => void;
    /** Tag text to display on the image (optional) */
    tag?: string;
    /** Top position of the tag as CSS value (default: "10%") */
    tagLocation?: string;
}

export const ScrollImage: React.FC<ScrollImageProps> = ({
    src,
    speed = 1,
    className = "",
    wrapperWidth = "80%",
    initialOffset = 0,
    z = 0,
    overlayText,
    overlayAction = () => { },
    tag,
    tagLocation = "10%"
}) => {
    const wrapperRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const [aspectRatio, setAspectRatio] = useState<number>(9 / 16);
    const [isXS, setIsXS] = useState<boolean>(false);

    // Detect if screen is xs on mount and resize
    useEffect(() => {
        const checkSize = () => setIsXS(window.innerWidth < XS_BREAKPOINT);
        checkSize();
        window.addEventListener("resize", checkSize);
        return () => window.removeEventListener("resize", checkSize);
    }, []);

    // Calculate aspect ratio only if not xs
    useEffect(() => {
        const img = imgRef.current;
        const handleLoad = () => {
            if (img?.naturalWidth && img?.naturalHeight) {
                setAspectRatio(img.naturalWidth / img.naturalHeight);
            }
        };
        if (img) {
            img.onload = handleLoad;
            if (img.complete) handleLoad();
        }
        return () => {
            if (img) img.onload = null;
        };
    }, [src]);

    // Scroll effect only if not xs
    const handleScroll = useCallback(() => {
        if (isXS) return;

        const wrapper = wrapperRef.current;
        if (!wrapper) return;

        const rect = wrapper.getBoundingClientRect();
        const windowHeight = window.innerHeight;

        const start = windowHeight;
        const end = -rect.height;
        const progress = (rect.top + initialOffset - end) / (start - end);
        const clamped = Math.min(1, Math.max(0, progress));
        const frameTranslate = initialOffset + (1 - clamped) * (start - end) * (speed - 1);
        const translateY = -frameTranslate;
        wrapper.style.transform = `translateY(${translateY}px)`;

        const fadeStart = 0.3 * windowHeight;
        let opacity = (windowHeight - rect.top) / fadeStart;
        opacity = Math.min(1, Math.max(0, opacity));
        wrapper.style.opacity = String(opacity);
    }, [isXS, initialOffset, speed]);

    useScrollManager(handleScroll);

    // Run handleScroll on mount and when dependencies change
    useEffect(() => {
        handleScroll();
    }, [handleScroll]);

    // xs mode: just show image
    if (isXS) {
        return (
            <div
                className={clsx("relative mx-auto mb-4 overflow-visible", className)}
                style={{
                    aspectRatio: String(aspectRatio),
                    width: wrapperWidth,
                    zIndex: z,
                    transform: 'none',
                } as CSSProperties}>
                <img src={src} alt="" loading="lazy" className="w-full object-cover" />
                {tag !== undefined && (
                    <div
                        className="absolute left-0 -translate-x-[30%] bg-primary text-white px-3 py-1.5 text-sm font-bold rounded-md z-[2]"
                        style={{ top: tagLocation }}
                    >
                        {tag}
                    </div>
                )}
                {overlayText !== undefined &&
                    <div
                        className="absolute bottom-0 left-0 w-full h-full text-white bg-black/60 flex items-center justify-center opacity-0 transition-opacity duration-500 ease-in-out cursor-pointer hover:opacity-100"
                        onClick={overlayAction}
                    >
                        <div>{overlayText}</div>
                    </div>
                }

            </div>
        );
    }

    // non-xs full animated version
    return (
        <div
            className={clsx("relative mx-auto mb-0 overflow-visible min-w-75", className)}
            ref={wrapperRef}
            style={{
                aspectRatio: String(aspectRatio),
                width: wrapperWidth,
                opacity: 0,
                zIndex: z,
            } as CSSProperties}
        >
            <img src={src} ref={imgRef} alt="" loading="lazy" className="w-full object-cover" />
            {tag !== undefined && (
                <div
                    className="absolute left-0 -translate-x-[30%] bg-primary text-white px-3 py-1.5 text-sm font-bold rounded-md z-[2]"
                    style={{ top: tagLocation }}
                >
                    {tag}
                </div>
            )}
            {overlayText !== undefined &&
                <div
                    className="absolute bottom-0 left-0 w-full h-full text-white bg-black/60 flex items-center justify-center opacity-0 transition-opacity duration-500 ease-in-out cursor-pointer hover:opacity-100"
                    onClick={overlayAction}
                >
                    <div>{overlayText}</div>
                </div>
            }
        </div>
    );
};

/**
 * Props for the StickyText component
 * A fixed-position text that fades in/out based on scroll position relative to target elements
 */
interface StickyTextProps {
    /** Text content to display (default: "Gallery") */
    text?: string;
    /** ID of the target element to track for visibility (default: "gallery") */
    targetId?: string;
    /** ID of the element where fade-in starts (default: "first-image") */
    fadeStartId?: string;
    /** ID of the element where fade-out ends (optional). If not provided, uses targetId bottom */
    fadeEndId?: string;
}

export const StickyText: React.FC<StickyTextProps> = ({
    text = "Gallery",
    targetId = "gallery",
    fadeStartId = "first-image",
    fadeEndId
}) => {
    const [opacity, setOpacity] = useState<number>(0);

    const handleScroll = useCallback(() => {
        const targetObject = document.getElementById(targetId);
        const fadeStart = document.getElementById(fadeStartId);
        if (!targetObject || !fadeStart) return;

        const targetRect = targetObject.getBoundingClientRect();
        const fadeStartRect = fadeStart.getBoundingClientRect();
        const fadeStartY = fadeStartRect.top;

        let galleryBottomY = 0;

        if (fadeEndId !== undefined) {
            const targetEndObject = document.getElementById(fadeStartId);
            const targetEndRect = targetEndObject?.getBoundingClientRect();
            galleryBottomY = targetEndRect?.bottom || 0;
        } else {
            galleryBottomY = targetRect.bottom;
        }

        const vh = window.innerHeight * 1.1;


        if (fadeStartY >= vh) {
            // Not reached fade start yet
            setOpacity(0);
        } else if (galleryBottomY <= 0) {
            // Gallery is completely out of view
            setOpacity(0);
        } else {
            // Between fade start and gallery bottom — interpolate
            const totalFadeDistance = 0.45 * vh + galleryBottomY - fadeStartY;
            const distanceScrolled = Math.max(0, vh - fadeStartY);
            const progress = distanceScrolled / totalFadeDistance;


            const newOpacity = Math.min(progress < 0.4 ? (1 - progress) ** 0.5 : Math.max(0, (1 - progress)) ** 1.5, 1);
            setOpacity(newOpacity);
        }
    }, [targetId, fadeStartId, fadeEndId]);

    useScrollManager(handleScroll);

    // Run handleScroll on mount and when dependencies change
    useEffect(() => {
        handleScroll();
    }, [handleScroll]);

    return (
        <h3
            className="fixed text-white top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 -z-10 text-center w-full pointer-events-none transition-opacity duration-100 ease-in-out"
            style={{ opacity }}
        >
            {text}
        </h3>
    );
};
