import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

export type EncounterType = "outpatient" | "inpatient" | "telehealth" | "procedure" | "other";
export type EncounterStatus = "planned" | "active" | "completed" | "archived";

export interface EncounterOut {
  id: string;
  patient_id: string;
  encounter_number: string;
  encounter_type: EncounterType;
  start_datetime: string;
  end_datetime: string | null;
  status: EncounterStatus;
  chief_complaint: string | null;
  clinician_note: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface EncounterCreatePayload {
  encounter_type: EncounterType;
  chief_complaint?: string;
  clinician_note?: string;
}

const encountersKey = (patientId: string) => ["patients", patientId, "encounters"] as const;

export function usePatientEncounters(patientId: string) {
  return useQuery({
    queryKey: encountersKey(patientId),
    queryFn: () => apiFetch<EncounterOut[]>(`/api/patients/${patientId}/encounters`),
  });
}

export function useCreateEncounter(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EncounterCreatePayload) =>
      apiFetch<EncounterOut>(`/api/patients/${patientId}/encounters`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: encountersKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
      queryClient.invalidateQueries({ queryKey: ["patients", "search"] });
    },
  });
}

export function useUpdateEncounter(patientId: string, encounterId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Pick<EncounterOut, "status" | "chief_complaint" | "clinician_note">>) =>
      apiFetch<EncounterOut>(`/api/encounters/${encounterId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: encountersKey(patientId) });
      queryClient.invalidateQueries({ queryKey: ["patients", patientId, "timeline"] });
    },
  });
}
