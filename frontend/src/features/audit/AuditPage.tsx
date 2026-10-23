import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Download, MessageSquareWarning, ScrollText, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { Fragment, useState } from "react";
import { Navigate } from "react-router";
import { useMe } from "@/api/hooks";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Skeleton, Table, TBody, TD, TH, THead, TR, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, fmtDateTime, fmtRelative } from "@/lib/utils";

interface AuditRow { id: number; at: string; user_email: string | null; action: string; entity_type: string | null; entity_id: string | null; patient_id: string | null; summary: string; details: Record<string, any>; ip: string | null; outcome: string }

const ACTION_TONE = (a: string) => (a.startsWith("auth") ? "info" : a.startsWith("ai") || a.startsWith("research") ? "primary" : a.startsWith("settings") || a.startsWith("user") ? "warning" : a.includes("delete") ? "danger" : "neutral") as any;

function AuditLog() {
  const [q, setQ] = useState("");
  const [action, setAction] = useState("all");
  const [user, setUser] = useState("all");
  const [outcome, setOutcome] = useState("all");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const params = { q: q || undefined, action: action === "all" ? undefined : action, user_email: user === "all" ? undefined : user, outcome: outcome === "all" ? undefined : outcome };
  const { data, isLoading } = useQuery({ queryKey: ["audit", params, page], queryFn: () => api<{ total: number; items: AuditRow[] }>("/api/audit", { query: { ...params, page, page_size: 50 } }) });
  const { data: facets } = useQuery({ queryKey: ["audit-facets"], queryFn: () => api<{ actions: string[]; users: string[] }>("/api/audit/facets") });
  const groups = Array.from(new Set((facets?.actions ?? []).map((a) => a.split(".")[0])));
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / 50));
  const exportUrl = `/api/audit/export.csv?${new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString()}`;

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
        <Input icon={<Search />} placeholder="Search summary or user…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className="max-w-xs" />
        <Select size="sm" className="w-40" value={action} onValueChange={(v) => { setAction(v); setPage(1); }} options={[{ value: "all", label: "All actions" }, ...groups.map((g) => ({ value: g, label: g }))]} />
        <Select size="sm" className="w-52" value={user} onValueChange={(v) => { setUser(v); setPage(1); }} options={[{ value: "all", label: "All users" }, ...(facets?.users ?? []).map((u) => ({ value: u, label: u }))]} />
        <Select size="sm" className="w-36" value={outcome} onValueChange={(v) => { setOutcome(v); setPage(1); }} options={[{ value: "all", label: "Any outcome" }, { value: "success", label: "Success" }, { value: "failure", label: "Failure" }]} />
        <Button size="sm" variant="secondary" className="ml-auto" asChild><a href={exportUrl}><Download /> Export CSV</a></Button>
      </div>
      {isLoading ? <div className="space-y-2 p-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div> : !data?.items.length ? <EmptyState icon={<ScrollText />} title="No matching events" /> : (
        <Table>
          <THead><TR><TH>Time</TH><TH>User</TH><TH>Action</TH><TH>Summary</TH><TH /></TR></THead>
          <TBody>
            {data.items.map((r) => (
              <Fragment key={r.id}>
                <TR data-clickable="true" onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <TD className="whitespace-nowrap text-xs text-muted-foreground" title={fmtDateTime(r.at)}>{fmtRelative(r.at)}</TD>
                  <TD className="whitespace-nowrap text-[0.8rem]">{r.user_email ?? <span className="text-muted-foreground">anonymous</span>}</TD>
                  <TD><Badge tone={ACTION_TONE(r.action)} square className="font-mono">{r.action}</Badge>{r.outcome === "failure" && <Badge tone="danger" className="ml-1">failed</Badge>}</TD>
                  <TD className="max-w-xl truncate text-[0.82rem]">{r.summary}</TD>
                  <TD className="text-right"><ChevronDown className={cn("inline size-4 text-muted-foreground transition-transform", open === r.id && "rotate-180")} /></TD>
                </TR>
                {open === r.id && (
                  <tr className="border-b bg-subtle"><td colSpan={5} className="px-4 py-3 text-xs">
                    <div className="grid gap-x-6 gap-y-1 sm:grid-cols-3">
                      <div><span className="text-muted-foreground">Exact time:</span> {fmtDateTime(r.at)}</div>
                      <div><span className="text-muted-foreground">Entity:</span> {r.entity_type ?? "—"} {r.entity_id && <code className="text-[0.7rem]">{r.entity_id}</code>}</div>
                      <div><span className="text-muted-foreground">IP:</span> {r.ip ?? "—"}</div>
                    </div>
                    {Object.keys(r.details ?? {}).length > 0 && <pre className="mt-2 overflow-x-auto rounded-md bg-card p-2 font-mono text-[0.7rem]">{JSON.stringify(r.details, null, 2)}</pre>}
                  </td></tr>
                )}
              </Fragment>
            ))}
          </TBody>
        </Table>
      )}
      <div className="flex items-center justify-between border-t px-4 py-2.5 text-xs text-muted-foreground">
        <span>{data?.total ?? 0} events</span>
        <div className="flex items-center gap-2"><Button size="xs" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button><span>Page {page} of {pages}</span><Button size="xs" variant="secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
      </div>
    </Card>
  );
}

