import { useState } from "react";
import { Plus, Search } from "lucide-react";
import { AddPatientModal } from "@/components/AddPatientModal";
import { PatientCard } from "@/components/PatientCard";
import { usePatients } from "@/api/patients";
import { useCanWrite } from "@/api/auth";

export default function PatientsPage() {
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const { data: patients, isLoading, isError, error } = usePatients(query, includeArchived);
  const canWrite = useCanWrite();

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-navy">Patients</h1>
          <p className="text-sm text-muted-text">Search, review, and manage patient records.</p>
        </div>
        {canWrite && (
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90"
          >
            <Plus className="h-4 w-4" />
            Add Patient
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-text" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or MRN…"
            aria-label="Search patients"
            className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-muted-text">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
            className="rounded border-border"
          />
          Include archived
        </label>
      </div>

      {isError && (
        <div role="alert" className="gms-card border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          Could not load patients: {(error as Error).message}
        </div>
      )}

      {isLoading && <p className="text-sm text-muted-text">Loading patients…</p>}

      {!isLoading && patients?.length === 0 && (
        <div className="gms-card p-8 text-center text-sm text-muted-text">
          {query ? "No patients match your search." : "No patients yet — add one to get started."}
        </div>
      )}

      {patients && patients.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {patients.map((patient) => (
            <PatientCard key={patient.id} patient={patient} />
          ))}
        </div>
      )}

      {showAddModal && <AddPatientModal onClose={() => setShowAddModal(false)} />}
    </div>
  );
}
