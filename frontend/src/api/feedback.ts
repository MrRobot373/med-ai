import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/models/feedback.py
export type FeedbackTarget = "message" | "clinical_module_run";

export type FeedbackRating =
  | "helpful"
  | "not_helpful"
  | "incorrect"
  | "missing_evidence"
  | "outdated_evidence"
  | "wrong_patient_context";

export const FEEDBACK_RATING_LABELS: Record<FeedbackRating, string> = {
  helpful: "Helpful",
  not_helpful: "Not Helpful",
  incorrect: "Incorrect",
  missing_evidence: "Missing Evidence",
  outdated_evidence: "Outdated Evidence",
  wrong_patient_context: "Wrong Patient Context",
};

export interface FeedbackOut {
  id: string;
  target_type: FeedbackTarget;
  target_id: string;
  user_id: string;
  rating: FeedbackRating;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export function useMyFeedback(targetType: FeedbackTarget, targetId: string | undefined) {
  return useQuery({
    queryKey: ["feedback", "mine", targetType, targetId],
    queryFn: () =>
      apiFetch<FeedbackOut | null>(`/api/feedback/mine?target_type=${targetType}&target_id=${targetId}`),
    enabled: Boolean(targetId),
  });
}

export function useSubmitFeedback(targetType: FeedbackTarget, targetId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { rating: FeedbackRating; comment?: string }) =>
      apiFetch<FeedbackOut>("/api/feedback", {
        method: "POST",
        body: JSON.stringify({ target_type: targetType, target_id: targetId, ...payload }),
      }),
    onSuccess: (feedback) => {
      queryClient.setQueryData(["feedback", "mine", targetType, targetId], feedback);
    },
  });
}

export interface AdminFeedbackFilters {
  targetType?: FeedbackTarget;
  rating?: FeedbackRating;
  limit?: number;
}

export function useAdminFeedback(filters: AdminFeedbackFilters) {
  return useQuery({
    queryKey: ["feedback", "admin", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.targetType) params.set("target_type", filters.targetType);
      if (filters.rating) params.set("rating", filters.rating);
      params.set("limit", String(filters.limit ?? 100));
      return apiFetch<FeedbackOut[]>(`/api/feedback?${params.toString()}`);
    },
  });
}
