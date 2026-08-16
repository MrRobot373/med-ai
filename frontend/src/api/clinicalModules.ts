import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/models/clinical_module_run.py / app/modules/*.py
export type ClinicalModuleType = "summary" | "soap" | "entity_extraction" | "differential_support" | "guideline_qa" | "report_comparison";

export type SummaryType = "concise" | "discharge" | "encounter" | "progress_note";

export interface ClinicalModuleRunOut {
  id: string;
  module_type: ClinicalModuleType;
  patient_id: string | null;
  encounter_id: string | null;
  input_params: Record<string, unknown>;
  payload: Record<string, unknown> | null;
  model: string | null;
  generation_error: string | null;
  created_at: string;
}

// --- Payload shapes (spec §63's schemas) ---

export interface SummaryPayload {
  summary: string;
  key_points: string[];
  source_trace: string[];
}

export interface SOAPPayload {
  subjective: Record<string, string>;
  objective: Record<string, string>;
  assessment: string[];
  plan: string[];
  missing_information: string[];
  source_trace: string[];
}

export interface ExtractedEntity {
  text: string;
  category: "condition" | "medication" | "allergy" | "procedure" | "lab_finding" | "symptom" | "other";
  context: string;
}

export interface EntityExtractionPayload {
  entities: ExtractedEntity[];
}

export interface DifferentialCandidate {
  condition: string;
  supporting_findings: string[];
  findings_against: string[];
  missing_information: string[];
  evidence_ids: string[];
}

export interface DifferentialPayload {
  patient_summary: string;
  differential: DifferentialCandidate[];
  red_flags: string[];
  recommended_clarifications: string[];
  evidence_quality: string;
}

export interface GuidelineCitation {
  label: string;
  source_title: string;
  page: number | null;
  section: string | null;
  excerpt: string;
}

export interface GuidelineQAPayload {
  answer: string;
  no_guideline_found: boolean;
  evidence_quality: string;
  citations: GuidelineCitation[];
}

export interface NumericChange {
  name: string;
  previous_value: number | null;
  current_value: number | null;
  unit: string | null;
  delta: number | null;
  percent_change: number | null;
  direction: "increased" | "decreased" | "unchanged" | "new" | "resolved";
}

export interface ComparisonEvidence {
  source_title: string;
  page: number | null;
  section: string | null;
  excerpt: string;
}

export interface ReportComparisonPayload {
  previous_report_id: string;
  current_report_id: string;
  numeric_changes: NumericChange[];
  narrative_differences: string[];
  limitations: string[];
  clinical_evidence: ComparisonEvidence[];
}

// --- History ---

const runsKey = (patientId: string | undefined, moduleType?: ClinicalModuleType) =>
  ["clinical-runs", patientId ?? "global", moduleType ?? "all"] as const;

export function usePatientRuns(patientId: string, moduleType?: ClinicalModuleType) {
  return useQuery({
    queryKey: runsKey(patientId, moduleType),
    queryFn: () =>
      apiFetch<ClinicalModuleRunOut[]>(
        `/api/patients/${patientId}/clinical/runs${moduleType ? `?module_type=${moduleType}` : ""}`,
      ),
  });
}

export function useGlobalRuns(moduleType?: ClinicalModuleType) {
  return useQuery({
    queryKey: runsKey(undefined, moduleType),
    queryFn: () => apiFetch<ClinicalModuleRunOut[]>(`/api/clinical/runs${moduleType ? `?module_type=${moduleType}` : ""}`),
  });
}

// --- Mutations — each is a real generation-triggering action, not a cached query ---

function invalidateFor(queryClient: ReturnType<typeof useQueryClient>, run: ClinicalModuleRunOut) {
  queryClient.invalidateQueries({ queryKey: runsKey(run.patient_id ?? undefined) });
  queryClient.invalidateQueries({ queryKey: runsKey(run.patient_id ?? undefined, run.module_type) });
}

export function useCreateSummary(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { summary_type: SummaryType; encounter_id?: string }) =>
      apiFetch<ClinicalModuleRunOut>(`/api/patients/${patientId}/clinical/summary`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}

export function useCreateSOAP(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { encounter_id: string }) =>
      apiFetch<ClinicalModuleRunOut>(`/api/patients/${patientId}/clinical/soap`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}

export function useCreateEntityExtraction(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { report_id?: string; encounter_id?: string }) =>
      apiFetch<ClinicalModuleRunOut>(`/api/patients/${patientId}/clinical/entities`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}

export function useCreateDifferential(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { encounter_id?: string }) =>
      apiFetch<ClinicalModuleRunOut>(`/api/patients/${patientId}/clinical/differential`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}

export function useCreateReportComparison(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { previous_report_id: string; current_report_id: string }) =>
      apiFetch<ClinicalModuleRunOut>(`/api/patients/${patientId}/clinical/report-comparison`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}

export function useCreateGuidelineQA() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { question: string }) =>
      apiFetch<ClinicalModuleRunOut>("/api/clinical/guideline-qa", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (run) => invalidateFor(queryClient, run),
  });
}
