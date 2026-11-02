import { useQueryClient } from "@tanstack/react-query";
import { Check, FileSearch, FlaskConical, HeartPulse, Plus, ScanLine, Sparkles, TestTubes, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import type { CopilotRun, Order, ResultReviewOutput } from "@/api/types";
import { Badge, Button, EmptyState, Input, Segmented, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import { Bullets, MiniHeading, RunError, RunMeta } from "./parts";

export const QUICK_TESTS = ["CBC", "KFT", "LFT", "HbA1c", "Lipid profile", "TSH", "Urine routine", "USG abdomen", "X-ray chest", "ECG"];
const CAT_ICON = { lab: TestTubes, radiology: ScanLine, cardiology: HeartPulse, other: FlaskConical };
const STATUS = {
  ordered: { label: "Awaiting result", tone: "neutral" },
  result_received: { label: "Result back — review", tone: "warning" },
  reviewed: { label: "Reviewed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "outline" },
} as const;

export function OrderForm({ patientId, encounterId, onDone }: { patientId: string; encounterId?: string | null; onDone?: () => void }) {
  const qc = useQueryClient();
  const [test, setTest] = useState("");
  const [reason, setReason] = useState("");
  const [urgency, setUrgency] = useState<"routine" | "urgent">("routine");
  const [busy, setBusy] = useState(false);
  const submit = async (name = test) => {
    if (name.trim().length < 2) return;
    setBusy(true);
    try {
      await api(`/api/patients/${patientId}/orders`, { method: "POST", body: { test_name: name.trim(), reason: reason || null, urgency, encounter_id: encounterId ?? null } });
      toast.success(`Ordered ${name}`, { description: "When the report is uploaded it is matched to this order automatically." });
      setTest("");
      qc.invalidateQueries({ queryKey: ["patient", patientId] });
      qc.invalidateQueries({ queryKey: ["consultation"] });
      onDone?.();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not order");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-1.5">
        {QUICK_TESTS.map((t) => <button key={t} type="button" onClick={() => setTest(t)} className={cn("rounded-full border px-2.5 py-1 text-[0.72rem] font-medium transition", test === t ? "border-strong bg-strong text-strong-foreground" : "text-muted-foreground hover:border-primary/40 hover:text-foreground")}>{t}</button>)}
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
        <Input value={test} onChange={(e) => setTest(e.target.value)} placeholder="Test or scan — e.g. USG abdomen, MRI lumbar spine" onKeyDown={(e) => e.key === "Enter" && submit()} />
        <Segmented value={urgency} onChange={setUrgency} options={[{ value: "routine", label: "Routine" }, { value: "urgent", label: "Urgent" }]} />
      </div>
      <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What should it answer? e.g. exclude gallstones — the AI reads the report against this" />
      <Button size="sm" variant="strong" className="rounded-full" disabled={test.trim().length < 2} loading={busy} onClick={() => submit()}><Plus /> Order</Button>
    </div>
  );
}

export function OrderRow({ order, canWrite, canAI }: { order: Order; canWrite: boolean; canAI: boolean }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"ai" | "review" | "cancel" | null>(null);
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(order.status === "result_received");
  const Icon = CAT_ICON[order.category] ?? FlaskConical;
  const st = STATUS[order.status];
  const ai = order.ai_review;
  const out = ai?.status === "draft" ? ai.output : null;
  const refresh = () => { qc.invalidateQueries({ queryKey: ["patient", order.patient_id] }); qc.invalidateQueries({ queryKey: ["consultation"] }); qc.invalidateQueries({ queryKey: ["inbox"] }); };
  const act = async (kind: "ai" | "review" | "cancel") => {
    setBusy(kind);
    try {
      if (kind === "ai") {
        const r = await api<CopilotRun<ResultReviewOutput>>(`/api/orders/${order.id}/ai-review`, { method: "POST" });
        if (r.status === "error") toast.error(r.error ?? "Review failed");
      } else if (kind === "review") {
        await api(`/api/orders/${order.id}/reviewed`, { method: "POST", body: { note: note || null } });
        toast.success("Marked as reviewed");
      } else {
        await api(`/api/orders/${order.id}`, { method: "PATCH", body: { status: "cancelled" } });
      }
      refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={cn("rounded-xl border bg-card/70 p-3", order.status === "result_received" ? "border-warning/40" : "border-border/70")}>
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-foreground"><Icon className="size-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[0.88rem] font-semibold">{order.test_name}</span>
            <Badge tone={st.tone}>{st.label}</Badge>
            {order.urgency === "urgent" && <Badge tone="danger">Urgent</Badge>}
          </div>
          <div className="mt-0.5 text-[0.72rem] text-muted-foreground">Ordered {fmtDate(order.ordered_at)}{order.result_at ? ` · result ${fmtDate(order.result_at)}` : ""}{order.reason ? ` · ${order.reason}` : ""}</div>
          {order.result_document && (
            <Link to={`/patients/${order.patient_id}/documents?doc=${order.result_document.id}`} className="mt-1.5 inline-flex items-center gap-1 text-[0.78rem] font-medium text-primary hover:underline"><FileSearch className="size-3.5" /> {order.result_document.title}</Link>
          )}
          {order.review_note && <p className="mt-1 text-[0.76rem]"><b>Doctor's note:</b> {order.review_note}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {order.result_document && (out || order.status === "result_received") && <Button size="xs" variant="ghost" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Details"}</Button>}
          {canWrite && order.status === "ordered" && <Button size="icon-xs" variant="ghost" aria-label="Cancel order" loading={busy === "cancel"} onClick={() => act("cancel")}><X /></Button>}
        </div>
      </div>
      {open && order.result_document && (
        <div className="mt-3 space-y-3 border-t pt-3">
          <RunError run={ai} />
          {out ? (
            <div className="space-y-2 rounded-xl border border-primary/20 bg-primary-soft/30 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge tone={out.urgency === "urgent" ? "danger" : out.urgency === "soon" ? "warning" : "success"} className="capitalize"><Sparkles /> {out.urgency}</Badge>
                <RunMeta run={ai} onRerun={canAI ? () => act("ai") : undefined} busy={busy === "ai"} />
              </div>
              <p className="text-[0.82rem] font-medium">{out.answers_question}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {!!out.key_findings.length && <div><MiniHeading>Key findings</MiniHeading><Bullets items={out.key_findings} /></div>}
                {!!out.next_steps.length && <div><MiniHeading>Next steps to consider</MiniHeading><Bullets items={out.next_steps} /></div>}
              </div>
              {!!out.abnormal.length && <div><MiniHeading>Abnormal</MiniHeading><Bullets items={out.abnormal.map((a) => `${a.finding} — ${a.significance}`)} /></div>}
              {out.change_from_previous && <p className="text-[0.78rem]"><b>Compared with previous:</b> {out.change_from_previous}</p>}
              {out.patient_explanation && <p className="rounded-lg bg-card/80 px-2.5 py-1.5 text-[0.76rem] text-muted-foreground"><b className="text-foreground">For the patient:</b> {out.patient_explanation}</p>}
            </div>
          ) : canAI && order.result_document.status === "ready" ? (
            <Button size="sm" variant="soft" className="rounded-full" loading={busy === "ai"} onClick={() => act("ai")}><Sparkles /> Read report against the question</Button>
          ) : null}
          {canWrite && order.status === "result_received" && (
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your note — kept with the result for future visits" />
              <Button size="sm" variant="strong" className="shrink-0 rounded-full" loading={busy === "review"} onClick={() => act("review")}><Check /> Mark reviewed</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function OrderList({ orders, canWrite, canAI, empty }: { orders: Order[]; canWrite: boolean; canAI: boolean; empty?: string }) {
  if (!orders.length) return <EmptyState compact icon={<FlaskConical />} title={empty ?? "No investigations ordered"} />;
  return <div className="space-y-2">{orders.map((o) => <OrderRow key={o.id} order={o} canWrite={canWrite} canAI={canAI} />)}</div>;
}
