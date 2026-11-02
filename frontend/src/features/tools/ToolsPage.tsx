import { ArrowRight, Eye, FileSearch, ImageUp, Play } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { useDomains, useMe } from "@/api/hooks";
import type { AIRun } from "@/api/types";
import { Badge, Button, Card, CardHeader, Field, Input, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { PatientPicker } from "@/components/clinical/PatientPicker";
import { PATIENT_TOOLS } from "@/components/clinical/ToolForms";
import { ToolRunCard } from "@/components/clinical/ToolOutput";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ToolsPage() {
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: domains } = useDomains();
  const [question, setQuestion] = useState("");
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [qaRun, setQaRun] = useState<AIRun | null>(null);
  const [qaBusy, setQaBusy] = useState(false);
  const [image, setImage] = useState<File | null>(null);
  const [vq, setVq] = useState("");
  const [visionRun, setVisionRun] = useState<AIRun | null>(null);
  const [vBusy, setVBusy] = useState(false);
  const [patient, setPatient] = useState<{ id: string; full_name: string; mrn: string } | null>(null);

  const ask = async () => {
    setQaBusy(true); setQaRun(null);
    try { setQaRun(await api<AIRun>("/api/tools/guideline_qa/run", { method: "POST", body: { question, domains: selectedDomains.length ? selectedDomains : undefined } })); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setQaBusy(false); }
  };
  const analyse = async () => {
    if (!image) return;
    setVBusy(true); setVisionRun(null);
    const form = new FormData();
    form.append("file", image);
    if (vq) form.append("question", vq);
    try { setVisionRun(await api<AIRun>("/api/vision/analyze", { method: "POST", body: form })); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setVBusy(false); }
  };
  const populated = (domains ?? []).filter((d) => d.count > 0);

  return (
    <div className="space-y-[var(--gap)]">
      <PageHeader title="Clinical tools" description="Structured AI workflows. Every output is a reviewable draft grounded in your records and library." />

      <Card>
        <CardHeader title="Patient tools" description="Case summaries, SOAP notes, differentials, report comparison, medication reconciliation and more — run inside a patient's chart." icon={<ArrowRight />} />
        <div className="card-pad flex flex-col gap-4 lg:flex-row lg:items-end">
          <Field label="Patient" className="lg:w-96"><PatientPicker value={patient} onChange={setPatient} /></Field>
          <Button disabled={!patient} onClick={() => patient && navigate(`/patients/${patient.id}/tools`)}>Open tools <ArrowRight /></Button>
          <div className="flex flex-wrap gap-1.5 lg:ml-auto">{PATIENT_TOOLS.map((t) => <Badge key={t.id} tone="neutral"><t.icon /> {t.name}</Badge>)}</div>
        </div>
      </Card>

      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <Card>
          <CardHeader title="Guideline Q&A" description="Answers only from the knowledge library — abstains when the library doesn't cover it." icon={<FileSearch />} />
          <div className="card-pad space-y-4">
            <Field label="Question"><Textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. What blood pressure target is recommended in CKD?" onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(); }} /></Field>
            {populated.length > 0 && (
              <Field label="Limit to specialties" hint="Leave empty to search the whole library">
                <div className="flex flex-wrap gap-1.5">
                  {populated.map((d) => {
                    const on = selectedDomains.includes(d.id);
                    return <button key={d.id} onClick={() => setSelectedDomains((s) => (on ? s.filter((x) => x !== d.id) : [...s, d.id]))} className={cn("rounded-full border px-2.5 py-1 text-xs font-medium transition-colors", on ? "border-primary bg-primary-soft text-primary-soft-foreground" : "bg-card text-muted-foreground hover:text-foreground")}>{d.name} <span className="opacity-60">{d.count}</span></button>;
                  })}
                </div>
              </Field>
            )}
            <div className="flex justify-end"><Button onClick={ask} loading={qaBusy} disabled={question.trim().length < 3}><Play /> Ask</Button></div>
            {qaBusy && <Skeleton className="h-32" />}
            {qaRun && <div className="border-t pt-4"><ToolRunCard run={qaRun} canReview={false} /></div>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Image analysis" description="Neutral, structured description of a clinical image — never a diagnosis." icon={<Eye />} />
          <div className="card-pad space-y-4">
            <label className="flex h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-input bg-subtle text-sm text-muted-foreground hover:border-primary/50">
              <ImageUp className="size-5" /> {image ? image.name : "Choose PNG, JPG or WEBP"}
              <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
            </label>
            <Field label="Question (optional)"><Input value={vq} onChange={(e) => setVq(e.target.value)} /></Field>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">{me?.role !== "viewer" ? "To file the image in a chart, run this from the patient's tools." : ""}</p>
              <Button onClick={analyse} loading={vBusy} disabled={!image}><Play /> Analyse</Button>
            </div>
            {vBusy && <Skeleton className="h-32" />}
            {visionRun && <div className="border-t pt-4"><ToolRunCard run={visionRun} canReview={false} /></div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
