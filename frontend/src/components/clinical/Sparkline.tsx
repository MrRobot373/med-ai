import { cn } from "@/lib/utils";

export function Sparkline({ values, className, tone = "primary", height = 28, width = 96 }: { values: number[]; className?: string; tone?: "primary" | "danger" | "warning" | "success"; height?: number; width?: number }) {
  if (values.length < 2) return <div className={cn("h-7", className)} style={{ width }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => [i * step, height - 3 - ((v - min) / span) * (height - 6)] as const);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const color = { primary: "hsl(var(--primary))", danger: "hsl(var(--danger))", warning: "hsl(var(--warning))", success: "hsl(var(--success))" }[tone];
  const last = pts[pts.length - 1];
  return (
    <svg width={width} height={height} className={className} aria-hidden>
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={color} opacity={0.08} />
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={color} />
    </svg>
  );
}
