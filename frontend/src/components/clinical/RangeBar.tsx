import { cn, fmtNum } from "@/lib/utils";

/** Where a value sits relative to the range the source document stated.
 *  Without a stated range nothing is judged — the bar is shown neutral. */
export function rangeStatus(value: number | null, low: number | null, high: number | null) {
  if (value === null || (low === null && high === null)) return { label: "No range stated", tone: "neutral" as const };
  if (low !== null && value < low) return { label: "Below range", tone: "warning" as const };
  if (high !== null && value > high) return { label: "Above range", tone: "danger" as const };
  return { label: "Within range", tone: "success" as const };
}

export function RangeBar({ value, low, high, className }: { value: number | null; low: number | null; high: number | null; className?: string }) {
  if (value === null || (low === null && high === null)) {
    return <div className={cn("h-2 rounded-full bg-muted", className)} />;
  }
  // Scale: stated range occupies the middle; extend both sides so outliers stay visible.
  let min: number, max: number, gradient: string;
  if (low !== null && high !== null) {
    const span = high - low || Math.abs(high) || 1;
    min = Math.min(low - span * 0.6, value - span * 0.1);
    max = Math.max(high + span * 0.6, value + span * 0.1);
    gradient = "range-gradient";
  } else if (high !== null) {
    min = 0;
    max = Math.max(high * 1.8, value * 1.1);
    gradient = "range-gradient-high";
  } else {
    min = Math.min(low! * 0.4, value * 0.9);
    max = Math.max(low! * 1.6, value * 1.1);
    gradient = "range-gradient-low";
  }
  const pos = (v: number) => `${Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100))}%`;
  return (
    <div className={cn("space-y-1", className)}>
      <div className="relative h-2.5">
        <div className={cn("absolute inset-0 rounded-full opacity-90", gradient)} />
        {low !== null && <span className="absolute top-0 h-full w-px bg-white/90" style={{ left: pos(low) }} />}
        {high !== null && <span className="absolute top-0 h-full w-px bg-white/90" style={{ left: pos(high) }} />}
        <span className="absolute -top-1 h-[18px] w-1 -translate-x-1/2 rounded-full bg-foreground shadow ring-2 ring-card" style={{ left: pos(value) }} />
      </div>
      <div className="relative h-3 text-[0.65rem] text-muted-foreground num">
        {low !== null && <span className="absolute -translate-x-1/2" style={{ left: pos(low) }}>{fmtNum(low)}</span>}
        {high !== null && <span className="absolute -translate-x-1/2" style={{ left: pos(high) }}>{fmtNum(high)}</span>}
      </div>
    </div>
  );
}

/** Segmented level bar for scores (Low → Very high). */
export function LevelBar({ level, levels, className }: { level: number; levels: string[]; className?: string }) {
  const n = levels.length;
  const colors = n <= 3 ? ["bg-success", "bg-warning", "bg-danger"] : ["bg-success", "bg-warning", "bg-orange-500", "bg-danger"];
  return (
    <div className={cn("flex gap-1", className)}>
      {levels.map((l, i) => (
        <div key={l} className="flex-1">
          <div className={cn("h-1.5 rounded-full", i <= level ? colors[Math.round((i / Math.max(n - 1, 1)) * (colors.length - 1))] : "bg-muted")} />
        </div>
      ))}
    </div>
  );
}
