import { AlertTriangle, HeartPulse, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useInvalidatePatient, useSubList } from "@/api/hooks";
import type { Allergy, Condition } from "@/api/types";
import { Badge, Button, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui";
import { SEVERITY_TONE } from "@/components/clinical/badges";
import { RecordDialog, type FieldDef } from "@/components/clinical/RecordDialog";
import { api } from "@/lib/api";
import { fmtDate, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

const CONDITION_FIELDS: FieldDef[] = [
  { name: "name", label: "Problem / diagnosis", required: true, wide: true },
  { name: "code", label: "ICD-10 code", placeholder: "optional, e.g. E11.9" },
  { name: "status", label: "Status", type: "select", options: ["active", "suspected", "resolved", "inactive"].map((v) => ({ value: v, label: titleCase(v) })) },
  { name: "onset_date", label: "Onset", type: "date" },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
];
const ALLERGY_FIELDS: FieldDef[] = [
  { name: "substance", label: "Substance", required: true, wide: true, placeholder: "e.g. Penicillin" },
  { name: "reaction", label: "Reaction", placeholder: "e.g. urticaria" },
  { name: "severity", label: "Severity", type: "select", options: ["unknown", "mild", "moderate", "severe"].map((v) => ({ value: v, label: titleCase(v) })) },
  { name: "status", label: "Status", type: "select", options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }, { value: "refuted", label: "Refuted" }] },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
];

function ItemActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
      <Button variant="ghost" size="icon-xs" onClick={onEdit} aria-label="Edit"><Pencil /></Button>
      <Button variant="ghost" size="icon-xs" onClick={onDelete} aria-label="Delete"><Trash2 /></Button>
    </div>
  );
}

export default function ProblemsTab() {
  const { patient, canWrite } = useWorkspace();
  const conditions = useSubList<Condition>(patient.id, "conditions");
  const allergies = useSubList<Allergy>(patient.id, "allergies");
  const invalidate = useInvalidatePatient();
  const [cond, setCond] = useState<Condition | null | undefined>(undefined);
  const [alg, setAlg] = useState<Allergy | null | undefined>(undefined);
  const del = async (kind: string, id: string) => { await api(`/api/patients/${patient.id}/${kind}/${id}`, { method: "DELETE" }); toast.success("Removed"); invalidate(patient.id); };
  const order = { active: 0, suspected: 1, inactive: 2, resolved: 3 } as Record<string, number>;

  return (
    <div className="grid gap-[var(--gap)] lg:grid-cols-[1.4fr_1fr]">
      <Card>
        <CardHeader title="Problem list" description="Diagnoses and conditions, current and historical" icon={<HeartPulse />} actions={canWrite && <Button size="sm" onClick={() => setCond(null)}><Plus /> Add</Button>} />
        <div className="card-pad">
          {conditions.isLoading ? <Skeleton className="h-40" /> : !conditions.data?.length ? <EmptyState compact title="No problems documented" /> : (
            <div className="divide-y">
              {[...conditions.data].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9)).map((c) => (
                <div key={c.id} className="group flex items-start gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{c.name}</span>{c.code && <span className="font-mono text-xs text-muted-foreground">{c.code}</span>}</div>
                    <div className="mt-0.5 text-xs text-muted-foreground">Onset {fmtDate(c.onset_date)}{c.notes ? ` · ${c.notes}` : ""}</div>
                  </div>
                  <Badge tone={c.status === "active" ? "warning" : c.status === "suspected" ? "info" : "neutral"}>{titleCase(c.status)}</Badge>
                  {canWrite && <ItemActions onEdit={() => setCond(c)} onDelete={() => del("conditions", c.id)} />}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
      <Card>
        <CardHeader title="Allergies & intolerances" icon={<AlertTriangle />} actions={canWrite && <Button size="sm" onClick={() => setAlg(null)}><Plus /> Add</Button>} />
        <div className="card-pad">
          {allergies.isLoading ? <Skeleton className="h-32" /> : !allergies.data?.length ? (
            <div className="rounded-lg border border-warning/30 bg-warning-soft p-3.5 text-sm text-warning-foreground">
              <div className="font-medium">No allergies documented</div>
              <p className="mt-1 text-xs opacity-90">This is not the same as “no known allergies”. Record NKDA explicitly once confirmed with the patient.</p>
            </div>
          ) : (
            <div className="divide-y">
              {allergies.data.map((a) => (
                <div key={a.id} className="group flex items-start gap-3 py-3">
                  <div className="min-w-0 flex-1"><div className="font-medium">{a.substance}</div><div className="text-xs text-muted-foreground">{a.reaction ?? "Reaction not recorded"}{a.status !== "active" ? ` · ${a.status}` : ""}</div></div>
                  <Badge tone={SEVERITY_TONE[a.severity]}>{titleCase(a.severity)}</Badge>
                  {canWrite && <ItemActions onEdit={() => setAlg(a)} onDelete={() => del("allergies", a.id)} />}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
      <RecordDialog open={cond !== undefined} onOpenChange={(o) => !o && setCond(undefined)} icon={<HeartPulse />} title={cond ? "Edit problem" : "Add problem"} fields={CONDITION_FIELDS} initial={cond ?? undefined}
        endpoint={cond ? `/api/patients/${patient.id}/conditions/${cond.id}` : `/api/patients/${patient.id}/conditions`} method={cond ? "PATCH" : "POST"} onSaved={() => invalidate(patient.id)} />
      <RecordDialog open={alg !== undefined} onOpenChange={(o) => !o && setAlg(undefined)} icon={<AlertTriangle />} title={alg ? "Edit allergy" : "Add allergy"} fields={ALLERGY_FIELDS} initial={alg ?? undefined}
        endpoint={alg ? `/api/patients/${patient.id}/allergies/${alg.id}` : `/api/patients/${patient.id}/allergies`} method={alg ? "PATCH" : "POST"} onSaved={() => invalidate(patient.id)} />
    </div>
  );
}
