import { MessageSquarePlus } from "lucide-react";
import type { ConversationOut } from "@/api/chat";
import { SCOPE_LABEL } from "./scope";

function relativeDate(iso: string): string {
  const date = new Date(iso);
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

export function ConversationList({
  conversations,
  isLoading,
  selectedId,
  onSelect,
  onNewChat,
  canStartNewChat,
}: {
  conversations: ConversationOut[] | undefined;
  isLoading: boolean;
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  canStartNewChat: boolean;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border p-3">
        <h2 className="text-sm font-semibold text-navy">Conversations</h2>
        {canStartNewChat && (
          <button
            type="button"
            onClick={onNewChat}
            className="inline-flex items-center gap-1 rounded-md bg-primary-blue px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-primary-blue/90"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
            New Chat
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && <p className="p-3 text-xs text-muted-text">Loading…</p>}
        {!isLoading && conversations?.length === 0 && (
          <p className="p-3 text-xs text-muted-text">No conversations yet. Start one to ask a clinical question.</p>
        )}
        <ul className="divide-y divide-border">
          {conversations?.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                className={`w-full px-3 py-2.5 text-left transition-colors ${
                  selectedId === c.id ? "bg-light-blue" : "hover:bg-light-blue/60"
                }`}
              >
                <div className="truncate text-sm font-medium text-navy">{c.title ?? "New conversation"}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-text">
                  <span>{SCOPE_LABEL[c.scope]}</span>
                  <span>·</span>
                  <span>{relativeDate(c.updated_at)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
