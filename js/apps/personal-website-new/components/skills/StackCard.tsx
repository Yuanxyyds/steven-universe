'use client';

import React, { useState } from "react";
import { AiFillStar, AiOutlineStar } from "react-icons/ai";
import clsx from 'clsx';

/**
 * Individual skill item with icon, name, and star rating
 */
export interface SkillItem {
    /** React icon component or JSX element */
    icon: React.ReactNode;
    /** Skill name displayed on hover */
    name: string;
    /** Skill proficiency level (0-6 stars) */
    stars: number;
}

/**
 * Props for StackCard component
 */
interface StackCardProps {
    /** Array of skills to display */
    skills: SkillItem[];
    /** Additional CSS classes */
    className?: string;
}

const TechIcon: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => {
    return (
        <div className={clsx(className)}>
            <div className={clsx(
                "flex items-center justify-center h-28",
                "border-2 border-gray-700 rounded-lg",
                "shadow-md hover:shadow-[0_0_15px_4px_rgba(129,72,144,0.6)] hover:border-primary",
                "transition-all duration-300 hover:scale-105"
            )}>
                {children}
            </div>
        </div>
    );
};

const YellowStars: React.FC<{ number: number }> = ({ number }) => {
    if (number < 0 || number > 6) {
        throw new Error('Invalid input. Number must be between 0 and 6.');
    }

    const stars = [];

    for (let i = 0; i < number; i++) {
        stars.push(<AiFillStar key={`filled-${i}`} className="text-yellow-400 pr-0.5" />);
    }

    const remainingStars = 6 - number;
    for (let i = 0; i < remainingStars; i++) {
        stars.push(<AiOutlineStar key={`empty-${i}`} className="pr-0.5" />);
    }

    return (
        <div className="flex justify-center">
            {stars}
        </div>
    );
};

/**
 * StackCard component displays a grid of skill items with hover interactions
 * Shows icon by default, displays name and star rating on hover
 */
export const StackCard: React.FC<StackCardProps> = ({ skills, className }) => {
    const [hoverIndex, setHoverIndex] = useState(-1);

    return (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 pb-12">
            {skills.map((skill, index) => (
                <TechIcon key={index} className={className}>
                    <div
                        onMouseEnter={() => setHoverIndex(index)}
                        onMouseLeave={() => setHoverIndex(-1)}
                        className="flex items-center justify-center w-full h-full"
                    >
                        {hoverIndex !== index && skill.icon}
                        {hoverIndex === index && (
                            <div className="text-center">
                                <p className="m-0 mb-2">{skill.name}</p>
                                <YellowStars number={skill.stars} />
                            </div>
                        )}
                    </div>
                </TechIcon>
            ))}
        </div>
    );
};
