import { AlertTriangle, ArrowRight, CalendarClock, FileText, FlaskConical, HeartPulse, Info, Pill, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { useOverview, useInvalidatePatient } from "@/api/hooks";
import type { AIRun, Alert } from "@/api/types";
import { Badge, Button, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui";
import { DocStatusBadge, FlagBadge, IdentityBadge, SEVERITY_TONE } from "@/components/clinical/badges";
import { ToolRunCard } from "@/components/clinical/ToolOutput";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, fmtNum, fmtRelative, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

function AlertStrip({ alerts, patientId }: { alerts: Alert[]; patientId: string }) {
  if (!alerts.length) return null;
  const icon = { danger: ShieldAlert, warning: AlertTriangle, info: Info };
  const tone = { danger: "border-danger/30 bg-danger-soft text-danger-foreground", warning: "border-warning/30 bg-warning-soft text-warning-foreground", info: "border-info/30 bg-info-soft text-info-foreground" };
  const link = (a: Alert) => (a.type === "lab" ? `/patients/${patientId}/results` : a.type === "gap" ? `/patients/${patientId}/problems` : `/patients/${patientId}/documents?doc=${a.id}`);
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {alerts.slice(0, 6).map((a, i) => {
        const Icon = icon[a.severity];
        return (
          <Link key={i} to={link(a)} className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm transition-opacity hover:opacity-90", tone[a.severity])}>
            <Icon className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0"><div className="font-medium">{a.title}</div><div className="truncate text-xs opacity-85">{a.detail}</div></div>
          </Link>
        );
      })}
    </div>
  );
}

export default function OverviewTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = useOverview(patient.id);
  const invalidate = useInvalidatePatient();
  const [running, setRunning] = useState(false);
  const [fresh, setFresh] = useState<AIRun | null>(null);

  if (isLoading || !data) return <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-64 lg:col-span-2" /><Skeleton className="h-64" /></div>;

  const generate = async () => {
    setRunning(true);
    try {
      const run = await api<AIRun>("/api/tools/summary/run", { method: "POST", body: { patient_id: patient.id } });
      setFresh(run);
      if (run.status === "error") toast.error(run.error ?? "Summary failed");
      invalidate(patient.id);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Summary failed");
    } finally {
      setRunning(false);
    }
  };

  const summaryRun: AIRun | null = fresh ?? (data.summary ? { id: data.summary.id, tool: "summary", patient_id: patient.id, encounter_id: null, input: {}, output: data.summary.output, citations: [], status: data.summary.status as AIRun["status"], error: null, model: null, latency_ms: null, created_at: data.summary.created_at, reviewed_at: null } : null);
  const active = data.conditions.filter((c) => ["active", "suspected"].includes(c.status));
  const meds = data.medications.filter((m) => m.status === "active");

  return (
    <div className="space-y-[var(--gap)]">
      <AlertStrip alerts={data.alerts} patientId={patient.id} />
      <div className="grid gap-[var(--gap)] lg:grid-cols-3">
        <div className="space-y-[var(--gap)] lg:col-span-2">
          <Card>
            <CardHeader
              title="AI case summary" icon={<Sparkles />}
              description={summaryRun ? `Generated ${fmtRelative(summaryRun.created_at)} from the chart and documents` : "A concise longitudinal summary with gaps and follow-ups, grounded in this chart."}
              actions={<Button size="sm" variant={summaryRun ? "secondary" : "primary"} loading={running} onClick={generate}>{summaryRun ? <><RefreshCw /> Regenerate</> : <><Sparkles /> Generate</>}</Button>}
            />
            <div className="card-pad">
              {running && !fresh ? <div className="space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-24" /><Skeleton className="h-24" /></div>
                : summaryRun ? <ToolRunCard run={summaryRun} canReview={canWrite} compactHeader onChange={(r) => setFresh(r)} />
                : <EmptyState compact icon={<Sparkles />} title="No summary yet" description="Generate a draft summary. It stays a draft until you accept it." />}
            </div>
          </Card>

          <Card>
            <CardHeader title="Latest results" description="Most recent value per test · flags only where the source states a range" icon={<FlaskConical />} actions={<Button size="sm" variant="ghost" asChild><Link to="../results" relative="path">All results <ArrowRight /></Link></Button>} />
            <div className="card-pad">
              {data.latest_observations.length === 0 ? <EmptyState compact icon={<FlaskConical />} title="No results recorded" description="Upload a lab report — values are extracted automatically." /> : (
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {data.latest_observations.map((o) => (
                    <div key={o.id} className={cn("rounded-lg border p-3", ["high", "low", "abnormal"].includes(o.flag ?? "") && "border-danger/25 bg-danger-soft/40")}>
                      <div className="flex items-center justify-between gap-2"><span className="truncate text-xs font-medium text-muted-foreground">{o.name}</span><FlagBadge flag={o.flag} compact /></div>
                      <div className="mt-1 text-lg font-semibold num">{o.value_num !== null ? fmtNum(o.value_num) : o.value_text} <span className="text-xs font-normal text-muted-foreground">{o.unit}</span></div>
                      <div className="text-[0.7rem] text-muted-foreground">{fmtDate(o.observed_at)}{o.ref_text ? ` · ref ${o.ref_text}` : ""}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Recent encounters" icon={<CalendarClock />} actions={<Button size="sm" variant="ghost" asChild><Link to="../encounters" relative="path">All encounters <ArrowRight /></Link></Button>} />
            <div className="card-pad space-y-3">
              {data.encounters.length === 0 ? <EmptyState compact title="No encounters recorded" /> : data.encounters.map((e) => (
                <div key={e.id} className="flex gap-3">
                  <div className="w-20 shrink-0 text-xs text-muted-foreground"><div className="font-medium text-foreground">{fmtDate(e.started_at, "d MMM")}</div>{fmtDate(e.started_at, "yyyy")}</div>
                  <div className="min-w-0 flex-1 border-l pl-3">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{e.reason ?? "Encounter"}</span><Badge>{titleCase(e.type)}</Badge></div>
                    {e.notes && <p className="mt-1 line-clamp-2 text-[0.8rem] text-muted-foreground">{e.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-[var(--gap)]">
          <Card>
            <CardHeader title="Problems" icon={<HeartPulse />} actions={<Button size="xs" variant="ghost" asChild><Link to="../problems" relative="path">Manage</Link></Button>} />
            <div className="card-pad space-y-2">
              {active.length === 0 ? <p className="text-sm text-muted-foreground">No active problems documented.</p> : active.map((c) => (
                <div key={c.id} className="flex items-start justify-between gap-2 text-sm"><span>{c.name}</span>{c.code && <span className="shrink-0 font-mono text-[0.7rem] text-muted-foreground">{c.code}</span>}</div>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader title="Allergies" icon={<AlertTriangle />} />
            <div className="card-pad space-y-2">
              {data.allergies.length === 0 ? (
                <div className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning-foreground">Not documented — absence of entries is not confirmation of no allergies.</div>
              ) : data.allergies.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-2 text-sm"><div><div className="font-medium">{a.substance}</div>{a.reaction && <div className="text-xs text-muted-foreground">{a.reaction}</div>}</div><Badge tone={SEVERITY_TONE[a.severity]}>{a.severity}</Badge></div>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader title="Active medications" icon={<Pill />} actions={<Button size="xs" variant="ghost" asChild><Link to="../medications" relative="path">Manage</Link></Button>} />
            <div className="card-pad space-y-2.5">
              {meds.length === 0 ? <p className="text-sm text-muted-foreground">No active medications documented.</p> : meds.map((m) => (
                <div key={m.id} className="text-sm"><div className="font-medium">{m.name}</div><div className="text-xs text-muted-foreground">{[m.dose, m.route, m.frequency].filter(Boolean).join(" · ") || "Dose not recorded"}</div></div>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader title="Recent documents" icon={<FileText />} actions={<Button size="xs" variant="ghost" asChild><Link to="../documents" relative="path">All</Link></Button>} />
            <div className="card-pad space-y-2">
              {data.documents.length === 0 ? <p className="text-sm text-muted-foreground">No documents uploaded.</p> : data.documents.map((d) => (
                <Link key={d.id} to={`../documents?doc=${d.id}`} relative="path" className="block rounded-lg px-2 py-1.5 -mx-2 hover:bg-muted">
                  <div className="truncate text-sm font-medium">{d.title}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-1"><DocStatusBadge status={d.status} /><IdentityBadge status={d.identity_status} /><span className="text-[0.7rem] text-muted-foreground">{fmtDate(d.document_date ?? d.created_at)}</span></div>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
