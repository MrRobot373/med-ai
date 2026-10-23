import { useQueryClient } from "@tanstack/react-query";
import {
  Activity, ArrowRight, ArrowUpRight, CalendarClock, ChevronLeft, ChevronRight, ClipboardCheck, FlaskConical, Gauge, HeartPulse,
  Inbox, ListChecks, Pill, RefreshCw, ShieldAlert, Sparkles, TrendingDown, TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { useInvalidatePatient, useOverview, usePatientDocuments, useScores, useTrends } from "@/api/hooks";
import type { AIRun, ClinicalScore, TrendSeries } from "@/api/types";
import { Badge, Button, Card, CardHeader, EmptyState, Popover, PopoverContent, PopoverTrigger, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { LevelBar, RangeBar, rangeStatus } from "@/components/clinical/RangeBar";
import { InsightCard, ReportViewer } from "@/components/clinical/ReportViewer";
import { PlanItem, Stack } from "@/components/clinical/DashboardParts";
import { ToolRunCard } from "@/components/clinical/ToolOutput";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, fmtNum, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

const TONE_TEXT = { danger: "text-danger-foreground", warning: "text-warning-foreground", success: "text-success-foreground", neutral: "text-muted-foreground" };

/* ---------- Score header (reference: "Cardiovascular System · Risk score") ---------- */
function ScoreHeader({ scores, abnormal, total }: { scores: ClinicalScore[]; abnormal: number; total: number }) {
  const [i, setI] = useState(0);
  const s = scores[i];
  if (!s) {
    return (
      <Card className="card-pad">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-full bg-primary-soft text-primary-soft-foreground ring-1 ring-primary/10"><Activity className="size-5" /></span>
          <div className="flex-1"><div className="text-lg font-semibold tracking-tight">Clinical snapshot</div><div className="text-xs text-muted-foreground">No condition-specific scores apply to this patient's documented data</div></div>
          <div className="w-40 text-right">
            <div className="text-xs text-muted-foreground">Outside stated range</div>
            <div className="text-sm font-semibold num">{abnormal} of {total} markers</div>
            <div className="mt-1 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-danger" style={{ width: `${total ? (abnormal / total) * 100 : 0}%` }} /></div>
          </div>
        </div>
      </Card>
    );
  }
  const tone = s.level >= s.levels.length - 1 ? "text-danger-foreground" : s.level > 0 ? "text-warning-foreground" : "text-success-foreground";
  return (
    <Card className="card-pad">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-full bg-primary-soft text-primary-soft-foreground ring-1 ring-primary/10">{s.kind === "check" ? <ShieldAlert className="size-5" /> : <Gauge className="size-5" />}</span>
        <div className="min-w-[12rem] flex-1">
          <div className="text-lg font-semibold leading-tight tracking-tight">{s.name}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            <span>{s.summary}</span>
            <Popover>
              <PopoverTrigger asChild><button className="font-medium text-primary hover:underline">How it's calculated</button></PopoverTrigger>
              <PopoverContent align="start" className="w-96">
                <div className="text-sm font-semibold">{s.name}: {s.value}</div>
                <p className="mt-1 text-xs text-muted-foreground">{s.summary}</p>
                <div className="mt-3 space-y-1.5">{s.inputs.map((x, k) => <div key={k} className="flex justify-between gap-3 text-xs"><span>{x.label}</span><span className="text-right text-muted-foreground">{x.value} · {x.source}{x.date ? `, ${fmtDate(x.date)}` : ""}</span></div>)}</div>
                {s.missing.length > 0 && <div className="mt-3 rounded-md bg-warning-soft px-2 py-1.5 text-xs text-warning-foreground">Not documented: {s.missing.join(", ")}</div>}
                {s.note && <p className="mt-2 text-xs text-muted-foreground">{s.note}</p>}
                <p className="mt-2 text-[0.7rem] italic text-muted-foreground">{s.reference}</p>
              </PopoverContent>
            </Popover>
          </div>
        </div>
        <div className="w-full sm:w-72">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-muted-foreground">{s.kind === "check" ? "Check" : "Score"} <span className="ml-1 font-semibold text-foreground num">{s.value}</span></span>
            <span className={cn("truncate text-xs font-semibold", tone)} title={s.category}>{s.category}</span>
          </div>
          <LevelBar level={s.level} levels={s.levels} className="mt-1.5" />
        </div>
        {scores.length > 1 && (
          <div className="flex items-center gap-1">
            <Button size="icon-xs" variant="ghost" onClick={() => setI((i - 1 + scores.length) % scores.length)} aria-label="Previous score"><ChevronLeft /></Button>
            <span className="text-[0.7rem] text-muted-foreground num">{i + 1}/{scores.length}</span>
            <Button size="icon-xs" variant="ghost" onClick={() => setI((i + 1) % scores.length)} aria-label="Next score"><ChevronRight /></Button>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ---------- Now vs previous (reference: "Heart age vs chronological age") ---------- */
function pickChange(series: TrendSeries[]) {
  const candidates = series.filter((s) => s.change !== null && s.points.filter((p) => p.value !== null).length >= 2);
  const rel = (s: TrendSeries) => {
    const nums = s.points.filter((p) => p.value !== null);
    const prev = nums[nums.length - 2].value!;
    return Math.abs(s.change! / (prev || 1)) * (s.abnormal ? 2 : 1);
  };
  return candidates.sort((a, b) => rel(b) - rel(a))[0] ?? null;
}

function ChangeCards({ s, onOpen }: { s: TrendSeries; onOpen: (docId: string) => void }) {
  const nums = s.points.filter((p) => p.value !== null);
  const now = nums[nums.length - 1];
  const prev = nums[nums.length - 2];
  const up = (s.change ?? 0) > 0;
  const max = Math.max(now.value!, prev.value!) || 1;
  const nowStatus = rangeStatus(now.value, now.ref_low, now.ref_high);
  return (
    <div className="grid gap-[var(--gap)] sm:grid-cols-[1.25fr_1fr]">
      <Card className="card-pad">
        <div className="mb-2 truncate text-xs font-medium text-muted-foreground">{s.name}</div>
        <div className="flex items-center gap-4">
          <div className="flex items-end gap-3">
            <Stack filled={Math.max(1, Math.round((now.value! / max) * 6))} tone={nowStatus.tone === "neutral" || nowStatus.tone === "success" ? "muted" : "danger"} />
            <div>
              <div className="text-xs text-muted-foreground">Now</div>
              <div className="text-3xl font-semibold tracking-tight num">{fmtNum(now.value)}<span className="ml-1 text-xs font-normal text-muted-foreground">{s.unit}</span></div>
            </div>
          </div>
          <ChevronRight className="size-5 shrink-0 text-muted-foreground/50" />
          <div className="flex items-end gap-3">
            <Stack filled={Math.max(1, Math.round((prev.value! / max) * 6))} tone="muted" />
            <div>
              <div className="whitespace-nowrap text-xs text-muted-foreground">Previous · {fmtDate(prev.at, "d MMM yy")}</div>
              <div className="text-3xl font-semibold tracking-tight text-muted-foreground num">{fmtNum(prev.value)}<span className="ml-1 text-xs font-normal">{s.unit}</span></div>
            </div>
          </div>
        </div>
      </Card>
      <Card className="flex flex-col justify-between gap-3 card-pad">
        <p className="text-[0.85rem] leading-snug text-muted-foreground">
          {s.name} has <span className={cn("font-semibold", up ? "text-danger-foreground" : "text-info-foreground")}>{up ? "risen" : "fallen"} by {fmtNum(Math.abs(s.change!))} {s.unit}</span> since {fmtDate(prev.at)} — currently <span className={cn("font-medium", TONE_TEXT[nowStatus.tone])}>{nowStatus.label.toLowerCase()}</span>.
        </p>
        {now.document_id && <Button variant="strong" size="sm" className="w-fit rounded-full" onClick={() => onOpen(now.document_id!)}>View full report <ArrowUpRight /></Button>}
      </Card>
    </div>
  );
}

/* ---------- Key areas of concern ---------- */
function ConcernTile({ s }: { s: TrendSeries }) {
  const p = s.latest;
  const st = rangeStatus(p.value, p.ref_low, p.ref_high);
  return (
    <Link to="../results" relative="path" className="group rounded-xl border border-border/70 bg-card/80 p-3 transition hover:border-primary/40 hover:shadow-card">
      <div className="flex items-center justify-between text-[0.8rem] font-medium">{s.name}<ChevronRight className="size-3.5 text-muted-foreground transition group-hover:translate-x-0.5" /></div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <span className="text-xl font-semibold num">{p.value !== null ? fmtNum(p.value) : p.text}<span className="ml-1 text-[0.7rem] font-normal text-muted-foreground">{s.unit}</span></span>
        <span className={cn("flex items-center gap-1 text-[0.7rem] font-medium", TONE_TEXT[st.tone])}>{s.trend === "up" ? <TrendingUp className="size-3" /> : s.trend === "down" ? <TrendingDown className="size-3" /> : null}{st.label}</span>
      </div>
      <RangeBar value={p.value} low={p.ref_low} high={p.ref_high} className="mt-2" />
    </Link>
  );
}

export default function OverviewTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = useOverview(patient.id);
  const { data: trends } = useTrends(patient.id);
  const { data: scores } = useScores(patient.id);
  const { data: docs } = usePatientDocuments(patient.id);
  const invalidate = useInvalidatePatient();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [docId, setDocId] = useState<string | null>(null);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [running, setRunning] = useState(false);
  const [fresh, setFresh] = useState<AIRun | null>(null);

  const viewerDocs = useMemo(() => (docs ?? []).filter((d) => d.status !== "failed"), [docs]);
  useEffect(() => {
    if (!docId && viewerDocs.length) {
      const imaging = viewerDocs.find((d) => ["imaging", "ecg"].includes(d.kind) && d.identity_status !== "mismatch");
      setDocId((imaging ?? viewerDocs.find((d) => d.identity_status !== "mismatch") ?? viewerDocs[0]).id);
    }
  }, [viewerDocs, docId]);

  if (isLoading || !data) return <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]"><Skeleton className="h-[640px] rounded-3xl" /><div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-32" /><Skeleton className="h-64" /></div></div>;

  const series = trends ?? [];
  const concerns = series.filter((s) => s.abnormal).slice(0, 3);
  const change = pickChange(series);
  const abnormal = series.filter((s) => s.abnormal).length;
  const findings = data.alerts.filter((a) => a.type !== "gap").length + data.documents.filter((d) => d.review_status === "pending" && d.status === "ready").length;
  const meds = data.medications.filter((m) => m.status === "active");
  const problems = data.conditions.filter((c) => ["active", "suspected"].includes(c.status));
  const checks = (scores ?? []).filter((s) => s.level > 0 || s.kind === "score");
  const summary = fresh?.output ?? data.summary?.output;
  const actions: { title: string; text?: string; tone: "danger" | "warning" | "primary" }[] = [
    ...(scores ?? []).filter((s) => s.kind === "check" && s.level >= 2).map((s) => ({ title: s.name, text: s.category, tone: "danger" as const })),
    ...((summary?.follow_up_considerations as string[] | undefined) ?? []).map((t) => ({ title: "Follow-up", text: t, tone: "primary" as const })),
    ...((summary?.missing_information as string[] | undefined) ?? []).map((t) => ({ title: "Missing information", text: t, tone: "warning" as const })),
  ];

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

  return (
    <div className="space-y-[var(--gap)]">
      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.08fr_1fr]">
        <ReportViewer
          className="h-[calc(100vh-220px)] min-h-[560px] min-w-0 xl:sticky xl:top-[88px]"
          documents={viewerDocs}
          selectedId={docId}
          onSelect={setDocId}
          onDetails={setDetailsId}
          emptyAction={canWrite && <Button size="sm" variant="strong" className="rounded-full" onClick={() => navigate("../documents", { relative: "path" })}>Upload reports</Button>}
          overlay={!dismissed && findings > 0 && (
            <InsightCard
              count={findings} title={findings === 1 ? "New finding" : "New findings"} icon={<Sparkles className="size-4" />}
              text="Abnormal results, new reports or document checks waiting for your review."
              onDismiss={() => setDismissed(true)}
              primary={<>
                <button onClick={() => navigate("/inbox")} className="flex w-full items-center justify-between rounded-xl bg-sky-200/90 px-3 py-2 text-[0.8rem] font-medium text-slate-900 hover:bg-sky-100">Review in inbox <Inbox className="size-4" /></button>
                <button onClick={() => setDismissed(true)} className="flex w-full items-center justify-between rounded-xl bg-white/10 px-3 py-2 text-[0.8rem] font-medium text-white/80 hover:bg-white/15">Dismiss <span>×</span></button>
              </>}
            />
          )}
        />

        <div className="min-w-0 space-y-[var(--gap)]">
          <ScoreHeader scores={scores ?? []} abnormal={abnormal} total={series.length} />
          {change && <ChangeCards s={change} onOpen={(id) => setDocId(id)} />}

          <Card>
            <CardHeader title="Key areas of concern" description="Latest values outside the range stated by the source" actions={<Button size="icon-sm" variant="secondary" className="rounded-full" asChild><Link to="../results" relative="path" aria-label="All results"><ArrowUpRight /></Link></Button>} />
            <div className="card-pad">
              {concerns.length === 0 ? <EmptyState compact icon={<FlaskConical />} title={series.length ? "No results outside stated ranges" : "No results recorded"} description={series.length ? "Every latest value is within the range given by its source." : "Upload a lab report — values are extracted automatically."} /> : (
                <div className="grid gap-2.5 sm:grid-cols-3">{concerns.map((s) => <ConcernTile key={s.code} s={s} />)}</div>
              )}
            </div>
          </Card>

          <Card>
            <Tabs key={actions.length ? "plan" : "meds"} defaultValue={actions.length ? "plan" : "meds"}>
              <div className="flex flex-wrap items-center justify-between gap-3 px-[var(--card-pad)] pt-[var(--card-pad)]">
                <h3 className="text-[0.95rem] font-semibold tracking-tight">Care overview</h3>
                <TabsList>
                  <TabsTrigger value="plan"><ListChecks /> Action plan {actions.length > 0 && <span className="rounded-full bg-strong px-1.5 text-[0.65rem] text-strong-foreground num">{actions.length}</span>}</TabsTrigger>
                  <TabsTrigger value="meds"><Pill /> Medications <span className="text-muted-foreground num">{meds.length}</span></TabsTrigger>
                  <TabsTrigger value="scores"><Gauge /> Scores <span className="text-muted-foreground num">{checks.length}</span></TabsTrigger>
                  <TabsTrigger value="problems"><HeartPulse /> Problems</TabsTrigger>
                </TabsList>
              </div>
              <div className="card-pad">
                <TabsContent value="plan" className="mt-0">
                  {actions.length === 0 ? <EmptyState compact icon={<ClipboardCheck />} title="No action items" description="Generate the AI case summary below to draft follow-ups and gaps." /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{actions.slice(0, 8).map((a, k) => <PlanItem key={k} icon={a.tone === "danger" ? <ShieldAlert /> : a.tone === "warning" ? <ClipboardCheck /> : <CalendarClock />} title={a.title} text={a.text} tone={a.tone} />)}</div>
                  )}
                </TabsContent>
                <TabsContent value="meds" className="mt-0">
                  {meds.length === 0 ? <EmptyState compact icon={<Pill />} title="No active medications documented" /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{meds.map((m) => <PlanItem key={m.id} icon={<Pill />} title={`${m.name}${m.dose ? ` ${m.dose}` : ""}`} text={[m.route, m.frequency, m.indication && `for ${m.indication}`].filter(Boolean).join(" · ")} />)}</div>
                  )}
                </TabsContent>
                <TabsContent value="scores" className="mt-0">
                  {!scores?.length ? <EmptyState compact icon={<Gauge />} title="No applicable scores" description="Scores appear when the chart documents the conditions and values they need." /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{scores.map((s) => <PlanItem key={s.id} icon={s.kind === "check" ? <ShieldAlert /> : <Gauge />} title={`${s.name}: ${s.value}`} text={s.category} tone={s.level >= s.levels.length - 1 ? "danger" : s.level > 0 ? "warning" : "success"} />)}</div>
                  )}
                </TabsContent>
                <TabsContent value="problems" className="mt-0">
                  {problems.length === 0 ? <EmptyState compact icon={<HeartPulse />} title="No active problems documented" /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{problems.map((c) => <PlanItem key={c.id} icon={<HeartPulse />} title={c.name} text={[c.code, c.status !== "active" && titleCase(c.status), c.onset_date && `since ${fmtDate(c.onset_date, "MMM yyyy")}`].filter(Boolean).join(" · ")} tone="warning" />)}</div>
                  )}
                </TabsContent>
              </div>
            </Tabs>
          </Card>
        </div>
      </div>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="AI case summary" icon={<Sparkles />} description={summaryRun ? `Generated ${fmtDate(summaryRun.created_at, "d MMM, HH:mm")} from the chart and documents` : "A concise longitudinal summary with gaps and follow-ups, grounded in this chart."}
            actions={<Button size="sm" variant={summaryRun ? "secondary" : "strong"} className="rounded-full" loading={running} onClick={generate}>{summaryRun ? <><RefreshCw /> Regenerate</> : <><Sparkles /> Generate</>}</Button>} />
          <div className="card-pad">
            {running && !fresh ? <div className="space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-24" /></div>
              : summaryRun ? <ToolRunCard run={summaryRun} canReview={canWrite} compactHeader onChange={(r) => { setFresh(r); qc.invalidateQueries({ queryKey: ["patient", patient.id] }); }} />
              : <EmptyState compact icon={<Sparkles />} title="No summary yet" description="Generate a draft summary. It stays a draft until you accept it." />}
          </div>
        </Card>
        <Card>
          <CardHeader title="Recent encounters" icon={<CalendarClock />} actions={<Button size="sm" variant="ghost" asChild><Link to="../encounters" relative="path">All <ArrowRight /></Link></Button>} />
          <div className="card-pad space-y-3">
            {data.encounters.length === 0 ? <EmptyState compact title="No encounters recorded" /> : data.encounters.map((e) => (
              <div key={e.id} className="flex gap-3">
                <div className="w-14 shrink-0 rounded-xl bg-muted/70 py-1.5 text-center"><div className="text-sm font-semibold leading-none">{fmtDate(e.started_at, "d")}</div><div className="text-[0.65rem] uppercase text-muted-foreground">{fmtDate(e.started_at, "MMM yy")}</div></div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{e.reason ?? "Encounter"}</span><Badge>{titleCase(e.type)}</Badge></div>
                  {e.notes && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{e.notes}</p>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <DocumentDrawer docId={detailsId} onClose={() => setDetailsId(null)} canWrite={canWrite} />
    </div>
  );
}
