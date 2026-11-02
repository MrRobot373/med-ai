import { MoreHorizontal, Pencil, Pill, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { useInvalidatePatient, useSubList } from "@/api/hooks";
import type { Medication } from "@/api/types";
import { Badge, Button, Card, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, EmptyState, Segmented, Skeleton, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { RecordDialog, type FieldDef } from "@/components/clinical/RecordDialog";
import { api } from "@/lib/api";
import { fmtDate, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

const FIELDS: FieldDef[] = [
  { name: "name", label: "Medication", required: true, wide: true, placeholder: "e.g. Metformin" },
  { name: "dose", label: "Dose", placeholder: "e.g. 500 mg" },
  { name: "route", label: "Route", placeholder: "e.g. oral" },
  { name: "frequency", label: "Frequency", placeholder: "e.g. twice daily" },
  { name: "indication", label: "Indication" },
  { name: "start_date", label: "Start date", type: "date" },
  { name: "end_date", label: "End date", type: "date" },
  { name: "status", label: "Status", type: "select", options: [{ value: "active", label: "Active" }, { value: "on_hold", label: "On hold" }, { value: "stopped", label: "Stopped" }] },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
];

export default function MedicationsTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = useSubList<Medication>(patient.id, "medications");
  const invalidate = useInvalidatePatient();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [editing, setEditing] = useState<Medication | null | undefined>(undefined);
  const rows = (data ?? []).filter((m) => filter === "all" || m.status === "active");

  const remove = async (m: Medication) => {
    await api(`/api/patients/${patient.id}/medications/${m.id}`, { method: "DELETE" });
    toast.success(`${m.name} removed`);
    invalidate(patient.id);
  };
  const stop = async (m: Medication) => {
    await api(`/api/patients/${patient.id}/medications/${m.id}`, { method: "PATCH", body: { status: "stopped", end_date: new Date().toISOString().slice(0, 10) } });
    toast.success(`${m.name} marked as stopped`);
    invalidate(patient.id);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={filter} onChange={setFilter} options={[{ value: "active", label: "Active" }, { value: "all", label: "All history" }]} />
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate("../tools?tool=med_reconciliation", { relative: "path" })}>Reconcile with a document</Button>
          {canWrite && <Button size="sm" onClick={() => setEditing(null)}><Plus /> Add medication</Button>}
        </div>
      </div>
      <Card className="overflow-hidden">
        {isLoading ? <div className="p-4"><Skeleton className="h-40" /></div> : rows.length === 0 ? (
          <EmptyState icon={<Pill />} title="No medications documented" description="Nothing is assumed — only documented medications are listed." />
        ) : (
          <Table>
            <THead><TR><TH>Medication</TH><TH>Dose & schedule</TH><TH>Indication</TH><TH>Started</TH><TH>Status</TH><TH /></TR></THead>
            <TBody>
              {rows.map((m) => (
                <TR key={m.id}>
                  <TD><div className="font-medium">{m.name}</div>{m.source !== "manual" && <div className="text-xs text-muted-foreground">from {m.source}</div>}</TD>
                  <TD className="text-muted-foreground">{[m.dose, m.route, m.frequency].filter(Boolean).join(" · ") || <span className="italic">not recorded</span>}</TD>
                  <TD className="text-muted-foreground">{m.indication ?? "—"}</TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{fmtDate(m.start_date)}</TD>
                  <TD><Badge tone={m.status === "active" ? "success" : m.status === "on_hold" ? "warning" : "neutral"}>{titleCase(m.status)}</Badge></TD>
                  <TD className="text-right">
                    {canWrite && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild><Button variant="ghost" size="icon-xs" aria-label="Actions"><MoreHorizontal /></Button></DropdownMenuTrigger>
                        <DropdownMenuContent>
                          <DropdownMenuItem onSelect={() => setEditing(m)}><Pencil /> Edit</DropdownMenuItem>
                          {m.status === "active" && <DropdownMenuItem onSelect={() => stop(m)}><Pill /> Mark stopped</DropdownMenuItem>}
                          <DropdownMenuItem danger onSelect={() => remove(m)}><Trash2 /> Delete entry</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
      <RecordDialog
        open={editing !== undefined} onOpenChange={(o) => !o && setEditing(undefined)} icon={<Pill />}
        title={editing ? `Edit ${editing.name}` : "Add medication"} fields={FIELDS} initial={editing ?? { status: "active" }}
        endpoint={editing ? `/api/patients/${patient.id}/medications/${editing.id}` : `/api/patients/${patient.id}/medications`}
        method={editing ? "PATCH" : "POST"} onSaved={() => invalidate(patient.id)}
      />
    </div>
  );
}
