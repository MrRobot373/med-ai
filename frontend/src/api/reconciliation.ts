import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/reconciliation.py
export type ReconciliationStatus = "newly_detected" | "not_in_document" | "matched_unchanged" | "matched_review";

export interface ReconciliationItem {
  status: ReconciliationStatus;
  current_medication_id: string | null;
  current_medication_name: string | null;
  current_dose: string | null;
  current_frequency: string | null;
  document_medication_name: string | null;
  document_dose: string | null;
  document_route: string | null;
  document_frequency: string | null;
  source_page: number | null;
  source_excerpt: string | null;
}

export interface ReconciliationResult {
  report_id: string;
  report_title: string;
  items: ReconciliationItem[];
}

export function useMedicationReconciliation(reportId: string | undefined) {
  return useQuery({
    queryKey: ["reports", reportId, "medication-reconciliation"],
    queryFn: () => apiFetch<ReconciliationResult>(`/api/reports/${reportId}/medication-reconciliation`),
    enabled: Boolean(reportId),
  });
}
