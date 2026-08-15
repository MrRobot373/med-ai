import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/observation.py
export type ExtractionMethod = "table" | "inline" | "manual";

export interface ObservationOut {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  report_id: string | null;
  observation_name: string;
  normalized_name: string;
  value_numeric: number | null;
  value_text: string | null;
  unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  abnormal_flag: boolean | null;
  measured_at: string | null;
  source_page: number | null;
  extraction_method: ExtractionMethod;
  source_excerpt: string | null;
  clinician_verified: boolean;
  created_at: string;
}

export interface TrendPoint {
  observation_id: string;
  measured_at: string | null;
  value_numeric: number | null;
  value_text: string | null;
  unit: string | null;
  abnormal_flag: boolean | null;
  report_id: string | null;
  source_page: number | null;
}

export interface ObservationTrend {
  normalized_name: string;
  display_name: string;
  unit: string | null;
  points: TrendPoint[];
  unit_conflict: boolean;
  excluded_units: string[];
}

export function usePatientObservations(patientId: string) {
  return useQuery({
    queryKey: ["patients", patientId, "observations"],
    queryFn: () => apiFetch<ObservationOut[]>(`/api/patients/${patientId}/observations`),
  });
}

export function usePatientObservationTrends(patientId: string) {
  return useQuery({
    queryKey: ["patients", patientId, "observations", "trends"],
    queryFn: () => apiFetch<ObservationTrend[]>(`/api/patients/${patientId}/observations/trends`),
  });
}
