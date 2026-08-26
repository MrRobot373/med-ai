import { useState, useMemo } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
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
import { usePatientTimeline, type TimelineEventType, type TimelineEvent } from "@/api/timeline";

// ─── Icon & tone maps ─────────────────────────────────────────────────────────
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

const EVENT_LABEL: Record<TimelineEventType, string> = {
  encounter: "Encounter",
  condition_recorded: "Condition",
  condition_resolved: "Resolved",
  medication_started: "Medication",
  medication_stopped: "Stopped",
  allergy_recorded: "Allergy",
  report_uploaded: "Report",
  abnormal_result: "Abnormal Result",
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function isoToYMD(iso: string) {
  const d = new Date(iso);
  return { y: d.getFullYear(), m: d.getMonth(), d: d.getDate() };
}

function sameDay(iso: string, y: number, m: number, day: number) {
  const { y: ey, m: em, d: ed } = isoToYMD(iso);
  return ey === y && em === m && ed === day;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ─── Calendar ─────────────────────────────────────────────────────────────────
interface CalendarProps {
  events: TimelineEvent[];
  selectedDate: { y: number; m: number; d: number } | null;
  onSelectDate: (date: { y: number; m: number; d: number } | null) => void;
}

function MiniCalendar({ events, selectedDate, onSelectDate }: CalendarProps) {
  const today = new Date();
  const [viewY, setViewY] = useState(today.getFullYear());
  const [viewM, setViewM] = useState(today.getMonth());

  // Set of day numbers that have events in current view month
  const eventDays = useMemo(() => {
    const s = new Set<number>();
    events.forEach((e) => {
      const { y, m, d } = isoToYMD(e.event_date);
      if (y === viewY && m === viewM) s.add(d);
    });
    return s;
  }, [events, viewY, viewM]);

  const firstWeekday = new Date(viewY, viewM, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(viewY, viewM + 1, 0).getDate();

  const prevMonth = () => {
    if (viewM === 0) { setViewY(y => y - 1); setViewM(11); }
    else setViewM(m => m - 1);
  };
  const nextMonth = () => {
    if (viewM === 11) { setViewY(y => y + 1); setViewM(0); }
    else setViewM(m => m + 1);
  };

  const handleDayClick = (day: number) => {
    if (!eventDays.has(day)) return; // only clickable if events exist
    const isSelected = selectedDate?.y === viewY && selectedDate?.m === viewM && selectedDate?.d === day;
    onSelectDate(isSelected ? null : { y: viewY, m: viewM, d: day });
  };

  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  // pad to complete last row
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="select-none">
      {/* Month navigation */}
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={prevMonth}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-text hover:bg-surface-hover hover:text-navy"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-sm font-semibold text-navy">
          {MONTHS[viewM]} {viewY}
        </span>
        <button
          type="button"
          onClick={nextMonth}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-text hover:bg-surface-hover hover:text-navy"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Day headers */}
      <div className="mb-1 grid grid-cols-7 text-center">
        {DAYS.map((d) => (
          <div key={d} className="text-[10px] font-semibold uppercase tracking-wide text-muted-text">
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7 gap-y-1 text-center">
        {cells.map((day, i) => {
          if (!day) return <div key={`e-${i}`} />;
          const hasEvent = eventDays.has(day);
          const isSelected =
            selectedDate?.y === viewY &&
            selectedDate?.m === viewM &&
            selectedDate?.d === day;
          const isToday =
            today.getFullYear() === viewY &&
            today.getMonth() === viewM &&
            today.getDate() === day;

          return (
            <button
              key={day}
              type="button"
              onClick={() => handleDayClick(day)}
              disabled={!hasEvent}
              className={`relative mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs transition-all
                ${isSelected ? "bg-primary-blue font-bold text-white shadow" : ""}
                ${!isSelected && hasEvent ? "cursor-pointer font-medium text-navy hover:bg-light-blue hover:text-primary-blue" : ""}
                ${!hasEvent ? "cursor-default text-muted-text/50" : ""}
                ${isToday && !isSelected ? "ring-2 ring-primary-blue ring-offset-1" : ""}
              `}
            >
              {day}
              {/* Event dot */}
              {hasEvent && !isSelected && (
                <span className="absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-primary-blue" />
              )}
            </button>
          );
        })}
      </div>

      {/* Clear filter button */}
      {selectedDate && (
        <button
          type="button"
          onClick={() => onSelectDate(null)}
          className="mt-3 w-full rounded-lg border border-border py-1 text-xs text-muted-text hover:border-primary-blue hover:text-primary-blue"
        >
          Clear date filter
        </button>
      )}
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────
export default function TimelineTab() {
  const patient = usePatientContext();
  const { data: events, isLoading } = usePatientTimeline(patient.id);
  const [selectedDate, setSelectedDate] = useState<{ y: number; m: number; d: number } | null>(null);
  const [activeType, setActiveType] = useState<TimelineEventType | "all">("all");

  // Derive event types present
  const presentTypes = useMemo<TimelineEventType[]>(() => {
    if (!events) return [];
    return [...new Set(events.map((e) => e.event_type))];
  }, [events]);

  // Filtered list
  const filtered = useMemo(() => {
    if (!events) return [];
    return events.filter((e) => {
      const typeOk = activeType === "all" || e.event_type === activeType;
      const dateOk = !selectedDate || sameDay(e.event_date, selectedDate.y, selectedDate.m, selectedDate.d);
      return typeOk && dateOk;
    });
  }, [events, activeType, selectedDate]);

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
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
      {/* ── LEFT: Calendar + Filter ─────────────────────────────── */}
      <div className="space-y-4 lg:col-span-4">
        {/* Calendar */}
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2 border-b border-border pb-2">
            <CalendarDays className="h-4 w-4 text-primary-blue" />
            <span className="text-sm font-semibold text-navy">Navigate by Date</span>
          </div>
          <MiniCalendar
            events={events}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />
        </Card>

        {/* Event type filter */}
        <Card className="p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-text">
            Filter by Type
          </div>
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => setActiveType("all")}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition-all ${
                activeType === "all"
                  ? "bg-light-blue font-semibold text-primary-blue"
                  : "text-navy hover:bg-surface-hover"
              }`}
            >
              All events
              <span className="ml-auto text-xs font-normal text-muted-text">
                {events.length}
              </span>
            </button>

            {presentTypes.map((type) => {
              const Icon = EVENT_ICON[type];
              const count = events.filter((e) => e.event_type === type).length;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setActiveType(type)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition-all ${
                    activeType === type
                      ? "bg-light-blue font-semibold text-primary-blue"
                      : "text-navy hover:bg-surface-hover"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0 text-muted-text" />
                  {EVENT_LABEL[type]}
                  <span className="ml-auto text-xs font-normal text-muted-text">{count}</span>
                </button>
              );
            })}
          </div>
        </Card>
      </div>

      {/* ── RIGHT: Event List ────────────────────────────────────── */}
      <div className="lg:col-span-8">
        <Card className="p-5">
          {/* Active filter summary */}
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="text-sm font-semibold text-navy">
              {selectedDate
                ? `Events on ${MONTHS[selectedDate.m]} ${selectedDate.d}, ${selectedDate.y}`
                : "All Timeline Events"}
            </div>
            <span className="rounded-full bg-light-blue px-2.5 py-0.5 text-xs font-semibold text-primary-blue">
              {filtered.length} event{filtered.length !== 1 ? "s" : ""}
            </span>
          </div>

          {filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-text">
              No events match the selected date or filter.
            </p>
          ) : (
            <ul className="space-y-5">
              {filtered.map((event, index) => {
                const Icon = EVENT_ICON[event.event_type];
                return (
                  <li
                    key={`${event.event_type}-${event.source_id}-${index}`}
                    className="flex gap-3"
                  >
                    {/* Timeline spine */}
                    <div className="flex flex-col items-center">
                      <div
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${EVENT_TONE[event.event_type]}`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      {index < filtered.length - 1 && (
                        <div className="mt-1 w-px flex-1 bg-border" />
                      )}
                    </div>

                    <div className="pb-5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium uppercase tracking-wide text-muted-text">
                          {formatDate(event.event_date)}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${EVENT_TONE[event.event_type]}`}
                        >
                          {EVENT_LABEL[event.event_type]}
                        </span>
                      </div>
                      <div className="mt-0.5 text-sm font-medium text-navy">{event.title}</div>
                      {event.description && (
                        <p className="mt-0.5 text-sm text-muted-text">{event.description}</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
