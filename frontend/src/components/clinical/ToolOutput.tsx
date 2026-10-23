import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, ArrowUp, Check, Clock, Copy, Cpu, Minus, X } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import type { AIRun } from "@/api/types";
import { Badge, Button } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, fmtNum, fmtRelative, titleCase } from "@/lib/utils";
import { RunStatusBadge } from "./badges";
import { Markdown } from "./Markdown";

const TOOL_NAMES: Record<string, string> = {
  summary: "Case summary", soap: "SOAP note", entities: "Entity extraction", differential: "Differential support",
  guideline_qa: "Guideline Q&A", comparison: "Report comparison", med_reconciliation: "Medication reconciliation",
  vision: "Image analysis",
};
export const toolName = (t: string) => TOOL_NAMES[t] ?? titleCase(t);

function Block({ title, children, tone }: { title: string; children: ReactNode; tone?: "warning" | "danger" }) {
  return (
    <div className={cn("rounded-lg border p-3.5", tone === "warning" && "border-warning/30 bg-warning-soft/50", tone === "danger" && "border-danger/30 bg-danger-soft/50")}>
      <div className="text-label mb-2">{title}</div>
      {children}
    </div>
  );
}

function Bullets({ items, render }: { items: any[] | undefined; render?: (x: any) => ReactNode }) {
  if (!items?.length) return <p className="text-sm text-muted-foreground">None documented.</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((x, i) => (
        <li key={i} className="flex gap-2 text-sm"><span className="mt-[0.6rem] size-1 shrink-0 rounded-full bg-muted-foreground" /><div className="min-w-0 flex-1">{render ? render(x) : typeof x === "string" ? <Markdown className="[&_p]:my-0">{x}</Markdown> : JSON.stringify(x)}</div></li>
      ))}
    </ul>
  );
}

const Cites = ({ c }: { c?: string[] }) => (c?.length ? <span className="ml-1">{c.map((l) => <Badge key={l} tone="primary" square className="ml-0.5 px-1 font-mono">{l}</Badge>)}</span> : null);

function Summary({ o }: { o: any }) {
  return (
    <div className="space-y-3">
      {o.one_liner && <p className="text-[0.95rem] leading-relaxed">{o.one_liner}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        <Block title="Active problems"><Bullets items={o.active_problems} render={(p) => <span><span className="font-medium">{p.problem}</span>{p.status && <span className="text-muted-foreground"> — {p.status}</span>}<Cites c={p.citations} /></span>} /></Block>
        <Block title="Key findings"><Bullets items={o.key_findings} render={(f) => <span>{f.finding ?? String(f)}<Cites c={f.citations} /></span>} /></Block>
        <Block title="Medications"><Bullets items={o.medications} /></Block>
        <Block title="Recent changes"><Bullets items={o.recent_changes} /></Block>
      </div>
      {!!o.missing_information?.length && <Block title="Missing information" tone="warning"><Bullets items={o.missing_information} /></Block>}
      {!!o.follow_up_considerations?.length && <Block title="Follow-up considerations"><Bullets items={o.follow_up_considerations} /></Block>}
    </div>
  );
}

function Soap({ o }: { o: any }) {
  return (
    <div className="space-y-3">
      {(["subjective", "objective", "assessment", "plan"] as const).map((k) => (
        <Block key={k} title={k}><Markdown>{String(o[k] ?? "Not documented.")}</Markdown></Block>
      ))}
      {!!o.missing_information?.length && <Block title="Missing information" tone="warning"><Bullets items={o.missing_information} /></Block>}
    </div>
  );
}

function Differential({ o }: { o: any }) {
  return (
    <div className="space-y-3">
      {o.summary && <Markdown>{o.summary}</Markdown>}
      {(o.considerations ?? []).map((c: any, i: number) => (
        <div key={i} className="rounded-lg border p-3.5">
          <div className="flex items-center gap-2"><span className="flex size-6 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary-soft-foreground">{i + 1}</span><span className="font-semibold">{c.condition}</span><Cites c={c.citations} /></div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <div><div className="text-label mb-1 !text-success-foreground">Supporting</div><Bullets items={c.supporting} /></div>
            <div><div className="text-label mb-1 !text-danger-foreground">Against</div><Bullets items={c.against} /></div>
            <div><div className="text-label mb-1">Suggested evaluation</div><Bullets items={c.suggested_evaluation} /></div>
          </div>
        </div>
      ))}
      {!!o.red_flags?.length && <Block title="Red flags" tone="danger"><Bullets items={o.red_flags} /></Block>}
      {!!o.missing_information?.length && <Block title="Missing information" tone="warning"><Bullets items={o.missing_information} /></Block>}
    </div>
  );
}

function Entities({ o }: { o: any }) {
  const ev = (x: any) => x.evidence && <div className="mt-0.5 text-xs italic text-muted-foreground">“{x.evidence}”</div>;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Block title="Problems"><Bullets items={o.problems} render={(x) => <><span className="font-medium">{x.name}</span> {x.status && <Badge>{x.status}</Badge>}{ev(x)}</>} /></Block>
      <Block title="Medications"><Bullets items={o.medications} render={(x) => <><span className="font-medium">{x.name}</span> <span className="text-muted-foreground">{[x.dose, x.route, x.frequency].filter(Boolean).join(" · ")}</span>{ev(x)}</>} /></Block>
      <Block title="Allergies"><Bullets items={o.allergies} render={(x) => <><span className="font-medium">{x.substance}</span> {x.reaction && <span className="text-muted-foreground">— {x.reaction}</span>}{ev(x)}</>} /></Block>
      <Block title="Results"><Bullets items={o.labs} render={(x) => <><span className="font-medium">{x.name}</span> {x.value} {x.unit} {x.flag && <Badge tone="warning">{x.flag}</Badge>}{ev(x)}</>} /></Block>
      <Block title="Procedures"><Bullets items={o.procedures} render={(x) => <><span className="font-medium">{x.name}</span> {x.date && <span className="text-muted-foreground">({x.date})</span>}{ev(x)}</>} /></Block>
      <Block title="Symptoms & follow-up"><Bullets items={[...(o.symptoms ?? []), ...(o.follow_up ?? [])]} /></Block>
    </div>
  );
}

