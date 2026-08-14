import { CheckCircle2, AlertTriangle, XCircle, Loader2 } from "lucide-react";

export type StatusTone = "ok" | "degraded" | "down" | "loading";

const TONE_STYLES: Record<StatusTone, { dot: string; text: string; bg: string; Icon: typeof CheckCircle2 }> = {
  ok: { dot: "bg-success", text: "text-success", bg: "bg-success/10", Icon: CheckCircle2 },
  degraded: { dot: "bg-amber-500", text: "text-amber-600", bg: "bg-amber-50", Icon: AlertTriangle },
  down: { dot: "bg-danger", text: "text-danger", bg: "bg-danger/10", Icon: XCircle },
  loading: { dot: "bg-muted-text", text: "text-muted-text", bg: "bg-light-blue", Icon: Loader2 },
};

/**
 * Small pill used throughout the header/dashboard to reflect REAL service status
 * (spec §84) — never render this with a hardcoded "ok" tone; always derive `tone`
 * from a live health check result.
 */
export function StatusChip({ label, tone }: { label: string; tone: StatusTone }) {
  const { text, bg, Icon } = TONE_STYLES[tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${bg} ${text}`}>
      <Icon className={`h-3.5 w-3.5 ${tone === "loading" ? "animate-spin" : ""}`} />
      {label}
    </span>
  );
}
