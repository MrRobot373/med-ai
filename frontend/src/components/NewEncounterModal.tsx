import { useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import { useCreateEncounter } from "@/api/encounters";
import type { EncounterType } from "@/api/encounters";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue";
const labelClass = "mb-1 block text-sm font-medium text-navy";

export function NewEncounterModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const [encounterType, setEncounterType] = useState<EncounterType>("outpatient");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicianNote, setClinicianNote] = useState("");
  const create = useCreateEncounter(patientId);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        encounter_type: encounterType,
        ...(chiefComplaint ? { chief_complaint: chiefComplaint } : {}),
        ...(clinicianNote ? { clinician_note: clinicianNote } : {}),
      },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Modal title="New Encounter" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="encounter_type" className={labelClass}>
            Encounter type
          </label>
          <select
            id="encounter_type"
            value={encounterType}
            onChange={(e) => setEncounterType(e.target.value as EncounterType)}
            className={inputClass}
          >
            <option value="outpatient">Outpatient</option>
            <option value="inpatient">Inpatient</option>
            <option value="telehealth">Telehealth</option>
            <option value="procedure">Procedure</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label htmlFor="chief_complaint" className={labelClass}>
            Chief complaint
          </label>
          <input
            id="chief_complaint"
            value={chiefComplaint}
            onChange={(e) => setChiefComplaint(e.target.value)}
            placeholder="e.g. Blurry vision, worse at night"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="clinician_note" className={labelClass}>
            Notes (optional)
          </label>
          <textarea
            id="clinician_note"
            rows={4}
            value={clinicianNote}
            onChange={(e) => setClinicianNote(e.target.value)}
            className={inputClass}
          />
        </div>

        {create.isError && (
          <div role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
            {(create.error as Error).message}
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium text-muted-text hover:bg-light-blue hover:text-navy"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Starting…" : "Start Encounter"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
