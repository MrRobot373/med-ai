import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card } from "@/components/Card";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientEncounters } from "@/api/encounters";
import { usePatientChanges, hasAnyChanges } from "@/api/changes";

/** Deterministic diff (spec §35) — never an LLM guess — of what changed since the
 * patient's previous encounter. Needs at least two encounters to have a "previous
 * visit" to compare against; with fewer, says so honestly rather than picking an
 * arbitrary fallback window like "last 30 days". */
export function ChangesCard() {
  const patient = usePatientContext();
  const { data: encounters } = usePatientEncounters(patient.id);

  const sorted = [...(encounters ?? [])].sort(
    (a, b) => new Date(b.start_datetime).getTime() - new Date(a.start_datetime).getTime(),
  );
  const since = sorted.length >= 2 ? sorted[1].start_datetime.slice(0, 10) : undefined;

  const { data: summary, isLoading } = usePatientChanges(patient.id, since);

  if (!since) {
    return (
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-navy">What's Changed</h2>
        <p className="mt-2 text-sm text-muted-text">
          Needs at least two encounters to compare against a previous visit — not enough history yet.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-navy">What's Changed</h2>
        <span className="text-xs text-muted-text">since {since}</span>
      </div>

      {isLoading && <p className="mt-2 text-sm text-muted-text">Comparing…</p>}

      {summary && !hasAnyChanges(summary) && (
        <p className="mt-2 text-sm text-muted-text">No recorded changes since the previous visit.</p>
      )}

      {summary && hasAnyChanges(summary) && (
        <ul className="mt-3 space-y-2 text-sm text-navy">
          {summary.conditions_new.map((c) => (
            <li key={`cn-${c.id}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary-blue" />
              New condition: {c.display}
            </li>
          ))}
          {summary.conditions_resolved.map((c) => (
            <li key={`cr-${c.id}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
              Resolved: {c.display}
            </li>
          ))}
          {summary.medications_started.map((m) => (
            <li key={`ms-${m.id}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan" />
              Started {m.medication_name}
            </li>
          ))}
          {summary.medications_stopped.map((m) => (
            <li key={`mst-${m.id}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-navy" />
              Stopped {m.medication_name}
            </li>
          ))}
          {summary.medications_dose_changed.map((m, i) => (
            <li key={`mdc-${i}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
              {m.previous_medication_name} → {m.current_medication_name}
            </li>
          ))}
          {summary.allergies_new.map((a) => (
            <li key={`al-${a.id}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-danger" />
              New allergy: {a.substance}
            </li>
          ))}
          {summary.observations_changed.map((o, i) => (
            <li key={`oc-${i}`} className="flex items-center gap-2">
              {o.direction === "increased" && <ArrowUp className="h-3.5 w-3.5 shrink-0 text-danger" />}
              {o.direction === "decreased" && <ArrowDown className="h-3.5 w-3.5 shrink-0 text-primary-blue" />}
              {o.direction === "unchanged" && <Minus className="h-3.5 w-3.5 shrink-0 text-muted-text" />}
              {o.display_name}: {o.previous_value} → {o.current_value} {o.current_unit}
            </li>
          ))}
          {summary.observations_new_tests.map((name, i) => (
            <li key={`ont-${i}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary-blue" />
              New test result: {name}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
