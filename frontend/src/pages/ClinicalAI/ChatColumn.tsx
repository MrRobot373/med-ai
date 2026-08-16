import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Loader2, Send, Square, TriangleAlert } from "lucide-react";
import type { MessageOut } from "@/api/chat";
import { FeedbackControls } from "@/components/FeedbackControls";

const CITATION_PATTERN = /\[([PLW]\d+)\]/g;

/** Renders `[P1]`-style markers as small clickable badges that jump to the matching
 * item in the Evidence panel, rather than leaving them as plain bracketed text. */
function renderWithCitations(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CITATION_PATTERN.lastIndex = 0;
  let key = 0;
  while ((match = CITATION_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const label = match[1];
    parts.push(
      <button
        key={key++}
        type="button"
        onClick={() => document.getElementById(`evidence-${label}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
        className="mx-0.5 inline-flex rounded bg-light-blue px-1 text-[11px] font-semibold text-primary-blue hover:bg-primary-blue hover:text-white"
      >
        {label}
      </button>,
    );
    lastIndex = CITATION_PATTERN.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function MessageBubble({ message }: { message: MessageOut }) {
  const isUser = message.role === "user";
  if (message.generation_error) {
    return (
      <div className="flex items-start gap-2 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <span>Generation failed: {message.generation_error}</span>
      </div>
    );
  }
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm whitespace-pre-wrap ${
          isUser ? "bg-primary-blue text-white" : "border border-border bg-surface text-navy"
        }`}
      >
        {isUser ? message.content : renderWithCitations(message.content)}
      </div>
      {!isUser && <FeedbackControls targetType="message" targetId={message.id} />}
    </div>
  );
}

export function ChatColumn({
  messages,
  streamingText,
  isStreaming,
  streamError,
  suggestedQuestions,
  disabled,
  readOnly = false,
  onSend,
  onStop,
}: {
  messages: MessageOut[] | undefined;
  streamingText: string;
  isStreaming: boolean;
  streamError: string | null;
  suggestedQuestions: string[];
  disabled: boolean;
  readOnly?: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Plain scrollTop assignment rather than scrollTo({ behavior: "smooth" }) — jsdom
    // (used in tests) doesn't implement Element.scrollTo, and a hard jump here is fine
    // since this fires on every new token, not a one-off user-triggered scroll.
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streamingText]);

  function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setDraft("");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    send(draft);
  }

  const showSuggestions = !isStreaming && (messages?.length ?? 0) === 0 && suggestedQuestions.length > 0;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages?.length === 0 && !isStreaming && (
          <p className="text-sm text-muted-text">Ask a question to get started.</p>
        )}

        {messages?.map((m) => <MessageBubble key={m.id} message={m} />)}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm whitespace-pre-wrap text-navy">
              {streamingText.length > 0 ? (
                renderWithCitations(streamingText)
              ) : (
                <span className="inline-flex items-center gap-1.5 text-muted-text">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Thinking…
                </span>
              )}
            </div>
          </div>
        )}

        {streamError && (
          <div className="flex items-start gap-2 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{streamError}</span>
          </div>
        )}

        {showSuggestions && (
          <div className="space-y-1.5 pt-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-text">Suggested questions</p>
            {suggestedQuestions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => send(q)}
                className="block w-full rounded-md border border-border px-3 py-2 text-left text-sm text-navy hover:bg-light-blue"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>

      {readOnly ? (
        <div className="border-t border-border p-3 text-center text-xs text-muted-text">
          Read-only access — a doctor or admin account is required to send messages.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={disabled}
            placeholder={disabled ? "Select or start a conversation…" : "Ask a clinical question…"}
            className="flex-1 rounded-md border border-border px-3 py-2 text-sm disabled:bg-light-blue/50"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex items-center gap-1.5 rounded-md bg-danger px-3 py-2 text-sm font-semibold text-white hover:bg-danger/90"
            >
              <Square className="h-3.5 w-3.5" />
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || !draft.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary-blue px-3 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
            >
              <Send className="h-3.5 w-3.5" />
              Send
            </button>
          )}
        </form>
      )}
    </div>
  );
}
