import { useState } from "react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateReportComparison, usePatientRuns, type ReportComparisonPayload } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import type { ReportListItem } from "@/api/reports";
import { Bulleted, GenerationError, RunHistoryList, Section } from "./shared";

const DIRECTION_STYLE: Record<string, string> = {
  increased: "text-danger",
  decreased: "text-primary-blue",
  unchanged: "text-muted-text",
  new: "text-success",
  resolved: "text-muted-text",
};

export function ReportComparisonView({ patientId, reports }: { patientId: string; reports: ReportListItem[] }) {
  const canWrite = useCanWrite();
  const [previousId, setPreviousId] = useState(reports[0]?.id ?? "");
  const [currentId, setCurrentId] = useState(reports[1]?.id ?? reports[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateReportComparison(patientId);
  const { data: history } = usePatientRuns(patientId, "report_comparison");

  const payload = create.data?.payload as ReportComparisonPayload | null | undefined;

  function generate() {
    if (!previousId || !currentId || previousId === currentId) return;
    setError(null);
    create.mutate(
      { previous_report_id: previousId, current_report_id: currentId },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not compare reports.") },
    );
  }

  if (reports.length < 2) {
    return (
      <Card className="p-6 text-center text-sm text-muted-text">
        Report comparison needs at least two reports for this patient — upload another report on the Reports tab to
        get started.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-xs text-muted-text">
          Numeric value changes are calculated deterministically from structured lab data — never by the model. The
          model only narrates non-numeric textual differences.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Previous</span>
            <select value={previousId} onChange={(e) => setPreviousId(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm">
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Current</span>
            <select value={currentId} onChange={(e) => setCurrentId(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm">
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        {previousId === currentId && <p className="mt-2 text-xs text-muted-text">Select two different reports to compare.</p>}
        {canWrite ? (
          <button
            type="button"
            onClick={generate}
            disabled={create.isPending || previousId === currentId}
            className="mt-3 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Comparing…" : "Compare Reports"}
          </button>
        ) : (
          <p className="mt-3 text-xs text-muted-text">Comparing reports requires a doctor or admin account.</p>
        )}
        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="space-y-3 p-4">
          <Section title="Numeric changes (deterministic)">
            {payload.numeric_changes.length === 0 ? (
              <p className="text-sm text-muted-text">No matching numeric observations were found on both reports.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-text">
                    <th className="py-1 font-medium">Test</th>
                    <th className="py-1 font-medium">Previous</th>
                    <th className="py-1 font-medium">Current</th>
                    <th className="py-1 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {payload.numeric_changes.map((c, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="py-1.5 text-navy">{c.name}</td>
                      <td className="py-1.5 text-navy">{c.previous_value ?? "—"}{c.unit && c.previous_value !== null ? ` ${c.unit}` : ""}</td>
                      <td className="py-1.5 text-navy">{c.current_value ?? "—"}{c.unit && c.current_value !== null ? ` ${c.unit}` : ""}</td>
                      <td className={`py-1.5 font-medium ${DIRECTION_STYLE[c.direction]}`}>
                        {c.direction}
                        {c.percent_change !== null && ` (${c.percent_change > 0 ? "+" : ""}${c.percent_change.toFixed(0)}%)`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section title="Narrative differences">
            <Bulleted items={payload.narrative_differences} />
          </Section>
          <Section title="Limitations">
            <Bulleted items={payload.limitations} />
          </Section>

          {payload.clinical_evidence.length > 0 && (
            <Section title="Clinical evidence">
              <div className="space-y-2">
                {payload.clinical_evidence.map((e, i) => (
                  <div key={i} className="rounded-md border border-border p-2 text-xs">
                    <div className="font-medium text-navy">
                      {e.source_title}
                      {e.page && <> · page {e.page}</>}
                      {e.section && <> · {e.section}</>}
                    </div>
                    <p className="mt-0.5 text-muted-text">&ldquo;{e.excerpt}&rdquo;</p>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="report comparison" />
    </div>
  );
}
