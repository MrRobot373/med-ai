import { useQueryClient } from "@tanstack/react-query";
import {
  Activity, AlertTriangle, Archive, ArchiveRestore, CalendarClock, ChevronLeft, Download, FileText, FlaskConical, LayoutDashboard,
  MessagesSquare, MoreHorizontal, Pill, Pencil, Stethoscope, Trash2, Wand2, HeartPulse,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { useMe, useOverview, usePatient } from "@/api/hooks";
import {
  Avatar, Badge, Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, EmptyState, Skeleton,
} from "@/components/ui";
import { ConfirmDialog } from "@/components/clinical/ConfirmDialog";
import { PatientFormDialog } from "@/features/patients/PatientFormDialog";
import { api } from "@/lib/api";
import { cn, fmtDate, sexLabel } from "@/lib/utils";

const TABS = [
  { to: "", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "timeline", label: "Timeline", icon: Activity },
  { to: "documents", label: "Reports & imaging", icon: FileText },
  { to: "results", label: "Results", icon: FlaskConical },
  { to: "medications", label: "Medications", icon: Pill },
  { to: "problems", label: "Problems", icon: HeartPulse },
  { to: "encounters", label: "Encounters", icon: CalendarClock },
  { to: "assistant", label: "Assistant", icon: MessagesSquare },
  { to: "tools", label: "Clinical tools", icon: Wand2 },
];

export default function PatientWorkspace() {
  const { patientId = "" } = useParams();
  const { data: patient, isLoading, error } = usePatient(patientId);
  const { data: overview } = useOverview(patientId);
  const { data: me } = useMe();
  const [editOpen, setEditOpen] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const canWrite = me?.role !== "viewer";

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-10" /><Skeleton className="h-96" /></div>;
  if (error || !patient) return <EmptyState icon={<AlertTriangle />} title="Patient not found" description="The chart may have been removed." action={<Button variant="secondary" asChild><Link to="/patients">Back to patients</Link></Button>} />;

  const allergies = overview?.allergies.filter((a) => a.status === "active") ?? [];
  const activeProblems = overview?.conditions.filter((c) => c.status === "active") ?? [];
  const setStatus = async (status: "active" | "archived") => {
    await api(`/api/patients/${patient.id}`, { method: "PATCH", body: { status } });
    qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    qc.invalidateQueries({ queryKey: ["patients"] });
    toast.success(status === "archived" ? "Chart archived" : "Chart restored");
  };
  const exportSummary = async () => {
    const text = await api<string>(`/api/patients/${patient.id}/export`);
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${patient.mrn}-summary.md` });
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/patients" className="glass no-print flex size-10 shrink-0 items-center justify-center rounded-full border border-white/70 text-muted-foreground shadow-card hover:text-foreground dark:border-white/[0.06]" aria-label="Back to patients"><ChevronLeft className="size-4" /></Link>
          <Avatar name={patient.full_name} size="lg" className="ring-4 ring-white/70 dark:ring-white/5" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-[1.35rem] font-semibold tracking-tight">{patient.full_name}</h1>
              {patient.status === "archived" && <Badge tone="warning"><Archive /> Archived</Badge>}
              {patient.synthetic && <Badge tone="outline">Synthetic demo</Badge>}
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8rem] text-muted-foreground">
              <span className="font-semibold text-foreground/80">{patient.mrn}</span>
              <span>{patient.age ?? "—"} y · {sexLabel(patient.sex)}</span>
              <span>DOB {fmtDate(patient.date_of_birth)}</span>
              {patient.blood_group && <span>Blood {patient.blood_group}</span>}
            </div>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5 xl:ml-4">
          {overview ? (allergies.length ? allergies.map((a) => (
            <Badge key={a.id} tone="danger" title={a.reaction ?? ""}><AlertTriangle /> {a.substance}{a.severity !== "unknown" ? ` · ${a.severity}` : ""}</Badge>
          )) : <Badge tone="warning"><AlertTriangle /> Allergies not documented</Badge>) : <Skeleton className="h-5 w-40" />}
          {activeProblems.slice(0, 2).map((c) => <Badge key={c.id} tone="neutral" className="max-w-[14rem] truncate">{c.name}</Badge>)}
          {activeProblems.length > 2 && <Badge tone="outline">+{activeProblems.length - 2}</Badge>}
        </div>
        <div className="no-print flex shrink-0 items-center gap-2 xl:ml-auto">
          <Button variant="secondary" className="rounded-full" onClick={() => navigate("assistant")}><MessagesSquare /> Ask about patient</Button>
          <Button variant="strong" className="rounded-full" onClick={() => navigate("tools")}><Stethoscope /> Clinical tools</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="secondary" size="icon" className="rounded-full" aria-label="More actions"><MoreHorizontal /></Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              {canWrite && <DropdownMenuItem onSelect={() => setEditOpen(true)}><Pencil /> Edit demographics</DropdownMenuItem>}
              <DropdownMenuItem onSelect={exportSummary}><Download /> Export summary (.md)</DropdownMenuItem>
              {canWrite && (patient.status === "active"
                ? <DropdownMenuItem onSelect={() => setStatus("archived")}><Archive /> Archive chart</DropdownMenuItem>
                : <DropdownMenuItem onSelect={() => setStatus("active")}><ArchiveRestore /> Restore chart</DropdownMenuItem>)}
              {me?.role === "admin" && (
                <>
                  <DropdownMenuSeparator />
                  <ConfirmDialog
                    danger title="Delete patient permanently?" confirmLabel="Delete permanently"
                    description="This removes the chart, documents, results, AI history and search index entries. This cannot be undone."
                    onConfirm={async () => { await api(`/api/patients/${patient.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["patients"] }); toast.success("Patient deleted"); navigate("/patients"); }}
                    trigger={<DropdownMenuItem danger onSelect={(e) => e.preventDefault()}><Trash2 /> Delete permanently</DropdownMenuItem>}
                  />
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <nav className="glass no-print mb-5 flex w-fit max-w-full gap-1 overflow-x-auto rounded-full border border-white/70 p-1 shadow-card dark:border-white/[0.06]">
        {TABS.map((t) => (
          <NavLink
            key={t.label} to={t.to} end={t.end}
            className={({ isActive }) => cn("flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[0.8rem] font-medium transition-all", isActive ? "bg-strong text-strong-foreground shadow-card" : "text-muted-foreground hover:bg-muted/80 hover:text-foreground")}
          >
            <t.icon className="size-4" /> {t.label}
            {t.to === "documents" && overview && <span className="rounded-full bg-black/10 px-1.5 text-[0.65rem] num dark:bg-white/10">{overview.counts.documents}</span>}
          </NavLink>
        ))}
      </nav>

      <Outlet context={{ patient, canWrite }} />
      <PatientFormDialog open={editOpen} onOpenChange={setEditOpen} patient={patient} />
    </div>
  );
}
