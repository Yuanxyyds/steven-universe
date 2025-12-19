'use client';

import { useState } from 'react';
import ReactPlayer from 'react-player';
import clsx from 'clsx';

/**
 * Custom hook for managing video popup state
 *
 * @returns Object containing VideoPopup component and openVideo function
 *
 * @example
 * ```tsx
 * const { VideoPopup, openVideo } = useVideoPopup();
 *
 * return (
 *   <>
 *     <VideoPopup />
 *     <button onClick={() => openVideo('https://youtube.com/watch?v=...')}>
 *       Watch Video
 *     </button>
 *   </>
 * );
 * ```
 */
export const useVideoPopup = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [videoUrl, setVideoUrl] = useState('');

    const openVideo = (url: string) => {
        setVideoUrl(url);
        setIsOpen(true);
    };

    const VideoPopup = () => (
        isOpen ? (
            <div
                className={clsx(
                    "fixed inset-0 bg-black/80 flex items-center justify-center z-10000",
                    "backdrop-blur-sm"
                )}
                onClick={() => setIsOpen(false)}
            >
                <div
                    className={clsx(
                        "relative w-[90vw] h-[90vh] max-w-300 max-h-168.75",
                        "bg-black rounded-lg overflow-hidden shadow-2xl"
                    )}
                    onClick={(e) => e.stopPropagation()}
                >
                    <ReactPlayer
                        src={videoUrl}
                        playing
                        controls
                        width="100%"
                        height="100%"
                    />
                    <button
                        className={clsx(
                            "absolute top-2 right-2 w-10 h-10",
                            "bg-black/50 hover:bg-black/70 text-white",
                            "rounded-full text-2xl font-bold",
                            "flex items-center justify-center",
                            "transition-colors duration-200",
                            "cursor-pointer border-none"
                        )}
                        onClick={() => setIsOpen(false)}
                    >
                        ×
                    </button>
                </div>
            </div>
        ) : null
    );

    return { VideoPopup, openVideo };
};