function Feedback() {
  const { data, isLoading } = useQuery({ queryKey: ["feedback"], queryFn: () => api<{ summary: { up: number; down: number }; items: any[] }>("/api/audit/feedback") });
  if (isLoading) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-4">
      <div className="grid gap-[var(--gap)] sm:grid-cols-3">
        <Card className="card-pad"><div className="text-xs text-muted-foreground">Helpful</div><div className="mt-1 flex items-center gap-2 text-2xl font-semibold num"><ThumbsUp className="size-5 text-success" /> {data?.summary.up ?? 0}</div></Card>
        <Card className="card-pad"><div className="text-xs text-muted-foreground">Not helpful</div><div className="mt-1 flex items-center gap-2 text-2xl font-semibold num"><ThumbsDown className="size-5 text-danger" /> {data?.summary.down ?? 0}</div></Card>
        <Card className="card-pad"><div className="text-xs text-muted-foreground">Satisfaction</div><div className="mt-1 text-2xl font-semibold num">{data && data.summary.up + data.summary.down ? `${Math.round((100 * data.summary.up) / (data.summary.up + data.summary.down))}%` : "—"}</div></Card>
      </div>
      <Card className="divide-y">
        {!data?.items.length ? <EmptyState icon={<MessageSquareWarning />} title="No feedback yet" description="Clinicians can rate answers with thumbs up/down in the assistant." /> : data.items.map((f) => (
          <div key={f.id} className="flex gap-3 px-5 py-3">
            {f.rating === "up" ? <ThumbsUp className="mt-0.5 size-4 shrink-0 text-success" /> : <ThumbsDown className="mt-0.5 size-4 shrink-0 text-danger" />}
            <div className="min-w-0 flex-1"><p className="line-clamp-2 text-sm">{f.content}</p>{f.note && <p className="mt-1 text-xs italic text-muted-foreground">“{f.note}”</p>}<div className="mt-1 text-xs text-muted-foreground">{f.model} · {fmtRelative(f.at)}</div></div>
          </div>
        ))}
      </Card>
    </div>
  );
}

export default function AuditPage() {
  const { data: me } = useMe();
  if (me && me.role !== "admin") return <Navigate to="/" replace />;
  return (
    <div>
      <PageHeader title="Audit log" description="A complete trail of sign-ins, chart access, AI usage, document handling and configuration changes." />
      <Tabs defaultValue="log">
        <TabsList className="mb-4"><TabsTrigger value="log"><ScrollText /> Events</TabsTrigger><TabsTrigger value="feedback"><MessageSquareWarning /> Answer feedback</TabsTrigger></TabsList>
        <TabsContent value="log"><AuditLog /></TabsContent>
        <TabsContent value="feedback"><Feedback /></TabsContent>
      </Tabs>
    </div>
  );
}
