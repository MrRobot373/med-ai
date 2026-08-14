import { Users } from "lucide-react";
import { Card } from "@/components/Card";

/**
 * Spec §22 calls for real clinician dashboard metrics ("12 Active Patients", "4 New
 * Reports", ...) sourced from actual application data — explicitly NOT hardcoded fake
 * numbers. Patient/report data doesn't exist until Phase 04/05, so rather than invent
 * placeholder counts (which would violate that rule the moment someone reads them as
 * real), this section says plainly that it isn't wired up yet. It gets replaced with
 * real metric tiles, not removed, once Phase 04 lands.
 */
export function DashboardSnapshot() {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
        <Users className="h-5 w-5" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-navy">Clinical activity snapshot</h3>
        <p className="mt-0.5 text-sm text-muted-text">
          Active patients, new reports, and pending AI analyses will appear here once
          Patient Management (Phase 04) is built — not shown as placeholder numbers in
          the meantime.
        </p>
      </div>
    </Card>
  );
}
