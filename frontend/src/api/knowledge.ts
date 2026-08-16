import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/api/client";

// Mirrors backend/app/models/web_cache.py's AuthorityTier (reused for admin-curated
// knowledge documents rather than a second authority-tier concept).
export type AuthorityTier = "a" | "b" | "c" | "d" | "e" | "f";
export type IngestionStatus = "queued" | "processing" | "completed" | "failed";

export interface KnowledgeDocumentOut {
  id: string;
  title: string;
  source: string | null;
  specialty: string | null;
  authority_tier: AuthorityTier;
  tags: string | null;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeVersionOut {
  id: string;
  document_id: string;
  version_number: number;
  source_filename: string;
  mime_type: string;
  file_size_bytes: number;
  effective_date: string | null;
  review_date: string | null;
  is_active: boolean;
  ingestion_status: IngestionStatus;
  ingestion_error: string | null;
  chunk_count: number;
  created_at: string;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocumentOut {
  versions: KnowledgeVersionOut[];
}

export interface KnowledgeDocumentCreatePayload {
  title: string;
  source?: string;
  specialty?: string;
  authority_tier: AuthorityTier;
  tags?: string;
}

const documentsKey = (includeArchived: boolean, search: string) => ["knowledge", "documents", includeArchived, search] as const;

export function useKnowledgeDocuments(includeArchived = false, search = "") {
  return useQuery({
    queryKey: documentsKey(includeArchived, search),
    queryFn: () => {
      const params = new URLSearchParams();
      if (includeArchived) params.set("include_archived", "true");
      if (search) params.set("search", search);
      const qs = params.toString();
      return apiFetch<KnowledgeDocumentOut[]>(`/api/knowledge/documents${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useKnowledgeDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: ["knowledge", "documents", documentId],
    queryFn: () => apiFetch<KnowledgeDocumentDetail>(`/api/knowledge/documents/${documentId}`),
    enabled: Boolean(documentId),
    // Ingestion runs in a backend BackgroundTask — poll while any version is still
    // queued/processing so the UI reflects real status instead of a static snapshot.
    refetchInterval: (query) => {
      const data = query.state.data as KnowledgeDocumentDetail | undefined;
      const active = data?.versions.some((v) => v.ingestion_status === "queued" || v.ingestion_status === "processing");
      return active ? 2000 : false;
    },
  });
}

export function useCreateKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: KnowledgeDocumentCreatePayload) =>
      apiFetch<KnowledgeDocumentOut>("/api/knowledge/documents", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] }),
  });
}

export function useUpdateKnowledgeDocument(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<KnowledgeDocumentCreatePayload>) =>
      apiFetch<KnowledgeDocumentOut>(`/api/knowledge/documents/${documentId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge", "documents", documentId] });
    },
  });
}

export function useArchiveKnowledgeDocument(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<KnowledgeDocumentOut>(`/api/knowledge/documents/${documentId}/archive`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge", "documents", documentId] });
    },
  });
}

export function useUploadKnowledgeVersion(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, effectiveDate, reviewDate }: { file: File; effectiveDate?: string; reviewDate?: string }) => {
      const formData = new FormData();
      formData.append("file", file);
      const params = new URLSearchParams();
      if (effectiveDate) params.set("effective_date", effectiveDate);
      if (reviewDate) params.set("review_date", reviewDate);
      const qs = params.toString();
      // apiFetch always sets Content-Type: application/json — wrong for multipart, so
      // this bypasses it directly, same convention as useUploadReport.
      const res = await fetch(`/api/knowledge/documents/${documentId}/versions${qs ? `?${qs}` : ""}`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const raw = await res.text().catch(() => "");
        let message = raw || res.statusText;
        try {
          const parsed = JSON.parse(raw) as { detail?: string };
          if (typeof parsed.detail === "string") message = parsed.detail;
        } catch {
          // keep fallback
        }
        throw new ApiError(res.status, message);
      }
      return (await res.json()) as KnowledgeVersionOut;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge", "documents", documentId] }),
  });
}

export function useReindexKnowledgeDocument(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<KnowledgeVersionOut>(`/api/knowledge/documents/${documentId}/reindex`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge", "documents", documentId] }),
  });
}

export function useActivateKnowledgeVersion(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      apiFetch<KnowledgeVersionOut>(`/api/knowledge/documents/${documentId}/activate-version`, {
        method: "POST",
        body: JSON.stringify({ version_id: versionId }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge", "documents", documentId] }),
  });
}
