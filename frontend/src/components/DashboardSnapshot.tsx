import { FileText, Sparkles, Users } from "lucide-react";
import { Card } from "@/components/Card";
import { useDashboardSummary } from "@/api/dashboard";

/**
 * Spec §22 clinician dashboard metrics — sourced from actual application data, never
 * hardcoded. Originally shipped in Phase 01/02 before reports (Phase 05) or any
 * AI-generated output (Phase 08-10) existed, so the last two cards honestly said "not
 * available yet". Phase 16's live UI review found that placeholder was never replaced
 * once those phases landed — real report/AI-analysis data existed, but the dashboard
 * still claimed the features hadn't arrived. Now backed by `GET /api/dashboard/summary`.
 */
export function DashboardSnapshot() {
  const { data, isLoading } = useDashboardSummary();

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
          <Users className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-semibold text-navy">{isLoading ? "…" : (data?.active_patients ?? 0)}</div>
          <div className="text-xs text-muted-text">Active Patients</div>
        </div>
      </Card>

      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
          <FileText className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-semibold text-navy">{isLoading ? "…" : (data?.total_reports ?? 0)}</div>
          <div className="text-xs text-muted-text">Reports Processed</div>
        </div>
      </Card>

      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-semibold text-navy">{isLoading ? "…" : (data?.total_ai_analyses ?? 0)}</div>
          <div className="text-xs text-muted-text">AI Analyses</div>
        </div>
      </Card>
    </div>
  );
}
