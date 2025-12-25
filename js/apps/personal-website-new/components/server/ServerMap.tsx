'use client';

import dynamic from 'next/dynamic';
import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { FaDatabase, FaCloud, FaRocket } from 'react-icons/fa';
import { BsGpuCard } from "react-icons/bs";
import { GoServer } from "react-icons/go";
import { GrGateway } from "react-icons/gr";
import { SiProxmox } from "react-icons/si";
import clsx from 'clsx';
import { IconType, drawHexNode, drawNodeConnector, drawNodeLabel, paintHexPointerArea } from './HexNode';
import { useResizeManager } from '@/hooks/useResizeManager';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

type ArchNode = {
    id: string;
    name: string;
    status: 'on' | 'off';
    icon?: IconType;
    iconImg?: HTMLImageElement;
    color?: string;
    size?: number;
    x?: number;
    y?: number;
    fx?: number;
    fy?: number;
};

type ArchLink = {
    source: string;
    target: string;
    label?: string;
    kind?: 'http' | 'grpc' | 'sse' | 'queue' | 'db';
};

function colorByStatus(status: 'on' | 'off') {
    return status === 'on' ? '#22C55E' : '#EF4444'; // green-500 : red-500
}

// Icon map for React Icons
const iconMap = {
    database: FaDatabase,
    server: SiProxmox,
    node: GoServer,
    gateway: GrGateway,
    cloud: FaCloud,
    gpu: BsGpuCard,
    rocket: FaRocket,
} as const;

// Convert React Icon to HTMLImageElement for canvas rendering
function iconToImage(Icon: React.ComponentType<any>, size = 48, color = 'white'): HTMLImageElement {
    const svgString = renderToStaticMarkup(<Icon size={size} color={color} />);
    const img = new Image();
    img.src = `data:image/svg+xml;utf8,${encodeURIComponent(svgString)}`;
    return img;
}


