import { useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import { useCreateAllergy } from "@/api/clinical";
import type { AllergySeverity } from "@/api/clinical";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue";
const labelClass = "mb-1 block text-sm font-medium text-navy";

export function AddAllergyModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const [substance, setSubstance] = useState("");
  const [reaction, setReaction] = useState("");
  const [severity, setSeverity] = useState<AllergySeverity>("unknown");
  const create = useCreateAllergy(patientId);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { substance, severity, ...(reaction ? { reaction } : {}) },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Modal title="Add Allergy" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="substance" className={labelClass}>
            Substance
          </label>
          <input
            id="substance"
            required
            value={substance}
            onChange={(e) => setSubstance(e.target.value)}
            placeholder="e.g. Penicillin"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="reaction" className={labelClass}>
            Reaction (optional)
          </label>
          <input
            id="reaction"
            value={reaction}
            onChange={(e) => setReaction(e.target.value)}
            placeholder="e.g. Anaphylaxis, rash"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="severity" className={labelClass}>
            Severity
          </label>
          <select
            id="severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as AllergySeverity)}
            className={inputClass}
          >
            <option value="unknown">Unknown</option>
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
          </select>
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
            {create.isPending ? "Adding…" : "Add Allergy"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
