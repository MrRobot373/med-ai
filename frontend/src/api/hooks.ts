import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AIRun, BriefOutput, ClinicalScore, Branding, ChunkItem, Consultation, Conversation, ConversationDetail, CopilotRun, DocumentItem, Domain, Health,
  InboxItem, Observation, Order, Patient, PatientListItem, PatientOverview, Preferences, Prescription, PrevisitFacts, TimelineEvent, TodayList,
  TrendSeries, User,
} from "./types";

export const qk = {
  me: ["me"] as const,
  branding: ["branding"] as const,
  health: ["health"] as const,
  dashboard: ["dashboard"] as const,
  inbox: ["inbox"] as const,
  patients: (params?: object) => ["patients", params ?? {}] as const,
  patient: (id: string) => ["patient", id] as const,
  overview: (id: string) => ["patient", id, "overview"] as const,
  sub: (id: string, kind: string) => ["patient", id, kind] as const,
  documents: (id: string) => ["patient", id, "documents"] as const,
  document: (id: string) => ["document", id] as const,
  conversations: (pid?: string | null) => ["conversations", pid ?? "all"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  runs: (params: object) => ["runs", params] as const,
  knowledge: (params: object) => ["knowledge", params] as const,
  settings: ["settings"] as const,
  today: ["today"] as const,
  consultation: (id: string) => ["consultation", id] as const,
};

export const useMe = () => useQuery({ queryKey: qk.me, queryFn: () => api<User>("/api/auth/me"), retry: false, staleTime: 60_000 });
export const useBranding = () => useQuery({ queryKey: qk.branding, queryFn: () => api<Branding>("/api/branding"), staleTime: 5 * 60_000 });
export const useHealth = () => useQuery({ queryKey: qk.health, queryFn: () => api<Health>("/api/system/health"), refetchInterval: 60_000, staleTime: 20_000 });
export const useDashboard = () => useQuery({ queryKey: qk.dashboard, queryFn: () => api<any>("/api/dashboard"), refetchInterval: 60_000 });
export const useInbox = (enabled = true) => useQuery({ queryKey: qk.inbox, enabled, queryFn: () => api<InboxItem[]>("/api/inbox"), refetchInterval: 45_000 });

export function usePatients(params: { q?: string; status?: string; tag?: string; sort?: string }) {
  return useQuery({ queryKey: qk.patients(params), queryFn: () => api<PatientListItem[]>("/api/patients", { query: params }), placeholderData: keepPreviousData });
}
export const usePatient = (id: string) => useQuery({ queryKey: qk.patient(id), queryFn: () => api<Patient>(`/api/patients/${id}`) });
export const useOverview = (id: string, enabled = true) => useQuery({ queryKey: qk.overview(id), enabled, queryFn: () => api<PatientOverview>(`/api/patients/${id}/overview`) });
export const useScores = (id: string) => useQuery({ queryKey: qk.sub(id, "scores"), queryFn: () => api<ClinicalScore[]>(`/api/patients/${id}/scores`) });
export const useTimeline = (id: string) => useQuery({ queryKey: qk.sub(id, "timeline"), queryFn: () => api<TimelineEvent[]>(`/api/patients/${id}/timeline`) });
export const useTrends = (id: string) => useQuery({ queryKey: qk.sub(id, "trends"), queryFn: () => api<TrendSeries[]>(`/api/patients/${id}/trends`) });
export const useObservations = (id: string) => useQuery({ queryKey: qk.sub(id, "observations"), enabled: !!id, queryFn: () => api<Observation[]>(`/api/patients/${id}/observations`) });
export function useSubList<T>(id: string, kind: "conditions" | "allergies" | "medications" | "encounters") {
  return useQuery({ queryKey: qk.sub(id, kind), queryFn: () => api<T[]>(`/api/patients/${id}/${kind}`) });
}

export function usePatientDocuments(id: string) {
  return useQuery({
    queryKey: qk.documents(id),
    queryFn: () => api<DocumentItem[]>(`/api/patients/${id}/documents`),
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => d.status === "processing") ? 2000 : false),
  });
}
export const useDocument = (id: string | null) =>
  useQuery({
    queryKey: qk.document(id ?? ""), enabled: !!id, queryFn: () => api<DocumentItem>(`/api/documents/${id}`),
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 2000 : false),
  });
export const useChunks = (id: string | null) => useQuery({ queryKey: ["chunks", id], enabled: !!id, queryFn: () => api<ChunkItem[]>(`/api/documents/${id}/chunks`) });

export const useConversations = (patientId?: string | null) =>
  useQuery({ queryKey: qk.conversations(patientId), queryFn: () => api<Conversation[]>("/api/conversations", { query: { patient_id: patientId ?? undefined } }) });
export const useConversation = (id: string | null) =>
  useQuery({ queryKey: qk.conversation(id ?? ""), enabled: !!id, queryFn: () => api<ConversationDetail>(`/api/conversations/${id}`) });

export const useRuns = (params: { patient_id?: string; tool?: string; status?: string; limit?: number }) =>
  useQuery({ queryKey: qk.runs(params), queryFn: () => api<AIRun[]>("/api/ai-runs", { query: params }) });

export const useKnowledge = (params: { q?: string; domain?: string; status?: string }) =>
  useQuery({
    queryKey: qk.knowledge(params), queryFn: () => api<DocumentItem[]>("/api/knowledge", { query: params }), placeholderData: keepPreviousData,
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => d.status === "processing") ? 2000 : false),
  });
export const useDomains = () => useQuery({ queryKey: ["domains"], queryFn: () => api<Domain[]>("/api/knowledge/domains") });

export function useSavePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Preferences) => api<User>("/api/auth/me/preferences", { method: "PUT", body: prefs }),
    onSuccess: (user) => qc.setQueryData(qk.me, user),
  });
}

/** Invalidate everything belonging to a patient after a mutation. */
export function useInvalidatePatient() {
  const qc = useQueryClient();
  return (patientId: string) => {
    qc.invalidateQueries({ queryKey: ["patient", patientId] });
    qc.invalidateQueries({ queryKey: ["patients"] });
    qc.invalidateQueries({ queryKey: qk.inbox });
    qc.invalidateQueries({ queryKey: qk.dashboard });
  };
}

/* ---- Point of care ---------------------------------------------------------------------- */

export const useToday = () => useQuery({ queryKey: qk.today, queryFn: () => api<TodayList>("/api/today"), refetchInterval: 60_000 });
export const usePrevisit = (patientId: string, enabled = true) =>
  useQuery({ queryKey: qk.sub(patientId, "previsit"), enabled: enabled && !!patientId, queryFn: () => api<{ facts: PrevisitFacts; brief: CopilotRun<BriefOutput> | null }>(`/api/patients/${patientId}/previsit`) });
export const useConsultation = (encounterId: string | null) =>
  useQuery({ queryKey: qk.consultation(encounterId ?? ""), enabled: !!encounterId, queryFn: () => api<Consultation>(`/api/consultations/${encounterId}`) });
export const usePrescriptions = (patientId: string) =>
  useQuery({ queryKey: qk.sub(patientId, "prescriptions"), queryFn: () => api<Prescription[]>(`/api/patients/${patientId}/prescriptions`) });
export const useOrders = (patientId: string, status?: string) =>
  useQuery({
    queryKey: [...qk.sub(patientId, "orders"), status ?? "all"], enabled: !!patientId,
    queryFn: () => api<Order[]>(`/api/patients/${patientId}/orders`, { query: { status } }),
  });
