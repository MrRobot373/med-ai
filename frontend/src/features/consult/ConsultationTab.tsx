import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardPen, FlaskConical, ListPlus, Microscope, Play, Plus, Sparkles, Stethoscope, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { qk, useConsultation, useMe, useSubList, useToday } from "@/api/hooks";
import type { CopilotRun, Diagnosis, DiagnosisCheckOutput, Encounter, Prescription } from "@/api/types";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Skeleton, Spinner, Textarea, Tooltip } from "@/components/ui";
import { useWorkspace } from "@/features/workspace/context";
import { api, ApiError } from "@/lib/api";
import { canChart } from "@/lib/roles";
import { cn, fmtDateTime } from "@/lib/utils";
import { BriefCard } from "./BriefCard";
import { OrderForm, OrderList } from "./OrdersPanel";
import { AIEmpty, Bullets, MiniHeading, RunError, RunMeta } from "./parts";
import { PrescriptionBuilder } from "./PrescriptionBuilder";

const VITALS = [
  { key: "bp", label: "BP", placeholder: "120/80", suffix: "mmHg" },
  { key: "hr", label: "Pulse", placeholder: "76", suffix: "/min" },
  { key: "temp_f", label: "Temp", placeholder: "98.6", suffix: "°F" },
  { key: "spo2", label: "SpO₂", placeholder: "98", suffix: "%" },
  { key: "weight_kg", label: "Weight", placeholder: "70", suffix: "kg" },
];
const VERDICT = {
  consistent: { label: "Consistent", tone: "success" },
  partly_consistent: { label: "Partly consistent", tone: "warning" },
  inconsistent: { label: "Doesn't fit well", tone: "danger" },
  insufficient_information: { label: "Need more information", tone: "neutral" },
} as const;

export default function ConsultationTab() {
  const { patient } = useWorkspace();
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const { data: encounters, isLoading } = useSubList<Encounter>(patient.id, "encounters");
  const { data: today } = useToday();
  const qc = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [reason, setReason] = useState("");
  const writer = canChart(me?.role);

  const appt = today?.appointments.find((a) => a.patient_id === patient.id && a.status !== "seen");
  const current = params.get("e") ?? encounters?.find((e) => e.status === "in_progress")?.id ?? null;

  const start = async () => {
    setStarting(true);
    try {
      const enc = await api<Encounter>(`/api/patients/${patient.id}/consultations`, { method: "POST", body: { appointment_id: appt?.id ?? null, reason: reason || null } });
      qc.invalidateQueries({ queryKey: qk.sub(patient.id, "encounters") });
      qc.invalidateQueries({ queryKey: qk.today });
      setParams({ e: enc.id }, { replace: true });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start");
    } finally {
      setStarting(false);
    }
  };

  if (isLoading) return <Skeleton className="h-96" />;
  if (!current) {
    return (
      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.1fr_1fr]">
        <BriefCard patientId={patient.id} canRun={writer || me?.role === "viewer"} />
        <Card>
          <CardHeader icon={<Stethoscope />} title="Start consultation" description={appt ? `On today's list${appt.time ? ` at ${appt.time}` : ""} — ${appt.reason ?? "no reason given"}` : "Walk-in or unscheduled visit"} />
          <div className="card-pad space-y-3">
            {!appt && <Field label="Chief complaint"><Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Stomach pain since 2 days" /></Field>}
            {writer ? <Button variant="strong" className="rounded-full" loading={starting} onClick={start}><Play /> Start consultation</Button>
              : <p className="text-sm text-muted-foreground">Only clinicians can start a consultation.</p>}
            <p className="text-xs text-muted-foreground">Notes, prescription and orders are saved as you go. The AI checks are drafts for you to verify — nothing is added to the chart until you finalise.</p>
          </div>
        </Card>
      </div>
    );
  }
  return <Consultation encounterId={current} writer={writer} />;
}

