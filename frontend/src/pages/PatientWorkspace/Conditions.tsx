import { useState } from "react";
import { AlertTriangle, Plus } from "lucide-react";
import { Card } from "@/components/Card";
import { AddConditionModal } from "@/components/AddConditionModal";
import { AddAllergyModal } from "@/components/AddAllergyModal";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientConditions, usePatientAllergies, useResolveCondition } from "@/api/clinical";
import { useCanWrite } from "@/api/auth";

const SEVERITY_STYLE: Record<string, string> = {
  severe: "bg-danger/10 text-danger",
  moderate: "bg-amber-100 text-amber-700",
  mild: "bg-light-blue text-primary-blue",
  unknown: "bg-light-blue text-muted-text",
};

const CONDITION_STATUS_STYLE: Record<string, string> = {
  active: "bg-success/10 text-success",
  resolved: "bg-light-blue text-muted-text",
  inactive: "bg-light-blue text-muted-text",
};

export default function ConditionsTab() {
  const patient = usePatientContext();
  const { data: conditions } = usePatientConditions(patient.id);
  const { data: allergies } = usePatientAllergies(patient.id);
  const resolveCondition = useResolveCondition(patient.id);
  const [showAddCondition, setShowAddCondition] = useState(false);
  const [showAddAllergy, setShowAddAllergy] = useState(false);
  const canWrite = useCanWrite();

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-navy">Conditions</h2>
          {canWrite && (
            <button
              type="button"
              onClick={() => setShowAddCondition(true)}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary-blue hover:underline"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Condition
            </button>
          )}
        </div>

        {conditions?.length === 0 && <p className="mt-3 text-sm text-muted-text">No conditions documented.</p>}

        {conditions && conditions.length > 0 && (
          <ul className="mt-3 divide-y divide-border">
            {conditions.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <div className="text-sm text-navy">{c.display}</div>
                  <div className="text-xs text-muted-text">
                    {c.onset_date && <>Onset {c.onset_date} · </>}
                    {c.resolved_date && <>Resolved {c.resolved_date} · </>}
                    {c.verification_status}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${CONDITION_STATUS_STYLE[c.status]}`}>
                    {c.status}
                  </span>
                  {c.status === "active" && canWrite && (
                    <button
                      type="button"
                      onClick={() => resolveCondition.mutate(c.id)}
                      disabled={resolveCondition.isPending}
                      className="text-xs font-medium text-primary-blue hover:underline disabled:opacity-60"
                    >
                      Mark resolved
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4 text-danger" />
            <h2 className="text-sm font-semibold text-navy">Allergies</h2>
          </div>
          {canWrite && (
            <button
              type="button"
              onClick={() => setShowAddAllergy(true)}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary-blue hover:underline"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Allergy
            </button>
          )}
        </div>

        {allergies?.length === 0 && (
          <p className="mt-3 text-sm text-muted-text">
            No allergies documented — this means not yet recorded, not confirmed absent.
          </p>
        )}

        {allergies && allergies.length > 0 && (
          <ul className="mt-3 divide-y divide-border">
            {allergies.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <div className="text-sm text-navy">{a.substance}</div>
                  {a.reaction && <div className="text-xs text-muted-text">{a.reaction}</div>}
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY_STYLE[a.severity]}`}>
                  {a.severity}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {showAddCondition && <AddConditionModal patientId={patient.id} onClose={() => setShowAddCondition(false)} />}
      {showAddAllergy && <AddAllergyModal patientId={patient.id} onClose={() => setShowAddAllergy(false)} />}
    </div>
  );
}
