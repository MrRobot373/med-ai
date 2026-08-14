import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

export type VerificationStatus = "confirmed" | "provisional" | "unconfirmed";

// --- Conditions --------------------------------------------------------------------

export type ConditionStatus = "active" | "resolved" | "inactive";

export interface ConditionOut {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  code: string | null;
  display: string;
  status: ConditionStatus;
  onset_date: string | null;
  resolved_date: string | null;
  verification_status: VerificationStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConditionCreatePayload {
  display: string;
  status?: ConditionStatus;
  onset_date?: string;
  notes?: string;
}

const conditionsKey = (patientId: string) => ["patients", patientId, "conditions"] as const;

export function usePatientConditions(patientId: string) {
  return useQuery({
    queryKey: conditionsKey(patientId),
    queryFn: () => apiFetch<ConditionOut[]>(`/api/patients/${patientId}/conditions`),
  });
}

export function useCreateCondition(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConditionCreatePayload) =>
      apiFetch<ConditionOut>(`/api/patients/${patientId}/conditions`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: conditionsKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
      queryClient.invalidateQueries({ queryKey: ["patients", "search"] });
    },
  });
}

export function useResolveCondition(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conditionId: string) =>
      apiFetch<ConditionOut>(`/api/conditions/${conditionId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "resolved" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: conditionsKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
      queryClient.invalidateQueries({ queryKey: ["patients", "search"] });
    },
  });
}

// --- Allergies -----------------------------------------------------------------------

export type AllergySeverity = "mild" | "moderate" | "severe" | "unknown";
export type AllergyStatus = "active" | "inactive" | "resolved";

export interface AllergyOut {
  id: string;
  patient_id: string;
  substance: string;
  reaction: string | null;
  severity: AllergySeverity;
  status: AllergyStatus;
  source: string | null;
  verification_status: VerificationStatus;
  created_at: string;
  updated_at: string;
}

export interface AllergyCreatePayload {
  substance: string;
  reaction?: string;
  severity?: AllergySeverity;
}

const allergiesKey = (patientId: string) => ["patients", patientId, "allergies"] as const;

export function usePatientAllergies(patientId: string) {
  return useQuery({
    queryKey: allergiesKey(patientId),
    queryFn: () => apiFetch<AllergyOut[]>(`/api/patients/${patientId}/allergies`),
  });
}

export function useCreateAllergy(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AllergyCreatePayload) =>
      apiFetch<AllergyOut>(`/api/patients/${patientId}/allergies`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: allergiesKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
    },
  });
}

// --- Medications -----------------------------------------------------------------------

export interface MedicationOut {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  medication_name: string;
  normalized_name: string | null;
  dose: string | null;
  dose_unit: string | null;
  route: string | null;
  frequency: string | null;
  start_date: string | null;
  stop_date: string | null;
  active: boolean;
  source: string | null;
  verification_status: VerificationStatus;
  created_at: string;
  updated_at: string;
}

export interface MedicationCreatePayload {
  medication_name: string;
  dose?: string;
  dose_unit?: string;
  route?: string;
  frequency?: string;
  start_date?: string;
}

const medicationsKey = (patientId: string) => ["patients", patientId, "medications"] as const;

export function usePatientMedications(patientId: string) {
  return useQuery({
    queryKey: medicationsKey(patientId),
    queryFn: () => apiFetch<MedicationOut[]>(`/api/patients/${patientId}/medications`),
  });
}

export function useCreateMedication(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MedicationCreatePayload) =>
      apiFetch<MedicationOut>(`/api/patients/${patientId}/medications`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: medicationsKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
    },
  });
}

export function useStopMedication(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (medicationId: string) =>
      apiFetch<MedicationOut>(`/api/medications/${medicationId}/stop`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: medicationsKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
    },
  });
}
