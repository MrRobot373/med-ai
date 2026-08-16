import { useState } from "react";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import {
  FEEDBACK_RATING_LABELS,
  useMyFeedback,
  useSubmitFeedback,
  type FeedbackRating,
  type FeedbackTarget,
} from "@/api/feedback";

// Spec §81: every AI answer should allow Helpful / Not Helpful / Incorrect / Missing
// Evidence / Outdated Evidence / Wrong Patient Context. "Helpful" is the one positive
// rating (its own thumbs-up button); the other five are all flavors of "something's
// wrong," grouped behind a thumbs-down menu rather than six same-weight buttons.
const NEGATIVE_RATINGS: FeedbackRating[] = [
  "not_helpful",
  "incorrect",
  "missing_evidence",
  "outdated_evidence",
  "wrong_patient_context",
];

export function FeedbackControls({ targetType, targetId }: { targetType: FeedbackTarget; targetId: string | undefined }) {
  const { data: mine } = useMyFeedback(targetType, targetId);
  const submit = useSubmitFeedback(targetType, targetId);
  const [menuOpen, setMenuOpen] = useState(false);

  if (!targetId) return null;

  function rate(rating: FeedbackRating) {
    setMenuOpen(false);
    submit.mutate({ rating });
  }

  return (
    <div className="relative mt-1 flex items-center gap-1 text-[11px] text-muted-text">
      <button
        type="button"
        onClick={() => rate("helpful")}
        disabled={submit.isPending}
        aria-label="Mark as helpful"
        aria-pressed={mine?.rating === "helpful"}
        className={`inline-flex items-center rounded p-1 hover:bg-light-blue disabled:opacity-60 ${
          mine?.rating === "helpful" ? "bg-success/10 text-success" : ""
        }`}
      >
        <ThumbsUp className="h-3 w-3" />
      </button>
      <button
        type="button"
        onClick={() => setMenuOpen((v) => !v)}
        disabled={submit.isPending}
        aria-label="Report an issue with this answer"
        aria-pressed={Boolean(mine && mine.rating !== "helpful")}
        className={`inline-flex items-center rounded p-1 hover:bg-light-blue disabled:opacity-60 ${
          mine && mine.rating !== "helpful" ? "bg-danger/10 text-danger" : ""
        }`}
      >
        <ThumbsDown className="h-3 w-3" />
      </button>
      {mine && (
        <span className="inline-flex items-center gap-0.5">
          <Check className="h-3 w-3" />
          {FEEDBACK_RATING_LABELS[mine.rating]}
        </span>
      )}

      {menuOpen && (
        <div className="absolute left-0 top-full z-10 mt-1 w-48 rounded-md border border-border bg-surface p-1 shadow-md">
          {NEGATIVE_RATINGS.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => rate(r)}
              className="block w-full rounded px-2 py-1 text-left text-xs text-navy hover:bg-light-blue"
            >
              {FEEDBACK_RATING_LABELS[r]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
