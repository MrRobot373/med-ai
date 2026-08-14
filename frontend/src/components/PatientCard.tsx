import { Link } from "react-router-dom";
import { Card } from "@/components/Card";
import type { PatientListItem } from "@/api/patients";

function formatLastVisit(iso: string | null): string {
  if (!iso) return "No visits yet";
  const date = new Date(iso);
  const today = new Date();
  const isToday = date.toDateString() === today.toDateString();
  if (isToday) return "Today";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const SEX_LABEL: Record<PatientListItem["sex"], string> = {
  male: "M",
  female: "F",
  other: "Other",
  unknown: "—",
};

export function PatientCard({ patient }: { patient: PatientListItem }) {
  const displayName = patient.preferred_name || `${patient.first_name} ${patient.last_name}`;

  return (
    <Link to={`/patients/${patient.id}`} className="block">
      <Card className="h-full p-4 transition-shadow hover:shadow-md">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-navy">{displayName}</h3>
              {patient.synthetic && (
                <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                  SYNTHETIC
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-text">
              {patient.age} {SEX_LABEL[patient.sex]}
            </p>
          </div>
        </div>

        <dl className="mt-3 space-y-1 text-xs text-muted-text">
          <div className="flex justify-between">
            <dt>MRN</dt>
            <dd className="font-medium text-navy">{patient.mrn}</dd>
          </div>
          <div className="flex justify-between">
            <dt>Last Visit</dt>
            <dd className="font-medium text-navy">{formatLastVisit(patient.last_encounter_at)}</dd>
          </div>
        </dl>

        {patient.active_condition_names.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {patient.active_condition_names.map((name) => (
              <span key={name} className="rounded-full bg-light-blue px-2 py-0.5 text-[11px] text-primary-blue">
                {name}
              </span>
            ))}
          </div>
        )}
      </Card>
    </Link>
  );
}
