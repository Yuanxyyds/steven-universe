'use client';

import { useState, useEffect, useCallback } from 'react';
import { BsGithub } from "react-icons/bs";
import clsx from 'clsx';
import { useResizeManager } from '@/hooks/useResizeManager';

/**
 * Props for the FeaturedProjectCard component
 * A card component displaying project information with hover overlay
 */
interface FeaturedProjectCardProps {
    /** Project cover image URL */
    imageSrc: string;
    /** Project logo URL (optional) */
    logoSrc?: string;
    /** Project title */
    title: string;
    /** Full project description */
    description: string;
    /** Shortened description for mobile (optional, falls back to description) */
    shortDescription?: string;
    /** GitHub repository link (optional) */
    githubLink?: string;
    /** Project tags/categories */
    tags: string[];
    /** Text for detail/demo button (default: "Demo") */
    detailText?: string;
    /** Callback when detail button is clicked */
    onDetailClick?: () => void;
}

const FeaturedProjectCard: React.FC<FeaturedProjectCardProps> = ({
    imageSrc,
    logoSrc,
    title,
    description,
    shortDescription,
    githubLink,
    tags,
    detailText = "Demo",
    onDetailClick,
}) => {
    const [showOverlay, setShowOverlay] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

    const checkMobile = useCallback(() => {
        setIsMobile(window.innerWidth <= 600);
    }, []);

    useResizeManager(checkMobile);

    // Check mobile on mount
    useEffect(() => {
        checkMobile();
    }, [checkMobile]);

    return (
        <div
            className={clsx(
                "opacity-90 rounded-3xl border-[1.5px] border-gray-300 overflow-hidden",
                "text-white w-full flex flex-col cursor-default"
            )}
            onMouseEnter={() => setShowOverlay(true)}
            onMouseLeave={() => setShowOverlay(false)}
        >
            <div className="relative w-full overflow-hidden">
                <img
                    className={clsx(
                        "w-full aspect-[1.5] opacity-85 object-cover block",
                        "transition-transform duration-600 ease-in-out",
                        showOverlay && "scale-110"
                    )}
                    src={imageSrc}
                    alt={title}
                />

                {showOverlay && (
                    <div className="absolute inset-0 bg-black/70 flex flex-col items-start justify-center text-left p-5">
                        {logoSrc && (
                            <div className="mb-1">
                                <img
                                    className="aspect-square w-[15%] object-cover"
                                    src={logoSrc}
                                    alt="Logo"
                                />
                            </div>
                        )}
                        <p className="m-0 text-[11pt] sm:text-sm md:text-md xl:text-[14.5px]">
                            {isMobile ? (shortDescription ?? description) : description}
                        </p>
                        <div className="flex gap-x-2.5 gap-y-1.5 justify-start flex-wrap mt-4">
                            {tags.map((tag, i) => (
                                <p
                                    className="bg-white text-black rounded-full px-2 py-1 sm:px-3.5 sm:py-1.5 text-[11pt] sm:text-sm md:text-md xl:text-[14.5px] m-0"
                                    key={i}
                                >
                                    {tag}
                                </p>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div className="px-5 py-4 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <h4 className="m-0 font-bold text-base sm:text-lg md:text-xl">{title}</h4>
                    {githubLink && (
                        <a
                            href={githubLink}
                            className="text-white mb-0.5 hover:text-gray-300 text-base"
                            onClick={(e) => e.stopPropagation()}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <BsGithub />
                        </a>
                    )}
                </div>

                {onDetailClick && (
                    <div
                        className="text-yellow-400 font-semibold text-base cursor-pointer hover:underline"
                        onClick={(e) => {
                            e.stopPropagation();
                            onDetailClick();
                        }}
                    >
                        {detailText}
                    </div>
                )}
            </div>
        </div>
    );
}

export default FeaturedProjectCard;
