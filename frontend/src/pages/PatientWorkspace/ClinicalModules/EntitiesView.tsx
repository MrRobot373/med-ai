import { useState } from "react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateEntityExtraction, usePatientRuns, type EntityExtractionPayload } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import type { EncounterOut } from "@/api/encounters";
import type { ReportListItem } from "@/api/reports";
import { GenerationError, RunHistoryList } from "./shared";

const CATEGORY_STYLE: Record<string, string> = {
  condition: "bg-danger/10 text-danger",
  medication: "bg-primary-blue/10 text-primary-blue",
  allergy: "bg-amber-100 text-amber-700",
  procedure: "bg-light-blue text-navy",
  lab_finding: "bg-success/10 text-success",
  symptom: "bg-light-blue text-navy",
  other: "bg-light-blue text-muted-text",
};

export function EntitiesView({
  patientId,
  encounters,
  reports,
}: {
  patientId: string;
  encounters: EncounterOut[];
  reports: ReportListItem[];
}) {
  const canWrite = useCanWrite();
  const [source, setSource] = useState<"encounter" | "report">(encounters.length > 0 ? "encounter" : "report");
  const [encounterId, setEncounterId] = useState(encounters[0]?.id ?? "");
  const [reportId, setReportId] = useState(reports[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateEntityExtraction(patientId);
  const { data: history } = usePatientRuns(patientId, "entity_extraction");

  const payload = create.data?.payload as EntityExtractionPayload | null | undefined;
  const canGenerate = source === "encounter" ? Boolean(encounterId) : Boolean(reportId);

  function generate() {
    if (!canGenerate) return;
    setError(null);
    create.mutate(
      source === "encounter" ? { encounter_id: encounterId } : { report_id: reportId },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not extract entities.") },
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-xs text-muted-text">
          Extracts clinical entities literally present in the source text — never inferred beyond what's written.
        </p>
        <div className="mt-3 flex gap-4 text-sm">
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={source === "encounter"} onChange={() => setSource("encounter")} disabled={encounters.length === 0} />
            From an encounter
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={source === "report"} onChange={() => setSource("report")} disabled={reports.length === 0} />
            From a report
          </label>
        </div>
        {source === "encounter" ? (
          <select
            value={encounterId}
            onChange={(e) => setEncounterId(e.target.value)}
            className="mt-2 w-full max-w-md rounded-md border border-border px-2 py-1.5 text-sm"
          >
            {encounters.map((enc) => (
              <option key={enc.id} value={enc.id}>
                {(enc.chief_complaint || enc.encounter_type) + " — " + new Date(enc.start_datetime).toLocaleDateString()}
              </option>
            ))}
          </select>
        ) : (
          <select
            value={reportId}
            onChange={(e) => setReportId(e.target.value)}
            className="mt-2 w-full max-w-md rounded-md border border-border px-2 py-1.5 text-sm"
          >
            {reports.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        )}
        {canWrite ? (
          <button
            type="button"
            onClick={generate}
            disabled={create.isPending || !canGenerate}
            className="mt-3 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Extracting…" : "Extract Entities"}
          </button>
        ) : (
          <p className="mt-3 text-xs text-muted-text">Extracting entities requires a doctor or admin account.</p>
        )}
        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="p-4">
          {payload.entities.length === 0 ? (
            <p className="text-sm text-muted-text">No clinical entities were found in the source text.</p>
          ) : (
            <ul className="space-y-2">
              {payload.entities.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${CATEGORY_STYLE[e.category] ?? CATEGORY_STYLE.other}`}>
                    {e.category.replace(/_/g, " ")}
                  </span>
                  <span>
                    <span className="font-medium text-navy">{e.text}</span>
                    {e.context && <span className="text-muted-text"> — &ldquo;{e.context}&rdquo;</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="entity extraction" />
    </div>
  );
}
