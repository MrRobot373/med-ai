import { useState } from "react";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientEncounters } from "@/api/encounters";
import { usePatientReports } from "@/api/reports";
import { SummaryView } from "./SummaryView";
import { SoapView } from "./SoapView";
import { EntitiesView } from "./EntitiesView";
import { DifferentialView } from "./DifferentialView";
import { ReportComparisonView } from "./ReportComparisonView";

type Module = "summary" | "soap" | "entities" | "differential" | "compare";

const MODULES: { key: Module; label: string }[] = [
  { key: "summary", label: "Summary" },
  { key: "soap", label: "SOAP Note" },
  { key: "entities", label: "Entity Extraction" },
  { key: "differential", label: "Differential Support" },
  { key: "compare", label: "Compare Reports" },
];

/**
 * Structured Clinical Modules (spec §63) — each a real dedicated workflow with its
 * own schema, not "the same prompt sent to the chat endpoint." Guideline Q&A lives on
 * the global Workflow page instead of here, since it's patient-independent.
 */
export default function ClinicalModulesTab() {
  const patient = usePatientContext();
  const { data: encounters } = usePatientEncounters(patient.id);
  const { data: reports } = usePatientReports(patient.id);
  const [active, setActive] = useState<Module>("summary");

  const encounterList = encounters ?? [];
  const reportList = (reports ?? []).filter((r) => r.ingestion_status === "completed" && r.patient_match_status !== "mismatch");

  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap gap-1 border-b border-border pb-2">
        {MODULES.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setActive(m.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              active === m.key ? "bg-light-blue text-primary-blue" : "text-muted-text hover:bg-light-blue hover:text-navy"
            }`}
          >
            {m.label}
          </button>
        ))}
      </nav>

      {active === "summary" && <SummaryView patientId={patient.id} encounters={encounterList} />}
      {active === "soap" && <SoapView patientId={patient.id} encounters={encounterList} />}
      {active === "entities" && <EntitiesView patientId={patient.id} encounters={encounterList} reports={reportList} />}
      {active === "differential" && <DifferentialView patientId={patient.id} encounters={encounterList} />}
      {active === "compare" && <ReportComparisonView patientId={patient.id} reports={reportList} />}
    </div>
  );
}
