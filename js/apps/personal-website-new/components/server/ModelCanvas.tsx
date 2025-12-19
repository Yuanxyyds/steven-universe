'use client';

import React, { Suspense, useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Preload, useGLTF } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { RoomModel } from "./ServerRoom";
import { useResizeManager } from "@/hooks/useResizeManager";

// Preload the GLTF model before component mounts
useGLTF.preload('/server/server.glb');

/**
 * ModelCanvas component sets up the Three.js Canvas with camera, lighting, and controls
 *
 * Features:
 * - Responsive camera settings based on screen width
 * - Orbit controls with angle/distance constraints
 * - Bloom post-processing effect (optimized)
 * - Ambient and directional lighting
 * - Performance optimizations (preloading, proper disposal, limited DPR)
 */
export default function ModelCanvas() {
    const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1920);
    const controls = useRef<any>(null);

    const checkWidth = useCallback(() => {
        setWidth(window.innerWidth);
    }, []);

    useResizeManager(checkWidth);

    // Check width on mount
    useEffect(() => {
        checkWidth();
    }, [checkWidth]);

    // Compute distances and FOV based on screen width
    const { minDistance, maxDistance, fov, zoomDistance } = useMemo(() => {
        if (width < 576) {
            // Mobile: wider FOV, more zoom range
            return { minDistance: 1, maxDistance: 6, fov: 50, zoomDistance: 2 };
        } else if (width < 992) {
            // Tablet: medium settings
            return { minDistance: 1, maxDistance: 5, fov: 40, zoomDistance: 1.5 };
        } else {
            // Desktop: tighter view
            return { minDistance: 1, maxDistance: 4, fov: 40, zoomDistance: 1 };
        }
    }, [width]);

    return (
        <Canvas
            camera={{ fov: fov, position: [2, 1, 2] }}
            dpr={[1, 2]}
            performance={{ min: 0.5 }}
            gl={{
                antialias: true,
                powerPreference: "high-performance"
            }}
        >
            {/* Lighting */}
            <ambientLight intensity={0.6} />
            <directionalLight position={[3, 3, 3]} intensity={0.8} />

            {/* 3D Scene */}
            <Suspense fallback={null}>
                <RoomModel controls={controls} zoomDistance={zoomDistance} />
            </Suspense>

            {/* Post-Processing Effects - Optimized */}
            <EffectComposer multisampling={0}>
                <Bloom
                    intensity={0.5}
                    luminanceThreshold={0}
                    luminanceSmoothing={0.9}
                    height={300}
                />
            </EffectComposer>

            {/* Camera Controls */}
            <OrbitControls
                ref={controls}
                makeDefault
                target={[0, 1, 0]}
                maxDistance={maxDistance}
                minDistance={minDistance}
                minPolarAngle={Math.PI / 4}
                maxPolarAngle={Math.PI / 2}
                minAzimuthAngle={0}
                maxAzimuthAngle={Math.PI / 2}
                enablePan={false}
                enableZoom={true}
                zoomSpeed={0.5}
                enableDamping
                dampingFactor={0.05}
            />

            {/* Preload all assets */}
            <Preload all />
        </Canvas>
    );
}