function Comparison({ o }: { o: any }) {
  return (
    <div className="space-y-3">
      {o.overview && <Markdown>{o.overview}</Markdown>}
      {!!o.lab_changes?.length && (
        <Block title="Measured changes (computed from extracted values)">
          <div className="divide-y">
            {o.lab_changes.map((l: any) => (
              <div key={l.name} className="flex items-center gap-3 py-1.5 text-sm">
                <span className="flex-1 font-medium">{l.name}</span>
                <span className="num text-muted-foreground">{fmtNum(l.prior)} → <span className="font-semibold text-foreground">{fmtNum(l.current)}</span> {l.unit}</span>
                <span className={cn("flex w-20 items-center justify-end gap-1 num text-xs font-medium", l.direction === "up" ? "text-danger-foreground" : l.direction === "down" ? "text-info-foreground" : "text-muted-foreground")}>
                  {l.direction === "up" ? <ArrowUp className="size-3" /> : l.direction === "down" ? <ArrowDown className="size-3" /> : <Minus className="size-3" />}{l.delta > 0 ? "+" : ""}{fmtNum(l.delta)}
                </span>
              </div>
            ))}
          </div>
        </Block>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <Block title="New findings"><Bullets items={o.new_findings} /></Block>
        <Block title="Resolved"><Bullets items={o.resolved_findings} /></Block>
        <Block title="Worsened"><Bullets items={o.worsened} /></Block>
        <Block title="Improved"><Bullets items={o.improved} /></Block>
      </div>
      {!!o.clinically_relevant_changes?.length && <Block title="Clinically relevant changes" tone="warning"><Bullets items={o.clinically_relevant_changes} /></Block>}
    </div>
  );
}

function MedRec({ o }: { o: any }) {
  const med = (m: any) => <><span className="font-medium">{m.name}</span> <span className="text-muted-foreground">{[m.dose, m.frequency].filter(Boolean).join(" · ")}</span></>;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Block title={`Discrepancies (${o.discrepancies?.length ?? 0})`} tone={o.discrepancies?.length ? "danger" : undefined}>
        <Bullets items={o.discrepancies} render={(d) => <><span className="font-medium">{d.name}</span><div className="text-xs text-muted-foreground">Chart: {[d.chart?.dose, d.chart?.frequency].filter(Boolean).join(" · ") || "—"} · Document: {[d.document?.dose, d.document?.frequency, d.document?.status].filter(Boolean).join(" · ") || "—"}</div>{d.document?.evidence && <div className="text-xs italic text-muted-foreground">“{d.document.evidence}”</div>}</>} />
      </Block>
      <Block title={`Matched (${o.matched?.length ?? 0})`}><Bullets items={o.matched} render={(d) => <span className="font-medium">{d.name}</span>} /></Block>
      <Block title="Only in document — not on chart" tone={o.only_in_document?.length ? "warning" : undefined}><Bullets items={o.only_in_document} render={med} /></Block>
      <Block title="Only on chart — not in document"><Bullets items={o.only_in_chart} render={med} /></Block>
    </div>
  );
}

function Vision({ o }: { o: any }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2"><Badge tone="primary">{o.image_type}</Badge>{o.quality && <Badge>Quality: {o.quality}</Badge>}</div>
      <div className="grid gap-3 md:grid-cols-2">
        <Block title="Observations"><Bullets items={o.observations} /></Block>
        <Block title="Measurements"><Bullets items={o.measurements} render={(m) => <span><span className="font-medium">{m.name}</span>: {m.value} {m.unit}</span>} /></Block>
        <Block title="Considerations for the clinician"><Bullets items={o.possible_considerations} /></Block>
        <Block title="Limitations" tone="warning"><Bullets items={o.limitations} /></Block>
      </div>
      {o.text_found && <Block title="Text in image"><pre className="whitespace-pre-wrap font-mono text-xs">{o.text_found}</pre></Block>}
      {o.recommended_review && <Block title="Recommended review"><p className="text-sm">{o.recommended_review}</p></Block>}
    </div>
  );
}

