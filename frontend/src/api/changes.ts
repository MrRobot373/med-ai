import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/changes.py
export interface ConditionChange {
  id: string;
  display: string;
  onset_date: string | null;
  resolved_date: string | null;
}

export interface MedicationStartStop {
  id: string;
  medication_name: string;
  dose: string | null;
  start_date: string | null;
  stop_date: string | null;
}

export interface MedicationDoseChange {
  previous_medication_name: string;
  current_medication_name: string;
  previous_dose: string | null;
  current_dose: string | null;
  stopped_id: string;
  started_id: string;
}

export interface AllergyChange {
  id: string;
  substance: string;
  recorded_at: string;
}

export interface ObservationChange {
  normalized_name: string;
  display_name: string;
  previous_value: number | null;
  previous_unit: string | null;
  previous_date: string | null;
  current_value: number | null;
  current_unit: string | null;
  current_date: string | null;
  direction: "increased" | "decreased" | "unchanged";
}

export interface ChangesSummary {
  patient_id: string;
  since: string;
  conditions_new: ConditionChange[];
  conditions_resolved: ConditionChange[];
  medications_started: MedicationStartStop[];
  medications_stopped: MedicationStartStop[];
  medications_dose_changed: MedicationDoseChange[];
  allergies_new: AllergyChange[];
  observations_changed: ObservationChange[];
  observations_new_tests: string[];
}

export function hasAnyChanges(summary: ChangesSummary): boolean {
  return (
    summary.conditions_new.length > 0 ||
    summary.conditions_resolved.length > 0 ||
    summary.medications_started.length > 0 ||
    summary.medications_stopped.length > 0 ||
    summary.medications_dose_changed.length > 0 ||
    summary.allergies_new.length > 0 ||
    summary.observations_changed.length > 0 ||
    summary.observations_new_tests.length > 0
  );
}

export function usePatientChanges(patientId: string, since: string | undefined) {
  return useQuery({
    queryKey: ["patients", patientId, "changes", since],
    queryFn: () => apiFetch<ChangesSummary>(`/api/patients/${patientId}/changes?since=${since}`),
    enabled: Boolean(since),
  });
}
