import { Modal } from "@/components/Modal";
import { useMedicationReconciliation } from "@/api/reconciliation";
import type { ReconciliationItem, ReconciliationStatus } from "@/api/reconciliation";

const STATUS_LABEL: Record<ReconciliationStatus, string> = {
  newly_detected: "Newly detected in this document",
  not_in_document: "Not mentioned in this document",
  matched_unchanged: "No difference detected",
  matched_review: "Possible difference — review",
};

const STATUS_TONE: Record<ReconciliationStatus, string> = {
  newly_detected: "text-primary-blue",
  not_in_document: "text-muted-text",
  matched_unchanged: "text-success",
  matched_review: "text-danger",
};

function medLine(name: string | null, dose: string | null, frequency: string | null): string {
  if (!name) return "—";
  return [name, dose, frequency].filter(Boolean).join(" · ");
}

export function ReconciliationModal({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const { data, isLoading, isError, error } = useMedicationReconciliation(reportId);

  return (
    <Modal title="Medication Reconciliation" onClose={onClose}>
      <p className="text-xs text-muted-text">
        Compares this document's mentioned medications against the patient's current recorded list (spec §36). This
        is a read-only comparison — nothing here changes the medication list automatically; add or stop medications
        from the Medications tab after review.
      </p>

      {isLoading && <p className="mt-3 text-sm text-muted-text">Comparing…</p>}
      {isError && <p className="mt-3 text-sm text-danger">Could not load reconciliation: {(error as Error).message}</p>}

      {data && data.items.length === 0 && (
        <p className="mt-3 text-sm text-muted-text">
          No medications were recorded on the system side or detected in this document.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-muted-text">
                <th className="py-2 pr-3">Current (system)</th>
                <th className="py-2 pr-3">Detected (this document)</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: ReconciliationItem, index: number) => (
                <tr key={index} className="border-b border-border align-top">
                  <td className="py-2 pr-3 text-navy">
                    {medLine(item.current_medication_name, item.current_dose, item.current_frequency)}
                  </td>
                  <td className="py-2 pr-3 text-navy">
                    {medLine(item.document_medication_name, item.document_dose, item.document_frequency)}
                    {item.source_page !== null && (
                      <span className="ml-1 text-xs text-muted-text">(p. {item.source_page})</span>
                    )}
                  </td>
                  <td className={`py-2 text-xs font-medium ${STATUS_TONE[item.status]}`}>
                    {STATUS_LABEL[item.status]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
