import { useNavigate } from "react-router-dom";
import {
  BookOpenCheck,
  FileStack,
  LineChart,
  Pill,
  ScanEye,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { Card } from "@/components/Card";
import { usePatients, type PatientListItem } from "@/api/patients";
import type { AskAINavState } from "@/api/chat";
import type { ClinicalModulesNavState } from "@/pages/PatientWorkspace/ClinicalModules";
import type { ResearchNavState } from "@/pages/Research";

/**
 * Demo Scenarios (spec §89) — each card "opens the correct patient/context
 * automatically" by navigating to a real route with real deep-link state (the same
 * AskAINavState/ClinicalModulesNavState/ResearchNavState mechanisms other parts of
 * the app already use), and every button invokes the actual implemented pipeline —
 * never a replayed/static response.
 */
type Scenario = {
  title: string;
  description: string;
  icon: typeof FileStack;
  mrn: string;
  go: (navigate: ReturnType<typeof useNavigate>, patient: PatientListItem) => void;
};

const SCENARIOS: Scenario[] = [
  {
    title: "Patient Report Comparison",
    description: "Two real metabolic panels for Elena Novak, deterministically diffed — HbA1c/glucose/LDL down, creatinine up.",
    icon: FileStack,
    mrn: "DEMO-1003",
    go: (navigate, patient) =>
      navigate(`/patients/${patient.id}/clinical-modules`, { state: { module: "compare" } satisfies ClinicalModulesNavState }),
  },
  {
    title: "Longitudinal Lab Analysis",
    description: "Elena Novak's HbA1c/glucose trend across two real lab panels, months apart — a genuine trend line, not a mock.",
    icon: LineChart,
    mrn: "DEMO-1003",
    go: (navigate, patient) => navigate(`/patients/${patient.id}/labs`),
  },
  {
    title: "Vision + Guideline RAG",
    description: "Ask about Priya Patel's OCT imaging — real vision analysis, image-to-RAG, and cited local AMD guidance.",
    icon: ScanEye,
    mrn: "DEMO-1004",
    go: (navigate, patient) =>
      navigate(`/patients/${patient.id}/clinical-ai`, {
        state: {
          prefillQuestion:
            "What does the retinal imaging show, and what does local guidance recommend for managing wet age-related macular degeneration?",
          scope: "current_patient",
        } satisfies AskAINavState,
      }),
  },
  {
    title: "Medication Reconciliation",
    description: "Reconcile Robert Klein's most recent visit note against his system medication list — a real newly-detected drug.",
    icon: Pill,
    mrn: "DEMO-1002",
    go: (navigate, patient) => navigate(`/patients/${patient.id}/reports`),
  },
  {
    title: "Current Evidence Research",
    description: "Ask Research Mode about SLT vs. topical therapy for Robert Klein's glaucoma — real PubMed/FDA evidence when enabled.",
    icon: BookOpenCheck,
    mrn: "DEMO-1002",
    go: (navigate, patient) =>
      navigate("/research", {
        state: {
          prefillQuestion: "What is the recent evidence for selective laser trabeculoplasty (SLT) as first-line treatment for open-angle glaucoma?",
          patientId: patient.id,
        } satisfies ResearchNavState,
      }),
  },
  {
    title: "Clinical Note Generation",
    description: "Draft a SOAP note for Thomas Ferreira, a genuinely complex multi-morbidity patient (glaucoma + cataract + diabetic retinopathy).",
    icon: Sparkles,
    mrn: "DEMO-1005",
    go: (navigate, patient) =>
      navigate(`/patients/${patient.id}/clinical-modules`, { state: { module: "soap" } satisfies ClinicalModulesNavState }),
  },
];

export default function DemoScenariosPage() {
  const navigate = useNavigate();
  const { data: patients, isLoading } = usePatients("", false);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-primary-blue" />
        <h1 className="text-lg font-semibold text-navy">Demo Scenarios</h1>
      </div>
      <p className="text-sm text-muted-text">
        Each button opens the right synthetic patient and context, then invokes the real implemented pipeline — no
        replayed video or static response (spec §89). Requires the seeded demo dataset —
        run <code className="rounded bg-light-blue px-1 py-0.5">start-demo.bat</code> first if a scenario below shows
        as unavailable.
      </p>

      {isLoading && <p className="text-sm text-muted-text">Loading demo patients…</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SCENARIOS.map((scenario) => {
          const patient = patients?.find((p) => p.mrn === scenario.mrn);
          const Icon = scenario.icon;
          return (
            <Card key={scenario.title} className="flex flex-col gap-3 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-light-blue text-primary-blue">
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-navy">{scenario.title}</h2>
                  <p className="mt-1 text-xs text-muted-text">{scenario.description}</p>
                </div>
              </div>

              {patient ? (
                <button
                  type="button"
                  onClick={() => scenario.go(navigate, patient)}
                  className="mt-auto self-start rounded-md bg-primary-blue px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-blue/90"
                >
                  Run Scenario — {patient.first_name} {patient.last_name}
                </button>
              ) : (
                !isLoading && (
                  <div className="mt-auto flex items-center gap-1.5 text-xs text-danger">
                    <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                    Demo patient {scenario.mrn} not found — run start-demo.bat (or scripts/seed_demo_patients.py) first.
                  </div>
                )
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
