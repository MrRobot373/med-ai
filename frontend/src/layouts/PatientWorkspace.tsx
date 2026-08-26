import { useState } from "react";
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { usePatient, type PatientOut } from "@/api/patients";
import { useCanWrite } from "@/api/auth";
import { NewEncounterModal } from "@/components/NewEncounterModal";

const TABS = [
  { to: "overview", label: "Overview" },
  { to: "timeline", label: "Timeline" },
  { to: "reports", label: "Reports" },
  { to: "labs", label: "Labs" },
  { to: "medications", label: "Medications" },
  { to: "conditions", label: "Conditions" },
  { to: "clinical-ai", label: "Clinical AI" },
];

const SEX_LABEL: Record<PatientOut["sex"], string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  unknown: "Unknown",
};

/** Tab pages read the already-fetched patient via this instead of re-querying
 * GET /api/patients/{id} themselves — one fetch per workspace visit, not one per tab. */
export function usePatientContext() {
  return useOutletContext<PatientOut>();
}

export function PatientWorkspace() {
  const { patientId } = useParams<{ patientId: string }>();
  const { data: patient, isLoading, isError } = usePatient(patientId);
  const [showNewEncounter, setShowNewEncounter] = useState(false);
  const navigate = useNavigate();
  const canWrite = useCanWrite();

  if (isLoading) {
    return <div className="mx-auto max-w-6xl py-12 text-sm text-muted-text">Loading patient…</div>;
  }

  if (isError || !patient) {
    return (
      <div className="mx-auto max-w-6xl space-y-3 py-12 text-center">
        <p className="text-sm text-muted-text">Patient not found.</p>
        <button
          type="button"
          onClick={() => navigate("/patients")}
          className="text-sm font-medium text-primary-blue hover:underline"
        >
          Back to Patients
        </button>
      </div>
    );
  }

  const displayName = patient.preferred_name || `${patient.first_name} ${patient.last_name}`;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Current patient context is always visible — spec §24: never let the clinician
         forget which patient is active. */}
      <div className="gms-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-navy">{displayName}</h1>
              {patient.synthetic && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                  SYNTHETIC DEMO DATA — NOT A REAL PATIENT
                </span>
              )}
              {patient.archived && (
                <span className="rounded-full bg-light-blue px-2 py-0.5 text-[11px] font-medium text-muted-text">
                  Archived
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-muted-text">
              {patient.mrn} · {patient.age} years · {SEX_LABEL[patient.sex]}
            </p>
          </div>
          {canWrite && (
            <button
              type="button"
              onClick={() => setShowNewEncounter(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90"
            >
              <Plus className="h-4 w-4" />
              New Encounter
            </button>
          )}
        </div>

        <nav className="mt-4 flex flex-wrap gap-1 border-t border-border pt-3">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-light-blue text-primary-blue" : "text-muted-text hover:bg-light-blue hover:text-navy"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <Outlet context={patient} />

      {showNewEncounter && <NewEncounterModal patientId={patient.id} onClose={() => setShowNewEncounter(false)} />}
    </div>
  );
}
