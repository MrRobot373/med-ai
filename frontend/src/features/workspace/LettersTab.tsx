import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, FileText, Plus, Printer, Send, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, Dialog, DialogContent, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, EmptyState, Field, Input, Segmented, Skeleton, SwitchRow, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import { useWorkspace } from "./context";

interface Letter { id: string; kind: Kind; title: string; number: string | null; status: "draft" | "final" | "void"; fields: Record<string, any>; body: string; created_at: string; finalized_at: string | null; void_reason: string | null }
type Kind = "medical_certificate" | "fitness" | "referral" | "visit_summary";
const KINDS: { kind: Kind; label: string; hint: string }[] = [
  { kind: "medical_certificate", label: "Medical certificate", hint: "Rest advised, for work or school" },
  { kind: "fitness", label: "Fitness certificate", hint: "Fit to work, travel or join" },
  { kind: "referral", label: "Referral letter", hint: "To a specialist, with the record filled in" },
  { kind: "visit_summary", label: "Visit summary", hint: "Plain-language copy for the patient" },
];
const STATUS_TONE = { draft: "warning", final: "success", void: "neutral" } as const;

export default function LettersTab() {
  const { patient, canWrite } = useWorkspace();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["letters", patient.id], queryFn: () => api<Letter[]>(`/api/patients/${patient.id}/letters`) });
  const [selected, setSelected] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["letters", patient.id] });
  const create = async (kind: Kind) => {
    try { const l = await api<Letter>(`/api/patients/${patient.id}/letters`, { method: "POST", body: { kind } }); await refresh(); setSelected(l.id); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not start the letter"); }
  };
  const newMenu = canWrite && (
    <DropdownMenu>
      <DropdownMenuTrigger asChild><Button size="sm"><Plus /> New letter</Button></DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        {KINDS.map((k) => <DropdownMenuItem key={k.kind} onSelect={() => create(k.kind)}><span><span className="block font-medium">{k.label}</span><span className="block text-xs text-muted-foreground">{k.hint}</span></span></DropdownMenuItem>)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
  if (isLoading) return <Skeleton className="h-96" />;
  const list = data ?? [];
  if (!list.length) return <Card><EmptyState icon={<FileText />} title="No letters yet" description="Certificates, referral letters and a plain-language visit summary for the patient. Each is numbered, printed on your letterhead and can be verified by scanning its QR code." action={newMenu || undefined} /></Card>;
  const current = list.find((l) => l.id === selected) ?? list[0];
  return (
    <div className="grid gap-[var(--gap)] lg:grid-cols-[300px_1fr]">
      <Card className="h-fit space-y-1 p-2">
        <div className="flex justify-end px-1 pb-1">{newMenu}</div>
        {list.map((l) => (
          <button key={l.id} onClick={() => setSelected(l.id)} className={cn("w-full rounded-xl px-3 py-2.5 text-left transition", l.id === current.id ? "bg-strong text-strong-foreground shadow-card" : "hover:bg-muted")}>
            <div className="flex items-center justify-between gap-2"><span className="text-[0.82rem] font-semibold">{l.title}</span><Badge tone={STATUS_TONE[l.status]}>{l.status === "final" ? "Issued" : l.status === "void" ? "Void" : "Draft"}</Badge></div>
            <div className={cn("mt-0.5 text-[0.72rem]", l.id === current.id ? "text-strong-foreground/75" : "text-muted-foreground")}>{l.number ?? "Not issued"} · {fmtDate(l.finalized_at ?? l.created_at)}</div>
          </button>
        ))}
      </Card>
      <LetterEditor key={current.id + current.status} letter={current} canWrite={canWrite} onChanged={refresh} />
    </div>
  );
}

function LetterEditor({ letter, canWrite, onChanged }: { letter: Letter; canWrite: boolean; onChanged: () => void }) {
  const editable = canWrite && letter.status === "draft";
  const [fields, setFields] = useState<Record<string, any>>(letter.fields);
  const [body, setBody] = useState(letter.body);
  const [busy, setBusy] = useState<string | null>(null);
  const [voidOpen, setVoidOpen] = useState(false);
  const [reason, setReason] = useState("");
  useEffect(() => { setFields(letter.fields); setBody(letter.body); }, [letter]);
  const set = (patch: Record<string, any>) => setFields((f) => ({ ...f, ...patch }));
  const dirtyFields = JSON.stringify(fields) !== JSON.stringify(letter.fields);
  const dirtyBody = body !== letter.body;

  const save = async (): Promise<Letter | null> => {
    try {
      // Changing a date or purpose rewrites the standard wording; only send the text when the doctor changed it.
      const saved = await api<Letter>(`/api/letters/${letter.id}`, { method: "PATCH", body: { fields: dirtyFields ? fields : undefined, body: dirtyBody ? body : undefined } });
      setFields(saved.fields); setBody(saved.body); onChanged();
      return saved;
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not save"); return null; }
  };
  const run = async (name: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(name);
    try { await fn(); toast.success(ok); onChanged(); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(null); }
  };
  const input = (k: string, label: string, props: { type?: string; placeholder?: string; className?: string } = {}) => (
    <Field label={label} className={props.className}><Input type={props.type} disabled={!editable} value={fields[k] ?? ""} placeholder={props.placeholder} onChange={(e) => set({ [k]: e.target.value })} /></Field>
  );
  const area = (k: string, label: string, rows = 3) => <Field label={label}><Textarea rows={rows} disabled={!editable} value={fields[k] ?? ""} onChange={(e) => set({ [k]: e.target.value })} /></Field>;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-[var(--card-pad)] py-3">
        <div><h3 className="text-[0.95rem] font-semibold">{letter.title}</h3><p className="text-xs text-muted-foreground">{letter.number ? `No. ${letter.number}` : "Draft — not numbered until issued"}{letter.status === "void" && ` · Void: ${letter.void_reason}`}</p></div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" className="rounded-full" asChild><a href={`/api/letters/${letter.id}/pdf`} target="_blank" rel="noreferrer"><Printer /> {letter.status === "draft" ? "Preview" : "Print"}</a></Button>
          {editable && <Button size="sm" variant="secondary" loading={busy === "save"} onClick={() => run("save", async () => { await save(); }, "Draft saved")} disabled={!dirtyFields && !dirtyBody}>Save draft</Button>}
          {editable && <Button size="sm" loading={busy === "issue"} onClick={() => run("issue", async () => { if ((dirtyFields || dirtyBody) && !(await save())) throw new ApiError(422, "Fix the problem above first"); await api(`/api/letters/${letter.id}/issue`, { method: "POST" }); }, "Letter issued")}><Send /> Issue</Button>}
          {editable && <Button size="icon-sm" variant="ghost" aria-label="Delete draft" onClick={() => run("del", () => api(`/api/letters/${letter.id}`, { method: "DELETE" }), "Draft deleted")}><Trash2 /></Button>}
          {canWrite && letter.status === "final" && <Button size="sm" variant="ghost" onClick={() => setVoidOpen(true)}><Ban /> Void</Button>}
        </div>
      </div>
      <div className="card-pad space-y-4">
        {letter.kind === "medical_certificate" && (
          <div className="grid gap-4 md:grid-cols-3">
            {input("from_date", "Rest from", { type: "date" })}{input("to_date", "Rest until", { type: "date" })}
            <Field label="Days"><Input disabled value={fields.days ?? ""} /></Field>
            {input("diagnosis", "Diagnosis", { className: "md:col-span-3", placeholder: "Shown only if you turn it on below" })}
            <div className="md:col-span-3"><SwitchRow label="Show the diagnosis on the certificate" description="Off by default — patients are entitled to keep this private" checked={!!fields.show_diagnosis} disabled={!editable} onCheckedChange={(v) => set({ show_diagnosis: v })} /></div>
          </div>
        )}
        {letter.kind === "fitness" && <div className="grid gap-4 md:grid-cols-2">{input("purpose", "Fit to", { placeholder: "e.g. resume work, travel, join school" })}{input("examined_on", "Examined on", { type: "date" })}</div>}
        {letter.kind === "referral" && (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">{input("to_name", "Refer to", { placeholder: "Dr. …" })}{input("to_speciality", "Speciality")}{input("to_hospital", "Hospital / clinic")}</div>
            <Field label="Urgency"><Segmented value={fields.urgency ?? "routine"} onChange={(v) => set({ urgency: v })} options={[{ value: "routine", label: "Routine" }, { value: "urgent", label: "Urgent" }]} /></Field>
            {area("reason", "Reason for referral", 2)}
            <div className="grid gap-4 md:grid-cols-2">{area("problems", "Problems (one per line)")}{area("medicines", "Current medicines")}{area("allergies", "Allergies")}{area("investigations", "Investigations done")}</div>
            <p className="text-xs text-muted-foreground">Filled in from the chart as it is now. Edit anything before issuing.</p>
          </div>
        )}
        {letter.kind === "visit_summary" && (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">{area("complaint", "Why you came", 2)}{area("diagnosis", "What we found", 2)}</div>
            {area("advice", "Advice")}
            <div className="grid gap-4 md:grid-cols-2">{input("follow_up", "Come back on", { type: "date" })}</div>
            <div className="rounded-lg border bg-muted/30 p-3 text-sm"><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Medicines (from the issued prescription)</div>{(fields.items ?? []).length ? (fields.items as any[]).map((i, n) => <div key={n}>{i.drug} — {i.dose}, {i.frequency}{i.duration_days ? `, ${i.duration_days} days` : ""}</div>) : <span className="text-muted-foreground">No issued prescription for this visit.</span>}</div>
          </div>
        )}
        <Field label="Letter text" hint={editable && letter.kind !== "referral" && letter.kind !== "visit_summary" ? "Changing the dates or purpose rewrites this wording. Edit it last." : undefined}><Textarea rows={5} disabled={!editable} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
      </div>
      <Dialog open={voidOpen} onOpenChange={setVoidOpen}>
        <DialogContent size="sm" title={`Void ${letter.number}`} description="The number stays on record as void and cannot be reused." footer={<><Button variant="secondary" onClick={() => setVoidOpen(false)}>Cancel</Button><Button disabled={reason.trim().length < 3} onClick={async () => { await run("void", () => api(`/api/letters/${letter.id}/void`, { method: "POST", body: { reason } }), "Letter voided"); setVoidOpen(false); setReason(""); }}>Void letter</Button></>}>
          <Field label="Reason"><Input value={reason} onChange={(e) => setReason(e.target.value)} autoFocus placeholder="e.g. Wrong dates" /></Field>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
