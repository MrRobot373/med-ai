import { useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import { useCreateCondition } from "@/api/clinical";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue";
const labelClass = "mb-1 block text-sm font-medium text-navy";

export function AddConditionModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const [display, setDisplay] = useState("");
  const [onsetDate, setOnsetDate] = useState("");
  const create = useCreateCondition(patientId);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { display, ...(onsetDate ? { onset_date: onsetDate } : {}) },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Modal title="Add Condition" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="condition_display" className={labelClass}>
            Condition
          </label>
          <input
            id="condition_display"
            required
            value={display}
            onChange={(e) => setDisplay(e.target.value)}
            placeholder="e.g. Primary open-angle glaucoma, bilateral"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="onset_date" className={labelClass}>
            Onset date (optional)
          </label>
          <input
            id="onset_date"
            type="date"
            value={onsetDate}
            onChange={(e) => setOnsetDate(e.target.value)}
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
            {create.isPending ? "Adding…" : "Add Condition"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
