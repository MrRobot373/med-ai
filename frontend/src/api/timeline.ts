import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

export type TimelineEventType =
  | "encounter"
  | "condition_recorded"
  | "condition_resolved"
  | "medication_started"
  | "medication_stopped"
  | "allergy_recorded";

export interface TimelineEvent {
  event_type: TimelineEventType;
  event_date: string;
  title: string;
  description: string | null;
  encounter_id: string | null;
  source_id: string;
}

export function usePatientTimeline(patientId: string) {
  return useQuery({
    queryKey: ["patients", patientId, "timeline"],
    queryFn: () => apiFetch<TimelineEvent[]>(`/api/patients/${patientId}/timeline`),
  });
}
