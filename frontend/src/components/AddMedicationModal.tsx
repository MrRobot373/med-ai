import { useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import { useCreateMedication } from "@/api/clinical";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue";
const labelClass = "mb-1 block text-sm font-medium text-navy";

export function AddMedicationModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [frequency, setFrequency] = useState("");
  const create = useCreateMedication(patientId);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        medication_name: name,
        ...(dose ? { dose } : {}),
        ...(frequency ? { frequency } : {}),
      },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Modal title="Add Medication" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="medication_name" className={labelClass}>
            Medication
          </label>
          <input
            id="medication_name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Latanoprost 0.005%"
            className={inputClass}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="dose" className={labelClass}>
              Dose (optional)
            </label>
            <input id="dose" value={dose} onChange={(e) => setDose(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="frequency" className={labelClass}>
              Frequency (optional)
            </label>
            <input
              id="frequency"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              placeholder="e.g. nightly, both eyes"
              className={inputClass}
            />
          </div>
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
            {create.isPending ? "Adding…" : "Add Medication"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
