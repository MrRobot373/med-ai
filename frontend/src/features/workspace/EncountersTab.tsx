import { CalendarClock, FileSignature, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useInvalidatePatient, useSubList } from "@/api/hooks";
import type { Encounter } from "@/api/types";
import { Badge, Button, Card, EmptyState, Skeleton } from "@/components/ui";
import { RecordDialog, type FieldDef } from "@/components/clinical/RecordDialog";
import { fmtDate, fmtDateTime, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

const VITALS = [["bp", "Blood pressure", "e.g. 128/82"], ["hr", "Heart rate", "bpm"], ["temp_c", "Temperature", "°C"], ["spo2", "SpO₂", "%"], ["weight_kg", "Weight", "kg"], ["rr", "Respiratory rate", "/min"]] as const;
const FIELDS: FieldDef[] = [
  { name: "reason", label: "Reason for visit", required: true, wide: true, placeholder: "Chief complaint" },
  { name: "type", label: "Type", type: "select", options: ["outpatient", "follow_up", "telehealth", "emergency", "inpatient", "procedure"].map((v) => ({ value: v, label: titleCase(v) })) },
  { name: "status", label: "Status", type: "select", options: ["in_progress", "completed", "planned", "cancelled"].map((v) => ({ value: v, label: titleCase(v) })) },
  { name: "started_at", label: "Date & time", type: "datetime" },
  ...VITALS.map(([k, label, ph]) => ({ name: `v_${k}`, label, placeholder: ph })),
  { name: "notes", label: "Clinical notes", type: "textarea", wide: true, placeholder: "History, examination, assessment and plan…" },
];

const toBody = (v: Record<string, any>) => {
  const vitals: Record<string, any> = {};
  const out: Record<string, any> = {};
  for (const [k, val] of Object.entries(v)) {
    if (k.startsWith("v_")) { if (val !== null && val !== "") vitals[k.slice(2)] = val; } else out[k] = val;
  }
  return { ...out, vitals };
};

export default function EncountersTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = useSubList<Encounter>(patient.id, "encounters");
  const invalidate = useInvalidatePatient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState<Encounter | null | undefined>(undefined);
  const initial = editing ? { ...editing, ...Object.fromEntries(Object.entries(editing.vitals ?? {}).map(([k, v]) => [`v_${k}`, v])) } : { type: "outpatient", status: "in_progress", started_at: new Date().toISOString() };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">{canWrite && <Button size="sm" onClick={() => setEditing(null)}><Plus /> Start encounter</Button>}</div>
      {isLoading ? <Skeleton className="h-60" /> : !data?.length ? <Card><EmptyState icon={<CalendarClock />} title="No encounters" description="Start an encounter to document a visit, then draft a SOAP note from it." /></Card> : (
        <div className="space-y-3">
          {data.map((e) => (
            <Card key={e.id} className="card-pad">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                <div className="w-28 shrink-0"><div className="text-sm font-semibold">{fmtDate(e.started_at, "d MMM yyyy")}</div><div className="text-xs text-muted-foreground">{fmtDateTime(e.started_at).split(", ")[1]}</div></div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{e.reason ?? "Encounter"}</span><Badge>{titleCase(e.type)}</Badge><Badge tone={e.status === "completed" ? "success" : e.status === "in_progress" ? "primary" : "neutral"}>{titleCase(e.status)}</Badge></div>
                  {Object.keys(e.vitals ?? {}).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(e.vitals).map(([k, v]) => <span key={k} className="rounded-md bg-muted px-2 py-0.5 text-xs"><span className="text-muted-foreground">{VITALS.find((x) => x[0] === k)?.[1] ?? k}</span> <span className="font-medium num">{String(v)}</span></span>)}</div>
                  )}
                  {e.notes && <p className="mt-2 whitespace-pre-wrap text-[0.85rem] leading-relaxed text-muted-foreground">{e.notes}</p>}
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Button size="sm" variant="soft" onClick={() => navigate(`../tools?tool=soap&encounter=${e.id}`, { relative: "path" })}><FileSignature /> Draft SOAP</Button>
                  {canWrite && <Button size="icon-sm" variant="ghost" onClick={() => setEditing(e)} aria-label="Edit"><Pencil /></Button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <RecordDialog
        open={editing !== undefined} onOpenChange={(o) => !o && setEditing(undefined)} icon={<CalendarClock />}
        title={editing ? "Edit encounter" : "Start encounter"} fields={FIELDS} initial={initial} transform={toBody}
        endpoint={editing ? `/api/patients/${patient.id}/encounters/${editing.id}` : `/api/patients/${patient.id}/encounters`}
        method={editing ? "PATCH" : "POST"} onSaved={() => invalidate(patient.id)}
      />
    </div>
  );
}
