import { useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ClipboardList, FileText, FlaskConical, HelpCircle, Pill, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { qk, usePrevisit } from "@/api/hooks";
import type { BriefOutput, CopilotRun } from "@/api/types";
import { Badge, Button, Card, CardHeader, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import { AIEmpty, Bullets, MiniHeading, RunError, RunMeta } from "./parts";

/** What to know before the patient sits down: chart facts since the last visit plus an AI brief. */
export function BriefCard({ patientId, canRun, className }: { patientId: string; canRun: boolean; className?: string }) {
  const { data, isLoading } = usePrevisit(patientId);
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const r = await api<CopilotRun<BriefOutput>>(`/api/patients/${patientId}/previsit/brief`, { method: "POST" });
      if (r.status === "error") toast.error(r.error ?? "Brief failed");
      qc.invalidateQueries({ queryKey: qk.sub(patientId, "previsit") });
      qc.invalidateQueries({ queryKey: qk.today });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Brief failed");
    } finally {
      setBusy(false);
    }
  };

  const f = data?.facts;
  const brief = data?.brief;
  const out = brief?.status === "draft" ? brief.output : null;

  return (
    <Card className={className}>
      <CardHeader
        icon={<ClipboardList />}
        title="Before you see the patient"
        description={f?.last_visit ? `Last visit ${fmtDate(f.last_visit.date)} · ${f.days_since_last_visit} days ago` : "First visit in this system"}
        actions={f?.follow_up && f.follow_up.overdue_days > 0 && <Badge tone="warning"><CalendarClock /> Follow-up {f.follow_up.overdue_days} d overdue</Badge>}
      />
      <div className="card-pad space-y-4">
        {isLoading || !f ? <Skeleton className="h-40" /> : (
          <>
            {f.last_visit && (
              <div className="rounded-xl border border-border/60 bg-card/60 p-3">
                <MiniHeading icon={<CalendarClock />}>Last time</MiniHeading>
                <div className="text-[0.85rem] font-medium">{f.last_visit.reason}</div>
                {!!f.last_visit.diagnoses.length && <div className="mt-1 flex flex-wrap gap-1">{f.last_visit.diagnoses.map((d) => <Badge key={d.name} tone="neutral">{d.name}</Badge>)}</div>}
                {f.last_visit.plan && <p className="mt-1.5 text-[0.78rem] text-muted-foreground">Plan: {f.last_visit.plan}</p>}
                {f.last_prescription && (
                  <div className="mt-2 flex flex-wrap items-center gap-1 text-[0.75rem]">
                    <Pill className="size-3.5 text-muted-foreground" />
                    {f.last_prescription.items.map((i) => <span key={i.line} className="rounded-md bg-muted px-1.5 py-0.5">{i.line}</span>)}
                  </div>
                )}
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <FactList icon={<FlaskConical />} title="Results since then" empty="No new abnormal results"
                items={f.abnormal_results.map((r) => ({ key: r.id, text: <><b>{r.name}</b> {String(r.value)} {r.unit} <span className={cn("font-medium", r.flag === "low" ? "text-info-foreground" : "text-danger-foreground")}>{r.flag}</span></>, sub: fmtDate(r.date) }))} />
              <FactList icon={<FileText />} title="Reports & tests" empty="Nothing pending"
                items={[
                  ...f.orders.map((o) => ({ key: o.id, text: <><b>{o.test_name}</b> — {o.status === "result_received" ? <span className="font-medium text-warning-foreground">result back, not reviewed</span> : "awaiting result"}</>, sub: `Ordered ${fmtDate(o.ordered_at)}` })),
                  ...f.new_documents.slice(0, 3).map((d) => ({ key: d.id, text: <Link to={`/patients/${patientId}/documents?doc=${d.id}`} className="hover:underline">{d.title}</Link>, sub: fmtDate(d.date) })),
                ]} />
            </div>

            <RunError run={brief} />
            {out ? (
              <div className="space-y-3 rounded-xl border border-primary/20 bg-primary-soft/30 p-3.5">
                <RunMeta run={brief} onRerun={canRun ? run : undefined} busy={busy} />
                <p className="text-[0.9rem] font-semibold leading-snug">{out.headline}</p>
                {!!out.ask_about.length && (
                  <div>
                    <MiniHeading icon={<HelpCircle />}>Ask about</MiniHeading>
                    <ol className="space-y-1.5">
                      {out.ask_about.map((q, i) => (
                        <li key={i} className="flex gap-2 text-[0.82rem]">
                          <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-strong text-[0.65rem] font-semibold text-strong-foreground num">{i + 1}</span>
                          <div><div className="font-medium leading-snug">{q.question}</div>{q.why && <div className="text-[0.72rem] text-muted-foreground">{q.why}</div>}</div>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  {!!out.since_last_visit.length && <div><MiniHeading>Since last visit</MiniHeading><Bullets items={out.since_last_visit} /></div>}
                  {!!out.watch_outs.length && <div><MiniHeading icon={<ShieldAlert />}>Watch out today</MiniHeading><Bullets items={out.watch_outs} /></div>}
                </div>
                {!!out.consider_today.length && <div><MiniHeading>Consider today</MiniHeading><Bullets items={out.consider_today} /></div>}
              </div>
            ) : canRun ? (
              <AIEmpty busy={busy} title="AI pre-visit brief" text="Reads the full record — previous complaints, results, reports and medicines — and suggests what to ask today."
                action={<Button size="sm" variant="strong" className="rounded-full" onClick={run}><Sparkles /> Prepare brief</Button>} />
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}

function FactList({ icon, title, items, empty }: { icon: React.ReactNode; title: string; items: { key: string; text: React.ReactNode; sub?: string }[]; empty: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/60 p-3">
      <MiniHeading icon={icon}>{title}</MiniHeading>
      {items.length ? (
        <ul className="space-y-1.5">{items.map((i) => <li key={i.key} className="text-[0.8rem] leading-snug">{i.text}{i.sub && <div className="text-[0.68rem] text-muted-foreground">{i.sub}</div>}</li>)}</ul>
      ) : <p className="text-[0.78rem] text-muted-foreground">{empty}</p>}
    </div>
  );
}
