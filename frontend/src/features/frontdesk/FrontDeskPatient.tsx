import { ChevronLeft, FileText, Pencil } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { usePatientDocuments } from "@/api/hooks";
import type { Patient } from "@/api/types";
import { DocStatusBadge } from "@/components/clinical/badges";
import { Avatar, Button, Card, CardHeader, EmptyState, KeyValue, Skeleton } from "@/components/ui";
import { PatientFormDialog } from "@/features/patients/PatientFormDialog";
import { fmtDate, sexLabel } from "@/lib/utils";
import { ReportUpload } from "./ReportUpload";

/** The front desk sees registration details and paperwork only — never clinical content. */
export function FrontDeskPatient({ patient }: { patient: Patient }) {
  const { data: docs, isLoading } = usePatientDocuments(patient.id);
  const [edit, setEdit] = useState(false);
  return (
    <div className="space-y-[var(--gap)]">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="glass flex size-10 items-center justify-center rounded-full border border-white/70 text-muted-foreground shadow-card dark:border-white/[0.06]" aria-label="Back"><ChevronLeft className="size-4" /></Link>
        <Avatar name={patient.full_name} size="lg" />
        <div>
          <h1 className="text-[1.35rem] font-semibold tracking-tight">{patient.full_name}</h1>
          <div className="text-[0.8rem] text-muted-foreground">{patient.mrn} · {patient.age ?? "—"} y · {sexLabel(patient.sex)}</div>
        </div>
        <Button variant="secondary" className="ml-auto rounded-full" onClick={() => setEdit(true)}><Pencil /> Edit details</Button>
      </div>
      <div className="grid gap-[var(--gap)] lg:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader title="Registration" />
          <div className="card-pad divide-y divide-border/60">
            <KeyValue label="Date of birth" value={fmtDate(patient.date_of_birth)} />
            <KeyValue label="Phone" value={patient.phone ?? "—"} />
            <KeyValue label="Email" value={patient.email ?? "—"} />
            <KeyValue label="Address" value={patient.address ?? "—"} />
            <KeyValue label="Blood group" value={patient.blood_group ?? "—"} />
          </div>
        </Card>
        <div className="min-w-0 space-y-[var(--gap)]">
          <Card>
            <CardHeader title="Upload a report" description="Goes to the doctor for review" />
            <div className="card-pad"><ReportUpload patientId={patient.id} /></div>
          </Card>
          <Card>
            <CardHeader title="Filed documents" description="Titles and processing status" />
            <div className="card-pad">
              {isLoading ? <Skeleton className="h-24" /> : !docs?.length ? <EmptyState compact icon={<FileText />} title="Nothing filed yet" /> : (
                <ul className="divide-y divide-border/60">{docs.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-2 text-[0.82rem]"><FileText className="size-4 text-muted-foreground" /><span className="min-w-0 flex-1 truncate font-medium">{d.title}</span><span className="text-xs text-muted-foreground">{fmtDate(d.document_date ?? d.created_at)}</span><DocStatusBadge status={d.status} /></li>
                ))}</ul>
              )}
            </div>
          </Card>
        </div>
      </div>
      <PatientFormDialog open={edit} onOpenChange={setEdit} patient={patient} />
    </div>
  );
}
