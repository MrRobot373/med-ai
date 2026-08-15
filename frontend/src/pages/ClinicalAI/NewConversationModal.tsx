import { useState } from "react";
import { Modal } from "@/components/Modal";
import type { ConversationScope } from "@/api/chat";
import type { ReportListItem } from "@/api/reports";
import type { EncounterOut } from "@/api/encounters";
import { SCOPE_DESCRIPTION, SCOPE_LABEL, UNIMPLEMENTED_SCOPES } from "./scope";

interface NewConversationSelection {
  scope: ConversationScope;
  encounterId?: string;
  reportId?: string;
}

export function NewConversationModal({
  implementedScopes,
  reports,
  encounters,
  onCreate,
  onClose,
  isPending,
  error,
}: {
  implementedScopes: ConversationScope[];
  reports?: ReportListItem[];
  encounters?: EncounterOut[];
  onCreate: (selection: NewConversationSelection) => void;
  onClose: () => void;
  isPending: boolean;
  error: string | null;
}) {
  const [scope, setScope] = useState<ConversationScope>(implementedScopes[0]);
  const [encounterId, setEncounterId] = useState(encounters?.[0]?.id ?? "");
  const [reportId, setReportId] = useState(reports?.[0]?.id ?? "");

  const needsEncounter = scope === "current_encounter";
  const needsReport = scope === "selected_report";
  const canSubmit = !needsEncounter || Boolean(encounterId);
  const canSubmitReport = !needsReport || Boolean(reportId);

  return (
    <Modal
      title="New Conversation"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className="rounded-md px-3 py-1.5 text-sm text-muted-text hover:bg-light-blue">
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending || !canSubmit || !canSubmitReport}
            onClick={() =>
              onCreate({
                scope,
                encounterId: needsEncounter ? encounterId : undefined,
                reportId: needsReport ? reportId : undefined,
              })
            }
            className="rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {isPending ? "Starting…" : "Start Chat"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <p className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}

        <fieldset className="space-y-2">
          <legend className="text-xs font-semibold uppercase tracking-wide text-muted-text">Scope</legend>
          {implementedScopes.map((s) => (
            <label key={s} className="flex cursor-pointer items-start gap-2 rounded-md p-2 hover:bg-light-blue">
              <input type="radio" name="scope" checked={scope === s} onChange={() => setScope(s)} className="mt-0.5" />
              <span>
                <span className="block text-sm font-medium text-navy">{SCOPE_LABEL[s]}</span>
                <span className="block text-xs text-muted-text">{SCOPE_DESCRIPTION[s]}</span>
              </span>
            </label>
          ))}
          {UNIMPLEMENTED_SCOPES.map((s) => (
            <div key={s} className="flex items-start gap-2 rounded-md p-2 opacity-50">
              <input type="radio" disabled className="mt-0.5" />
              <span>
                <span className="block text-sm font-medium text-navy">{SCOPE_LABEL[s]}</span>
                <span className="block text-xs text-muted-text">{SCOPE_DESCRIPTION[s]}</span>
              </span>
            </div>
          ))}
        </fieldset>

        {needsEncounter && (
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Encounter</span>
            {encounters && encounters.length > 0 ? (
              <select
                value={encounterId}
                onChange={(e) => setEncounterId(e.target.value)}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              >
                {encounters.map((e) => (
                  <option key={e.id} value={e.id}>
                    {(e.chief_complaint || e.encounter_type) + " — " + new Date(e.start_datetime).toLocaleDateString()}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-muted-text">No encounters recorded for this patient yet.</p>
            )}
          </label>
        )}

        {needsReport && (
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Report</span>
            {reports && reports.length > 0 ? (
              <select
                value={reportId}
                onChange={(e) => setReportId(e.target.value)}
                className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
              >
                {reports.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-muted-text">No reports uploaded for this patient yet.</p>
            )}
          </label>
        )}
      </div>
    </Modal>
  );
}
