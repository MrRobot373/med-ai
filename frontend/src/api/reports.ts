import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/api/client";

// Mirrors backend/app/schemas/report.py / app/models/report.py
export type ReportType =
  | "lab_report"
  | "imaging_report"
  | "consultation_note"
  | "discharge_summary"
  | "referral_letter"
  | "other";

export type IngestionStatus = "queued" | "processing" | "completed" | "failed";
export type ExtractionStatus = "pending" | "success" | "partial" | "failed" | "not_applicable";
export type PatientMatchStatus = "matched" | "mismatch" | "unconfirmed" | "not_checked";

export interface ReportListItem {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  title: string;
  report_type: ReportType;
  report_date: string | null;
  source_filename: string;
  mime_type: string;
  file_size_bytes: number;
  ingestion_status: IngestionStatus;
  extraction_status: ExtractionStatus;
  patient_match_status: PatientMatchStatus;
  source_patient_name: string | null;
  source_mrn: string | null;
  page_count: number | null;
  ocr_used: boolean;
  archived: boolean;
  created_at: string;
}

export interface ReportPage {
  page: number;
  text: string;
  method: "text" | "ocr" | "metadata" | "none";
}

export interface ReportDetail extends ReportListItem {
  extraction_error: string | null;
  pages: ReportPage[];
}

const IN_PROGRESS: IngestionStatus[] = ["queued", "processing"];
const reportsKey = (patientId: string) => ["patients", patientId, "reports"] as const;

export function reportFileUrl(reportId: string): string {
  return `/api/reports/${reportId}/file`;
}

export function reportPreviewUrl(reportId: string): string {
  return `/api/reports/${reportId}/preview`;
}

export function usePatientReports(patientId: string, includeArchived = false) {
  return useQuery({
    queryKey: [...reportsKey(patientId), includeArchived],
    queryFn: () =>
      apiFetch<ReportListItem[]>(
        `/api/patients/${patientId}/reports${includeArchived ? "?include_archived=true" : ""}`,
      ),
    // Auto-refresh while anything is still queued/processing so status badges update
    // live without the clinician having to reload — stops once everything settles.
    refetchInterval: (query) => {
      const data = query.state.data as ReportListItem[] | undefined;
      return data?.some((r) => IN_PROGRESS.includes(r.ingestion_status)) ? 2000 : false;
    },
  });
}

export function useReport(reportId: string | undefined) {
  return useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => apiFetch<ReportDetail>(`/api/reports/${reportId}`),
    enabled: Boolean(reportId),
  });
}

export function useUploadReport(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, allowDuplicate }: { file: File; allowDuplicate?: boolean }) => {
      const formData = new FormData();
      formData.append("file", file);
      const params = allowDuplicate ? "?allow_duplicate=true" : "";
      // apiFetch always sets Content-Type: application/json — wrong for multipart, so
      // this bypasses it directly rather than teaching the shared helper about forms.
      const res = await fetch(`/api/patients/${patientId}/reports${params}`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const raw = await res.text().catch(() => "");
        let message = raw || res.statusText;
        try {
          const parsed = JSON.parse(raw) as { detail?: string };
          if (typeof parsed.detail === "string") message = parsed.detail;
        } catch {
          // keep fallback
        }
        throw new ApiError(res.status, message);
      }
      return (await res.json()) as ReportListItem;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reportsKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
    },
  });
}

export function useConfirmReportMatch(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) =>
      apiFetch<ReportListItem>(`/api/reports/${reportId}/confirm-match`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportsKey(patientId) }),
  });
}

export function useArchiveReport(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) => apiFetch<ReportListItem>(`/api/reports/${reportId}/archive`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportsKey(patientId) }),
  });
}
