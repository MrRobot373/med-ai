import { useLocation, useNavigate } from "react-router-dom";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientReports } from "@/api/reports";
import { usePatientEncounters } from "@/api/encounters";
import type { AskAINavState } from "@/api/chat";
import { ClinicalAIWorkspace, type InitialPrompt } from "@/pages/ClinicalAI/Workspace";
import { PATIENT_SUGGESTED_QUESTIONS, REPORT_SUGGESTED_QUESTIONS } from "@/pages/ClinicalAI/scope";

export default function ClinicalAITab() {
  const patient = usePatientContext();
  const { data: reports } = usePatientReports(patient.id);
  const { data: encounters } = usePatientEncounters(patient.id);
  const location = useLocation();
  const navigate = useNavigate();

  const navState = location.state as AskAINavState | null;
  const initialPrompt: InitialPrompt | undefined = navState?.prefillQuestion
    ? { text: navState.prefillQuestion, scope: navState.scope ?? "current_patient", reportId: navState.reportId }
    : undefined;

  return (
    <ClinicalAIWorkspace
      // Keyed by patient so switching patients fully remounts the workspace — spec
      // §40: never silently continue a patient-specific conversation for someone else.
      key={patient.id}
      patient={patient}
      implementedScopes={["current_patient", "current_encounter", "selected_report"]}
      reports={reports}
      encounters={encounters}
      suggestedQuestionsFor={(scope) => (scope === "selected_report" ? REPORT_SUGGESTED_QUESTIONS : PATIENT_SUGGESTED_QUESTIONS)}
      initialPrompt={initialPrompt}
      onConsumedInitialPrompt={() => navigate(location.pathname, { replace: true, state: null })}
    />
  );
}
