import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/dashboard.py
export interface DashboardSummary {
  active_patients: number;
  total_reports: number;
  total_ai_analyses: number;
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiFetch<DashboardSummary>("/api/dashboard/summary"),
  });
}
