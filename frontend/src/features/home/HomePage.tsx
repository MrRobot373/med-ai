import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, ArrowUpRight, CalendarClock, Check, Microscope, ChevronRight, Clock, FileClock, FileWarning, FlaskConical, Inbox, LayoutDashboard, MessagesSquare,
  ShieldAlert, Sparkles, Stethoscope, UserPlus, Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { useDashboard, useHealth, useInbox, useMe } from "@/api/hooks";
import type { AttentionPatient, InboxItem, QueueDocument } from "@/api/types";
import { Avatar, Badge, Button, Card, CardHeader, Dot, EmptyState, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { PlanItem, Stack } from "@/components/clinical/DashboardParts";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { LevelBar, RangeBar, rangeStatus } from "@/components/clinical/RangeBar";
import { InsightCard, ReportViewer } from "@/components/clinical/ReportViewer";
import { ComponentRow, STATUS_TONE } from "@/components/layout/StatusIndicator";
import { api, ApiError } from "@/lib/api";
import { TodayCard } from "@/features/today/TodayCard";
import { canChart } from "@/lib/roles";
import { cn, fmtDate, fmtNum, fmtRelative, greeting, sexLabel } from "@/lib/utils";

const TONE_TEXT = { danger: "text-danger-foreground", warning: "text-warning-foreground", success: "text-success-foreground", neutral: "text-muted-foreground" };
const INBOX_ICON: Record<InboxItem["type"], typeof Inbox> = { identity: ShieldAlert, ingestion: FileWarning, lab: FlaskConical, review: FileClock, draft: Sparkles, result: Microscope, follow_up: CalendarClock };
const INBOX_TONE: Record<InboxItem["priority"], "danger" | "warning" | "primary"> = { high: "danger", medium: "warning", low: "primary" };

function inboxLink(i: InboxItem) {
  if (!i.patient_id) return "/library";
  if (i.type === "lab") return `/patients/${i.patient_id}/results`;
  if (i.type === "draft") return `/patients/${i.patient_id}/tools?run=${i.ref_id}`;
  if (i.type === "result") return `/patients/${i.patient_id}/orders`;
  if (i.type === "follow_up") return `/patients/${i.patient_id}/prescriptions`;
  return `/patients/${i.patient_id}/documents?doc=${i.ref_id}${["identity", "ingestion"].includes(i.type) ? "&details=1" : ""}`;
}

/* Reference "risk score" header → today's workload, from real queue counts */
function WorkloadHeader({ open, urgent, docs, name }: { open: number; urgent: number; docs: number; name: string }) {
  const levels = ["Clear", "Light", "Busy", "Heavy"];
  const level = open === 0 ? 0 : open <= 5 ? 1 : open <= 15 ? 2 : 3;
  const tone = ["text-success-foreground", "text-success-foreground", "text-warning-foreground", "text-danger-foreground"][level];
  return (
    <Card className="card-pad">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-full bg-primary-soft text-primary-soft-foreground ring-1 ring-primary/10"><LayoutDashboard className="size-5" /></span>
        <div className="min-w-[12rem] flex-1">
          <div className="text-lg font-semibold leading-tight tracking-tight">{greeting()}{name ? `, ${name}` : ""}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">{fmtDate(new Date(), "EEEE, d MMMM")} · {open} open items · {urgent} urgent · {docs} documents to review</div>
        </div>
        <div className="w-full sm:w-64">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-muted-foreground">Workload</span>
            <span className={cn("text-xs font-semibold", tone)}>{levels[level]}</span>
          </div>
          <LevelBar level={level} levels={levels} className="mt-1.5" />
        </div>
      </div>
    </Card>
  );
}

function AttentionTile({ p }: { p: AttentionPatient }) {
  const m = p.marker;
  const st = m ? rangeStatus(m.value, m.ref_low, m.ref_high) : null;
  return (
    <Link to={`/patients/${p.id}`} className="group flex flex-col rounded-xl border border-border/70 bg-card/80 p-3 transition hover:border-primary/40 hover:shadow-card">
      <div className="flex items-center gap-2">
        <Avatar name={p.full_name} size="xs" />
        <span className="min-w-0 flex-1 truncate text-[0.82rem] font-semibold">{p.full_name}</span>
        <ChevronRight className="size-3.5 text-muted-foreground transition group-hover:translate-x-0.5" />
      </div>
      <div className="mt-0.5 text-[0.68rem] text-muted-foreground">{p.mrn} · {p.age ?? "—"} y · {sexLabel(p.sex)}</div>
      {m ? (
        <>
          <div className="mt-2 flex items-baseline justify-between gap-2">
            <span className="truncate text-[0.72rem] text-muted-foreground">{m.name}</span>
            <span className={cn("shrink-0 text-[0.68rem] font-medium", TONE_TEXT[st!.tone])}>{st!.label}</span>
          </div>
          <div className="text-lg font-semibold num">{fmtNum(m.value)}<span className="ml-1 text-[0.68rem] font-normal text-muted-foreground">{m.unit}</span></div>
          <RangeBar value={m.value} low={m.ref_low} high={m.ref_high} className="mt-1.5" />
        </>
      ) : p.score ? (
        <div className="mt-2">
          <div className="text-[0.72rem] text-muted-foreground">{p.score.name}</div>
          <div className="text-lg font-semibold num">{p.score.value}</div>
          <LevelBar level={p.score.level} levels={p.score.levels} className="mt-2" />
        </div>
      ) : <div className="mt-2 text-xs text-muted-foreground">No abnormal results</div>}
      <div className="mt-auto flex flex-wrap gap-1 pt-2">
        {p.mismatches > 0 && <Badge tone="danger"><ShieldAlert /> Identity</Badge>}
        {p.abnormal > 0 && <Badge tone="warning">{p.abnormal} abnormal</Badge>}
        {p.pending_documents > 0 && <Badge tone="primary">{p.pending_documents} to review</Badge>}
        {p.score && m && <Badge tone={p.score.level >= p.score.levels.length - 1 ? "danger" : "neutral"} title={p.score.category}>{p.score.name.split(" (")[0]} {p.score.value}</Badge>}
      </div>
    </Link>
  );
}

export default function HomePage() {
  const { data: me } = useMe();
  const { data, isLoading } = useDashboard();
  const { data: inbox } = useInbox();
  const { data: health } = useHealth();
  const queue = useQuery({ queryKey: ["review-queue"], queryFn: () => api<QueueDocument[]>("/api/dashboard/review-queue"), refetchInterval: 30_000 });
  const attention = useQuery({ queryKey: ["attention"], queryFn: () => api<AttentionPatient[]>("/api/dashboard/attention") });
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [docId, setDocId] = useState<string | null>(null);
  const [details, setDetails] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);

  const docs = useMemo(() => queue.data ?? [], [queue.data]);
  useEffect(() => { if ((!docId || !docs.some((d) => d.id === docId)) && docs.length) setDocId(docs[0].id); }, [docs, docId]);

  const s = data?.stats;
  const items = inbox ?? [];
  const urgent = items.filter((i) => i.priority === "high").length;
  const open = items.filter((i) => i.priority !== "low").length;
  const ranked = attention.data ?? [];
  const top = ranked[0];
  const name = me ? (me.title ? `${me.title} ${me.full_name.replace(/^Dr\.?\s+/, "").split(" ").slice(-1)[0]}` : me.full_name.split(" ")[0]) : "";
  const canWrite = canChart(me?.role);

  const markReviewed = async (id: string) => {
    setBusy(true);
    try {
      await api(`/api/documents/${id}`, { method: "PATCH", body: { review_status: "reviewed" } });
      toast.success("Marked as reviewed");
      const next = docs.find((d) => d.id !== id);
      setDocId(next?.id ?? null);
      ["review-queue", "inbox", "dashboard", "attention"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const pill = "flex h-9 items-center gap-1.5 rounded-full bg-white/90 px-3 text-xs font-medium text-slate-700 shadow-float ring-1 ring-black/5 transition hover:bg-white dark:bg-slate-800/90 dark:text-slate-200 dark:ring-white/10";

  return (
    <div className="space-y-[var(--gap)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="text-label">{fmtDate(new Date(), "EEEE, d MMMM yyyy")}</div>
          <h1 className="mt-0.5 text-[1.35rem] font-semibold tracking-tight">Clinical dashboard</h1>
        </div>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          {canWrite && <Button variant="secondary" className="rounded-full" onClick={() => navigate("/patients?new=1")}><UserPlus /> New patient</Button>}
          <Button variant="strong" className="rounded-full" onClick={() => navigate("/assistant?new=1")}><Sparkles /> Ask the assistant</Button>
        </div>
      </div>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.08fr_1fr]">
        <ReportViewer
          className="h-[calc(100vh-170px)] min-h-[560px] min-w-0 xl:sticky xl:top-[88px]"
          documents={docs}
          selectedId={docId}
          onSelect={setDocId}
          onDetails={setDetails}
          emptyTitle="Review queue is clear"
          emptyText="New reports, radiology and ECGs awaiting review across your patients appear here."
          subtitle={(d) => {
            const q = d as QueueDocument;
            return <Link to={`/patients/${q.patient_id}`} className="font-medium underline-offset-2 hover:underline">{q.patient_name} · {q.patient_mrn}</Link>;
          }}
          actions={(d) => (
            <>
              <Link to={`/patients/${d.patient_id}/documents?doc=${d.id}`} className={pill} title="Open chart"><Users className="size-3.5" /><span className="hidden 2xl:inline">Open chart</span></Link>
              {canWrite && d.status === "ready" && <button className={pill} disabled={busy} onClick={() => markReviewed(d.id)} title="Mark as reviewed"><Check className="size-3.5" /><span className="hidden 2xl:inline">Reviewed</span></button>}
            </>
          )}
          overlay={!dismissed && open > 0 && (
            <InsightCard
              count={open} title={open === 1 ? "Item needs attention" : "Items need attention"} icon={<Inbox className="size-4" />}
              text={urgent ? `${urgent} urgent — including suspected wrong-patient documents.` : "Abnormal results, documents and AI drafts waiting for review."}
              onDismiss={() => setDismissed(true)}
              primary={<>
                <button onClick={() => navigate("/inbox")} className="flex w-full items-center justify-between rounded-xl bg-sky-200/90 px-3 py-2 text-[0.8rem] font-medium text-slate-900 hover:bg-sky-100">Open inbox <Inbox className="size-4" /></button>
                <button onClick={() => setDismissed(true)} className="flex w-full items-center justify-between rounded-xl bg-white/10 px-3 py-2 text-[0.8rem] font-medium text-white/80 hover:bg-white/15">Dismiss <span>×</span></button>
              </>}
            />
          )}
        />

        <div className="min-w-0 space-y-[var(--gap)]">
          <WorkloadHeader open={open} urgent={urgent} docs={docs.length} name={name} />
          <TodayCard />

          <div className="grid gap-[var(--gap)] sm:grid-cols-[1.25fr_1fr]">
            <Card className="card-pad">
              <div className="mb-2 text-xs font-medium text-muted-foreground">Abnormal results · unacknowledged</div>
              <div className="flex items-center gap-4">
                <div className="flex items-end gap-3">
                  <Stack filled={Math.min(6, Math.ceil((s?.abnormal_unacknowledged ?? 0) / 5))} tone="danger" />
                  <div><div className="text-xs text-muted-foreground">Results</div><div className="text-3xl font-semibold tracking-tight num">{s?.abnormal_unacknowledged ?? "—"}</div></div>
                </div>
                <ChevronRight className="size-5 shrink-0 text-muted-foreground/50" />
                <div className="flex items-end gap-3">
                  <Stack filled={Math.min(6, ranked.filter((r) => r.abnormal).length)} tone="muted" />
                  <div><div className="text-xs text-muted-foreground">Patients</div><div className="text-3xl font-semibold tracking-tight text-muted-foreground num">{attention.data ? ranked.filter((r) => r.abnormal).length : "—"}<span className="ml-1 text-xs font-normal">of {s?.active_patients ?? "—"}</span></div></div>
                </div>
              </div>
            </Card>
            <Card className="flex flex-col justify-between gap-3 card-pad">
              <p className="text-[0.85rem] leading-snug text-muted-foreground">
                {top ? <>Most urgent: <span className="font-semibold text-foreground">{top.full_name}</span>{top.mismatches ? <> — <span className="font-medium text-danger-foreground">possible wrong-patient document</span></> : top.marker ? <> — {top.marker.name} <span className="font-medium text-danger-foreground">{rangeStatus(top.marker.value, top.marker.ref_low, top.marker.ref_high).label.toLowerCase()}</span></> : null}.</> : "No patient currently needs attention."}
              </p>
              {top && <Button variant="strong" size="sm" className="w-fit rounded-full" onClick={() => navigate(`/patients/${top.id}`)}>Open chart <ArrowUpRight /></Button>}
            </Card>
          </div>

          <Card>
            <CardHeader title="Patients needing attention" description="Ranked by open findings, document checks and applicable scores" actions={<Button size="icon-sm" variant="secondary" className="rounded-full" asChild><Link to="/patients" aria-label="All patients"><ArrowUpRight /></Link></Button>} />
            <div className="card-pad">
              {attention.isLoading ? <Skeleton className="h-36" /> : ranked.length === 0 ? <EmptyState compact icon={<Users />} title="Nothing outstanding" description="No active patient has unacknowledged abnormal results or documents to check." /> : (
                <div className="grid gap-2.5 sm:grid-cols-3">{ranked.slice(0, 6).map((p) => <AttentionTile key={p.id} p={p} />)}</div>
              )}
            </div>
          </Card>

          <Card>
            <Tabs defaultValue="inbox">
              <div className="flex flex-wrap items-center justify-between gap-3 px-[var(--card-pad)] pt-[var(--card-pad)]">
                <h3 className="text-[0.95rem] font-semibold tracking-tight">Work queue</h3>
                <TabsList>
                  <TabsTrigger value="inbox"><Inbox /> Inbox {open > 0 && <span className="rounded-full bg-strong px-1.5 text-[0.65rem] text-strong-foreground num">{open}</span>}</TabsTrigger>
                  <TabsTrigger value="recent"><Clock /> Recent</TabsTrigger>
                  <TabsTrigger value="chats"><MessagesSquare /> Conversations</TabsTrigger>
                  <TabsTrigger value="activity"><Activity /> Activity</TabsTrigger>
                </TabsList>
              </div>
              <div className="card-pad">
                <TabsContent value="inbox" className="mt-0">
                  {!inbox ? <Skeleton className="h-32" /> : items.length === 0 ? <EmptyState compact icon={<Inbox />} title="All caught up" /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      {items.slice(0, 6).map((i) => { const Icon = INBOX_ICON[i.type]; return <Link key={i.id} to={inboxLink(i)} className="transition hover:-translate-y-0.5"><PlanItem icon={<Icon />} title={i.title} text={[i.patient_name, i.detail].filter(Boolean).join(" · ")} tone={INBOX_TONE[i.priority]} /></Link>; })}
                    </div>
                  )}
                  {items.length > 6 && <Button variant="link" size="sm" className="mt-3" asChild><Link to="/inbox">View all {items.length} items</Link></Button>}
                </TabsContent>
                <TabsContent value="recent" className="mt-0">
                  {(data?.recent_patients ?? []).length === 0 ? <EmptyState compact icon={<Users />} title="No recently opened charts" /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{data.recent_patients.map((p: any) => <Link key={p.id} to={`/patients/${p.id}`}><PlanItem icon={<Users />} title={p.full_name} text={`${p.mrn} · opened ${fmtRelative(p.at)}`} /></Link>)}</div>
                  )}
                </TabsContent>
                <TabsContent value="chats" className="mt-0">
                  {(data?.recent_conversations ?? []).length === 0 ? <EmptyState compact icon={<MessagesSquare />} title="No conversations yet" action={<Button size="sm" variant="secondary" asChild><Link to="/assistant?new=1">Start one</Link></Button>} /> : (
                    <div className="grid gap-2.5 sm:grid-cols-2">{data.recent_conversations.map((c: any) => <Link key={c.id} to={`/assistant/${c.id}`}><PlanItem icon={<MessagesSquare />} title={c.title} text={fmtRelative(c.updated_at)} /></Link>)}</div>
                  )}
                </TabsContent>
                <TabsContent value="activity" className="mt-0">
                  {(data?.activity ?? []).length === 0 ? <EmptyState compact title="No activity yet" /> : (
                    <ol className="relative space-y-3 border-l pl-5">
                      {data.activity.slice(0, 8).map((a: any, k: number) => (
                        <li key={k} className="relative"><span className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-strong ring-4 ring-card" /><div className="text-sm">{a.summary}</div><div className="text-xs text-muted-foreground">{a.user ?? "system"} · {fmtRelative(a.at)}</div></li>
                      ))}
                    </ol>
                  )}
                </TabsContent>
              </div>
            </Tabs>
          </Card>
        </div>
      </div>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="Usage" description="Questions, tool runs and documents over the last 14 days" icon={<Activity />} />
          <div className="h-56 px-2 pb-3 pt-4">
            {isLoading ? <Skeleton className="mx-4 h-44" /> : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data?.usage ?? []} margin={{ left: -18, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tickFormatter={(d) => fmtDate(d, "d MMM")} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <ChartTooltip cursor={{ fill: "hsl(var(--muted))" }} contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} labelFormatter={(d) => fmtDate(String(d))} />
                  <Bar dataKey="questions" name="Questions" stackId="a" fill="hsl(var(--strong))" />
                  <Bar dataKey="tools" name="Tool runs" stackId="a" fill="hsl(var(--primary))" />
                  <Bar dataKey="documents" name="Documents" stackId="a" fill="hsl(var(--primary) / 0.35)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="AI services" description="Live status of models and retrieval" icon={<Stethoscope />} actions={health && <Badge tone={STATUS_TONE[health.status]} className="capitalize"><Dot tone={STATUS_TONE[health.status]} /> {health.status}</Badge>} />
          <div className="card-pad pt-2">{health ? health.components.map((c) => <ComponentRow key={c.component} c={c} />) : <Skeleton className="h-40" />}</div>
        </Card>
      </div>
      <DocumentDrawer docId={details} onClose={() => setDetails(null)} canWrite={canWrite} />
    </div>
  );
}
