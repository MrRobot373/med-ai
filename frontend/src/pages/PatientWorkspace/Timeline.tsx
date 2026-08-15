import {
  AlertTriangle,
  CheckCircle2,
  ClipboardPlus,
  FileText,
  Pill,
  Stethoscope,
  TrendingUp,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/Card";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientTimeline, type TimelineEventType } from "@/api/timeline";

const EVENT_ICON: Record<TimelineEventType, LucideIcon> = {
  encounter: Stethoscope,
  condition_recorded: ClipboardPlus,
  condition_resolved: CheckCircle2,
  medication_started: Pill,
  medication_stopped: XCircle,
  allergy_recorded: AlertTriangle,
  report_uploaded: FileText,
  abnormal_result: TrendingUp,
};

const EVENT_TONE: Record<TimelineEventType, string> = {
  encounter: "bg-light-blue text-primary-blue",
  condition_recorded: "bg-amber-100 text-amber-700",
  condition_resolved: "bg-success/10 text-success",
  medication_started: "bg-cyan/10 text-cyan",
  medication_stopped: "bg-navy/10 text-navy",
  allergy_recorded: "bg-danger/10 text-danger",
  report_uploaded: "bg-light-blue text-primary-blue",
  abnormal_result: "bg-danger/10 text-danger",
};

function formatEventDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export default function TimelineTab() {
  const patient = usePatientContext();
  const { data: events, isLoading } = usePatientTimeline(patient.id);

  if (isLoading) {
    return <p className="text-sm text-muted-text">Loading timeline…</p>;
  }

  if (!events || events.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-muted-text">
        No timeline events yet. Start an encounter or document a condition, allergy, or medication.
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <ul className="space-y-5">
        {events.map((event, index) => {
          const Icon = EVENT_ICON[event.event_type];
          return (
            <li key={`${event.event_type}-${event.source_id}-${index}`} className="flex gap-3">
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${EVENT_TONE[event.event_type]}`}>
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-muted-text">
                  {formatEventDate(event.event_date)}
                </div>
                <div className="text-sm font-medium text-navy">{event.title}</div>
                {event.description && <p className="mt-0.5 text-sm text-muted-text">{event.description}</p>}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
