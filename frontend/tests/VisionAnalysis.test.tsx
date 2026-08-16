import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReportsTab from "@/pages/PatientWorkspace/Reports";
import type { PatientOut } from "@/api/patients";
import type { ReportListItem } from "@/api/reports";

const PATIENT: PatientOut = {
  id: "p1",
  mrn: "DEMO-1001",
  first_name: "Margaret",
  last_name: "Wallace",
  preferred_name: null,
  date_of_birth: "1953-04-12",
  sex: "female",
  phone: null,
  email: null,
  notes: null,
  synthetic: true,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  age: 73,
};

const DOCTOR_ME = {
  id: "u1",
  email: "doctor@gms.local",
  display_name: "Dr. Demo",
  role: "doctor",
  active: true,
  last_login_at: null,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function imageReport(overrides: Partial<ReportListItem> = {}): ReportListItem {
  return {
    id: "r1",
    patient_id: "p1",
    encounter_id: null,
    title: "Fundus.png",
    report_type: "imaging_report",
    report_date: null,
    source_filename: "fundus.png",
    mime_type: "image/png",
    file_size_bytes: 1234,
    ingestion_status: "completed",
    extraction_status: "not_applicable",
    patient_match_status: "matched",
    source_patient_name: null,
    source_mrn: null,
    page_count: null,
    ocr_used: false,
    archived: false,
    created_at: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

function renderReportsTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients/p1/reports"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<Outlet context={PATIENT} />}>
            <Route path="reports" element={<ReportsTab />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Vision analysis on the Reports tab", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("offers to run vision analysis for an unanalyzed image report, and shows the result once run", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/reports") && method === "GET" && !url.includes("/vision")) return jsonResponse([imageReport()]);
        if (url.endsWith("/vision") && method === "GET") return jsonResponse({ detail: "not found" }, 404);
        if (url.endsWith("/vision/analyze") && method === "POST") {
          return jsonResponse({
            report_id: "r1",
            status: "success",
            model: "qwen3.5:9b",
            analysis_error: null,
            created_at: "2026-08-14T00:00:00Z",
            updated_at: "2026-08-14T00:00:00Z",
            image_type: "fundus photograph",
            visible_text: [],
            observations: ["optic disc margins well-defined"],
            measurements_visible: [],
            clinical_entities: ["optic disc"],
            quality_limitations: [],
            uncertainties: [],
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderReportsTab();

    const runButton = await screen.findByRole("button", { name: /Run Vision Analysis/i });
    await user.click(runButton);

    expect(await screen.findByText("optic disc margins well-defined")).toBeInTheDocument();
    expect(screen.getByText(/fundus photograph/)).toBeInTheDocument();
  });

  it("shows an already-completed vision analysis without a manual trigger (automatic on ingestion)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/reports") && !url.includes("/vision")) return jsonResponse([imageReport()]);
        if (url.endsWith("/vision")) {
          return jsonResponse({
            report_id: "r1",
            status: "success",
            model: "qwen3.5:9b",
            analysis_error: null,
            created_at: "2026-08-14T00:00:00Z",
            updated_at: "2026-08-14T00:00:00Z",
            image_type: "fundus photograph",
            visible_text: [],
            observations: ["mild optic disc pallor"],
            measurements_visible: [],
            clinical_entities: [],
            quality_limitations: [],
            uncertainties: [],
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderReportsTab();

    expect(await screen.findByText("mild optic disc pallor")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Run Vision Analysis/i })).not.toBeInTheDocument();
  });

  it("offers image comparison once at least two analyzable images exist, and shows the result", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/reports") && method === "GET" && !url.includes("/vision"))
          return jsonResponse([imageReport({ id: "r1", title: "Previous.png" }), imageReport({ id: "r2", title: "Current.png" })]);
        if (url.endsWith("/vision") && method === "GET") return jsonResponse({ detail: "not found" }, 404);
        if (url.includes("/vision/compare") && method === "POST") {
          return jsonResponse({
            previous_report_id: "r1",
            current_report_id: "r2",
            previous_findings: ["baseline cupping"],
            current_findings: ["increased cupping"],
            observable_changes: ["cup-to-disc ratio increased"],
            differences: ["cup-to-disc ratio increased from 0.4 to 0.6"],
            limitations: [],
            clinical_evidence: [],
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderReportsTab();

    const compareButton = await screen.findByRole("button", { name: /Compare Images/i });
    await user.click(compareButton);
    await user.click(screen.getByRole("button", { name: "Compare" }));

    expect(await screen.findByText("cup-to-disc ratio increased from 0.4 to 0.6")).toBeInTheDocument();
  });
});
