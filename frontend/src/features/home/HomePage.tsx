import { Activity, ArrowRight, BookOpenText, FileClock, FlaskConical, Inbox, MessagesSquare, Sparkles, Stethoscope, UserPlus, Users } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { useDashboard, useHealth, useInbox, useMe } from "@/api/hooks";
import { Avatar, Badge, Button, Card, CardHeader, Dot, EmptyState, Skeleton } from "@/components/ui";
import { ComponentRow, STATUS_TONE } from "@/components/layout/StatusIndicator";
import { cn, fmtDate, fmtRelative, greeting } from "@/lib/utils";
import { InboxRow } from "@/features/inbox/InboxPage";

function Stat({ label, value, icon: Icon, hint, to, tone = "primary" }: { label: string; value: number | undefined; icon: typeof Users; hint?: string; to?: string; tone?: "primary" | "danger" | "warning" | "success" }) {
  const tones = { primary: "bg-primary-soft text-primary-soft-foreground", danger: "bg-danger-soft text-danger-foreground", warning: "bg-warning-soft text-warning-foreground", success: "bg-success-soft text-success-foreground" };
  const body = (
    <Card className={cn("card-pad group h-full transition-all", to && "hover:-translate-y-0.5 hover:shadow-pop")}>
      <div className="flex items-start justify-between">
        <span className="text-[0.8rem] font-medium text-muted-foreground">{label}</span>
        <span className={cn("flex size-8 items-center justify-center rounded-lg", tones[tone])}><Icon className="size-4" /></span>
      </div>
      <div className="mt-2 text-[1.9rem] font-semibold leading-none tracking-tight num">{value ?? <Skeleton className="h-8 w-12" />}</div>
      {hint && <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">{hint}{to && <ArrowRight className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />}</div>}
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export default function HomePage() {
  const { data: me } = useMe();
  const { data, isLoading } = useDashboard();
  const { data: inbox } = useInbox();
  const { data: health } = useHealth();
  const navigate = useNavigate();
  const s = data?.stats;
  const firstName = me?.full_name.replace(/^Dr\.?\s+/, "").split(" ")[0];

  return (
    <div className="space-y-[var(--gap)]">
      <div className="flex flex-col gap-4 pb-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-label mb-1.5">{fmtDate(new Date(), "EEEE, d MMMM")}</div>
          <h1 className="text-[1.6rem] font-semibold tracking-tight">{greeting()}{me?.title ? `, ${me.title} ${me.full_name.replace(/^Dr\.?\s+/, "").split(" ").slice(-1)[0]}` : firstName ? `, ${firstName}` : ""}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {inbox ? (inbox.filter((i) => i.priority !== "low").length ? `${inbox.filter((i) => i.priority !== "low").length} items need your attention today.` : "Your inbox is clear — nothing urgent needs attention.") : "Loading your day…"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {me?.role !== "viewer" && <Button variant="secondary" onClick={() => navigate("/patients?new=1")}><UserPlus /> New patient</Button>}
          <Button onClick={() => navigate("/assistant?new=1")}><Sparkles /> Ask the assistant</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-[var(--gap)] lg:grid-cols-4">
        <Stat label="Active patients" value={s?.active_patients} icon={Users} hint={`${s?.encounters_today ?? 0} encounters today`} to="/patients" />
        <Stat label="Needs review" value={s ? s.documents_needing_review + s.drafts_pending : undefined} icon={FileClock} hint={`${s?.documents_needing_review ?? 0} documents · ${s?.drafts_pending ?? 0} AI drafts`} to="/inbox" tone="warning" />
        <Stat label="Abnormal results" value={s?.abnormal_unacknowledged} icon={FlaskConical} hint="Unacknowledged, outside stated ranges" to="/inbox" tone="danger" />
        <Stat label="AI activity · 7 days" value={s ? s.questions_7d + s.ai_runs_7d : undefined} icon={Sparkles} hint={`${s?.questions_7d ?? 0} questions · ${s?.ai_runs_7d ?? 0} tool runs`} tone="success" />
      </div>

      <div className="grid gap-[var(--gap)] lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Needs attention" description="Highest-priority items from your clinical inbox" icon={<Inbox />} actions={<Button variant="ghost" size="sm" asChild><Link to="/inbox">Open inbox <ArrowRight /></Link></Button>} />
          <div className="mt-3 divide-y border-t">
            {!inbox ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="px-5 py-3"><Skeleton className="h-10" /></div>)
              : inbox.length === 0 ? <EmptyState compact icon={<Inbox />} title="All caught up" description="New documents, abnormal results and AI drafts will appear here." />
              : inbox.slice(0, 5).map((item) => <InboxRow key={item.id} item={item} compact />)}
          </div>
        </Card>

        <Card>
          <CardHeader title="Recently opened" description="Patients you viewed last" icon={<Users />} />
          <div className="card-pad space-y-1 pt-3">
            {isLoading ? <Skeleton className="h-32" /> : (data?.recent_patients?.length ?? 0) === 0 ? (
              <EmptyState compact icon={<Users />} title="No recent patients" description="Patients you open will show up here." action={<Button size="sm" variant="secondary" asChild><Link to="/patients">Browse patients</Link></Button>} />
            ) : data.recent_patients.map((p: any) => (
              <Link key={p.id} to={`/patients/${p.id}`} className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted">
                <Avatar name={p.full_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{p.full_name}</div>
                  <div className="text-xs text-muted-foreground">{p.mrn}</div>
                </div>
                <span className="text-xs text-muted-foreground">{fmtRelative(p.at)}</span>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-[var(--gap)] lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Usage" description="Questions, tool runs and documents over the last 14 days" icon={<Activity />} />
          <div className="h-60 px-2 pb-3 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.usage ?? []} margin={{ left: -18, right: 8 }}>
                <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tickFormatter={(d) => fmtDate(d, "d MMM")} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                <ChartTooltip cursor={{ fill: "hsl(var(--muted))" }} contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} labelFormatter={(d) => fmtDate(String(d))} />
                <Bar dataKey="questions" name="Questions" stackId="a" fill="hsl(var(--primary))" radius={[0, 0, 0, 0]} />
                <Bar dataKey="tools" name="Tool runs" stackId="a" fill="hsl(var(--primary) / 0.55)" />
                <Bar dataKey="documents" name="Documents" stackId="a" fill="hsl(var(--primary) / 0.25)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="AI services" description="Live status of models and retrieval" icon={<Stethoscope />} actions={health && <Badge tone={STATUS_TONE[health.status]} className="capitalize"><Dot tone={STATUS_TONE[health.status]} /> {health.status}</Badge>} />
          <div className="card-pad pt-2">{health ? health.components.map((c) => <ComponentRow key={c.component} c={c} />) : <Skeleton className="h-40" />}</div>
        </Card>
      </div>

      <div className="grid gap-[var(--gap)] lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recent activity" description="Across the whole team" icon={<Activity />} />
          <div className="card-pad pt-3">
            {(data?.activity ?? []).length === 0 ? <EmptyState compact title="No activity yet" /> : (
              <ol className="relative space-y-3 border-l pl-5">
                {data.activity.map((a: any, i: number) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-primary ring-4 ring-card" />
                    <div className="text-sm">{a.summary}</div>
                    <div className="text-xs text-muted-foreground">{a.user ?? "system"} · {fmtRelative(a.at)}</div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Continue" description="Your latest conversations" icon={<MessagesSquare />} />
          <div className="card-pad space-y-1 pt-3">
            {(data?.recent_conversations ?? []).length === 0 ? (
              <EmptyState compact icon={<MessagesSquare />} title="No conversations yet" action={<Button size="sm" variant="secondary" asChild><Link to="/assistant?new=1">Start one</Link></Button>} />
            ) : data.recent_conversations.map((c: any) => (
              <Link key={c.id} to={`/assistant/${c.id}`} className="flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm hover:bg-muted">
                <MessagesSquare className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{c.title}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">{fmtRelative(c.updated_at)}</span>
              </Link>
            ))}
            <Link to="/library" className="mt-2 flex items-center gap-2.5 rounded-lg border border-dashed px-3 py-2.5 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground">
              <BookOpenText className="size-4" /> {data?.stats?.knowledge_documents ?? 0} documents in the knowledge library
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
