import { useEffect, useRef, useState } from "react";
import { BotMessageSquare } from "lucide-react";
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
 * The shared three-column Clinical AI surface (Conversations | Clinical Assistant | Evidence).
 * Used by the global /clinical-ai route (no patient) and the per-patient workspace tab.
 * Route wrappers key this on patient.id so a patient switch fully remounts it.
 *
 * heightClass lets callers tune the panel height for their layout context:
 *  - Global /clinical-ai route: "h-[calc(100vh-8rem)]"   (only the top navbar above)
 *  - Patient workspace tab:     "h-[calc(100vh-17rem)]"  (navbar + patient card + tab row)
 */
export function ClinicalAIWorkspace({
  patient,
  implementedScopes,
  reports,
  encounters,
  suggestedQuestionsFor,
  initialPrompt,
  onConsumedInitialPrompt,
  heightClass = "h-[calc(100vh-8rem)]",
}: {
  patient?: PatientOut;
  implementedScopes: ConversationScope[];
  reports?: ReportListItem[];
  encounters?: EncounterOut[];
  suggestedQuestionsFor: (scope: ConversationScope) => string[];
  initialPrompt?: InitialPrompt;
  onConsumedInitialPrompt?: () => void;
  heightClass?: string;
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
    // mutateAsync avoids the React 18 StrictMode observer-detachment race that
    // silently drops .mutate()'s onSuccess/onError when the effect unmounts+remounts
    // mid-flight. The initialHandledRef guard above prevents running more than once.
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
    // Runs once per mount — route wrapper keys by patient so a fresh mount is the
    // only time a new initialPrompt should be handled.
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
        onError: (err) =>
          setCreateError(err instanceof ApiError ? err.message : "Could not start a new conversation."),
      },
    );
  }

  const lastAssistant = messages ? [...messages].reverse().find((m) => m.role === "assistant") : undefined;
  const selectedConversation = conversations?.find((c) => c.id === selectedId);
  const activeScope = selectedConversation?.scope ?? implementedScopes[0];

  return (
    <div className={`grid ${heightClass} grid-cols-1 gap-4 lg:grid-cols-[260px_1fr_320px] 2xl:grid-cols-[300px_1fr_380px]`}>
      {/* Column 1 — Conversation list */}
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

      {/* Column 2 — Chat area */}
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
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-light-blue text-primary-blue">
              <BotMessageSquare className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-semibold text-navy">No conversation selected</p>
              <p className="mt-1 text-xs text-muted-text">
                {canWrite
                  ? "Pick a conversation from the left, or start a new one."
                  : "Select a conversation to view it. A doctor or admin account is required to send messages."}
              </p>
            </div>
            {createError && <p className="text-xs text-danger">{createError}</p>}
            {canWrite && (
              <button
                type="button"
                onClick={() => setShowNewChat(true)}
                className="rounded-lg bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90"
              >
                Start New Chat
              </button>
            )}
          </div>
        )}
      </div>

      {/* Column 3 — Evidence panel */}
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
