import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Stack({ filled, tone }: { filled: number; tone: "danger" | "muted" }) {
  return (
    <div className="flex flex-col-reverse gap-[3px]">
      {Array.from({ length: 6 }).map((_, i) => <span key={i} className={cn("h-[5px] w-7 rounded-sm", i < filled ? (tone === "danger" ? "bg-danger/80" : "bg-strong/70") : "bg-muted")} />)}
    </div>
  );
}

export function PlanItem({ icon, title, text, tone = "primary" }: { icon: ReactNode; title: string; text?: string | null; tone?: "primary" | "danger" | "warning" | "success" }) {
  const tones = { primary: "bg-primary-soft text-primary-soft-foreground", danger: "bg-danger-soft text-danger-foreground", warning: "bg-warning-soft text-warning-foreground", success: "bg-success-soft text-success-foreground" };
  return (
    <div className="flex gap-3 rounded-xl border border-border/60 bg-card/70 p-3">
      <span className={cn("flex size-11 shrink-0 items-center justify-center rounded-xl shadow-xs [&_svg]:size-5", tones[tone])}>{icon}</span>
      <div className="min-w-0">
        <div className="truncate text-[0.82rem] font-semibold">{title}</div>
        {text && <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{text}</p>}
      </div>
    </div>
  );
}

