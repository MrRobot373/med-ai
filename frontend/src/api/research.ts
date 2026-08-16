import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { ClinicalModuleRunOut } from "@/api/clinicalModules";

// Mirrors backend/app/models/web_cache.py
export type WebSource = "pubmed" | "fda" | "clinicaltrials" | "searxng";
export type DateRange = "any" | "5y" | "1y";

export interface ResearchStatusOut {
  enabled: boolean;
  searxng_reachable: boolean;
  sources_available: WebSource[];
}

export interface ResearchCitation {
  label: string;
  source_title: string;
  url: string | null;
  collection: "patient_documents" | "medical_knowledge" | "web_cache";
  page: number | null;
  section: string | null;
  excerpt: string;
}

export interface ResearchPayload {
  evidence_summary: string;
  consensus: string;
  conflicting_evidence: string[];
  patient_applicability: string;
  exclusion_criteria: string[];
  limitations: string[];
  evidence_quality: string;
  citations: ResearchCitation[];
  research_mode_used: boolean;
  deidentification: { removed_count: number; removed_categories: string[] };
}

export function useResearchStatus() {
  return useQuery({
    queryKey: ["research", "status"],
    queryFn: () => apiFetch<ResearchStatusOut>("/api/research/status"),
  });
}

export function useResearchRuns(patientId?: string) {
  return useQuery({
    queryKey: ["research", "runs", patientId ?? "all"],
    queryFn: () => apiFetch<ClinicalModuleRunOut[]>(`/api/research/runs${patientId ? `?patient_id=${patientId}` : ""}`),
  });
}

export interface ResearchQueryPayload {
  question: string;
  patient_id?: string;
  sources: WebSource[];
  date_range: DateRange;
  prefer_reviews: boolean;
}

export function useRunResearchQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResearchQueryPayload) =>
      apiFetch<ClinicalModuleRunOut>("/api/research/query", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research", "runs"] });
    },
  });
}
