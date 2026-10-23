import { useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Check, FileSignature, Plus, Printer, ShieldAlert, ShieldCheck, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { CheckItem, CheckResult, CopilotRun, Prescription, RxItem, RxReviewOutput, Severity } from "@/api/types";
import { Badge, Button, Card, CardHeader, Dialog, DialogContent, Field, Input, Select, Spinner, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import { MedicineInput, MedicineThumb } from "./MedicineInput";
import { AIEmpty, Bullets, FindingList, MiniHeading, RunError, RunMeta, SEVERITY_META, SeverityBadge } from "./parts";

const FREQUENCIES = ["OD", "BD", "TDS", "QID", "HS", "1-0-1", "1-1-1", "1-0-0", "0-0-1", "SOS", "STAT", "Weekly", "q8h", "q12h"];
const FREQ_HINT: Record<string, string> = { OD: "once daily", BD: "twice daily", TDS: "three times", QID: "four times", HS: "at bedtime", SOS: "as needed", STAT: "single dose" };
const FOLLOW_UPS = [["3 d", 3], ["1 wk", 7], ["2 wk", 14], ["1 mo", 30], ["3 mo", 90]] as const;
const VERDICT_TONE = { appropriate: "success", adjust: "warning", avoid: "danger" } as const;

type Row = RxItem & { key: string };
const newRow = (): Row => ({ key: crypto.randomUUID(), drug: "", dose: "1 tab", frequency: "BD", duration_days: 5, instructions: "" });
const toRows = (items: RxItem[]): Row[] => items.map((i) => ({ ...i, key: i.id ?? crypto.randomUUID(), instructions: i.instructions ?? "" }));
const plusDays = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

export function PrescriptionBuilder({ rx, review, canWrite, onFinalised }: {
  rx: Prescription; review: CopilotRun<RxReviewOutput> | null; canWrite: boolean; onFinalised?: () => void;
}) {
  const qc = useQueryClient();
  const editable = canWrite && rx.status === "draft";
  const [rows, setRows] = useState<Row[]>(() => (rx.items.length ? toRows(rx.items) : [newRow()]));
  const [diagnosis, setDiagnosis] = useState(rx.diagnosis ?? "");
  const [advice, setAdvice] = useState(rx.advice ?? "");
  const [followUp, setFollowUp] = useState(rx.follow_up_date ?? "");
  const [check, setCheck] = useState<CheckResult | null>(rx.check ?? null);
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [reviewing, setReviewing] = useState(false);
  const [finalising, setFinalising] = useState(false);
  const [askReasons, setAskReasons] = useState(false);
  const dirty = useRef(false);

  useEffect(() => { if (rx.status !== "draft") setRows(toRows(rx.items)); }, [rx]);

  const payload = useCallback(() => ({
    diagnosis: diagnosis || null, advice: advice || null, follow_up_date: followUp || null,
    items: rows.filter((r) => r.drug.trim()).map(({ key: _k, checks: _c, id: _i, line: _l, generic: _g, position: _p, ...r }) => ({ ...r, instructions: r.instructions || null })),
  }), [rows, diagnosis, advice, followUp]);

  const save = useCallback(async () => {
    if (!editable) return null;
    setSaving("saving");
    try {
      const saved = await api<Prescription>(`/api/prescriptions/${rx.id}`, { method: "PUT", body: payload() });
      setCheck(saved.check ?? null);
      setSaving("saved");
      dirty.current = false;
      return saved;
    } catch (e) {
      setSaving("idle");
      toast.error(e instanceof ApiError ? e.message : "Could not save the prescription");
      return null;
    }
  }, [editable, payload, rx.id]);

  // Autosave + re-check shortly after typing stops.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; if (editable && rx.items.length) save(); return; }
    dirty.current = true;
    const t = setTimeout(save, 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, diagnosis, advice, followUp]);

  const filled = rows.filter((r) => r.drug.trim());
  const checkFor = (row: Row): CheckItem | undefined => {
    const idx = filled.indexOf(row);
    return idx >= 0 ? check?.items[idx] : undefined;
  };
  const storedFindings = (row: Row) => row.checks ?? [];
  const reviewOut = review?.status === "draft" ? review.output : null;
  const reviewFor = (row: Row) => reviewOut?.items.find((i) => i.index === filled.indexOf(row));
  const criticalRows = filled.filter((r) => (checkFor(r)?.status ?? "ok") === "critical");

  const update = (key: string, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const runReview = async () => {
    setReviewing(true);
    try {
      await save();
      const r = await api<CopilotRun<RxReviewOutput>>(`/api/prescriptions/${rx.id}/review`, { method: "POST" });
      if (r.status === "error") toast.error(r.error ?? "Review failed");
      qc.invalidateQueries({ queryKey: ["consultation"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Review failed");
    } finally {
      setReviewing(false);
    }
  };

  const finalise = async () => {
    if (criticalRows.some((r) => !r.override_reason?.trim())) { setAskReasons(true); return; }
    setFinalising(true);
    try {
      const saved = await save();
      if (!saved) return;
      await api(`/api/prescriptions/${rx.id}/finalize`, { method: "POST", body: { overrides: {} } });
      toast.success("Prescription finalised", { description: "Medicines added to the chart and kept for future visits." });
      setAskReasons(false);
      qc.invalidateQueries({ queryKey: ["consultation"] });
      qc.invalidateQueries({ queryKey: ["patient", rx.patient_id] });
      onFinalised?.();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not finalise");
    } finally {
      setFinalising(false);
    }
  };

  const facts = check?.patient ?? rx.context?.patient;
  const status: Severity = check?.status ?? rx.context?.status ?? "ok";

  return (
    <Card>
      <CardHeader
        icon={<FileSignature />}
        title={rx.status === "final" ? `Prescription · ${fmtDate(rx.finalized_at)}` : "Prescription"}
        description={rx.status === "final" ? "Final — part of the record" : "Every line is checked against this patient as you type"}
        actions={<>
          {editable && <span className="text-[0.7rem] text-muted-foreground">{saving === "saving" ? <span className="flex items-center gap-1"><Spinner className="size-3" /> Checking…</span> : saving === "saved" ? "Saved" : ""}</span>}
          {filled.length > 0 && <SeverityBadge severity={status} label={status === "ok" ? "Checks passed" : `${check?.summary.critical ?? 0} critical · ${check?.summary.warning ?? 0} caution`} />}
          {rx.status === "final" && <Button size="sm" variant="secondary" className="rounded-full" asChild><a href={`/print/prescription/${rx.id}`} target="_blank" rel="noreferrer"><Printer /> Print</a></Button>}
        </>}
      />
      <div className="card-pad space-y-4">
        {facts && (
          <div className="flex flex-wrap items-center gap-1.5 text-[0.72rem]">
            <span className="text-muted-foreground">Checked against:</span>
            <Badge tone="neutral">{facts.age ?? "?"} y{facts.elderly ? " · older adult" : ""}</Badge>
            {facts.weight ? <Badge tone="neutral">{String(facts.weight.value)} kg</Badge> : <Badge tone="outline">weight unknown</Badge>}
            {facts.egfr ? <Badge tone={Number(facts.egfr.value) < 60 ? "warning" : "neutral"} title={`${facts.egfr.source}${facts.egfr.date ? `, ${facts.egfr.date}` : ""}`}>eGFR {String(facts.egfr.value)}{facts.egfr.source.startsWith("calculated") ? " (calc.)" : ""}</Badge> : <Badge tone="outline">no kidney function</Badge>}
            {facts.hepatic && <Badge tone="warning">Liver impairment</Badge>}
            {facts.pregnant && <Badge tone="danger">Pregnant</Badge>}
            {facts.allergies.map((a) => <Badge key={a.substance} tone="danger">Allergy: {a.substance}</Badge>)}
            {facts.current_meds.length > 0 && <Badge tone="neutral" title={facts.current_meds.map((m) => m.name).join(", ")}>{facts.current_meds.length} current medicines</Badge>}
          </div>
        )}

        {editable && (
          <Field label="Diagnosis on prescription">
            <Input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} placeholder="e.g. Acute gastritis" />
          </Field>
        )}

        <div className="space-y-2.5">
          {rows.map((row, i) => {
            const c = checkFor(row);
            const findings = c?.findings ?? (rx.status === "final" ? storedFindings(row) : []);
            const sev: Severity = c?.status ?? (findings.length ? (findings.some((f) => f.severity === "critical") ? "critical" : findings.some((f) => f.severity === "warning") ? "warning" : "info") : "ok");
            const ai = reviewFor(row);
            const m = SEVERITY_META[sev];
            return (
              <div key={row.key} className={cn("rounded-xl border bg-card/70 p-3 transition-colors", row.drug && sev === "critical" ? "border-danger/40" : row.drug && sev === "warning" ? "border-warning/40" : "border-border/70")}>
                <div className="flex gap-3">
                  <MedicineThumb genericId={c?.generics[0]?.id ?? row.generic?.split("+")[0]} />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="grid gap-2 md:grid-cols-[minmax(0,1.6fr)_7rem_7.5rem_5.5rem]">
                      {editable ? (
                        <MedicineInput value={row.drug} autoFocus={i === rows.length - 1 && !row.drug && i > 0}
                          onChange={(v) => update(row.key, { drug: v })}
                          onPick={(o) => update(row.key, { drug: o.drug, frequency: o.frequency || row.frequency, dose: o.form === "syrup" ? "5 ml" : o.form === "cap" ? "1 cap" : o.form === "sachet" ? "1 sachet" : "1 tab" })} />
                      ) : <div className="flex h-9 items-center text-[0.9rem] font-semibold">{row.drug}</div>}
                      <Input aria-label="Dose" value={row.dose} disabled={!editable} onChange={(e) => update(row.key, { dose: e.target.value })} className="h-9" />
                      {editable ? (
                        <Select size="md" value={FREQUENCIES.includes(row.frequency) ? row.frequency : row.frequency} onValueChange={(v) => update(row.key, { frequency: v })}
                          options={[...new Set([...FREQUENCIES, row.frequency])].map((f) => ({ value: f, label: f, description: FREQ_HINT[f] }))} />
                      ) : <div className="flex h-9 items-center text-sm">{row.frequency}</div>}
                      <Input aria-label="Days" type="number" min={0} value={row.duration_days ?? ""} disabled={!editable} suffix="days"
                        onChange={(e) => update(row.key, { duration_days: e.target.value === "" ? null : Number(e.target.value) })} className="h-9" />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {editable ? (
                        <input value={row.instructions ?? ""} onChange={(e) => update(row.key, { instructions: e.target.value })} placeholder="Instructions — after food, before breakfast…"
                          className="h-7 min-w-[12rem] flex-1 rounded-md border border-transparent bg-transparent px-1.5 text-[0.78rem] text-muted-foreground hover:border-border focus:border-primary/50 focus:outline-none" />
                      ) : row.instructions ? <span className="text-[0.78rem] text-muted-foreground">{row.instructions}</span> : null}
                      {c && <span className="text-[0.72rem] text-muted-foreground">{c.recognised ? c.description : "Not in formulary"}{Object.keys(c.per_day).length ? ` · ${Object.entries(c.per_day).map(([g, v]) => `${v.toLocaleString()} ${c.generics.find((x) => x.id === g)?.unit ?? "mg"}/day`).join(" + ")}` : ""}</span>}
                      {row.drug && (c || findings.length > 0) && <span className={cn("ml-auto flex items-center gap-1 text-[0.72rem] font-semibold", m.text)}><m.icon className="size-3.5" /> {m.label}</span>}
                      {ai && <Badge tone={VERDICT_TONE[ai.verdict]} title={ai.comment}><Sparkles /> AI: {ai.verdict}{ai.dose_assessment !== "unclear" ? ` · dose ${ai.dose_assessment}` : ""}</Badge>}
                    </div>
                    {findings.filter((f) => f.severity !== "info" || findings.length <= 2).length > 0 && <FindingList findings={findings} dense max={4} />}
                    {ai && (ai.comment || ai.suggestion) && <p className="rounded-lg bg-primary-soft/50 px-2.5 py-1.5 text-[0.76rem]"><Sparkles className="mr-1 inline size-3 text-primary" />{ai.comment}{ai.suggestion && <> <b>Suggestion:</b> {ai.suggestion}</>}</p>}
                    {sev === "critical" && editable && (
                      <input value={row.override_reason ?? ""} onChange={(e) => update(row.key, { override_reason: e.target.value })} placeholder="Reason to proceed anyway (required to finalise)"
                        className="h-8 w-full rounded-md border border-danger/30 bg-danger-soft/40 px-2 text-[0.78rem] focus:outline-none focus:ring-2 focus:ring-danger/20" />
                    )}
                    {row.override_reason && !editable && <p className="text-[0.72rem] text-muted-foreground"><b>Prescriber's reason:</b> {row.override_reason}</p>}
                  </div>
                  {editable && <Button size="icon-xs" variant="ghost" aria-label="Remove" onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.key !== row.key) : [newRow()]))}><X /></Button>}
                </div>
              </div>
            );
          })}
          {editable && <Button size="sm" variant="secondary" className="rounded-full" onClick={() => setRows((rs) => [...rs, newRow()])}><Plus /> Add medicine</Button>}
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <Field label="Advice">
            <Textarea rows={2} value={advice} disabled={!editable} onChange={(e) => setAdvice(e.target.value)} placeholder="Diet, warning signs, when to come back…" />
          </Field>
          <Field label="Follow-up">
            <div className="space-y-1.5">
              <Input type="date" value={followUp} disabled={!editable} onChange={(e) => setFollowUp(e.target.value)} />
              {editable && <div className="flex flex-wrap gap-1">{FOLLOW_UPS.map(([l, n]) => <button key={l} type="button" onClick={() => setFollowUp(plusDays(n))} className="rounded-full border px-2 py-0.5 text-[0.7rem] text-muted-foreground hover:border-primary/40 hover:text-foreground">{l}</button>)}</div>}
            </div>
          </Field>
        </div>

        {/* AI second opinion */}
        <RunError run={review} />
        {reviewOut ? (
          <div className="space-y-2.5 rounded-xl border border-primary/20 bg-primary-soft/30 p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[0.85rem] font-semibold"><ShieldCheck className="size-4 text-primary" /> Clinical review
                <Badge tone={reviewOut.overall === "appropriate" ? "success" : reviewOut.overall === "unsafe" ? "danger" : "warning"} className="capitalize">{reviewOut.overall}</Badge>
              </div>
              <RunMeta run={review} onRerun={editable ? runReview : undefined} busy={reviewing} label="Review again" />
            </div>
            <p className="text-[0.82rem]">{reviewOut.summary}</p>
            {reviewOut.diagnosis_fit && <p className="text-[0.78rem] text-muted-foreground"><b className="text-foreground">Fit with diagnosis:</b> {reviewOut.diagnosis_fit}</p>}
            <div className="grid gap-3 sm:grid-cols-3">
              {!!reviewOut.missing.length && <div><MiniHeading>Consider adding</MiniHeading><Bullets items={reviewOut.missing} /></div>}
              {!!reviewOut.monitoring.length && <div><MiniHeading>Monitoring</MiniHeading><Bullets items={reviewOut.monitoring} /></div>}
              {!!reviewOut.counselling.length && <div><MiniHeading>Tell the patient</MiniHeading><Bullets items={reviewOut.counselling} /></div>}
            </div>
          </div>
        ) : editable && filled.length > 0 ? (
          <AIEmpty busy={reviewing} title="Second opinion on doses" text="The clinical model checks each dose for this patient — age, weight, kidney and liver function, current medicines — and whether it is enough or too strong."
            action={<Button size="sm" variant="soft" className="rounded-full" onClick={runReview}><Sparkles /> Review with clinical AI</Button>} />
        ) : null}

        {editable && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-4">
            {followUp && <span className="mr-auto flex items-center gap-1 text-[0.75rem] text-muted-foreground"><CalendarPlus className="size-3.5" /> Follow-up {fmtDate(followUp)} — added to the day list</span>}
            <Button variant="strong" className="rounded-full" disabled={!filled.length} loading={finalising} onClick={finalise}><Check /> Finalise prescription</Button>
          </div>
        )}
      </div>

      <Dialog open={askReasons} onOpenChange={setAskReasons}>
        <DialogContent title="Critical safety findings" description="These medicines triggered a stop-and-check rule. Change them, or record why you are proceeding — the reason is kept with the prescription." icon={<ShieldAlert />}
          footer={<><Button variant="secondary" onClick={() => setAskReasons(false)}>Back to edit</Button><Button variant="danger" loading={finalising} disabled={criticalRows.some((r) => !r.override_reason?.trim())} onClick={finalise}>Proceed and finalise</Button></>}>
          <div className="space-y-4">
            {criticalRows.map((r) => (
              <div key={r.key} className="space-y-2">
                <div className="text-sm font-semibold">{r.drug}</div>
                <FindingList findings={(checkFor(r)?.findings ?? []).filter((f) => f.severity === "critical")} dense />
                <Input value={r.override_reason ?? ""} onChange={(e) => update(r.key, { override_reason: e.target.value })} placeholder="Reason to proceed" />
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
