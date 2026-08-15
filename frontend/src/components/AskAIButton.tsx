import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import type { AskAINavState, ConversationScope } from "@/api/chat";
import { useCanWrite } from "@/api/auth";

/**
 * "Ask AI About This" entry point (spec §41) — auto-passes the relevant object's
 * context (report, lab trend, medication…) as a real, already-composed question
 * rather than making the clinician retype it. Always lands on the patient's Clinical
 * AI tab (a sibling route of wherever this button is rendered), which actually sends
 * the question — this is never decorative.
 */
export function AskAIButton({
  question,
  scope = "current_patient",
  reportId,
  className = "",
  label = "Ask AI",
}: {
  question: string;
  scope?: ConversationScope;
  reportId?: string;
  className?: string;
  label?: string;
}) {
  // Starting a conversation is a write action (POST /api/conversations) — hidden for
  // read-only viewers rather than shown as a button that would just 403, matching
  // every other write control in the app (useCanWrite).
  const canWrite = useCanWrite();
  if (!canWrite) return null;

  const state: AskAINavState = { prefillQuestion: question, scope, reportId };
  return (
    <Link
      to="../clinical-ai"
      state={state}
      className={`inline-flex items-center gap-1 text-primary-blue hover:underline ${className}`}
    >
      <Sparkles className="h-3.5 w-3.5" />
      {label}
    </Link>
  );
}