function Guideline({ o, citations }: { o: any; citations: any[] }) {
  return (
    <div className="space-y-3">
      <Markdown>{o.answer ?? ""}</Markdown>
      {!!o.key_points?.length && <Block title="Key points"><Bullets items={o.key_points} /></Block>}
      {!!citations.length && (
        <Block title="Sources">
          <div className="space-y-2">
            {citations.map((c: any) => (
              <div key={c.chunk_id} className="text-sm"><Badge tone="primary" square className="mr-1.5 font-mono">{c.label}</Badge><span className="font-medium">{c.document_title}</span>{c.section && <span className="text-muted-foreground"> · {c.section}</span>}<p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{c.excerpt}</p></div>
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}

export function ToolOutputBody({ run }: { run: AIRun }) {
  if (run.status === "error") {
    return <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3 text-sm text-danger-foreground"><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><div className="font-medium">The tool could not complete</div><div className="mt-0.5 opacity-90">{run.error}</div></div></div>;
  }
  const o = run.output ?? {};
  switch (run.tool) {
    case "summary": return <Summary o={o} />;
    case "soap": return <Soap o={o} />;
    case "differential": return <Differential o={o} />;
    case "entities": return <Entities o={o} />;
    case "comparison": return <Comparison o={o} />;
    case "med_reconciliation": return <MedRec o={o} />;
    case "vision": return <Vision o={o} />;
    case "guideline_qa": return <Guideline o={o} citations={run.citations} />;
    default: return <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(o, null, 2)}</pre>;
  }
}

export function ToolRunCard({ run, canReview, onChange, compactHeader }: { run: AIRun; canReview?: boolean; onChange?: (r: AIRun) => void; compactHeader?: boolean }) {
  const qc = useQueryClient();
  const review = async (decision: "accepted" | "discarded") => {
    const r = await api<AIRun>(`/api/ai-runs/${run.id}/review`, { method: "POST", body: { decision } });
    toast.success(decision === "accepted" ? "Accepted into the record" : "Draft discarded");
    qc.invalidateQueries({ queryKey: ["runs"] });
    if (run.patient_id) qc.invalidateQueries({ queryKey: ["patient", run.patient_id] });
    qc.invalidateQueries({ queryKey: ["inbox"] });
    onChange?.(r);
  };
  const copy = () => { navigator.clipboard.writeText(JSON.stringify(run.output, null, 2)); toast.success("Copied as JSON"); };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {!compactHeader && <span className="font-semibold">{toolName(run.tool)}</span>}
        <RunStatusBadge status={run.status} />
        <span className="flex items-center gap-1 text-xs text-muted-foreground"><Clock className="size-3" /> {fmtRelative(run.created_at)}</span>
        {run.model && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Cpu className="size-3" /> {run.model}{run.latency_ms ? ` · ${(run.latency_ms / 1000).toFixed(1)}s` : ""}</span>}
        <div className="ml-auto flex items-center gap-1.5">
          {run.status !== "error" && <Button size="xs" variant="ghost" onClick={copy}><Copy /> Copy</Button>}
          {canReview && run.status === "draft" && (
            <>
              <Button size="xs" variant="secondary" onClick={() => review("discarded")}><X /> Discard</Button>
              <Button size="xs" onClick={() => review("accepted")}><Check /> Accept</Button>
            </>
          )}
        </div>
      </div>
      <ToolOutputBody run={run} />
      {run.status === "draft" && <p className="text-xs text-muted-foreground">AI-generated draft. Verify against the source record before accepting — nothing is written to the chart until you do.</p>}
    </div>
  );
}
