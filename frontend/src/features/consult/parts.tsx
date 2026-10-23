import { AlertOctagon, AlertTriangle, CheckCircle2, Info, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import type { CopilotRun, Finding, Severity } from "@/api/types";
import { Badge, Button, Spinner } from "@/components/ui";
import { cn, fmtRelative } from "@/lib/utils";

export const SEVERITY_META: Record<Severity, { label: string; tone: "success" | "info" | "warning" | "danger"; icon: typeof Info; text: string; soft: string }> = {
  ok: { label: "No issues", tone: "success", icon: CheckCircle2, text: "text-success-foreground", soft: "bg-success-soft" },
  info: { label: "Note", tone: "info", icon: Info, text: "text-info-foreground", soft: "bg-info-soft" },
  warning: { label: "Caution", tone: "warning", icon: AlertTriangle, text: "text-warning-foreground", soft: "bg-warning-soft" },
  critical: { label: "Stop & check", tone: "danger", icon: AlertOctagon, text: "text-danger-foreground", soft: "bg-danger-soft" },
};

export function SeverityBadge({ severity, label, className }: { severity: Severity; label?: string; className?: string }) {
  const m = SEVERITY_META[severity];
  return <Badge tone={m.tone} className={className}><m.icon /> {label ?? m.label}</Badge>;
}

export function FindingList({ findings, dense, max }: { findings: Finding[]; dense?: boolean; max?: number }) {
  const shown = max ? findings.slice(0, max) : findings;
  if (!findings.length) return null;
  return (
    <ul className={cn("space-y-1.5", dense && "space-y-1")}>
      {shown.map((f, i) => {
        const m = SEVERITY_META[f.severity];
        return (
          <li key={i} className={cn("flex gap-2 rounded-lg px-2.5 py-1.5 text-[0.78rem] leading-snug", m.soft)}>
            <m.icon className={cn("mt-0.5 size-3.5 shrink-0", m.text)} />
            <div className="min-w-0">
              <span className={cn("font-semibold", m.text)}>{f.title}</span>
              <span className="text-foreground/80"> — {f.detail}</span>
              {f.basis && !dense && <div className="mt-0.5 text-[0.7rem] text-muted-foreground">Based on: {f.basis}</div>}
            </div>
          </li>
        );
      })}
      {max && findings.length > max && <li className="pl-2 text-[0.72rem] text-muted-foreground">+{findings.length - max} more</li>}
    </ul>
  );
}

/** Header strip for an AI result: model, when, regenerate. */
export function RunMeta({ run, onRerun, busy, label = "Regenerate" }: { run: CopilotRun | null | undefined; onRerun?: () => void; busy?: boolean; label?: string }) {
  if (!run) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[0.7rem] text-muted-foreground">
      <Sparkles className="size-3 text-primary" />
      <span>{run.model ?? "AI"} · {fmtRelative(run.created_at)}{run.latency_ms ? ` · ${(run.latency_ms / 1000).toFixed(1)} s` : ""}</span>
      <Badge tone="outline">Draft · verify before acting</Badge>
      {onRerun && <Button size="xs" variant="ghost" onClick={onRerun} loading={busy}>{label}</Button>}
    </div>
  );
}

export function AIEmpty({ title, text, action, busy }: { title: string; text: string; action: ReactNode; busy?: boolean }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-primary/30 bg-primary-soft/40 p-4">
      <div className="flex items-center gap-2 text-[0.85rem] font-semibold"><Sparkles className="size-4 text-primary" /> {title}</div>
      <p className="text-[0.78rem] text-muted-foreground">{text}</p>
      {busy ? <div className="flex items-center gap-2 text-xs text-muted-foreground"><Spinner className="size-3.5" /> Thinking — a 27B clinical model can take a minute on local hardware…</div> : action}
    </div>
  );
}

export function RunError({ run }: { run: CopilotRun | null | undefined }) {
  if (!run || run.status !== "error") return null;
  return <div className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger-foreground">{run.error ?? "The AI request failed."}</div>;
}

export function Bullets({ items, className }: { items: string[]; className?: string }) {
  if (!items?.length) return null;
  return <ul className={cn("list-disc space-y-1 pl-4 text-[0.8rem] leading-snug marker:text-muted-foreground", className)}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>;
}

export function MiniHeading({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return <div className="mb-1.5 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground [&_svg]:size-3.5">{icon}{children}</div>;
}
