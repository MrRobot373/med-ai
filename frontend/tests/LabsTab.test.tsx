import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import LabsTab from "@/pages/PatientWorkspace/Labs";
import type { PatientOut } from "@/api/patients";

const PATIENT: PatientOut = {
  id: "p1",
  mrn: "DEMO-1003",
  first_name: "Elena",
  last_name: "Novak",
  preferred_name: null,
  date_of_birth: "1971-03-14",
  sex: "female",
  phone: null,
  email: null,
  notes: null,
  synthetic: true,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  age: 55,
};

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderLabsTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients/p1/labs"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<Outlet context={PATIENT} />}>
            <Route path="labs" element={<LabsTab />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LabsTab", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an honest empty state when no structured labs exist yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/trends")) return jsonResponse([]);
        if (url.includes("/observations")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderLabsTab();

    expect(await screen.findByText(/No structured lab values yet/)).toBeInTheDocument();
  });

  it("renders a trend with an abnormal badge and the reference range from the source document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/trends")) {
          return jsonResponse([
            {
              normalized_name: "hba1c",
              display_name: "HbA1c",
              unit: "%",
              unit_conflict: false,
              excluded_units: [],
              points: [
                {
                  observation_id: "o1",
                  measured_at: "2026-08-10",
                  value_numeric: 8.1,
                  value_text: null,
                  unit: "%",
                  abnormal_flag: true,
                  report_id: "r1",
                  source_page: 1,
                },
              ],
            },
          ]);
        }
        if (url.includes("/observations")) {
          return jsonResponse([
            {
              id: "o1",
              patient_id: "p1",
              encounter_id: null,
              report_id: "r1",
              observation_name: "HbA1c",
              normalized_name: "hba1c",
              value_numeric: 8.1,
              value_text: null,
              unit: "%",
              reference_low: 4.0,
              reference_high: 5.6,
              abnormal_flag: true,
              measured_at: "2026-08-10",
              source_page: 1,
              extraction_method: "table",
              source_excerpt: "HbA1c | 8.1 | % | 4.0-5.6",
              clinician_verified: false,
              created_at: "2026-08-10T00:00:00Z",
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderLabsTab();

    expect(await screen.findByText("HbA1c")).toBeInTheDocument();
    expect(screen.getByText("Abnormal result")).toBeInTheDocument();
    expect(screen.getByText("4–5.6")).toBeInTheDocument();
  });
});
