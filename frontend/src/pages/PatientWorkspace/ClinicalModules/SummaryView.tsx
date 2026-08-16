import { useState } from "react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateSummary, usePatientRuns, type SummaryPayload, type SummaryType } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import type { EncounterOut } from "@/api/encounters";
import { Bulleted, GenerationError, RunHistoryList, Section } from "./shared";

const SUMMARY_TYPES: { value: SummaryType; label: string }[] = [
  { value: "concise", label: "Concise patient summary" },
  { value: "encounter", label: "Encounter summary" },
  { value: "progress_note", label: "Progress-note summary" },
  { value: "discharge", label: "Discharge summary" },
];

export function SummaryView({ patientId, encounters }: { patientId: string; encounters: EncounterOut[] }) {
  const canWrite = useCanWrite();
  const [summaryType, setSummaryType] = useState<SummaryType>("concise");
  const [encounterId, setEncounterId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateSummary(patientId);
  const { data: history } = usePatientRuns(patientId, "summary");

  const payload = create.data?.payload as SummaryPayload | null | undefined;

  function generate() {
    setError(null);
    create.mutate(
      { summary_type: summaryType, encounter_id: encounterId || undefined },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not generate summary.") },
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-xs text-muted-text">
          A draft summary generated from this patient's documented facts — never a finalized clinical record.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Summary type</span>
            <select
              value={summaryType}
              onChange={(e) => setSummaryType(e.target.value as SummaryType)}
              className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
            >
              {SUMMARY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Encounter (optional)</span>
            <select
              value={encounterId}
              onChange={(e) => setEncounterId(e.target.value)}
              className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
            >
              <option value="">Overall recent state (no specific encounter)</option>
              {encounters.map((enc) => (
                <option key={enc.id} value={enc.id}>
                  {(enc.chief_complaint || enc.encounter_type) + " — " + new Date(enc.start_datetime).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        </div>
        {canWrite ? (
          <button
            type="button"
            onClick={generate}
            disabled={create.isPending}
            className="mt-3 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Generating…" : "Generate Summary"}
          </button>
        ) : (
          <p className="mt-3 text-xs text-muted-text">Generating a summary requires a doctor or admin account.</p>
        )}
        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="space-y-3 p-4">
          <Section title="Summary">
            <p className="whitespace-pre-wrap text-sm text-navy">{payload.summary}</p>
          </Section>
          <Section title="Key points">
            <Bulleted items={payload.key_points} />
          </Section>
          <Section title="Source trace">
            <Bulleted items={payload.source_trace} />
          </Section>
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="summary" />
    </div>
  );
}
