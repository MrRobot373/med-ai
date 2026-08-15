import { AlertTriangle } from "lucide-react";
import { Card } from "@/components/Card";
import { TrendChart } from "@/components/TrendChart";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientObservationTrends, usePatientObservations } from "@/api/observations";

function formatValue(value: number | null, text: string | null, unit: string | null): string {
  if (value !== null) return `${value}${unit ? ` ${unit}` : ""}`;
  if (text !== null) return text;
  return "—";
}

function formatReferenceRange(low: number | null, high: number | null): string {
  if (low !== null && high !== null) return `${low}–${high}`;
  if (low !== null) return `≥ ${low}`;
  if (high !== null) return `≤ ${high}`;
  return "Not stated in source";
}

export default function LabsTab() {
  const patient = usePatientContext();
  const { data: trends, isLoading: trendsLoading } = usePatientObservationTrends(patient.id);
  const { data: observations } = usePatientObservations(patient.id);

  if (trendsLoading) {
    return <p className="text-sm text-muted-text">Loading labs…</p>;
  }

  if (!trends || trends.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-muted-text">
        No structured lab values yet. Values are extracted automatically from uploaded reports that contain
        recognizable test results (spec §33) — upload a lab report on the Reports tab to get started.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-text">
        Trends are computed deterministically from stored values — not the language model — and only ever compare
        readings recorded in the same (or a verified-equivalent) unit.
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {trends.map((trend) => {
          const relatedObservations = observations?.filter((o) => o.normalized_name === trend.normalized_name) ?? [];
          const hasAbnormal = trend.points.some((p) => p.abnormal_flag);
          return (
            <Card key={trend.normalized_name} className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-navy">{trend.display_name}</h2>
                {hasAbnormal && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-medium text-danger">
                    <AlertTriangle className="h-3 w-3" />
                    Abnormal result
                  </span>
                )}
              </div>

              <div className="mt-3">
                <TrendChart trend={trend} />
              </div>

              <table className="mt-3 w-full text-xs">
                <thead>
                  <tr className="border-t border-border text-left text-muted-text">
                    <th className="py-1.5 font-medium">Date</th>
                    <th className="py-1.5 font-medium">Result</th>
                    <th className="py-1.5 font-medium">Reference range</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedObservations.map((o) => (
                    <tr key={o.id} className="border-t border-border">
                      <td className="py-1.5 text-navy">{o.measured_at ?? "Date unknown"}</td>
                      <td className={`py-1.5 ${o.abnormal_flag ? "font-medium text-danger" : "text-navy"}`}>
                        {formatValue(o.value_numeric, o.value_text, o.unit)}
                        {o.abnormal_flag && " ⚠"}
                      </td>
                      <td className="py-1.5 text-muted-text">{formatReferenceRange(o.reference_low, o.reference_high)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
