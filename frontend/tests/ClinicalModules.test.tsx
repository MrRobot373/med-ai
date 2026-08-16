import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ClinicalModulesTab from "@/pages/PatientWorkspace/ClinicalModules";
import WorkflowPage from "@/pages/Workflow";
import type { PatientOut } from "@/api/patients";

const PATIENT: PatientOut = {
  id: "p1",
  mrn: "DEMO-1001",
  first_name: "Iris",
  last_name: "Whitfield",
  preferred_name: null,
  date_of_birth: "1962-11-20",
  sex: "female",
  phone: null,
  email: null,
  notes: null,
  synthetic: true,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  age: 63,
};

const DOCTOR_ME = {
  id: "u1",
  email: "doctor@gms.local",
  display_name: "Dr. Demo",
  role: "doctor",
  active: true,
  last_login_at: null,
};

const ENCOUNTER = {
  id: "e1",
  patient_id: "p1",
  encounter_number: "DEMO-1001-ENC001",
  encounter_type: "outpatient",
  start_datetime: "2026-08-01T00:00:00Z",
  end_datetime: null,
  status: "completed",
  chief_complaint: "Blurry vision",
  clinician_note: null,
  created_by: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

function reportFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: "r1",
    patient_id: "p1",
    encounter_id: null,
    title: "Lab Report",
    report_type: "lab_report",
    report_date: null,
    source_filename: "lab.pdf",
    mime_type: "application/pdf",
    file_size_bytes: 100,
    ingestion_status: "completed",
    extraction_status: "success",
    patient_match_status: "matched",
    source_patient_name: null,
    source_mrn: null,
    page_count: 1,
    ocr_used: false,
    archived: false,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderClinicalModulesTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients/p1/clinical-modules"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<Outlet context={PATIENT} />}>
            <Route path="clinical-modules" element={<ClinicalModulesTab />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderWorkflowPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/workflow"]}>
        <Routes>
          <Route path="/workflow" element={<WorkflowPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Clinical Modules — patient tab", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("generates a summary and shows the structured result", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/encounters")) return jsonResponse([ENCOUNTER]);
        if (url.includes("/reports") && !url.includes("/clinical")) return jsonResponse([]);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        if (url.includes("/clinical/summary") && method === "POST") {
          return jsonResponse({
            id: "run1",
            module_type: "summary",
            patient_id: "p1",
            encounter_id: null,
            input_params: { summary_type: "concise" },
            payload: { summary: "Stable glaucoma, controlled IOP.", key_points: ["IOP controlled"], source_trace: ["patient facts"] },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderClinicalModulesTab();

    await user.click(await screen.findByRole("button", { name: "Generate Summary" }));

    expect(await screen.findByText("Stable glaucoma, controlled IOP.")).toBeInTheDocument();
    expect(screen.getByText("IOP controlled")).toBeInTheDocument();
  });

  it("generates a SOAP note for a selected encounter", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/encounters")) return jsonResponse([ENCOUNTER]);
        if (url.includes("/reports") && !url.includes("/clinical")) return jsonResponse([]);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        if (url.includes("/clinical/soap") && method === "POST") {
          return jsonResponse({
            id: "run2",
            module_type: "soap",
            patient_id: "p1",
            encounter_id: "e1",
            input_params: {},
            payload: {
              subjective: { chief_complaint: "blurry vision" },
              objective: {},
              assessment: ["POAG, stable"],
              plan: ["continue latanoprost"],
              missing_information: [],
              source_trace: [],
            },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderClinicalModulesTab();
    await user.click(await screen.findByRole("button", { name: "SOAP Note" }));
    await user.click(screen.getByRole("button", { name: "Generate SOAP Note" }));

    expect(await screen.findByText("POAG, stable")).toBeInTheDocument();
    expect(screen.getByText("continue latanoprost")).toBeInTheDocument();
  });

  it("shows an honest empty state for report comparison with fewer than two reports", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/encounters")) return jsonResponse([]);
        if (url.includes("/reports") && !url.includes("/clinical")) return jsonResponse([reportFixture()]);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderClinicalModulesTab();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Compare Reports" }));

    expect(await screen.findByText(/needs at least two reports/i)).toBeInTheDocument();
  });

  it("hides generation controls and shows a read-only notice for a viewer", async () => {
    const VIEWER_ME = { ...DOCTOR_ME, id: "u2", email: "viewer@gms.local", role: "viewer" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(VIEWER_ME);
        if (url.includes("/encounters")) return jsonResponse([ENCOUNTER]);
        if (url.includes("/reports") && !url.includes("/clinical")) return jsonResponse([]);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderClinicalModulesTab();

    expect(await screen.findByText(/requires a doctor or admin account/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate Summary" })).not.toBeInTheDocument();
  });
});

describe("Workflow page — Guideline Q&A", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks a question and shows a cited, evidence-grounded answer", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        if (url.includes("/clinical/guideline-qa") && method === "POST") {
          return jsonResponse({
            id: "run3",
            module_type: "guideline_qa",
            patient_id: null,
            encounter_id: null,
            input_params: { question: "What is the target IOP?" },
            payload: {
              answer: "Target IOP is individualized per patient [L1].",
              no_guideline_found: false,
              evidence_quality: "moderate",
              citations: [{ label: "L1", source_title: "ICO Guidelines", page: 12, section: "POAG", excerpt: "Target IOP..." }],
            },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderWorkflowPage();

    const input = await screen.findByPlaceholderText("Ask a guideline question…");
    await user.type(input, "What is the target IOP?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/Target IOP is individualized/)).toBeInTheDocument();
    expect(screen.getByText(/ICO Guidelines/)).toBeInTheDocument();
  });

  it("suggested questions actually send a real question", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/clinical/runs")) return jsonResponse([]);
        if (url.includes("/clinical/guideline-qa") && method === "POST") {
          const body = JSON.parse((init?.body as string) ?? "{}");
          return jsonResponse({
            id: "run4",
            module_type: "guideline_qa",
            patient_id: null,
            encounter_id: null,
            input_params: { question: body.question },
            payload: { answer: "No relevant guideline was found in the local knowledge base for this question.", no_guideline_found: true, evidence_quality: "insufficient", citations: [] },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderWorkflowPage();
    const suggestion = await screen.findByRole("button", {
      name: "What are the diagnostic criteria for primary open-angle glaucoma?",
    });
    await user.click(suggestion);

    expect(await screen.findByText(/No relevant guideline was found/)).toBeInTheDocument();
  });
});
