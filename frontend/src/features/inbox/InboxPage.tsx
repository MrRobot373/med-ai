import { useQueryClient } from "@tanstack/react-query";
import { Check, FileCheck2, FileWarning, FlaskConical, Inbox, RotateCw, ShieldAlert, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { useInbox, useMe } from "@/api/hooks";
import type { InboxItem } from "@/api/types";
import { Badge, Button, Card, EmptyState, PageHeader, Segmented, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, fmtRelative } from "@/lib/utils";

const META: Record<InboxItem["type"], { icon: typeof Inbox; label: string; tone: string }> = {
  identity: { icon: ShieldAlert, label: "Identity", tone: "bg-danger-soft text-danger-foreground" },
  ingestion: { icon: FileWarning, label: "Processing", tone: "bg-danger-soft text-danger-foreground" },
  lab: { icon: FlaskConical, label: "Result", tone: "bg-warning-soft text-warning-foreground" },
  review: { icon: FileCheck2, label: "Document", tone: "bg-info-soft text-info-foreground" },
  draft: { icon: Sparkles, label: "AI draft", tone: "bg-primary-soft text-primary-soft-foreground" },
};

function useAct() {
  const qc = useQueryClient();
  return async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      toast.success(msg);
      qc.invalidateQueries({ queryKey: ["inbox"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["patient"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Action failed");
    }
  };
}

export function InboxRow({ item, compact }: { item: InboxItem; compact?: boolean }) {
  const meta = META[item.type];
  const act = useAct();
  const { data: me } = useMe();
  const canWrite = me?.role !== "viewer";
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>, msg: string) => { setBusy(true); await act(fn, msg); setBusy(false); };
  const openTo = item.patient_id
    ? item.type === "lab" ? `/patients/${item.patient_id}/results`
    : item.type === "draft" ? `/patients/${item.patient_id}/tools?run=${item.ref_id}`
    : `/patients/${item.patient_id}/documents?doc=${item.ref_id}`
    : "/library";

  return (
    <div className={cn("group flex items-start gap-3 px-5 transition-colors hover:bg-subtle", compact ? "py-3" : "py-3.5")}>
      <div className={cn("mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg", meta.tone)}><meta.icon className="size-4" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Link to={openTo} className="truncate text-sm font-medium hover:underline">{item.title}</Link>
          {item.priority === "high" && <Badge tone="danger">Urgent</Badge>}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          {item.patient_name && <Link to={`/patients/${item.patient_id}`} className="font-medium text-foreground/80 hover:underline">{item.patient_name}</Link>}
          {item.mrn && <span>{item.mrn}</span>}
          {item.detail && <span className="truncate">· {item.detail}</span>}
          <span>· {fmtRelative(item.at)}</span>
        </div>
      </div>
      {canWrite && !compact && (
        <div className="flex shrink-0 items-center gap-1.5 opacity-90 group-hover:opacity-100">
          {item.type === "lab" && <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => api(`/api/patients/${item.patient_id}/observations/${item.ref_id}/acknowledge`, { method: "POST" }), "Result acknowledged")}><Check /> Acknowledge</Button>}
          {item.type === "review" && <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => api(`/api/documents/${item.ref_id}`, { method: "PATCH", body: { review_status: "reviewed" } }), "Marked as reviewed")}><Check /> Mark reviewed</Button>}
          {item.type === "ingestion" && <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => api(`/api/documents/${item.ref_id}/reprocess`, { method: "POST" }), "Re-processing started")}><RotateCw /> Retry</Button>}
          <Button size="sm" variant="ghost" asChild><Link to={openTo}>Open</Link></Button>
        </div>
      )}
    </div>
  );
}

type Filter = "all" | "urgent" | "lab" | "review" | "draft";

export default function InboxPage() {
  const { data, isLoading } = useInbox();
  const [filter, setFilter] = useState<Filter>("all");
  const items = useMemo(() => {
    const all = data ?? [];
    if (filter === "urgent") return all.filter((i) => i.priority === "high");
    if (filter === "all") return all;
    return all.filter((i) => i.type === filter);
  }, [data, filter]);
  const count = (f: Filter) => (data ?? []).filter((i) => (f === "urgent" ? i.priority === "high" : f === "all" ? true : i.type === f)).length;

  return (
    <div>
      <PageHeader title="Inbox" description="Everything that needs a clinician's decision: suspected wrong-patient documents, abnormal results, new reports and AI drafts." />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
          <Segmented<Filter>
            value={filter} onChange={setFilter}
            options={[
              { value: "all", label: <>All <span className="text-muted-foreground num">{count("all")}</span></> },
              { value: "urgent", label: <>Urgent <span className="text-muted-foreground num">{count("urgent")}</span></> },
              { value: "lab", label: <>Results <span className="text-muted-foreground num">{count("lab")}</span></> },
              { value: "review", label: <>Documents <span className="text-muted-foreground num">{count("review")}</span></> },
              { value: "draft", label: <>AI drafts <span className="text-muted-foreground num">{count("draft")}</span></> },
            ]}
          />
          <span className="text-xs text-muted-foreground">Sorted by priority, then most recent</span>
        </div>
        <div className="divide-y">
          {isLoading ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="px-5 py-4"><Skeleton className="h-10" /></div>)
            : items.length === 0 ? <EmptyState icon={<Inbox />} title="Nothing here" description="You're all caught up for this filter." />
            : items.map((item) => <InboxRow key={item.id} item={item} />)}
        </div>
      </Card>
    </div>
  );
}
