import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/patient.py
export type Sex = "male" | "female" | "other" | "unknown";

export interface PatientOut {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  preferred_name: string | null;
  date_of_birth: string;
  sex: Sex;
  phone: string | null;
  email: string | null;
  notes: string | null;
  synthetic: boolean;
  archived: boolean;
  created_at: string;
  updated_at: string;
  age: number;
}

export interface PatientListItem {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  preferred_name: string | null;
  sex: Sex;
  date_of_birth: string;
  synthetic: boolean;
  archived: boolean;
  last_encounter_at: string | null;
  active_condition_names: string[];
  age: number;
}

export interface PatientCreatePayload {
  mrn?: string;
  first_name: string;
  last_name: string;
  preferred_name?: string;
  date_of_birth: string;
  sex: Sex;
  phone?: string;
  email?: string;
  notes?: string;
}

export type PatientUpdatePayload = Partial<Omit<PatientCreatePayload, "mrn">>;

const PATIENTS_KEY = ["patients"] as const;
const patientKey = (id: string) => ["patients", id] as const;

export function usePatients(query: string, includeArchived: boolean) {
  return useQuery({
    queryKey: [...PATIENTS_KEY, "search", query, includeArchived],
    queryFn: () =>
      apiFetch<PatientListItem[]>(
        `/api/patients?${new URLSearchParams({
          ...(query ? { q: query } : {}),
          ...(includeArchived ? { include_archived: "true" } : {}),
        }).toString()}`,
      ),
  });
}

export function usePatient(patientId: string | undefined) {
  return useQuery({
    queryKey: patientId ? patientKey(patientId) : ["patients", "none"],
    queryFn: () => apiFetch<PatientOut>(`/api/patients/${patientId}`),
    enabled: Boolean(patientId),
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PatientCreatePayload) =>
      apiFetch<PatientOut>("/api/patients", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PATIENTS_KEY });
    },
  });
}

export function useUpdatePatient(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PatientUpdatePayload) =>
      apiFetch<PatientOut>(`/api/patients/${patientId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PATIENTS_KEY });
    },
  });
}

export function useArchivePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patientId: string) => apiFetch<PatientOut>(`/api/patients/${patientId}/archive`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PATIENTS_KEY }),
  });
}
