import { FileText, Sparkles, Users } from "lucide-react";
import { Card } from "@/components/Card";
import { usePatients } from "@/api/patients";

/**
 * Spec §22 clinician dashboard metrics — sourced from actual application data, never
 * hardcoded. Patient counts are real as of Phase 04; report/AI-analysis counts stay
 * honestly "not available yet" until Phase 05 (ingestion) and Phase 08-10 (Clinical AI)
 * exist to generate them for real.
 */
export function DashboardSnapshot() {
  const { data: patients, isLoading } = usePatients("", false);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
          <Users className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-semibold text-navy">{isLoading ? "…" : (patients?.length ?? 0)}</div>
          <div className="text-xs text-muted-text">Active Patients</div>
        </div>
      </Card>

      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-muted-text">
          <FileText className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-medium text-muted-text">Not available yet</div>
          <div className="text-xs text-muted-text">Reports — arrives in Phase 05</div>
        </div>
      </Card>

      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-muted-text">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-medium text-muted-text">Not available yet</div>
          <div className="text-xs text-muted-text">AI analyses — arrives in Phases 08–10</div>
        </div>
      </Card>
    </div>
  );
}
