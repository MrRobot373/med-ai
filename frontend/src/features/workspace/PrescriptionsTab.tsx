import { FileSignature, Printer } from "lucide-react";
import { useState } from "react";
import { usePrescriptions } from "@/api/hooks";
import { Badge, Button, Card, EmptyState, Skeleton } from "@/components/ui";
import { PrescriptionBuilder } from "@/features/consult/PrescriptionBuilder";
import { SeverityBadge } from "@/features/consult/parts";
import { cn, fmtDate } from "@/lib/utils";
import { useWorkspace } from "./context";

export default function PrescriptionsTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = usePrescriptions(patient.id);
  const [selected, setSelected] = useState<string | null>(null);
  if (isLoading) return <Skeleton className="h-96" />;
  const list = data ?? [];
  if (!list.length) return <Card><EmptyState icon={<FileSignature />} title="No prescriptions yet" description="Prescriptions written in a consultation appear here and are used as context at the next visit." /></Card>;
  const current = list.find((r) => r.id === selected) ?? list[0];
  return (
    <div className="grid gap-[var(--gap)] lg:grid-cols-[300px_1fr]">
      <Card className="h-fit p-2">
        {list.map((r) => (
          <button key={r.id} onClick={() => setSelected(r.id)} className={cn("w-full rounded-xl px-3 py-2.5 text-left transition", r.id === current.id ? "bg-strong text-strong-foreground shadow-card" : "hover:bg-muted")}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[0.82rem] font-semibold">{fmtDate(r.date)}</span>
              {r.status === "draft" ? <Badge tone="warning">Draft</Badge> : r.context?.status && r.context.status !== "ok" ? <SeverityBadge severity={r.context.status} label={r.context.status === "critical" ? "Overridden" : "Cautions"} /> : null}
            </div>
            <div className={cn("mt-0.5 truncate text-[0.72rem]", r.id === current.id ? "text-strong-foreground/75" : "text-muted-foreground")}>{r.diagnosis ?? "No diagnosis"} · {r.items.map((i) => i.drug).join(", ")}</div>
          </button>
        ))}
      </Card>
      <div className="min-w-0 space-y-3">
        {current.status === "final" && <div className="flex justify-end"><Button size="sm" variant="secondary" className="rounded-full" asChild><a href={`/print/prescription/${current.id}`} target="_blank" rel="noreferrer"><Printer /> Print</a></Button></div>}
        <PrescriptionBuilder key={current.id + current.status} rx={current} review={null} canWrite={canWrite && current.status === "draft"} />
      </div>
    </div>
  );
}
