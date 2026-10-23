import { useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CalendarPlus, Check, FileUp, UserCheck, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { qk, useMe, useToday } from "@/api/hooks";
import type { Appointment } from "@/api/types";
import { PatientPicker } from "@/components/clinical/PatientPicker";
import { Avatar, Button, Card, CardHeader, EmptyState, Field, Input, Skeleton } from "@/components/ui";
import { PatientFormDialog } from "@/features/patients/PatientFormDialog";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, greeting, sexLabel } from "@/lib/utils";
import { ReportUpload } from "./ReportUpload";

type Picked = { id: string; full_name: string; mrn: string } | null;

export default function FrontDeskHome() {
  const { data: me } = useMe();
  const { data, isLoading } = useToday();
  const qc = useQueryClient();
  const [registerOpen, setRegisterOpen] = useState(false);
  const [patient, setPatient] = useState<Picked>(null);
  const [time, setTime] = useState("");
  const [reason, setReason] = useState("");
  const [uploadFor, setUploadFor] = useState<Picked>(null);
  const [busy, setBusy] = useState(false);

  const add = async () => {
    if (!patient) return;
    setBusy(true);
    try {
      await api("/api/appointments", { method: "POST", body: { patient_id: patient.id, time: time || null, reason: reason || null } });
      toast.success(`${patient.full_name} added to today's list`);
      setPatient(null); setTime(""); setReason("");
      qc.invalidateQueries({ queryKey: qk.today });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not add");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-[var(--gap)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div>
          <div className="text-label">{fmtDate(new Date(), "EEEE, d MMMM yyyy")}</div>
          <h1 className="mt-0.5 text-[1.35rem] font-semibold tracking-tight">{greeting()}{me ? `, ${me.full_name.split(" ")[0]}` : ""}</h1>
        </div>
        <Button variant="strong" className="rounded-full sm:ml-auto" onClick={() => setRegisterOpen(true)}><UserPlus /> Register new patient</Button>
      </div>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader icon={<CalendarDays />} title="Today's list" description={data ? `${data.appointments.length} patients · ${data.counts.arrived} waiting · ${data.counts.seen} seen` : undefined} />
          <div className="card-pad pt-3">
            {isLoading ? <Skeleton className="h-48" /> : !data?.appointments.length ? (
              <EmptyState compact icon={<CalendarDays />} title="Nobody on the list yet" description="Add patients as they book or walk in." />
            ) : <ul className="divide-y divide-border/60">{data.appointments.map((a) => <DeskRow key={a.id} a={a} onUpload={() => setUploadFor({ id: a.patient_id, full_name: a.patient?.name ?? "", mrn: a.patient?.mrn ?? "" })} />)}</ul>}
          </div>
        </Card>

        <div className="min-w-0 space-y-[var(--gap)]">
          <Card>
            <CardHeader icon={<CalendarPlus />} title="Add to today's list" />
            <div className="card-pad space-y-3">
              <PatientPicker value={patient} onChange={setPatient} placeholder="Search patient by name or MRN" />
              <div className="grid gap-2 sm:grid-cols-[7rem_1fr]">
                <Field label="Time"><Input type="time" value={time} onChange={(e) => setTime(e.target.value)} /></Field>
                <Field label="Reason"><Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Follow-up with reports" /></Field>
              </div>
              <Button variant="strong" className="rounded-full" disabled={!patient} loading={busy} onClick={add}><CalendarPlus /> Add</Button>
            </div>
          </Card>
          <Card>
            <CardHeader icon={<FileUp />} title="Upload a report" description="Reports the patient brings in go straight to their chart and to the doctor's review list" />
            <div className="card-pad space-y-3">
              <PatientPicker value={uploadFor} onChange={setUploadFor} placeholder="Whose report is it?" />
              {uploadFor ? <ReportUpload key={uploadFor.id} patientId={uploadFor.id} compact /> : <p className="text-xs text-muted-foreground">Choose the patient first. The report's name and date of birth are checked against the chart.</p>}
            </div>
          </Card>
        </div>
      </div>
      <PatientFormDialog open={registerOpen} onOpenChange={setRegisterOpen} />
    </div>
  );
}

function DeskRow({ a, onUpload }: { a: Appointment; onUpload: () => void }) {
  const qc = useQueryClient();
  const setStatus = async (status: Appointment["status"]) => {
    try {
      await api(`/api/appointments/${a.id}`, { method: "PATCH", body: { status } });
      qc.invalidateQueries({ queryKey: qk.today });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed");
    }
  };
  return (
    <li className="flex flex-wrap items-center gap-3 py-2.5">
      <span className="w-11 text-[0.78rem] font-semibold text-muted-foreground num">{a.time ?? "—"}</span>
      <Avatar name={a.patient?.name ?? "?"} size="sm" />
      <div className="min-w-0 flex-1">
        <Link to={`/patients/${a.patient_id}`} className="text-[0.85rem] font-semibold hover:underline">{a.patient?.name}</Link>
        <div className="text-[0.72rem] text-muted-foreground">{a.patient?.mrn} · {a.patient?.age ?? "—"} y · {sexLabel(a.patient?.sex ?? "unknown")}{a.patient?.phone ? ` · ${a.patient.phone}` : ""} · {a.reason ?? "—"}</div>
      </div>
      <span className={cn("rounded-full px-2 py-0.5 text-[0.68rem] font-medium", a.status === "arrived" ? "bg-primary-soft text-primary-soft-foreground" : a.status === "seen" ? "bg-success-soft text-success-foreground" : "bg-muted text-muted-foreground")}>
        {{ expected: "Expected", arrived: "Waiting", seen: "Seen", cancelled: "Cancelled" }[a.status]}
      </span>
      <div className="flex gap-1">
        {a.status === "expected" && <Button size="xs" variant="secondary" onClick={() => setStatus("arrived")}><UserCheck /> Arrived</Button>}
        {a.status === "seen" && <Check className="size-4 text-success" />}
        <Button size="xs" variant="ghost" onClick={onUpload}><FileUp /> Report</Button>
        {a.status === "expected" && <Button size="icon-xs" variant="ghost" aria-label="Cancel" onClick={() => setStatus("cancelled")}><X /></Button>}
      </div>
    </li>
  );
}
