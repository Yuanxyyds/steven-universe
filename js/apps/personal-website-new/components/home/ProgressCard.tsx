'use client';

import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';

const designTasks: string[] = ["User Research", "UI Design", "UI Rendering"];
const devTasks: string[] = ["Frontend", "Backend/ML", "Testing"];

export default function ProgressCard() {
    const [progress, setProgress] = useState<number>(0);
    const [completedTasks, setCompletedTasks] = useState<string[]>([]);
    const [hasStarted, setHasStarted] = useState<boolean>(false);
    const cardRef = useRef<HTMLDivElement>(null);

    // Observer to detect when card is visible
    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting && !hasStarted) {
                    setHasStarted(true);
                    observer.disconnect();
                }
            },
            { threshold: 0.4 }
        );

        if (cardRef.current) {
            observer.observe(cardRef.current);
        }

        return () => observer.disconnect();
    }, [hasStarted]);

    // Animation logic once visible
    useEffect(() => {
        if (!hasStarted) return;

        const allTasks: string[] = ["", ...designTasks, ...devTasks];
        const totalTasks = allTasks.length;
        const totalDuration = (totalTasks - 1) * 600;
        const updateInterval = 50;
        const progressStep = 100 / (totalDuration / updateInterval);

        let pct = 0;
        const interval = setInterval(() => {
            pct += progressStep;
            if (pct >= 100) {
                setProgress(100);
                clearInterval(interval);
            } else {
                setProgress(pct);
            }
        }, updateInterval);

        allTasks.forEach((task, index) => {
            setTimeout(() => {
                setCompletedTasks(prev => [...prev, task]);
            }, index * 600);
        });

        return () => clearInterval(interval);
    }, [hasStarted]);

    const isCompleted = (task: string): boolean => completedTasks.includes(task);

    const handleRestart = () => {
        setCompletedTasks([]);
        setProgress(0);
        setHasStarted(false);
    };

    return (
        <div
            ref={cardRef}
            onClick={handleRestart}
            className={clsx(
                "m-0 p-6.25 w-[90%] max-sm:w-full rounded-[20px]",
                "border-4 border-[#380b4a] cursor-pointer",
                "text-[#cfe9ff] bg-[#0a0a23]",
                "transition-all duration-300 ease-in-out hover:scale-105"
            )}
        >
            <div className="flex justify-between items-center font-medium mb-5">
                <h4>
                    &lt;&nbsp;&gt; {progress === 100
                        ? 'Project Completed!'
                        : 'Coding in Progress...'}
                </h4>
                <span><h4>{progress.toFixed(0)}%</h4></span>
            </div>

            <div className="h-3 bg-[#333] rounded-md overflow-hidden my-1.5 mb-6">
                <div
                    className={clsx(
                        "h-full w-0 transition-[width] duration-20 ease-in-out",
                        "bg-[linear-gradient(90deg,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc)]",
                        "bg-size-[300%_100%] bg-repeat",
                        "animate-[neonColorFlow_4s_linear_infinite]",
                        "shadow-[0_0_5px_#fff,0_0_10px_#ff00cc,0_0_20px_#00ccff,0_0_30px_#8000ff,0_0_40px_#b300ff]"
                    )}
                    style={{ width: `${progress}%` }}
                />
            </div>

            <div className="flex gap-5 flex-wrap">
                <div className={clsx(
                    "flex-1 p-0.5 rounded-xl",
                    "bg-[linear-gradient(90deg,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc)]",
                    "bg-size-[400%_100%] animate-[neonColorFlow_6s_linear_infinite]"
                )}>
                    <div className="h-full relative bg-slate-900 rounded-xl p-3.75 overflow-hidden z-10">
                        <p className="mb-1.5 text-[13pt]">✎ Design</p>
                        {designTasks.map((task) => (
                            <p
                                key={task}
                                className={clsx(
                                    "mb-1 text-[12pt] transition-opacity duration-400",
                                    isCompleted(task) ? "text-[#d2e7facd] font-bold" : "text-gray-500"
                                )}
                            >
                                {isCompleted(task) ? '✓ ' : '☐ '}{task}
                            </p>
                        ))}
                    </div>
                </div>
                <div className={clsx(
                    "flex-1 p-0.5 rounded-xl",
                    "bg-[linear-gradient(90deg,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc)]",
                    "bg-size-[400%_100%] animate-[neonColorFlow_6s_linear_infinite]"
                )}>
                    <div className="h-full relative bg-slate-900 rounded-xl p-[15px] overflow-hidden z-10">
                        <p className="mb-1.5 text-[13pt]">&lt;&nbsp;&gt; Develop</p>
                        {devTasks.map((task) => (
                            <p
                                key={task}
                                className={clsx(
                                    "mb-1 text-[12pt] transition-opacity duration-400",
                                    isCompleted(task) ? "text-[#d2e7facd] font-bold" : "text-gray-500"
                                )}
                            >
                                {isCompleted(task) ? '✓ ' : '☐ '}{task}
                            </p>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
