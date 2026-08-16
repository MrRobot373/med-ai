import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/models/audit_log.py
export type AuditAction =
  | "login"
  | "logout"
  | "patient_created"
  | "patient_modified"
  | "encounter_created"
  | "report_uploaded"
  | "report_archived"
  | "knowledge_document_uploaded"
  | "knowledge_version_changed"
  | "clinical_ai_query"
  | "research_mode_enabled"
  | "external_search_executed"
  | "ai_export_created"
  | "settings_changed";

export type AuditOutcome = "success" | "failure";

// Human-readable labels for the filter dropdown and table — kept in one place so the
// Audit page doesn't hand-format the enum value itself in more than one spot.
export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  login: "Login",
  logout: "Logout",
  patient_created: "Patient Created",
  patient_modified: "Patient Modified",
  encounter_created: "Encounter Created",
  report_uploaded: "Report Uploaded",
  report_archived: "Report Archived",
  knowledge_document_uploaded: "Knowledge Document Uploaded",
  knowledge_version_changed: "Knowledge Version Changed",
  clinical_ai_query: "Clinical AI Query",
  research_mode_enabled: "Research Mode Enabled",
  external_search_executed: "External Search Executed",
  ai_export_created: "AI Export Created",
  settings_changed: "Settings Changed",
};

export interface AuditLogOut {
  id: string;
  user_id: string | null;
  user_email: string | null;
  action: AuditAction;
  outcome: AuditOutcome;
  object_type: string | null;
  object_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditFilters {
  action?: AuditAction;
  outcome?: AuditOutcome;
  objectType?: string;
  limit?: number;
}

export function useAuditLogs(filters: AuditFilters) {
  return useQuery({
    queryKey: ["audit", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.action) params.set("action", filters.action);
      if (filters.outcome) params.set("outcome", filters.outcome);
      if (filters.objectType) params.set("object_type", filters.objectType);
      params.set("limit", String(filters.limit ?? 100));
      return apiFetch<AuditLogOut[]>(`/api/audit?${params.toString()}`);
    },
  });
}
