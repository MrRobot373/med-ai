import { Link } from "react-router-dom";
import { AlertTriangle, Sparkles } from "lucide-react";
import { Card } from "@/components/Card";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientConditions } from "@/api/clinical";
import { usePatientAllergies } from "@/api/clinical";
import { usePatientMedications } from "@/api/clinical";
import { usePatientEncounters } from "@/api/encounters";
import { usePatientReports } from "@/api/reports";

const SEVERITY_STYLE: Record<string, string> = {
  severe: "bg-danger/10 text-danger",
  moderate: "bg-amber-100 text-amber-700",
  mild: "bg-light-blue text-primary-blue",
  unknown: "bg-light-blue text-muted-text",
};

export default function OverviewTab() {
  const patient = usePatientContext();
  const { data: conditions } = usePatientConditions(patient.id);
  const { data: allergies } = usePatientAllergies(patient.id);
  const { data: medications } = usePatientMedications(patient.id);
  const { data: encounters } = usePatientEncounters(patient.id);
  const { data: reports } = usePatientReports(patient.id);

  const activeConditions = conditions?.filter((c) => c.status === "active") ?? [];
  const activeMedications = medications?.filter((m) => m.active) ?? [];
  const recentEncounters = encounters?.slice(0, 3) ?? [];
  const recentReports = reports?.slice(0, 3) ?? [];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-navy">Active Conditions</h2>
        {activeConditions.length === 0 ? (
          <p className="mt-2 text-sm text-muted-text">No active conditions documented.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {activeConditions.map((c) => (
              <li key={c.id} className="text-sm text-navy">
                {c.display}
                {c.onset_date && <span className="ml-2 text-xs text-muted-text">since {c.onset_date}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="h-4 w-4 text-danger" />
          <h2 className="text-sm font-semibold text-navy">Allergies</h2>
        </div>
        {allergies === undefined ? null : allergies.length === 0 ? (
          <p className="mt-2 text-sm text-muted-text">
            No allergies documented — this means not yet recorded, not confirmed absent.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {allergies.map((a) => (
              <li key={a.id} className="flex items-center justify-between text-sm">
                <span className="text-navy">
                  {a.substance}
                  {a.reaction && <span className="text-muted-text"> — {a.reaction}</span>}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY_STYLE[a.severity]}`}>
                  {a.severity}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-semibold text-navy">Current Medications</h2>
        {activeMedications.length === 0 ? (
          <p className="mt-2 text-sm text-muted-text">No active medications documented.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {activeMedications.map((m) => (
              <li key={m.id} className="text-sm text-navy">
                {m.medication_name}
                {m.dose && <span className="text-muted-text"> {m.dose}</span>}
                {m.frequency && <span className="text-muted-text"> — {m.frequency}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-semibold text-navy">Recent Encounters</h2>
        {recentEncounters.length === 0 ? (
          <p className="mt-2 text-sm text-muted-text">No encounters yet.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {recentEncounters.map((e) => (
              <li key={e.id} className="text-sm">
                <div className="text-navy">{e.chief_complaint || e.encounter_type}</div>
                <div className="text-xs text-muted-text">
                  {new Date(e.start_datetime).toLocaleDateString()} · {e.status}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-navy">Recent Reports</h2>
          <Link to="../reports" className="text-xs font-medium text-primary-blue hover:underline">
            View all
          </Link>
        </div>
        {recentReports.length === 0 ? (
          <p className="mt-2 text-sm text-muted-text">No reports uploaded yet.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {recentReports.map((r) => (
              <li key={r.id} className="text-sm">
                <div className="text-navy">{r.title}</div>
                <div className="text-xs text-muted-text">
                  {r.report_date ?? new Date(r.created_at).toLocaleDateString()} · {r.ingestion_status}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5 lg:col-span-2">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-4 w-4 text-primary-blue" />
          <h2 className="text-sm font-semibold text-navy">AI Case Summary</h2>
        </div>
        <p className="mt-2 text-sm text-muted-text">
          Generated case summaries arrive with Clinical AI (Phases 08–10) — evidence-grounded, sourced
          from this patient's actual record. Nothing is fabricated here in the meantime.{" "}
          <Link to="../clinical-ai" className="text-primary-blue hover:underline">
            View Clinical AI status
          </Link>
          .
        </p>
      </Card>
    </div>
  );
}