function Consultation({ encounterId, writer }: { encounterId: string; writer: boolean }) {
  const { patient } = useWorkspace();
  const { data, isLoading } = useConsultation(encounterId);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [completing, setCompleting] = useState(false);
  const [opening, setOpening] = useState(false);
  const [showOrder, setShowOrder] = useState(false);
  if (isLoading || !data) return <div className="grid gap-4 xl:grid-cols-2"><Skeleton className="h-[480px]" /><Skeleton className="h-[480px]" /></div>;
  const enc = data.encounter;
  const done = enc.status !== "in_progress";
  const editable = writer && !done;

  const openRx = async () => {
    setOpening(true);
    try {
      await api<Prescription>(`/api/consultations/${encounterId}/prescription`, { method: "POST" });
      qc.invalidateQueries({ queryKey: qk.consultation(encounterId) });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not open the prescription");
    } finally {
      setOpening(false);
    }
  };
  const complete = async () => {
    setCompleting(true);
    try {
      await api(`/api/consultations/${encounterId}/complete`, { method: "POST", body: {} });
      toast.success("Consultation completed", { description: "Notes, diagnosis, prescription and orders are now part of the record." });
      ["today", "inbox", "dashboard"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      navigate(`/patients/${patient.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not complete");
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="space-y-[var(--gap)]">
      <Card className="card-pad">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-full bg-strong text-strong-foreground"><Stethoscope className="size-5" /></span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-[0.95rem] font-semibold">Consultation {done ? <Badge tone="success"><CheckCircle2 /> Completed</Badge> : <Badge tone="primary">In progress</Badge>}</div>
            <div className="text-xs text-muted-foreground">Started {fmtDateTime(enc.started_at)}{enc.reason ? ` · ${enc.reason}` : ""}</div>
          </div>
          {editable && <Button variant="strong" className="rounded-full" loading={completing} onClick={complete}><CheckCircle2 /> Complete consultation</Button>}
        </div>
      </Card>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_1.12fr]">
        <div className="min-w-0 space-y-[var(--gap)]">
          <BriefCard patientId={patient.id} canRun={writer} />
          <NotesCard enc={enc} editable={editable} />
          <DiagnosisCheckCard encounterId={encounterId} run={data.diagnosis_check} canRun={writer} />
        </div>
        <div className="min-w-0 space-y-[var(--gap)]">
          {data.prescription ? (
            <PrescriptionBuilder key={data.prescription.id + data.prescription.status} rx={data.prescription} review={data.rx_review} canWrite={writer} />
          ) : (
            <Card>
              <EmptyState icon={<ClipboardPen />} title="No prescription yet" description="Medicines are checked live against age, weight, kidney and liver function, allergies, problems and current medicines."
                action={editable && <Button variant="strong" className="rounded-full" loading={opening} onClick={openRx}><Plus /> Write prescription</Button>} />
            </Card>
          )}
          <Card>
            <CardHeader icon={<Microscope />} title="Investigations" description="Reports uploaded later — by you or the front desk — are matched to these orders"
              actions={editable && <Button size="sm" variant={showOrder ? "ghost" : "secondary"} className="rounded-full" onClick={() => setShowOrder((s) => !s)}>{showOrder ? <><X /> Close</> : <><ListPlus /> Order test</>}</Button>} />
            <div className="card-pad space-y-3">
              {showOrder && <div className="rounded-xl border border-border/70 bg-subtle/60 p-3"><OrderForm patientId={patient.id} encounterId={encounterId} onDone={() => setShowOrder(false)} /></div>}
              <OrderList orders={data.orders} canWrite={writer} canAI={writer} empty="No tests ordered in this consultation" />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function NotesCard({ enc, editable }: { enc: Encounter; editable: boolean }) {
  const qc = useQueryClient();
  const [f, setF] = useState({
    reason: enc.reason ?? "", history: enc.history ?? "", examination: enc.examination ?? "", assessment: enc.assessment ?? "", plan: enc.plan ?? "",
  });
  const [vitals, setVitals] = useState<Record<string, any>>(enc.vitals ?? {});
  const [dx, setDx] = useState<Diagnosis[]>(enc.diagnoses ?? []);
  const [dxText, setDxText] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const first = useRef(true);
  const body = useMemo(() => ({ ...f, vitals, diagnoses: dx }), [f, vitals, dx]);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (!editable) return;
    const t = setTimeout(async () => {
      setState("saving");
      try {
        await api(`/api/consultations/${enc.id}`, { method: "PATCH", body });
        setState("saved");
        qc.invalidateQueries({ queryKey: qk.sub(enc.patient_id, "previsit") });
      } catch (e) {
        setState("idle");
        toast.error(e instanceof ApiError ? e.message : "Could not save notes");
      }
    }, 800);
    return () => clearTimeout(t);
  }, [body, editable, enc.id, enc.patient_id, qc]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  const addDx = () => { const n = dxText.trim(); if (n && !dx.some((d) => d.name.toLowerCase() === n.toLowerCase())) setDx((d) => [...d, { name: n, add_to_problems: false }]); setDxText(""); };

  return (
    <Card>
      <CardHeader icon={<ClipboardPen />} title="Consultation notes"
        actions={editable && <span className="text-[0.7rem] text-muted-foreground">{state === "saving" ? <span className="flex items-center gap-1"><Spinner className="size-3" /> Saving</span> : state === "saved" ? "Saved" : "Autosaves"}</span>} />
      <div className="card-pad space-y-3.5">
        <Field label="Chief complaint"><Input value={f.reason} disabled={!editable} onChange={set("reason")} placeholder="Stomach pain since 2 days" /></Field>
        <Field label="History"><Textarea rows={3} value={f.history} disabled={!editable} onChange={set("history")} placeholder="Onset, character, associated symptoms, relevant negatives…" /></Field>
        <div>
          <div className="mb-1.5 text-[0.8rem] font-medium">Vitals</div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {VITALS.map((v) => (
              <label key={v.key} className="rounded-lg border border-border/70 bg-card/70 px-2.5 py-1.5">
                <span className="block text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">{v.label}</span>
                <span className="flex items-baseline gap-1">
                  <input value={vitals[v.key] ?? ""} disabled={!editable} placeholder={v.placeholder} onChange={(e) => setVitals((x) => ({ ...x, [v.key]: e.target.value }))}
                    className="w-full min-w-0 bg-transparent text-[0.9rem] font-semibold num placeholder:font-normal placeholder:text-muted-foreground/60 focus:outline-none" />
                  <span className="text-[0.65rem] text-muted-foreground">{v.suffix}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
        <Field label="Examination"><Textarea rows={2} value={f.examination} disabled={!editable} onChange={set("examination")} placeholder="Findings" /></Field>
        <Field label="Diagnosis" hint="Press Enter to add. Tap the + on a diagnosis to add it to the problem list when you complete.">
          <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-input bg-card px-2 py-1.5">
            {dx.map((d) => (
              <span key={d.name} className={cn("inline-flex items-center gap-1 rounded-full py-0.5 pl-2.5 pr-1 text-[0.78rem] font-medium", d.add_to_problems ? "bg-strong text-strong-foreground" : "bg-muted")}>
                {d.name}
                {editable && <Tooltip content={d.add_to_problems ? "Will be added to the problem list" : "Add to problem list on completion"}>
                  <button type="button" onClick={() => setDx((all) => all.map((x) => (x.name === d.name ? { ...x, add_to_problems: !x.add_to_problems } : x)))} className="rounded-full p-0.5 opacity-70 hover:opacity-100" aria-label="Toggle problem list"><ListPlus className="size-3" /></button>
                </Tooltip>}
                {editable && <button type="button" onClick={() => setDx((all) => all.filter((x) => x.name !== d.name))} className="rounded-full p-0.5 opacity-60 hover:opacity-100" aria-label={`Remove ${d.name}`}><X className="size-3" /></button>}
              </span>
            ))}
            {editable && <input value={dxText} onChange={(e) => setDxText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDx(); } }} onBlur={addDx}
              placeholder={dx.length ? "Add another…" : "e.g. Acute gastritis"} className="min-w-[10rem] flex-1 bg-transparent text-[0.85rem] focus:outline-none" />}
          </div>
        </Field>
        <Field label="Assessment"><Textarea rows={2} value={f.assessment} disabled={!editable} onChange={set("assessment")} placeholder="Your reasoning" /></Field>
        <Field label="Plan"><Textarea rows={2} value={f.plan} disabled={!editable} onChange={set("plan")} placeholder="Treatment, tests, follow-up" /></Field>
      </div>
    </Card>
  );
}

function DiagnosisCheckCard({ encounterId, run, canRun }: { encounterId: string; run: CopilotRun<DiagnosisCheckOutput> | null; canRun: boolean }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const r = await api<CopilotRun<DiagnosisCheckOutput>>(`/api/consultations/${encounterId}/diagnosis-check`, { method: "POST" });
      if (r.status === "error") toast.error(r.error ?? "Check failed");
      qc.invalidateQueries({ queryKey: qk.consultation(encounterId) });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Check failed");
    } finally {
      setBusy(false);
    }
  };
  const out = run?.status === "draft" ? run.output : null;
  return (
    <Card>
      <CardHeader icon={<Sparkles />} title="Diagnosis — second look" description="Your diagnosis checked against today's findings and the whole history" />
      <div className="card-pad space-y-3">
        <RunError run={run} />
        {out ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge tone={VERDICT[out.verdict].tone}>{VERDICT[out.verdict].label}</Badge>
              <RunMeta run={run} onRerun={canRun ? go : undefined} busy={busy} label="Check again" />
            </div>
            <p className="text-[0.85rem]">{out.summary}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {!!out.supporting.length && <div><MiniHeading>Supports</MiniHeading><Bullets items={out.supporting} /></div>}
              {!!out.against.length && <div><MiniHeading>Against / missing</MiniHeading><Bullets items={out.against} /></div>}
            </div>
            {!!out.consider.length && (
              <div>
                <MiniHeading>Also consider</MiniHeading>
                <div className="space-y-1.5">{out.consider.map((c, i) => (
                  <div key={i} className="rounded-lg border border-border/60 bg-card/70 px-3 py-2 text-[0.8rem]"><b>{c.diagnosis}</b> — {c.why}{c.how_to_check && <div className="text-[0.72rem] text-muted-foreground">Check: {c.how_to_check}</div>}</div>
                ))}</div>
              </div>
            )}
            {!!out.red_flags.length && <div className="rounded-lg bg-danger-soft px-3 py-2"><MiniHeading>Red flags to ask about</MiniHeading><Bullets items={out.red_flags} /></div>}
            {!!out.suggested_tests.length && <div><MiniHeading icon={<FlaskConical />}>Tests that would help</MiniHeading><Bullets items={out.suggested_tests.map((t) => `${t.test} — ${t.why}`)} /></div>}
            {!!out.history_links.length && <div><MiniHeading>From the history</MiniHeading><Bullets items={out.history_links} /></div>}
          </>
        ) : canRun ? (
          <AIEmpty busy={busy} title="Double-check the diagnosis" text="We trust your diagnosis — the clinical AI looks for anything that doesn't fit and for dangerous alternatives, given age, diabetes, BP and past visits."
            action={<Button size="sm" variant="soft" className="rounded-full" onClick={go}><Sparkles /> Check diagnosis</Button>} />
        ) : <p className="text-sm text-muted-foreground">No check has been run.</p>}
      </div>
    </Card>
  );
}
