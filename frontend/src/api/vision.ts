import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/api/client";

// Mirrors backend/app/schemas/vision.py / app/models/vision_analysis.py
export type VisionAnalysisStatus = "success" | "failed" | "not_applicable";

export interface VisionAnalysisOut {
  report_id: string;
  status: VisionAnalysisStatus;
  model: string | null;
  analysis_error: string | null;
  created_at: string;
  updated_at: string;
  image_type: string | null;
  visible_text: string[];
  observations: string[];
  measurements_visible: string[];
  clinical_entities: string[];
  quality_limitations: string[];
  uncertainties: string[];
}

export interface ComparisonEvidenceOut {
  source_title: string;
  page: number | null;
  section: string | null;
  excerpt: string;
}

export interface VisionCompareResponse {
  previous_report_id: string;
  current_report_id: string;
  previous_findings: string[];
  current_findings: string[];
  observable_changes: string[];
  differences: string[];
  limitations: string[];
  clinical_evidence: ComparisonEvidenceOut[];
}

/** Mime types vision analysis (and comparison) can actually run against — mirrors
 * `services/vision.py`'s `_ANALYZABLE_IMAGE_TYPES` + DICOM. Used to decide when to
 * show vision UI at all rather than rendering it for every report type. */
export const VISION_ANALYZABLE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "application/dicom"]);

const visionKey = (reportId: string | undefined) => ["reports", reportId, "vision"] as const;

/** A report that has genuinely never had analysis run (spec's own NOT_APPLICABLE vs.
 * "no row at all" distinction) 404s — treated as "no result yet", not an error to
 * alert on, matching how `useMe` treats a 401 as a real signal rather than a fetch
 * failure. */
export function useVisionAnalysis(reportId: string | undefined) {
  return useQuery({
    queryKey: visionKey(reportId),
    queryFn: async () => {
      try {
        return await apiFetch<VisionAnalysisOut>(`/api/reports/${reportId}/vision`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: Boolean(reportId),
  });
}

export function useAnalyzeReport(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<VisionAnalysisOut>(`/api/reports/${reportId}/vision/analyze`, { method: "POST" }),
    onSuccess: (result) => {
      queryClient.setQueryData(visionKey(reportId), result);
    },
  });
}

export function useCompareVision(patientId: string) {
  return useMutation({
    mutationFn: (payload: { previous_report_id: string; current_report_id: string }) =>
      apiFetch<VisionCompareResponse>(`/api/patients/${patientId}/vision/compare`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}
