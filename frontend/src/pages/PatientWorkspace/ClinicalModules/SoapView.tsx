import { useState } from "react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useCreateSOAP, usePatientRuns, type SOAPPayload } from "@/api/clinicalModules";
import { useCanWrite } from "@/api/auth";
import type { EncounterOut } from "@/api/encounters";
import { Bulleted, GenerationError, RunHistoryList, Section } from "./shared";

export function SoapView({ patientId, encounters }: { patientId: string; encounters: EncounterOut[] }) {
  const canWrite = useCanWrite();
  const [encounterId, setEncounterId] = useState(encounters[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateSOAP(patientId);
  const { data: history } = usePatientRuns(patientId, "soap");

  const payload = create.data?.payload as SOAPPayload | null | undefined;

  function generate() {
    if (!encounterId) return;
    setError(null);
    create.mutate({ encounter_id: encounterId }, { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not generate SOAP note.") });
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-xs text-muted-text">
          A clinician-review DRAFT SOAP note for one encounter — never automatically saved as a finalized record.
        </p>
        {encounters.length === 0 ? (
          <p className="mt-3 text-sm text-muted-text">This patient has no encounters yet.</p>
        ) : (
          <label className="mt-3 block text-sm">
            <span className="mb-1 block font-medium text-navy">Encounter</span>
            <select
              value={encounterId}
              onChange={(e) => setEncounterId(e.target.value)}
              className="w-full max-w-md rounded-md border border-border px-2 py-1.5 text-sm"
            >
              {encounters.map((enc) => (
                <option key={enc.id} value={enc.id}>
                  {(enc.chief_complaint || enc.encounter_type) + " — " + new Date(enc.start_datetime).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        )}
        {canWrite ? (
          <button
            type="button"
            onClick={generate}
            disabled={create.isPending || !encounterId}
            className="mt-3 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {create.isPending ? "Generating…" : "Generate SOAP Note"}
          </button>
        ) : (
          <p className="mt-3 text-xs text-muted-text">Generating a SOAP note requires a doctor or admin account.</p>
        )}
        {error && (
          <div className="mt-3">
            <GenerationError message={error} />
          </div>
        )}
      </Card>

      {payload && (
        <Card className="space-y-3 p-4">
          <Section title="Subjective">
            {Object.entries(payload.subjective).length === 0 ? (
              <p className="text-sm text-muted-text">Not documented.</p>
            ) : (
              <dl className="space-y-1 text-sm">
                {Object.entries(payload.subjective).map(([k, v]) => (
                  <div key={k}>
                    <dt className="inline font-medium text-navy capitalize">{k.replace(/_/g, " ")}: </dt>
                    <dd className="inline text-navy">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Section>
          <Section title="Objective">
            {Object.entries(payload.objective).length === 0 ? (
              <p className="text-sm text-muted-text">Not documented.</p>
            ) : (
              <dl className="space-y-1 text-sm">
                {Object.entries(payload.objective).map(([k, v]) => (
                  <div key={k}>
                    <dt className="inline font-medium text-navy capitalize">{k.replace(/_/g, " ")}: </dt>
                    <dd className="inline text-navy">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Section>
          <Section title="Assessment">
            <Bulleted items={payload.assessment} />
          </Section>
          <Section title="Plan">
            <Bulleted items={payload.plan} />
          </Section>
          <Section title="Missing information">
            <Bulleted items={payload.missing_information} />
          </Section>
          <Section title="Source trace">
            <Bulleted items={payload.source_trace} />
          </Section>
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="SOAP note" />
    </div>
  );
}
