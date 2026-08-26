import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  FileText,
  Plus,
  Sparkles,
  Stethoscope,
  User,
  Users,
} from "lucide-react";
import { Card } from "@/components/Card";
import { useDashboardSummary } from "@/api/dashboard";
import { usePatients } from "@/api/patients";

interface ScheduleItem {
  id: string;
  patientName: string;
  mrn: string;
  patientId?: string;
  time: string;
  type: string;
  doctor: string;
  status: "confirmed" | "completed" | "in-progress";
}

const SAMPLE_SCHEDULE: Record<string, ScheduleItem[]> = {
  default: [
    {
      id: "s1",
      patientName: "Arthur Wallace",
      mrn: "DEMO-1001",
      time: "09:00 AM",
      type: "Cataract Pre-Operative Assessment",
      doctor: "Dr. Chen",
      status: "completed",
    },
    {
      id: "s2",
      patientName: "Robert Klein",
      mrn: "DEMO-1002",
      time: "10:30 AM",
      type: "Glaucoma Visual Field & IOP Check",
      doctor: "Dr. Chen",
      status: "in-progress",
    },
    {
      id: "s3",
      patientName: "Elena Novak",
      mrn: "DEMO-1003",
      time: "01:15 PM",
      type: "Diabetic Retinopathy Follow-up & OCT",
      doctor: "Dr. Patel",
      status: "confirmed",
    },
    {
      id: "s4",
      patientName: "Priya Patel",
      mrn: "DEMO-1004",
      time: "02:45 PM",
      type: "Wet AMD Anti-VEGF Response Review",
      doctor: "Dr. Chen",
      status: "confirmed",
    },
    {
      id: "s5",
      patientName: "Thomas Ferreira",
      mrn: "DEMO-1005",
      time: "04:00 PM",
      type: "Multi-morbidity Comprehensive Consult",
      doctor: "Dr. Chen",
      status: "confirmed",
    },
  ],
};

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: patients } = usePatients("", false);
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayIndex = new Date(year, month, 1).getDay();

  const prevMonthDays = new Date(year, month, 0).getDate();

  const handlePrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const isToday = (day: number) => {
    const today = new Date();
    return (
      day === today.getDate() &&
      month === today.getMonth() &&
      year === today.getFullYear()
    );
  };

  const isSelected = (day: number) => {
    return (
      day === selectedDate.getDate() &&
      month === selectedDate.getMonth() &&
      year === selectedDate.getFullYear()
    );
  };

  const handleSelectDay = (day: number) => {
    setSelectedDate(new Date(year, month, day));
  };

  // Find matching patient ID from patient list by MRN
  const findPatientId = (mrn: string) => {
    const found = patients?.find((p) => p.mrn === mrn);
    return found ? found.id : null;
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-navy">Clinical Dashboard</h1>
        <p className="text-sm text-muted-text">
          Real-time operations, diagnostic pipeline metrics, and clinic appointment schedule.
        </p>
      </div>

      {/* 3 Metric Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {/* Card 1: Active Patients */}
        <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-md">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-light-blue text-primary-blue">
            <Users className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <div className="text-2xl font-bold text-navy">
              {summaryLoading ? "…" : (summary?.active_patients ?? 0)}
            </div>
            <div className="text-sm font-medium text-navy">Active Patients</div>
            <div className="text-xs text-muted-text">Registered clinical records</div>
          </div>
        </Card>

        {/* Card 2: Reports Processed */}
        <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-md">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <FileText className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <div className="text-2xl font-bold text-navy">
              {summaryLoading ? "…" : (summary?.total_reports ?? 0)}
            </div>
            <div className="text-sm font-medium text-navy">Reports Processed</div>
            <div className="text-xs text-muted-text">Lab, OCT &amp; consult reports</div>
          </div>
        </Card>

        {/* Card 3: AI Analysis */}
        <Card className="flex items-center gap-4 p-5 transition-shadow hover:shadow-md">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
            <Sparkles className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <div className="text-2xl font-bold text-navy">
              {summaryLoading ? "…" : (summary?.total_ai_analyses ?? 0)}
            </div>
            <div className="text-sm font-medium text-navy">AI Analysis</div>
            <div className="text-xs text-muted-text">Automated vision &amp; notes</div>
          </div>
        </Card>
      </div>

      {/* Main Grid: Calendar and Schedule */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Calendar Section */}
        <div className="lg:col-span-5">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 text-primary-blue" />
                <h2 className="text-base font-semibold text-navy">
                  {monthNames[month]} {year}
                </h2>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handlePrevMonth}
                  className="rounded-md p-1.5 text-muted-text hover:bg-light-blue hover:text-navy"
                  aria-label="Previous Month"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const now = new Date();
                    setCurrentDate(now);
                    setSelectedDate(now);
                  }}
                  className="rounded px-2 py-1 text-xs font-medium text-primary-blue hover:bg-light-blue"
                >
                  Today
                </button>
                <button
                  type="button"
                  onClick={handleNextMonth}
                  className="rounded-md p-1.5 text-muted-text hover:bg-light-blue hover:text-navy"
                  aria-label="Next Month"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Calendar Grid */}
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-muted-text mb-2">
              <span>Su</span>
              <span>Mo</span>
              <span>Tu</span>
              <span>We</span>
              <span>Th</span>
              <span>Fr</span>
              <span>Sa</span>
            </div>

            <div className="grid grid-cols-7 gap-1 text-sm">
              {/* Previous Month Padded Days */}
              {Array.from({ length: firstDayIndex }).map((_, i) => (
                <div
                  key={`prev-${i}`}
                  className="flex h-9 items-center justify-center rounded-lg text-xs text-muted-text/40"
                >
                  {prevMonthDays - firstDayIndex + i + 1}
                </div>
              ))}

              {/* Current Month Days */}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = i + 1;
                const today = isToday(day);
                const selected = isSelected(day);
                // Highlight sample appointment days
                const hasAppointments = [2, 8, 14, 18, 25].includes(day);

                return (
                  <button
                    key={`day-${day}`}
                    type="button"
                    onClick={() => handleSelectDay(day)}
                    className={`relative flex h-9 items-center justify-center rounded-lg text-sm font-medium transition-all ${
                      selected
                        ? "bg-primary-blue text-white font-semibold shadow-sm"
                        : today
                        ? "border border-primary-blue text-primary-blue font-bold hover:bg-light-blue"
                        : "text-navy hover:bg-surface-hover"
                    }`}
                  >
                    <span>{day}</span>
                    {hasAppointments && !selected && (
                      <span className="absolute bottom-1 h-1 w-1 rounded-full bg-primary-blue" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs text-muted-text">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-primary-blue" /> Appointments Scheduled
              </span>
              <span className="font-medium">
                {selectedDate.toLocaleDateString("en-US", {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </div>
          </Card>
        </div>

        {/* Schedule & Quick Patient Access */}
        <div className="space-y-6 lg:col-span-7">
          {/* Scheduled Appointments Card */}
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary-blue" />
                <h2 className="text-base font-semibold text-navy">
                  Encounters for {selectedDate.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                </h2>
              </div>
              <span className="rounded-full bg-light-blue px-2.5 py-0.5 text-xs font-semibold text-primary-blue">
                {SAMPLE_SCHEDULE.default.length} Appointments
              </span>
            </div>

            <div className="divide-y divide-border">
              {SAMPLE_SCHEDULE.default.map((item) => {
                const matchedId = findPatientId(item.mrn);
                return (
                  <div key={item.id} className="flex flex-col gap-2 py-3.5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
                        <User className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-navy">{item.patientName}</span>
                          <span className="text-xs font-mono text-muted-text">({item.mrn})</span>
                        </div>
                        <p className="text-xs text-muted-text">{item.type}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-xs font-semibold text-navy">{item.time}</div>
                        <div className="text-[11px] text-muted-text">{item.doctor}</div>
                      </div>
                      {matchedId ? (
                        <Link
                          to={`/patients/${matchedId}`}
                          className="rounded-md border border-border bg-surface px-3 py-1 text-xs font-semibold text-navy transition-colors hover:border-primary-blue hover:text-primary-blue"
                        >
                          View Chart
                        </Link>
                      ) : (
                        <Link
                          to="/patients"
                          className="rounded-md border border-border bg-surface px-3 py-1 text-xs font-semibold text-navy transition-colors hover:border-primary-blue hover:text-primary-blue"
                        >
                          Patients
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Quick Actions & Clinical Shortcuts */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Link
              to="/clinical-ai"
              className="flex items-center gap-3.5 rounded-xl border border-border bg-surface p-4 transition-all hover:border-primary-blue hover:shadow-sm"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
                <Stethoscope className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-navy">Clinical AI Assistant</div>
                <div className="text-xs text-muted-text">Guideline Q&amp;A and differentials</div>
              </div>
            </Link>

            <Link
              to="/patients"
              className="flex items-center gap-3.5 rounded-xl border border-border bg-surface p-4 transition-all hover:border-primary-blue hover:shadow-sm"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Plus className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-navy">Patient Registry</div>
                <div className="text-xs text-muted-text">Manage &amp; review patient charts</div>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
