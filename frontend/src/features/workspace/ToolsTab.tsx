import { History, ImageUp, Play, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { useInvalidatePatient, usePatientDocuments, useRuns, useSubList } from "@/api/hooks";
import type { AIRun, Encounter } from "@/api/types";
import { Button, Card, CardHeader, Checkbox, EmptyState, Field, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { RunStatusBadge } from "@/components/clinical/badges";
import { PATIENT_TOOLS } from "@/components/clinical/ToolForms";
import { ToolRunCard, toolName } from "@/components/clinical/ToolOutput";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, fmtRelative, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

export default function ToolsTab() {
  const { patient, canWrite } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const [tool, setTool] = useState(params.get("tool") ?? "summary");
  const [run, setRun] = useState<AIRun | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: history, refetch } = useRuns({ patient_id: patient.id, limit: 40 });
  const { data: docs } = usePatientDocuments(patient.id);
  const { data: encounters } = useSubList<Encounter>(patient.id, "encounters");
  const invalidate = useInvalidatePatient();
  const ready = useMemo(() => (docs ?? []).filter((d) => d.status === "ready" && d.is_active), [docs]);

  const [encounterId, setEncounterId] = useState(params.get("encounter") ?? "");
  const [extra, setExtra] = useState("");
  const [presentation, setPresentation] = useState("");
  const [docId, setDocId] = useState("");
  const [prior, setPrior] = useState("");
  const [current, setCurrent] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [attach, setAttach] = useState(true);

  useEffect(() => { if (!encounterId && encounters?.length) setEncounterId(encounters[0].id); }, [encounters, encounterId]);
  useEffect(() => {
    if (ready.length && !docId) setDocId(ready[0].id);
    const labs = ready.filter((d) => d.kind === ready[0]?.kind).sort((a, b) => (a.document_date ?? a.created_at).localeCompare(b.document_date ?? b.created_at));
    if (labs.length >= 2 && !prior) { setPrior(labs[labs.length - 2].id); setCurrent(labs[labs.length - 1].id); }
  }, [ready, docId, prior]);
  useEffect(() => {
    const id = params.get("run");
    if (id) api<AIRun>(`/api/ai-runs/${id}`).then((r) => { setRun(r); setTool(r.tool); }).catch(() => undefined);
  }, [params]);

  const docOptions = ready.map((d) => ({ value: d.id, label: d.title, description: `${titleCase(d.kind)} · ${fmtDate(d.document_date ?? d.created_at)}` }));

  const execute = async () => {
    setBusy(true);
    setRun(null);
    try {
      let r: AIRun;
      if (tool === "vision") {
        if (!image) throw new ApiError(400, "Choose an image first");
        const form = new FormData();
        form.append("file", image);
        form.append("patient_id", patient.id);
        if (question) form.append("question", question);
        form.append("attach_to_record", String(attach && canWrite));
        r = await api<AIRun>("/api/vision/analyze", { method: "POST", body: form });
      } else {
        const body: Record<string, any> = { patient_id: patient.id };
        if (tool === "soap") Object.assign(body, { encounter_id: encounterId, extra_notes: extra || undefined });
        if (tool === "differential") body.presentation = presentation;
        if (tool === "entities" || tool === "med_reconciliation") body.document_id = docId;
        if (tool === "comparison") Object.assign(body, { prior_document_id: prior, current_document_id: current });
        r = await api<AIRun>(`/api/tools/${tool}/run`, { method: "POST", body });
      }
      setRun(r);
      setParams({ tool, run: r.id }, { replace: true });
      if (r.status === "error") toast.error(r.error ?? "Tool failed");
      refetch();
      invalidate(patient.id);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Tool failed");
    } finally {
      setBusy(false);
    }
  };

  const meta = PATIENT_TOOLS.find((t) => t.id === tool)!;
  const disabled = (tool === "soap" && !encounterId) || (tool === "differential" && presentation.trim().length < 3) || (["entities", "med_reconciliation"].includes(tool) && !docId) || (tool === "comparison" && (!prior || !current || prior === current)) || (tool === "vision" && !image);

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[280px_1fr]">
      <div className="space-y-1.5">
        {PATIENT_TOOLS.map((t) => (
          <button key={t.id} onClick={() => { setTool(t.id); setRun(null); setParams({ tool: t.id }, { replace: true }); }}
            className={cn("flex w-full items-start gap-3 rounded-xl border bg-card p-3 text-left shadow-xs transition-all hover:border-primary/40", tool === t.id && "border-primary ring-2 ring-primary/15")}>
            <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", tool === t.id ? "bg-primary text-primary-foreground" : "bg-primary-soft text-primary-soft-foreground")}><t.icon className="size-4" /></span>
            <span className="min-w-0"><span className="block text-sm font-medium">{t.name}</span><span className="block text-xs text-muted-foreground">{t.description}</span></span>
          </button>
        ))}
      </div>

      <div className="space-y-[var(--gap)]">
        <Card>
          <CardHeader title={meta.name} description={meta.description} icon={<meta.icon />} actions={<Button onClick={execute} loading={busy} disabled={disabled}><Play /> Run</Button>} />
          <div className="card-pad space-y-4">
            {tool === "summary" && <p className="text-sm text-muted-foreground">Uses the structured record and the most relevant passages from this patient's documents.</p>}
            {tool === "soap" && (
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Encounter">{encounters?.length ? <Select value={encounterId} onValueChange={setEncounterId} options={encounters.map((e) => ({ value: e.id, label: e.reason ?? "Encounter", description: `${fmtDate(e.started_at)} · ${titleCase(e.type)}` }))} /> : <p className="text-sm text-muted-foreground">No encounters — start one first.</p>}</Field>
                <Field label="Additional notes" hint="Optional dictation or details not yet in the encounter"><Textarea rows={3} value={extra} onChange={(e) => setExtra(e.target.value)} /></Field>
              </div>
            )}
            {tool === "differential" && <Field label="Presentation" hint="Symptoms, signs and the question you want support with"><Textarea rows={4} value={presentation} onChange={(e) => setPresentation(e.target.value)} placeholder="e.g. Progressive exertional dyspnoea and ankle oedema over 3 weeks" /></Field>}
            {(tool === "entities" || tool === "med_reconciliation") && <Field label="Document">{docOptions.length ? <Select value={docId} onValueChange={setDocId} options={docOptions} /> : <p className="text-sm text-muted-foreground">No processed documents yet.</p>}</Field>}
            {tool === "comparison" && (
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Prior report"><Select value={prior} onValueChange={setPrior} options={docOptions} placeholder="Select…" /></Field>
                <Field label="Current report"><Select value={current} onValueChange={setCurrent} options={docOptions} placeholder="Select…" /></Field>
              </div>
            )}
            {tool === "vision" && (
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Image">
                  <label className="flex h-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-input bg-subtle text-sm text-muted-foreground hover:border-primary/50">
                    <ImageUp className="size-5" /> {image ? image.name : "Choose PNG, JPG or WEBP"}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
                  </label>
                </Field>
                <div className="space-y-3">
                  <Field label="Question (optional)"><Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Any visible change compared to baseline?" /></Field>
                  {canWrite && <label className="flex items-center gap-2 text-sm"><Checkbox checked={attach} onCheckedChange={(v) => setAttach(!!v)} /> Also file the image in this patient's documents</label>}
                </div>
              </div>
            )}
            {busy && <div className="space-y-2"><Skeleton className="h-4 w-1/2" /><Skeleton className="h-28" /><p className="text-xs text-muted-foreground">Running on your configured model — local models can take a little while.</p></div>}
            {run && <div className="border-t pt-4"><ToolRunCard run={run} canReview={canWrite} onChange={setRun} /></div>}
          </div>
        </Card>

        <Card>
          <CardHeader title="History" description="Every run is kept with its status and model" icon={<History />} />
          <div className="card-pad">
            {!history?.length ? <EmptyState compact icon={<Wand2 />} title="No tool runs yet" /> : (
              <div className="divide-y">
                {history.map((h) => (
                  <button key={h.id} onClick={() => { setRun(h); setTool(h.tool === "research" ? tool : h.tool); setParams({ tool: h.tool, run: h.id }, { replace: true }); }} className={cn("flex w-full items-center gap-3 py-2.5 text-left text-sm hover:bg-subtle", run?.id === h.id && "bg-primary-soft/40")}>
                    <span className="flex-1 font-medium">{toolName(h.tool)}</span>
                    <RunStatusBadge status={h.status} />
                    <span className="w-28 text-right text-xs text-muted-foreground">{fmtRelative(h.created_at)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
