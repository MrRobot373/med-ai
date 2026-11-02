import { Activity, CalendarClock, FileText, FlaskConical, HeartPulse, Pill, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useTimeline } from "@/api/hooks";
import { Card, EmptyState, Segmented, Skeleton } from "@/components/ui";
import { cn, fmtDate } from "@/lib/utils";
import { useWorkspace } from "./context";

const KIND = {
  encounter: { icon: CalendarClock, label: "Encounters" }, document: { icon: FileText, label: "Documents" }, labs: { icon: FlaskConical, label: "Results" },
  condition: { icon: HeartPulse, label: "Diagnoses" }, medication: { icon: Pill, label: "Medications" }, ai: { icon: Sparkles, label: "AI" },
} as const;
const TONE: Record<string, string> = {
  primary: "bg-primary-soft text-primary-soft-foreground", info: "bg-info-soft text-info-foreground", warning: "bg-warning-soft text-warning-foreground",
  success: "bg-success-soft text-success-foreground", danger: "bg-danger-soft text-danger-foreground", neutral: "bg-muted text-muted-foreground",
};

export default function TimelineTab() {
  const { patient } = useWorkspace();
  const { data, isLoading } = useTimeline(patient.id);
  const [kind, setKind] = useState<string>("all");
  const groups = useMemo(() => {
    const items = (data ?? []).filter((e) => kind === "all" || e.kind === kind);
    const out: { month: string; items: typeof items }[] = [];
    for (const e of items) {
      const m = fmtDate(e.at, "MMMM yyyy");
      if (!out.length || out[out.length - 1].month !== m) out.push({ month: m, items: [] });
      out[out.length - 1].items.push(e);
    }
    return out;
  }, [data, kind]);

  const linkFor = (ref: Record<string, string> | null) =>
    ref?.document_id ? `../documents?doc=${ref.document_id}` : ref?.encounter_id ? "../encounters" : ref?.medication_id ? "../medications" : ref?.condition_id ? "../problems" : ref?.run_id ? `../tools?run=${ref.run_id}` : null;

  return (
    <div className="space-y-4">
      <Segmented value={kind} onChange={setKind} options={[{ value: "all", label: "Everything" }, ...Object.entries(KIND).map(([k, v]) => ({ value: k, label: v.label }))]} />
      <Card className="card-pad">
        {isLoading ? <Skeleton className="h-96" /> : groups.length === 0 ? <EmptyState icon={<Activity />} title="Nothing on the timeline yet" /> : (
          <div className="space-y-8">
            {groups.map((g) => (
              <div key={g.month}>
                <div className="text-label mb-3">{g.month}</div>
                <ol className="relative space-y-4 border-l pl-6">
                  {g.items.map((e, i) => {
                    const meta = KIND[e.kind as keyof typeof KIND] ?? KIND.encounter;
                    const to = linkFor(e.ref);
                    const body = (
                      <div className="rounded-lg px-2 py-1 -mx-2 transition-colors hover:bg-muted/60">
                        <div className="flex flex-wrap items-baseline gap-x-2"><span className="text-sm font-medium">{e.title}</span><span className="text-xs text-muted-foreground">{fmtDate(e.at, "EEE d MMM")}</span></div>
                        {e.detail && <p className="mt-0.5 text-[0.8rem] text-muted-foreground">{e.detail}</p>}
                      </div>
                    );
                    return (
                      <li key={i} className="relative">
                        <span className={cn("absolute -left-[37px] top-0.5 flex size-6 items-center justify-center rounded-full ring-4 ring-card", TONE[e.tone] ?? TONE.neutral)}><meta.icon className="size-3.5" /></span>
                        {to ? <Link to={to} relative="path">{body}</Link> : body}
                      </li>
                    );
                  })}
                </ol>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
