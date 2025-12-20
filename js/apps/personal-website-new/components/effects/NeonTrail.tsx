'use client';

import { useEffect } from 'react';

/**
 * NeonTrail Effect
 *
 * Creates a colorful neon trail following the mouse/touch movement
 * Features:
 * - Velocity-based trail generation
 * - Dynamic blur and opacity based on movement speed
 * - HSL color cycling for rainbow effect
 * - Physics-based animation with friction
 */

export default function NeonTrail() {
    useEffect(() => {
        let lastTime = performance.now();
        let lastX = 0;
        let lastY = 0;
        let maxVelocity = 0;
        let movementActive = false;
        const VELOCITY_THRESHOLD = 0.05;

        function handleMove(x: number, y: number) {
            const now = performance.now();
            const dt = now - lastTime;
            const dx = x - lastX;
            const dy = y - lastY;
            let velocity = Math.sqrt(dx * dx + dy * dy) / dt || 0;
            velocity = Math.min(velocity, 8);

            if (velocity > VELOCITY_THRESHOLD) {
                movementActive = true;
                maxVelocity = Math.max(maxVelocity, velocity);
            } else if (movementActive) {
                movementActive = false;
                maxVelocity = 0;
                return;
            }

            const direction = {
                x: dx / dt || 0,
                y: dy / dt || 0,
            };

            createTrail(x, y, velocity, maxVelocity, direction);
            lastTime = now;
            lastX = x;
            lastY = y;
        }

        const mouseMoveHandler = (e: MouseEvent) => handleMove(e.clientX, e.clientY);
        const touchMoveHandler = (e: TouchEvent) => {
            if (e.touches.length > 0) {
                const touch = e.touches[0];
                handleMove(touch.clientX, touch.clientY);
            }
        };

        document.addEventListener("mousemove", mouseMoveHandler);
        document.addEventListener("touchmove", touchMoveHandler, { passive: true });

        function createTrail(
            x: number,
            y: number,
            velocity: number,
            maxVelocity: number,
            direction: { x: number; y: number }
        ) {
            const trail = document.createElement("div");

            const hue = (performance.now() / 10) % 360;
            const color = `hsl(${hue}, 100%, 60%)`;

            const initialBlur = 3 + maxVelocity * 5;
            const maxBlur = initialBlur + maxVelocity * 2;
            const duration = 500;
            const friction = 0.2;

            let posX = x;
            let posY = y;
            let velX = direction.x * velocity * 2;
            let velY = direction.y * velocity * 2;

            trail.style.position = "fixed";
            trail.style.left = `${posX}px`;
            trail.style.top = `${posY}px`;
            trail.style.pointerEvents = "none";
            trail.style.zIndex = "9999";
            document.body.appendChild(trail);

            let start: number | null = null;

            function linearPeak(t: number): number {
                if (t <= 0.3) return (10 / 3) * t;
                if (t <= 1) return -(10 / 7) * (t - 0.3) + 1;
                return 0;
            }

            function animate(timestamp: number) {
                if (!start) start = timestamp;
                const elapsed = timestamp - start;
                const progress = elapsed / duration;
                const blur = initialBlur + (maxBlur - initialBlur) * (progress ** 2);
                const opacity = linearPeak(progress) * 0.6;

                velX *= friction;
                velY *= friction;
                posX += velX;
                posY += velY;

                trail.style.left = `${posX}px`;
                trail.style.top = `${posY}px`;
                trail.style.boxShadow = `0 0 ${blur}px ${blur / 2}px ${color}`;
                trail.style.opacity = opacity.toString();

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    trail.remove();
                }
            }

            requestAnimationFrame(animate);
        }

        // Cleanup function
        return () => {
            document.removeEventListener("mousemove", mouseMoveHandler);
            document.removeEventListener("touchmove", touchMoveHandler);
        };
    }, []);

    return null;
}
