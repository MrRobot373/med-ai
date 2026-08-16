import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateDifferential, usePatientRuns, type DifferentialPayload } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import type { EncounterOut } from "@/api/encounters";
import { Bulleted, GenerationError, RunHistoryList, Section } from "./shared";

export function DifferentialView({ patientId, encounters }: { patientId: string; encounters: EncounterOut[] }) {
  const canWrite = useCanWrite();
  const [encounterId, setEncounterId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateDifferential(patientId);
  const { data: history } = usePatientRuns(patientId, "differential_support");

  const payload = create.data?.payload as DifferentialPayload | null | undefined;

  function generate() {
    setError(null);
    create.mutate(
      { encounter_id: encounterId || undefined },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not generate differential support.") },
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-xs text-muted-text">
          <strong>Differential Support</strong> — clinician-support only, never an autonomous diagnosis. Each
          candidate is tied to real retrieved evidence, cited and validated, never invented.
        </p>
        <label className="mt-3 block max-w-md text-sm">
          <span className="mb-1 block font-medium text-navy">Encounter (optional — adds chief complaint context)</span>
          <select
            value={encounterId}
            onChange={(e) => setEncounterId(e.target.value)}
            className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
          >
            <option value="">Patient-level (no specific encounter)</option>
            {encounters.map((enc) => (
              <option key={enc.id} value={enc.id}>
                {(enc.chief_complaint || enc.encounter_type) + " — " + new Date(enc.start_datetime).toLocaleDateString()}
              </option>
            ))}
          </select>
        </label>
        {canWrite ? (
          <button
            type="button"
            onClick={generate}
            disabled={create.isPending}
            className="mt-3 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Generating…" : "Generate Differential Support"}
          </button>
        ) : (
          <p className="mt-3 text-xs text-muted-text">Generating differential support requires a doctor or admin account.</p>
        )}
        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="space-y-3 p-4">
          <Section title="Patient summary">
            <p className="text-sm text-navy">{payload.patient_summary}</p>
          </Section>

          {payload.red_flags.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/5 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
              <div>
                <div className="text-sm font-medium text-danger">Red flags</div>
                <Bulleted items={payload.red_flags} />
              </div>
            </div>
          )}

          <Section title="Differential">
            {payload.differential.length === 0 ? (
              <p className="text-sm text-muted-text">No candidates were generated from the available evidence.</p>
            ) : (
              <div className="space-y-3">
                {payload.differential.map((c, i) => (
                  <div key={i} className="rounded-md border border-border p-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-navy">
                      {c.condition}
                      {c.evidence_ids.length > 0 && (
                        <span className="flex gap-1">
                          {c.evidence_ids.map((id) => (
                            <span key={id} className="rounded bg-light-blue px-1.5 py-0.5 text-[11px] font-medium text-primary-blue">
                              {id}
                            </span>
                          ))}
                        </span>
                      )}
                    </div>
                    {c.supporting_findings.length > 0 && (
                      <div className="mt-1.5 text-xs">
                        <span className="font-medium text-success">Supporting: </span>
                        {c.supporting_findings.join("; ")}
                      </div>
                    )}
                    {c.findings_against.length > 0 && (
                      <div className="mt-1 text-xs">
                        <span className="font-medium text-danger">Against: </span>
                        {c.findings_against.join("; ")}
                      </div>
                    )}
                    {c.missing_information.length > 0 && (
                      <div className="mt-1 text-xs">
                        <span className="font-medium text-muted-text">Would help confirm/rule out: </span>
                        {c.missing_information.join("; ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Recommended clarifications">
            <Bulleted items={payload.recommended_clarifications} />
          </Section>

          <Section title="Evidence quality">
            <p className="text-sm text-muted-text">{payload.evidence_quality}</p>
          </Section>
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="differential support" />
    </div>
  );
}
