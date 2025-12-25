// Icon types
export type IconType =
    | 'database'
    | 'server'
    | 'cog'
    | 'network'
    | 'cloud'
    | 'rocket'
    | 'node'
    | 'gateway'
    | 'gpu';

// -----------------------------
// Utility helpers
// -----------------------------
export function clamp(v: number, min: number, max: number) {
    return Math.max(min, Math.min(max, v));
}

export function hexToRgba(hex: string, opacity: number): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

export function darkenColor(hex: string, amount: number): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgb(
    ${Math.round(r * (1 - amount))},
    ${Math.round(g * (1 - amount))},
    ${Math.round(b * (1 - amount))}
  )`;
}

// -----------------------------
// Hex geometry
// -----------------------------
export function drawHex(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    r: number
) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + r * Math.cos(angle);
        const py = y + r * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
}

// -----------------------------
// MAIN NODE RENDERER
// -----------------------------
export function drawHexNode(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    baseRadius: number,
    color: string,
    isSelected: boolean,
    globalScale: number,
    iconImg?: HTMLImageElement
) {
    // Clamp zoom influence
    const zoom = clamp(globalScale, 0.6, 1.5);

    // Node size behavior
    const radius = baseRadius * zoom;

    // Stroke should NOT scale too aggressively
    const strokeWidth = 1.4;

    // Glow scaling
    const glow = isSelected
        ? clamp(16 / zoom, 6, 18)
        : clamp(10 / zoom, 4, 14);

    ctx.save();

    // Glow
    ctx.shadowBlur = glow;
    ctx.shadowColor = isSelected
        ? 'rgba(255,210,125,0.85)'
        : hexToRgba(color, 0.35);

    // Hex fill
    drawHex(ctx, x, y, radius);
    ctx.fillStyle = darkenColor(color, 0.6);
    ctx.fill();

    // Stroke
    ctx.shadowBlur = 0;
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = isSelected
        ? 'rgba(255,210,125,0.95)'
        : color;
    ctx.stroke();

    // Icon (scales gently)
    if (iconImg) {
        const ir = radius * 0.55;

        ctx.drawImage(
            iconImg,
            x - ir,
            y - ir,
            ir * 2,
            ir * 2
        );
    }

    ctx.restore();
}

// -----------------------------
// LABEL RENDERING
// -----------------------------
export function drawNodeLabel(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    radius: number,
    label: string,
    isSelected: boolean,
    globalScale: number
) {

    const zoom = clamp(globalScale, 0.6, 1.5);
    // Smaller font for smaller nodes (radius 12 on mobile)
    const baseFontSize = radius <= 12 ? 7 : 13;
    const minSize = radius <= 12 ? 5 : 9;
    const maxSize = radius <= 12 ? 9 : 14;
    const fontSize = clamp(baseFontSize * zoom, minSize, maxSize);

    ctx.font = `${fontSize}px Poppins, ui-sans-serif, system-ui`;
    ctx.fillStyle = isSelected
        ? 'rgba(255,255,255,0.95)'
        : 'rgba(255,255,255,0.78)';

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    const extraspace = clamp(zoom * 4, 8, 2);

    ctx.fillText(label, x, y + radius * zoom + extraspace);
}


// -----------------------------
// LABEL RENDERING
// -----------------------------
export function drawNodeConnector(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    label: string,
    globalScale: number,
) {
    const zoom = clamp(globalScale, 0.6, 1.5);
    const fontSize = clamp(12 * zoom, 8, 12);
    ctx.save();
    ctx.font = `${fontSize}px Poppins, ui-sans-serif, system-ui`;
    ctx.fillStyle = 'rgba(255,255,255,0.60)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, x, y);
    ctx.restore();
}

// -----------------------------
// POINTER AREA (for hover/click detection)
// -----------------------------
export function paintHexPointerArea(
    node: any,
    color: string,
    ctx: CanvasRenderingContext2D
) {
    const r = node.size ?? 28;
    const x = node.x ?? 0;
    const y = node.y ?? 0;

    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + r * Math.cos(a);
        const py = y + r * Math.sin(a);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
}