export default function ServerMap() {
    const fgRef = useRef<any>(null);
    const wrapRef = useRef<HTMLDivElement | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [dim, setDim] = useState({ w: 0, h: 0 });
    const [isVertical, setIsVertical] = useState(false);
    const [size, setSize] = useState<number>(32);
    const [positionScale, setPositionScale] = useState<number>(1.0);

    // Check layout on resize
    const checkLayout = useCallback(() => {
        const width = window.innerWidth;
        setIsVertical(width < 764);
        setSize(width < 764 ? 12 : 30);

        // Calculate position scale: smoothly scale from 0.4 to 1.0
        if (width < 764) {
            setPositionScale(1);
        } else if (width < 1200) {
            setPositionScale(0.7 + (1.0 - 0.7) * ((width - 764) / (1200 - 764)));
        } else {
            setPositionScale(1.0);
        }
    }, []);

    useResizeManager(checkLayout);

    // Check layout on mount
    useEffect(() => {
        checkLayout();
    }, [checkLayout]);


    const graphData = useMemo(() => {

        const nodes: ArchNode[] = [
            // Physical Servers (leftmost)
            { id: 'server-west', name: 'US West Server', status: 'on', icon: 'server', size },
            { id: 'server-east', name: 'US East Server', status: 'on', icon: 'server', size },

            // Compute Nodes
            { id: 'node-local2', name: 'Node 9950X', status: 'on', icon: 'node', size },
            { id: 'node-local', name: 'Node 5800X', status: 'on', icon: 'node', size },

            // Gateway
            { id: 'web-gateway', name: 'Web Gateway', status: 'on', icon: 'gateway', size },

            // Core Services
            { id: 'steven-ai', name: 'Steven AI Service', status: 'on', icon: 'rocket', size },
            { id: 'misc-web-service', name: 'Misc Web Service', status: 'on', icon: 'cloud', size },
            { id: 'backup-web-service', name: 'Backup Web Service', status: 'on', icon: 'cloud', size },

            // GPU Service
            { id: 'gpu-server', name: 'GPU Service', status: 'on', icon: 'gpu', size },

            // Storage Services
            { id: 'stev-cloud', name: 'StevCloud', status: 'on', icon: 'database', size },
            { id: 'file-service', name: 'File Service', status: 'on', icon: 'database', size },
            { id: 'minio', name: 'MinIO', status: 'on', icon: 'database', size },
        ];

        const links: ArchLink[] = [
            // Servers to their nodes
            { source: 'server-west', target: 'node-local2', label: 'Host', kind: 'http' },
            { source: 'server-east', target: 'node-local', label: 'Host', kind: 'http' },

            // Nodes to gateway
            { source: 'node-local2', target: 'web-gateway', label: 'Connect', kind: 'http' },

            // Gateway to services
            { source: 'web-gateway', target: 'steven-ai', label: 'Route', kind: 'http' },
            { source: 'web-gateway', target: 'misc-web-service', label: 'Route', kind: 'http' },

            { source: 'node-local', target: 'stev-cloud', label: 'Connect', kind: 'http' },
            { source: 'node-local', target: 'backup-web-service', label: 'Connect', kind: 'http' },

            // Steven AI to GPU
            { source: 'steven-ai', target: 'gpu-server', label: 'Inference', kind: 'grpc' },

            // GPU and Misc services to File Server
            { source: 'gpu-server', target: 'file-service', label: 'Store', kind: 'http' },
            { source: 'misc-web-service', target: 'file-service', label: 'Access', kind: 'http' },

            // File Server to MinIO
            { source: 'file-service', target: 'minio', label: 'S3', kind: 'db' },
        ];

        const locked = true;
        if (locked) {
            const baseLayout: Record<string, { x: number; y: number }> = isVertical
                ? {
                    // Vertical layout - stacked top to bottom
                    'server-west': { x: -60, y: -400 },
                    'node-local2': { x: -60, y: -320 },
                    'web-gateway': { x: -60, y: -240 },
                    'steven-ai': { x: -100, y: -160 },
                    'misc-web-service': { x: -20, y: -160 },
                    'gpu-server': { x: -100, y: -80 },
                    'file-service': { x: -60, y: 0 },
                    'minio': { x: -60, y: 80 },

                    // US East path - stacked on right side
                    'server-east': { x: 60, y: -400 },
                    'node-local': { x: 60, y: -320 },
                    'stev-cloud': { x: 20, y: -240 },
                    'backup-web-service': { x: 100, y: -240 },
                }
                : {
                    // Horizontal layout - spread left to right
                    'server-west': { x: -450, y: -80 },
                    'node-local2': { x: -280, y: -80 },
                    'web-gateway': { x: -80, y: -80 },
                    'steven-ai': { x: 100, y: -150 },
                    'misc-web-service': { x: 100, y: -10 },
                    'gpu-server': { x: 280, y: -150 },
                    'file-service': { x: 450, y: -80 },
                    'minio': { x: 620, y: -80 },

                    // US East path (bottom)
                    'server-east': { x: -450, y: 120 },
                    'node-local': { x: -280, y: 120 },
                    'stev-cloud': { x: -80, y: 60 },
                    'backup-web-service': { x: -80, y: 220 },
                };

            // Scale all positions based on screen size
            const layout: Record<string, { x: number; y: number }> = {};
            Object.keys(baseLayout).forEach(key => {
                layout[key] = {
                    x: baseLayout[key].x * positionScale,
                    y: baseLayout[key].y * positionScale
                };
            });

            nodes.forEach((n) => {
                const p = layout[n.id];
                if (p) {
                    // Store anchor instead of hard lock
                    (n as any).anchor = { x: p.x, y: p.y };
                    n.x = p.x;
                    n.y = p.y;
                }
            });
        }

        return { nodes, links };
    }, [isVertical, size, positionScale]);

    // Measure container dimensions with ResizeObserver
    useEffect(() => {
        if (!wrapRef.current) return;
        const el = wrapRef.current;

        const ro = new ResizeObserver(() => {
            const r = el.getBoundingClientRect();
            setDim({ w: Math.floor(r.width), h: Math.floor(r.height) });
        });

        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    // Convert React Icons to images for canvas rendering
    useEffect(() => {
        const nodes = graphData.nodes as ArchNode[];

        nodes.forEach((n) => {
            if (!n.icon) return;

            // Get React Icon component from map
            const IconComponent = iconMap[n.icon as keyof typeof iconMap];
            if (!IconComponent) {
                console.warn(`Icon type "${n.icon}" not found in iconMap`);
                return;
            }

            // Convert React Icon to Image
            n.iconImg = iconToImage(IconComponent, 48, 'white');
        });

        // Force re-render by reheating simulation
        if (fgRef.current?.d3ReheatSimulation) {
            fgRef.current.d3ReheatSimulation();
        }
    }, [graphData.nodes]);


    const zoomToDefault = useCallback(() => {
        if (!fgRef.current) return;
        setSelectedId(null);
        // Responsive padding: 20% of smaller dimension
        const padding = Math.min(dim.w * 0.15, dim.h * 0.15);
        fgRef.current.zoomToFit(400, padding);
    }, [dim.w, dim.h]);

    const focusNode = useCallback((node: any) => {
        if (!fgRef.current || !node) return;
        const x = node.x ?? 0;
        const y = node.y ?? 0;
        const currentZoom = fgRef.current.zoom() || 1;

        // Shift center point right by 12.5% of screen width (in graph coords)
        // This makes the node appear at 37.5% from left, leaving 25% for right menu
        const screenOffsetX = dim.w * 0.125; // 12.5% of screen width
        const graphOffsetX = screenOffsetX / currentZoom; // Convert to graph coordinates

        fgRef.current.centerAt(x + graphOffsetX, y, 400);
        fgRef.current.zoom(currentZoom * 1.5, 400);
    }, [dim.w]);

    // Re-fit graph when dimensions change
    useEffect(() => {
        if (!fgRef.current || dim.w === 0 || dim.h === 0) return;

        const timer = setTimeout(() => {
            zoomToDefault();
        }, 200);

        return () => clearTimeout(timer);
    }, [dim.w, dim.h, zoomToDefault]);

    // Memoized callback functions for ForceGraph2D
    const handleNodeClick = useCallback((node: any) => {
        zoomToDefault();
        // Wait for zoom-to-fit animation to complete before focusing
        setTimeout(() => {
            setSelectedId(node.id);
            focusNode(node);
        }, 450); // Slightly longer than animation duration to ensure completion
    }, [focusNode, zoomToDefault]);

    const getLinkWidth = useCallback((l: any) => {
        return selectedId && (l.source?.id === selectedId || l.target?.id === selectedId) ? 2.2 : 2;
    }, [selectedId]);

    const getLinkColor = useCallback((l: any) => {
        const sid = l.source?.id ?? l.source;
        const tid = l.target?.id ?? l.target;
        const hot = selectedId && (sid === selectedId || tid === selectedId);
        return hot ? 'rgba(255,210,125,0.9)' : 'rgba(255,255,255,0.18)';
    }, [selectedId]);

    const renderLinkLabel = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        if (size <= 12) return;
        const label = link.label;
        if (!label) return;
        const src = link.source;
        const trg = link.target;
        if (!src || !trg) return;
        const x = (src.x + trg.x) / 2;
        const y = (src.y + trg.y) / 2;
        drawNodeConnector(ctx, x, y, label, globalScale);
    }, [size]);

    const renderNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        const n = node as ArchNode;
        const r = n.size ?? 28;
        const isSelected = selectedId === n.id;
        const color = n.color ?? colorByStatus(n.status);

        drawHexNode(ctx, n.x ?? 0, n.y ?? 0, r, color, isSelected, globalScale, n.iconImg);
        drawNodeLabel(ctx, n.x ?? 0, n.y ?? 0, r, n.name ?? n.id, isSelected, globalScale);
    }, [selectedId]);

    return (
        <div className={clsx("w-full h-full", isVertical && "pt-[15vh]")}>
            <div ref={wrapRef} className={clsx("w-full h-full")}>
                {dim.w > 0 && dim.h > 0 && (
                    <ForceGraph2D
                        ref={fgRef}
                        width={dim.w}
                        height={dim.h}
                        onEngineStop={() => {
                            zoomToDefault();
                        }}

                        graphData={graphData as any}
                        backgroundColor="transparent"
                        enableNodeDrag={false}
                        enablePanInteraction={true}
                        enableZoomInteraction={false}
                        cooldownTicks={0}
                        onNodeClick={handleNodeClick}
                        onBackgroundClick={zoomToDefault}
                        linkCurvature={0.06}
                        linkDirectionalParticles={4}
                        linkDirectionalParticleSpeed={0.006}
                        linkDirectionalParticleWidth={2}
                        linkWidth={getLinkWidth}
                        linkColor={getLinkColor}
                        linkCanvasObjectMode={() => 'after'}
                        linkCanvasObject={renderLinkLabel}
                        nodePointerAreaPaint={paintHexPointerArea}
                        nodeLabel={''}
                        nodeCanvasObject={renderNode}
                    />
                )}
            </div>
        </div>
    );
}
