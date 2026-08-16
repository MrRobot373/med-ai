import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { apiFetch } from "@/api/client";

// --- Types (mirror backend/app/schemas/chat.py) ---

export type ConversationScope =
  | "general"
  | "current_patient"
  | "current_encounter"
  | "selected_report"
  | "selected_reports_comparison"
  | "local_knowledge_only"
  | "research_mode";

export interface ConversationOut {
  id: string;
  user_id: string;
  patient_id: string | null;
  encounter_id: string | null;
  selected_report_id: string | null;
  scope: ConversationScope;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export type CitationSourceType = "patient_report" | "knowledge_document" | "patient_vision" | "external";

export interface CitationOut {
  id: string;
  label: string;
  source_type: CitationSourceType;
  chunk_id: string | null;
  report_id: string | null;
  source_title: string;
  page: number | null;
  section: string | null;
  source_excerpt: string;
  relevance_score: number | null;
}

export type MessageRole = "user" | "assistant" | "system";

export type EvidenceQuality = "strong" | "moderate" | "limited" | "insufficient";

export interface GroundingClaim {
  claim: string;
  cited_labels: string[];
  status: "supported" | "partially_supported" | "unsupported";
}

export interface MessageOut {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  model: string | null;
  generation_error: string | null;
  created_at: string;
  citations: CitationOut[];
  evidence_quality: EvidenceQuality | null;
  grounding: GroundingClaim[] | null;
}

// --- Conversations --------------------------------------------------------------

const conversationsKey = (patientId?: string) => ["conversations", patientId ?? "all"] as const;

export function useConversations(patientId?: string) {
  return useQuery({
    queryKey: conversationsKey(patientId),
    queryFn: () =>
      apiFetch<ConversationOut[]>(`/api/conversations${patientId ? `?patient_id=${patientId}` : ""}`),
  });
}

export interface ConversationCreatePayload {
  scope: ConversationScope;
  patient_id?: string;
  encounter_id?: string;
  selected_report_id?: string;
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConversationCreatePayload) =>
      apiFetch<ConversationOut>("/api/conversations", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: conversationsKey() });
      if (conversation.patient_id) {
        queryClient.invalidateQueries({ queryKey: conversationsKey(conversation.patient_id) });
      }
    },
  });
}

export function useConversation(conversationId: string | undefined) {
  return useQuery({
    queryKey: ["conversations", conversationId],
    queryFn: () => apiFetch<ConversationOut>(`/api/conversations/${conversationId}`),
    enabled: Boolean(conversationId),
  });
}

const messagesKey = (conversationId: string | undefined) => ["conversations", conversationId, "messages"] as const;

export function useMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: messagesKey(conversationId),
    queryFn: () => apiFetch<MessageOut[]>(`/api/conversations/${conversationId}/messages`),
    enabled: Boolean(conversationId),
  });
}

/** State shape "Ask AI About This" buttons (spec §41) navigate to the patient's
 * Clinical AI tab with — passed via router state rather than a query param so it
 * never sits in the URL/history as if it were a bookmarkable link. */
export interface AskAINavState {
  prefillQuestion: string;
  scope?: ConversationScope;
  reportId?: string;
}

// --- Streaming --------------------------------------------------------------------

export interface StreamFinalEvent {
  type: "final";
  message_id: string;
  citations: CitationOut[];
  evidence_quality: EvidenceQuality;
  grounding: GroundingClaim[] | null;
}

interface StreamTokenEvent {
  type: "token";
  content: string;
}

interface StreamErrorEvent {
  type: "error";
  message: string;
}

type StreamEvent = StreamTokenEvent | StreamFinalEvent | StreamErrorEvent;

/**
 * Streams one chat turn via `fetch` + a manually-parsed SSE body — not `EventSource`,
 * which can't send a POST body or attach a request signal for cancellation. Real
 * backend token streaming (spec §119 "no fake streaming"): tokens are handed to
 * `onToken` as they actually arrive over the wire, never chunked client-side from an
 * already-complete response.
 */
async function streamMessage(
  conversationId: string,
  text: string,
  handlers: {
    onToken: (content: string) => void;
    onFinal: (event: StreamFinalEvent) => void;
    onError: (message: string) => void;
  },
  signal: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal,
    });
  } catch (err) {
    if (signal.aborted) return; // user hit Stop — not an error to surface
    handlers.onError(err instanceof Error ? err.message : "Could not reach the server.");
    return;
  }

  if (!res.ok || !res.body) {
    const raw = await res.text().catch(() => "");
    let message = raw || res.statusText;
    try {
      const parsed = JSON.parse(raw) as { detail?: string };
      if (typeof parsed.detail === "string") message = parsed.detail;
    } catch {
      // keep fallback
    }
    handlers.onError(message);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const event = JSON.parse(part.slice("data: ".length)) as StreamEvent;
        if (event.type === "token") handlers.onToken(event.content);
        else if (event.type === "final") handlers.onFinal(event);
        else if (event.type === "error") handlers.onError(event.message);
      }
    }
  } catch (err) {
    if (!signal.aborted) {
      handlers.onError(err instanceof Error ? err.message : "Streaming connection was interrupted.");
    }
  }
}

interface ChatStreamState {
  streamingText: string;
  isStreaming: boolean;
  error: string | null;
}

/** Owns the streaming lifecycle for one conversation view: accumulates tokens as
 * they arrive, exposes `stop()` for spec §120 cancellation, and refetches the
 * persisted message list (with its real citations) once the stream settles rather
 * than trying to reconstruct citation state from the raw token stream itself. */
export function useChatStream(conversationId: string | undefined) {
  const [state, setState] = useState<ChatStreamState>({ streamingText: "", isStreaming: false, error: null });
  const abortRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const send = useCallback(
    (text: string) => {
      if (!conversationId) return;
      const controller = new AbortController();
      abortRef.current = controller;
      setState({ streamingText: "", isStreaming: true, error: null });

      // Reflect the just-sent user message immediately rather than waiting for the
      // eventual refetch, so the UI doesn't sit blank while the first token arrives.
      queryClient.setQueryData<MessageOut[]>(messagesKey(conversationId), (prev) => [
        ...(prev ?? []),
        {
          id: `pending-${Date.now()}`,
          conversation_id: conversationId,
          role: "user",
          content: text,
          model: null,
          generation_error: null,
          created_at: new Date().toISOString(),
          citations: [],
          evidence_quality: null,
          grounding: null,
        },
      ]);

      void streamMessage(
        conversationId,
        text,
        {
          onToken: (content) => setState((prev) => ({ ...prev, streamingText: prev.streamingText + content })),
          onFinal: () => {
            setState({ streamingText: "", isStreaming: false, error: null });
            queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) });
            queryClient.invalidateQueries({ queryKey: ["conversations", conversationId] });
            queryClient.invalidateQueries({ queryKey: conversationsKey() });
          },
          onError: (message) => {
            setState({ streamingText: "", isStreaming: false, error: message });
            queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) });
          },
        },
        controller.signal,
      );
    },
    [conversationId, queryClient],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  return { ...state, send, stop };
}
