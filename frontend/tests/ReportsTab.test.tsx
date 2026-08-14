import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReportsTab from "@/pages/PatientWorkspace/Reports";
import type { PatientOut } from "@/api/patients";

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

const VIEWER_ME = { ...DOCTOR_ME, id: "u2", email: "viewer@gms.local", role: "viewer" };

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
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

describe("ReportsTab", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an honest empty state when there are no reports", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/reports")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderReportsTab();

    expect(await screen.findByText(/No reports uploaded yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upload Report/i })).toBeInTheDocument();
  });

  it("renders a patient-mismatch banner with review actions for a doctor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/reports")) {
          return jsonResponse([
            {
              id: "r1",
              patient_id: "p1",
              encounter_id: null,
              title: "wrong_patient.pdf",
              report_type: "other",
              report_date: null,
              source_filename: "wrong_patient.pdf",
              mime_type: "application/pdf",
              file_size_bytes: 1234,
              ingestion_status: "completed",
              extraction_status: "success",
              patient_match_status: "mismatch",
              source_patient_name: "Sarah Demo",
              source_mrn: "DEMO-9999",
              page_count: 1,
              ocr_used: false,
              archived: false,
              created_at: "2026-08-14T00:00:00Z",
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderReportsTab();

    expect(await screen.findByText("Patient mismatch detected")).toBeInTheDocument();
    expect(screen.getByText("Sarah Demo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Confirm this is Margaret Wallace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel \(archive\)/i })).toBeInTheDocument();
  });

  it("hides the Upload Report control and mismatch review actions for a read-only viewer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(VIEWER_ME);
        if (url.includes("/reports")) {
          return jsonResponse([
            {
              id: "r1",
              patient_id: "p1",
              encounter_id: null,
              title: "wrong_patient.pdf",
              report_type: "other",
              report_date: null,
              source_filename: "wrong_patient.pdf",
              mime_type: "application/pdf",
              file_size_bytes: 1234,
              ingestion_status: "completed",
              extraction_status: "success",
              patient_match_status: "mismatch",
              source_patient_name: "Sarah Demo",
              source_mrn: "DEMO-9999",
              page_count: 1,
              ocr_used: false,
              archived: false,
              created_at: "2026-08-14T00:00:00Z",
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderReportsTab();

    await screen.findByText("Patient mismatch detected");
    expect(screen.queryByRole("button", { name: /Upload Report/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirm this is/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Cancel \(archive\)/i })).not.toBeInTheDocument();
  });
});
