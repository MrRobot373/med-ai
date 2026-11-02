import { CalendarDays, ChevronRight, ClipboardList, FlaskConical, Play, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useToday } from "@/api/hooks";
import type { Appointment } from "@/api/types";
import { Avatar, Badge, Button, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui";
import { cn, sexLabel } from "@/lib/utils";

const STATUS_STYLE: Record<Appointment["status"], string> = {
  expected: "bg-muted text-muted-foreground",
  arrived: "bg-primary-soft text-primary-soft-foreground",
  seen: "bg-success-soft text-success-foreground",
  cancelled: "bg-muted text-muted-foreground line-through",
};
const STATUS_LABEL = { expected: "Expected", arrived: "Waiting", seen: "Seen", cancelled: "Cancelled" };

/** The day's patients — deliberately just a short list with what the doctor should know. */
export function TodayCard({ className }: { className?: string }) {
  const { data, isLoading } = useToday();
  const navigate = useNavigate();
  const list = data?.appointments ?? [];
  const next = list.find((a) => a.status === "arrived") ?? list.find((a) => a.status === "expected");
  return (
    <Card className={className}>
      <CardHeader icon={<CalendarDays />} title="Today's patients"
        description={data ? `${data.counts.seen} seen · ${data.counts.arrived} waiting · ${data.counts.expected} expected` : undefined}
        actions={next && <Button size="sm" variant="strong" className="rounded-full" onClick={() => navigate(`/patients/${next.patient_id}/consult`)}><Play /> Next: {next.patient?.name.split(" ")[0]}</Button>} />
      <div className="card-pad pt-3">
        {isLoading ? <Skeleton className="h-40" /> : !list.length ? (
          <EmptyState compact icon={<CalendarDays />} title="No one on today's list" description="Walk-ins can be seen from any chart — open the patient and start a consultation." />
        ) : (
          <ul className="divide-y divide-border/60">
            {list.map((a) => <TodayRow key={a.id} a={a} />)}
          </ul>
        )}
      </div>
    </Card>
  );
}

function TodayRow({ a }: { a: Appointment }) {
  const c = a.clinical;
  return (
    <li className="group flex items-center gap-3 py-2.5">
      <span className="w-11 shrink-0 text-[0.78rem] font-semibold text-muted-foreground num">{a.time ?? "—"}</span>
      <Avatar name={a.patient?.name ?? "?"} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <Link to={`/patients/${a.patient_id}`} className="truncate text-[0.85rem] font-semibold hover:underline">{a.patient?.name}</Link>
          <span className="text-[0.7rem] text-muted-foreground">{a.patient?.age ?? "—"} y · {sexLabel(a.patient?.sex ?? "unknown")}</span>
          <span className={cn("rounded-full px-2 py-0.5 text-[0.65rem] font-medium", STATUS_STYLE[a.status])}>{STATUS_LABEL[a.status]}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[0.72rem] text-muted-foreground">
          <span className="truncate">{a.reason ?? "No reason given"}</span>
          {c?.conditions.slice(0, 2).map((x) => <Badge key={x} tone="neutral" className="max-w-[10rem] truncate">{x}</Badge>)}
          {!!c?.results_back && <Badge tone="warning"><FlaskConical /> {c.results_back} result back</Badge>}
          {!!c?.abnormal && <Badge tone="danger">{c.abnormal} abnormal</Badge>}
          {c?.has_brief && <Badge tone="primary"><Sparkles /> Brief ready</Badge>}
        </div>
      </div>
      {a.status !== "seen" && a.status !== "cancelled" && (
        <Button size="sm" variant={a.status === "arrived" ? "strong" : "secondary"} className="shrink-0 rounded-full" asChild>
          <Link to={`/patients/${a.patient_id}/consult`}>{a.encounter_id ? <><ClipboardList /> Continue</> : <>Open <ChevronRight /></>}</Link>
        </Button>
      )}
    </li>
  );
}
