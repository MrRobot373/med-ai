import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Modal } from "@/components/Modal";
import { useCreatePatient, type Sex } from "@/api/patients";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue";
const labelClass = "mb-1 block text-sm font-medium text-navy";

export function AddPatientModal({ onClose }: { onClose: () => void }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [sex, setSex] = useState<Sex>("unknown");
  const [phone, setPhone] = useState("");
  const create = useCreatePatient();
  const navigate = useNavigate();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        first_name: firstName,
        last_name: lastName,
        date_of_birth: dateOfBirth,
        sex,
        ...(phone ? { phone } : {}),
      },
      {
        onSuccess: (patient) => {
          onClose();
          navigate(`/patients/${patient.id}`);
        },
      },
    );
  }

  return (
    <Modal title="Add Patient" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="first_name" className={labelClass}>
              First name
            </label>
            <input
              id="first_name"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="last_name" className={labelClass}>
              Last name
            </label>
            <input
              id="last_name"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="dob" className={labelClass}>
              Date of birth
            </label>
            <input
              id="dob"
              type="date"
              required
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="sex" className={labelClass}>
              Sex
            </label>
            <select id="sex" value={sex} onChange={(e) => setSex(e.target.value as Sex)} className={inputClass}>
              <option value="unknown">Unknown</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="phone" className={labelClass}>
            Phone (optional)
          </label>
          <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} className={inputClass} />
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
            {create.isPending ? "Adding…" : "Add Patient"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
