import { useEffect, useRef, useState } from "react";
import {
  useChatStream,
  useConversations,
  useCreateConversation,
  useMessages,
  type ConversationScope,
} from "@/api/chat";
import { ApiError } from "@/api/client";
import { useCanWrite } from "@/api/auth";
import type { PatientOut } from "@/api/patients";
import type { ReportListItem } from "@/api/reports";
import type { EncounterOut } from "@/api/encounters";
import { ConversationList } from "./ConversationList";
import { NewConversationModal } from "./NewConversationModal";
import { ChatColumn } from "./ChatColumn";
import { EvidencePanel } from "./EvidencePanel";

export interface InitialPrompt {
  text: string;
  scope: ConversationScope;
  reportId?: string;
}

/**
 * The shared three-column Clinical AI surface (spec §39: Conversations | Clinical
 * Assistant | Evidence). Used both by the global `/clinical-ai` route (no `patient`,
 * general/local-knowledge scopes only) and the per-patient workspace tab (patient
 * fixed, patient-tied scopes). The route wrappers are responsible for keying this
 * component on `patient.id` so a patient switch fully remounts it — spec §40: never
 * silently continue a patient-specific conversation under a different patient.
 */
export function ClinicalAIWorkspace({
  patient,
  implementedScopes,
  reports,
  encounters,
  suggestedQuestionsFor,
  initialPrompt,
  onConsumedInitialPrompt,
}: {
  patient?: PatientOut;
  implementedScopes: ConversationScope[];
  reports?: ReportListItem[];
  encounters?: EncounterOut[];
  suggestedQuestionsFor: (scope: ConversationScope) => string[];
  initialPrompt?: InitialPrompt;
  onConsumedInitialPrompt?: () => void;
}) {
  const canWrite = useCanWrite();
  const patientId = patient?.id;
  const { data: conversations, isLoading: conversationsLoading } = useConversations(patientId);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [showNewChat, setShowNewChat] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | undefined>(undefined);
  const createConversation = useCreateConversation();

  const { data: messages, isLoading: messagesLoading } = useMessages(selectedId);
  const chat = useChatStream(selectedId);

  const initialHandledRef = useRef(false);
  useEffect(() => {
    if (!initialPrompt || initialHandledRef.current) return;
    initialHandledRef.current = true;
    // Deliberately `mutateAsync` + a local `await`, not `.mutate(vars, {onSuccess})`:
    // under React 18 StrictMode, this effect's setup/cleanup/setup-again dance can
    // unsubscribe-then-resubscribe the mutation observer *while the request is still
    // in flight*. `.mutate()`'s per-call `onSuccess`/`onError` are delivered through
    // that observer, so on the exact StrictMode timing where the unsubscribe happens
    // before the response arrives, the observer gets detached from its own in-flight
    // mutation and the callback is silently dropped forever — confirmed live: the
    // POST succeeded (real 201, real conversation row), but neither callback ever
    // fired and the hook's own `status` stayed "pending" indefinitely. `mutateAsync`
    // returns the mutation's raw execution promise, which settles independently of
    // observer subscription state, so `await`-ing it here is unaffected by that race.
    // No unmount-cancellation guard here on purpose: React 18 no longer warns (let
    // alone errors) on setting state after unmount, and the `initialHandledRef` guard
    // above already prevents this from running more than once per real mount — a
    // `cancelled` flag flipped in this effect's own cleanup would just reintroduce the
    // same StrictMode race we're fixing (its simulated unmount would flip it before
    // the real mount's request ever resolves).
    void (async () => {
      try {
        const conversation = await createConversation.mutateAsync({
          scope: initialPrompt.scope,
          patient_id: patientId,
          selected_report_id: initialPrompt.reportId,
        });
        setSelectedId(conversation.id);
        setPendingPrompt(initialPrompt.text);
      } catch (err) {
        setCreateError(err instanceof ApiError ? err.message : "Could not start a new conversation.");
      } finally {
        onConsumedInitialPrompt?.();
      }
    })();
    // Runs once per mount — the route wrapper keys this component by patient, so a
    // fresh mount is exactly when a new initialPrompt should be handled.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pendingPrompt && selectedId && !chat.isStreaming) {
      chat.send(pendingPrompt);
      setPendingPrompt(undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingPrompt, selectedId]);

  function handleCreate(selection: { scope: ConversationScope; encounterId?: string; reportId?: string }) {
    setCreateError(null);
    createConversation.mutate(
      {
        scope: selection.scope,
        patient_id: patientId,
        encounter_id: selection.encounterId,
        selected_report_id: selection.reportId,
      },
      {
        onSuccess: (conversation) => {
          setSelectedId(conversation.id);
          setShowNewChat(false);
        },
        onError: (err) => setCreateError(err instanceof ApiError ? err.message : "Could not start a new conversation."),
      },
    );
  }

  const lastAssistant = messages ? [...messages].reverse().find((m) => m.role === "assistant") : undefined;
  const selectedConversation = conversations?.find((c) => c.id === selectedId);
  const activeScope = selectedConversation?.scope ?? implementedScopes[0];

  return (
    <div className="grid h-[calc(100vh-13rem)] min-h-[500px] grid-cols-1 gap-4 lg:grid-cols-[260px_1fr_300px]">
      <div className="gms-card overflow-hidden">
        <ConversationList
          conversations={conversations}
          isLoading={conversationsLoading}
          selectedId={selectedId}
          onSelect={setSelectedId}
          canStartNewChat={canWrite}
          onNewChat={() => {
            setCreateError(null);
            setShowNewChat(true);
          }}
        />
      </div>

      <div className="gms-card overflow-hidden">
        {selectedId ? (
          <ChatColumn
            messages={messages}
            streamingText={chat.streamingText}
            isStreaming={chat.isStreaming}
            streamError={chat.error}
            suggestedQuestions={canWrite ? suggestedQuestionsFor(activeScope) : []}
            disabled={messagesLoading}
            readOnly={!canWrite}
            onSend={chat.send}
            onStop={chat.stop}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
            {createError && <p className="text-sm text-red-600">{createError}</p>}
            <p className="text-sm text-muted-text">
              {canWrite
                ? "Select a conversation, or start a new one to ask a question."
                : "Select a conversation to view it. Starting a new chat requires a doctor or admin account."}
            </p>
            {canWrite && (
              <button
                type="button"
                onClick={() => setShowNewChat(true)}
                className="text-sm font-medium text-primary-blue hover:underline"
              >
                Start New Chat
              </button>
            )}
          </div>
        )}
      </div>

      <div className="gms-card overflow-hidden">
        <EvidencePanel
          citations={lastAssistant?.citations}
          evidenceQuality={lastAssistant?.evidence_quality}
          grounding={lastAssistant?.grounding}
          provenance={lastAssistant?.provenance}
        />
      </div>

      {showNewChat && (
        <NewConversationModal
          implementedScopes={implementedScopes}
          reports={reports}
          encounters={encounters}
          onCreate={handleCreate}
          onClose={() => setShowNewChat(false)}
          isPending={createConversation.isPending}
          error={createError}
        />
      )}
    </div>
  );
}
