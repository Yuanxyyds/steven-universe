'use client';

import React, { useEffect, useRef, useState, useMemo } from "react";
import { Box3, Vector3, VideoTexture, LinearFilter, TextureLoader, RGBAFormat, ClampToEdgeWrapping, Object3D } from "three";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";

/**
 * Props for the RoomModel component
 */
interface RoomModelProps {
    /** Reference to OrbitControls for camera manipulation */
    controls: React.RefObject<any>;
    /** Distance to zoom when focusing on objects */
    zoomDistance: number;
}

/**
 * RoomModel component renders the 3D server room with interactive elements
 *
 * Features:
 * - Interactive TV that plays video on click
 * - 3 monitors that switch between video and images
 * - Draggable rotating chair
 * - Dynamic neon lighting effects
 * - Camera zoom to focused objects
 */
export function RoomModel({ controls, zoomDistance }: RoomModelProps) {
    const { nodes, scene } = useGLTF('/server/server.glb') as any;
    const [dragging, setDragging] = useState(false);
    const [focusedMedia, setFocusedMedia] = useState<string | null>(null);
    const originalPosition = useRef(new Vector3());
    const originalTarget = useRef(new Vector3());
    const selectedObject = useRef<Object3D | null>(null);
    const chairRef = useRef<Object3D | undefined>(undefined);

    // Remove monitors from main scene (will render separately)
    scene.remove(nodes["Monitor1"]);
    scene.remove(nodes["Monitor2"]);
    scene.remove(nodes["Monitor3"]);

    // Monitor video texture (always playing)
    const [monitorVideo] = useState(() => {
        const video = document.createElement("video");
        video.src = "/server/monitor.mp4";
        video.crossOrigin = "anonymous";
        video.loop = true;
        video.muted = true;
        video.playsInline = true;
        video.autoplay = true;
        video.play().catch(() => {
            // Handle autoplay failure silently
        });
        return video;
    });

    const monitorVideoTexture = useMemo(() => {
        const texture = new VideoTexture(monitorVideo);
        texture.minFilter = LinearFilter;
        texture.magFilter = LinearFilter;
        texture.format = RGBAFormat;
        texture.wrapS = ClampToEdgeWrapping;
        texture.wrapT = ClampToEdgeWrapping;
        texture.flipY = false;
        return texture;
    }, [monitorVideo]);

    // TV video texture (plays on focus)
    const [TvVideo] = useState(() => {
        const v = document.createElement("video");
        v.src = "/server/tv.mp4";
        v.crossOrigin = "anonymous";
        v.loop = true;
        v.muted = true;
        v.playsInline = true;
        v.autoplay = true;
        v.play().catch(() => {
            // Handle autoplay failure silently
        });
        return v;
    });

    const TvVideoTexture = useMemo(() => {
        const tex = new VideoTexture(TvVideo);
        tex.flipY = false;
        return tex;
    }, [TvVideo]);

    // Monitor image textures (shown when focused)
    const monitorImageTextures = useMemo(() => {
        const loader = new TextureLoader();
        return [
            loader.load("/server/node1.jpg", (texture) => { texture.flipY = false }),
            loader.load("/server/hosting.jpg", (texture) => { texture.flipY = false }),
            loader.load("/server/node2.jpg", (texture) => { texture.flipY = false }),
        ];
    }, []);

    // Cleanup videos and textures on unmount
    useEffect(() => {
        return () => {
            monitorVideo.pause();
            monitorVideo.src = "";
            TvVideo.pause();
            TvVideo.src = "";
            monitorVideoTexture.dispose();
            TvVideoTexture.dispose();
            monitorImageTextures.forEach(texture => texture.dispose());
        };
    }, [monitorVideo, TvVideo, monitorVideoTexture, TvVideoTexture, monitorImageTextures]);

    // Neon Light Effect - animates HSL color on materials with "Neon" in name
    // Throttled to update every 3 frames for better performance
    const frameCount = useRef(0);
    useFrame(({ clock }) => {
        frameCount.current++;

        // Update neon lights every 3 frames instead of every frame
        if (frameCount.current % 3 !== 0) return;

        const t = clock.getElapsedTime();
        const hue = (t * 60) % 360;
        const color = `hsl(${hue}, 100%, 50%)`;

        scene.traverse((child: any) => {
            if (child.isMesh) {
                const materials = Array.isArray(child.material)
                    ? child.material
                    : [child.material];

                materials.forEach((mat: any) => {
                    if (mat.name && mat.name.includes("Neon")) {
                        mat.emissive.setStyle(color);
                        mat.emissiveIntensity = 5;
                        mat.toneMapped = false;
                    }
                });
            }
        });
    });

    // Zoom Control - handles camera zoom to focused objects
    useEffect(() => {
        const zoomToObject = (object: Object3D) => {
            if (!object) return;
            const box = new Box3().setFromObject(object);
            const center = new Vector3();
            box.getCenter(center);

            // Save original camera position and target
            originalPosition.current.copy(controls.current.object.position);
            originalTarget.current.copy(controls.current.target);

            // Compute front-facing offset along the object's local Z axis
            const frontDirection = new Vector3(0, 0, 1);
            object.localToWorld(frontDirection);
            frontDirection.sub(object.getWorldPosition(new Vector3())).normalize();

            const distance = zoomDistance;
            const newPosition = center.clone().add(frontDirection.multiplyScalar(distance));

            // Move camera
            controls.current.object.position.copy(newPosition);
            controls.current.target.copy(center);

            // Disable controls during focus
            controls.current.enabled = false;
            controls.current.update();
        };

        if (focusedMedia === null) {
            // Restore original camera position
            if (chairRef.current) {
                chairRef.current.visible = true;
            }
            if (selectedObject.current) {
                selectedObject.current = null;
                controls.current.object.position.copy(originalPosition.current);
                controls.current.target.copy(originalTarget.current);
                controls.current.enabled = true;
                controls.current.update();
            }
        } else {
            // Hide chair and zoom to selected object
            if (chairRef.current) {
                chairRef.current.visible = false;
            }
            if (selectedObject.current) {
                zoomToObject(selectedObject.current)
            }
        }
    }, [focusedMedia, controls, zoomDistance]);

    // TV Display - renders TV with optional video texture when focused
    const tvDisplay = useMemo(() => {
        if (focusedMedia !== "TV") {
            return (
                <primitive
                    object={nodes["TV"]}
                    onPointerDown={(e: any) => {
                        e.stopPropagation();
                        if (focusedMedia === null) {
                            selectedObject.current = e.object;
                            TvVideo.currentTime = 0;
                            TvVideo.play();
                            setFocusedMedia("TV");
                        }
                    }}
                    onPointerOver={() => {
                        document.body.style.cursor = "pointer";
                    }}
                    onPointerOut={() => {
                        document.body.style.cursor = "default";
                    }}
                />
            );
        }

        // Focused: clone with video texture
        const clone = nodes["TV"].clone(true);
        clone.traverse((child: any) => {
            if (child.isMesh) {
                child.material = Array.isArray(child.material)
                    ? child.material.map((m: any) => m.clone())
                    : child.material.clone();
            }
        });
        clone.traverse((child: any) => {
            if (child.isMesh) {
                const mats = Array.isArray(child.material)
                    ? child.material
                    : [child.material];
                mats.forEach((mat: any) => {
                    if (mat.name.includes("Screen")) {
                        mat.map = TvVideoTexture;
                        mat.emissiveMap = TvVideoTexture;
                        mat.needsUpdate = true;
                        if (mat.map) mat.map.needsUpdate = true;
                        if (mat.emissiveMap) mat.emissiveMap.needsUpdate = true;
                    }
                });
            }
        });

        return (
            <group
                onPointerDown={(e: any) => {
                    e.stopPropagation();
                }}
                onPointerOver={() => {
                    document.body.style.cursor = "default";
                }}
                onPointerOut={() => {
                    document.body.style.cursor = "default";
                }}>
                <primitive object={clone} />
            </group>
        );
    }, [focusedMedia, TvVideo, TvVideoTexture, nodes]);

    // Monitor Displays - renders 3 monitors with video or image textures
    const monitorDisplays = useMemo(() => {
        const monitorConfigs = [
            { name: "Monitor1" },
            { name: "Monitor2" },
            { name: "Monitor3" },
        ];

        return monitorConfigs.map(({ name }, i) => {
            if (focusedMedia !== "Monitor") {
                // Not focused: show video texture
                const originalGroup = nodes[name];
                const groupClone = originalGroup.clone(true);

                // Clone all materials
                groupClone.traverse((child: any) => {
                    if (child.isMesh) {
                        child.material = Array.isArray(child.material)
                            ? child.material.map((m: any) => m.clone())
                            : child.material.clone();
                    }
                });

                // Replace "Screen" material's map with video
                groupClone.traverse((child: any) => {
                    if (child.isMesh) {
                        const mats = Array.isArray(child.material)
                            ? child.material
                            : [child.material];
                        mats.forEach((mat: any) => {
                            if (mat.name.includes("Screen")) {
                                mat.map = monitorVideoTexture;
                                mat.emissiveMap = monitorVideoTexture;
                                mat.needsUpdate = true;
                                if (mat.map) mat.map.needsUpdate = true;
                                if (mat.emissiveMap) mat.emissiveMap.needsUpdate = true;
                            }
                        });
                    }
                });

                return (
                    <group
                        key={name}
                        onPointerDown={(e: any) => {
                            e.stopPropagation();
                            if (focusedMedia === null) {
                                selectedObject.current = e.object;
                                setFocusedMedia("Monitor");
                            }
                        }}
                        onPointerOver={() => {
                            document.body.style.cursor = "pointer";
                        }}
                        onPointerOut={() => {
                            document.body.style.cursor = "default";
                        }}>
                        <primitive object={groupClone} />
                    </group>
                );
            } else {
                // Focused: show image texture
                const clone = nodes[name].clone(true);
                clone.traverse((child: any) => {
                    if (child.isMesh) {
                        child.material = Array.isArray(child.material)
                            ? child.material.map((m: any) => m.clone())
                            : child.material.clone();
                    }
                });

                clone.traverse((child: any) => {
                    if (child.isMesh) {
                        const mats = Array.isArray(child.material)
                            ? child.material
                            : [child.material];
                        mats.forEach((mat: any) => {
                            if (mat.name.includes("Screen")) {
                                mat.map = monitorImageTextures[i];
                                mat.emissiveMap = monitorImageTextures[i];
                                mat.needsUpdate = true;
                            }
                        });
                    }
                });
                return (
                    <primitive
                        key={name}
                        object={clone}
                        onPointerDown={(e: any) => {
                            e.stopPropagation();
                        }}
                        onPointerOver={() => {
                            document.body.style.cursor = "default";
                        }}
                        onPointerOut={() => {
                            document.body.style.cursor = "default";
                        }}
                    />
                );
            }
        });
    }, [focusedMedia, monitorImageTextures, monitorVideoTexture, nodes]);

    return (
        <>
            {/* Render the whole scene */}
            <primitive
                object={scene}
                onPointerDown={(e: any) => {
                    e.stopPropagation();
                    if (focusedMedia !== null) {
                        setFocusedMedia(null);
                    } else if (dragging) {
                        setDragging(false);
                        controls.current.enabled = true;
                    }
                }}
                onPointerUp={() => {
                    if (dragging) {
                        setDragging(false);
                        controls.current.enabled = true;
                    }
                }} />

            {/* Render chair separately with drag interaction */}
            <primitive
                object={nodes["Chair"]}
                ref={chairRef}
                onPointerDown={(e: any) => {
                    e.stopPropagation();
                    if (focusedMedia !== null) {
                        setFocusedMedia(null);
                        return;
                    }
                    if (!dragging) {
                        setDragging(true);
                        controls.current.enabled = false;
                    }
                }}
                onPointerUp={(e: any) => {
                    e.stopPropagation();
                    if (dragging) {
                        setDragging(false);
                        controls.current.enabled = true;
                    }
                }}
                onPointerMove={(e: any) => {
                    if (dragging && chairRef.current) {
                        const deltaX = e.movementX;
                        chairRef.current.rotation.z += deltaX * 0.01;
                    }
                }}
                onPointerOver={() => {
                    document.body.style.cursor = "grab";
                }}
                onPointerOut={() => {
                    document.body.style.cursor = "default";
                }}
            />

            {/* Render TV separately with click interaction */}
            {tvDisplay}

            {/* Render Monitors separately with click interaction */}
            {monitorDisplays}
        </>
    );
}
