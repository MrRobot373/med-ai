import { useState } from "react";
import { Plus } from "lucide-react";
import { Card } from "@/components/Card";
import { AddMedicationModal } from "@/components/AddMedicationModal";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientMedications, useStopMedication } from "@/api/clinical";
import { useCanWrite } from "@/api/auth";

export default function MedicationsTab() {
  const patient = usePatientContext();
  const { data: medications } = usePatientMedications(patient.id);
  const stopMedication = useStopMedication(patient.id);
  const [showAddMedication, setShowAddMedication] = useState(false);
  const canWrite = useCanWrite();

  const active = medications?.filter((m) => m.active) ?? [];
  const stopped = medications?.filter((m) => !m.active) ?? [];

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-navy">Medications</h2>
          {canWrite && (
            <button
              type="button"
              onClick={() => setShowAddMedication(true)}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary-blue hover:underline"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Medication
            </button>
          )}
        </div>

        {medications?.length === 0 && <p className="mt-3 text-sm text-muted-text">No medications documented.</p>}

        {active.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">Active</h3>
            <ul className="mt-2 divide-y divide-border">
              {active.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 py-3">
                  <div>
                    <div className="text-sm text-navy">
                      {m.medication_name} {m.dose}
                    </div>
                    <div className="text-xs text-muted-text">
                      {m.frequency}
                      {m.start_date && <> · started {m.start_date}</>}
                    </div>
                  </div>
                  {canWrite && (
                    <button
                      type="button"
                      onClick={() => stopMedication.mutate(m.id)}
                      disabled={stopMedication.isPending}
                      className="shrink-0 text-xs font-medium text-danger hover:underline disabled:opacity-60"
                    >
                      Stop
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {stopped.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">
              Discontinued — history preserved
            </h3>
            <ul className="mt-2 divide-y divide-border">
              {stopped.map((m) => (
                <li key={m.id} className="py-3">
                  <div className="text-sm text-muted-text line-through decoration-border">
                    {m.medication_name} {m.dose}
                  </div>
                  <div className="text-xs text-muted-text">
                    {m.start_date && <>{m.start_date} – </>}
                    {m.stop_date}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {showAddMedication && <AddMedicationModal patientId={patient.id} onClose={() => setShowAddMedication(false)} />}
    </div>
  );
}
