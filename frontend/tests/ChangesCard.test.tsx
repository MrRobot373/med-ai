import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangesCard } from "@/components/ChangesCard";
import type { PatientOut } from "@/api/patients";

const PATIENT: PatientOut = {
  id: "p1",
  mrn: "DEMO-1002",
  first_name: "Robert",
  last_name: "Klein",
  preferred_name: null,
  date_of_birth: "1958-09-03",
  sex: "male",
  phone: null,
  email: null,
  notes: null,
  synthetic: true,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  age: 67,
};

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients/p1/overview"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<Outlet context={PATIENT} />}>
            <Route path="overview" element={<ChangesCard />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ChangesCard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is honest about not having enough encounter history instead of picking an arbitrary window", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/encounters")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderCard();

    expect(await screen.findByText(/Needs at least two encounters/)).toBeInTheDocument();
  });

  it("renders detected changes since the previous encounter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/encounters")) {
          return jsonResponse([
            {
              id: "e2",
              patient_id: "p1",
              encounter_number: "DEMO-1002-ENC002",
              encounter_type: "outpatient",
              start_datetime: "2026-08-01T00:00:00Z",
              end_datetime: null,
              status: "completed",
              chief_complaint: "Follow-up",
              clinician_note: null,
              created_by: null,
              created_at: "2026-08-01T00:00:00Z",
              updated_at: "2026-08-01T00:00:00Z",
            },
            {
              id: "e1",
              patient_id: "p1",
              encounter_number: "DEMO-1002-ENC001",
              encounter_type: "outpatient",
              start_datetime: "2026-07-01T00:00:00Z",
              end_datetime: null,
              status: "completed",
              chief_complaint: "Initial visit",
              clinician_note: null,
              created_by: null,
              created_at: "2026-07-01T00:00:00Z",
              updated_at: "2026-07-01T00:00:00Z",
            },
          ]);
        }
        if (url.includes("/changes")) {
          return jsonResponse({
            patient_id: "p1",
            since: "2026-07-01",
            conditions_new: [{ id: "c1", display: "Dry eye", onset_date: "2026-07-15", resolved_date: null }],
            conditions_resolved: [],
            medications_started: [],
            medications_stopped: [],
            medications_dose_changed: [],
            allergies_new: [],
            observations_changed: [],
            observations_new_tests: [],
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderCard();

    expect(await screen.findByText(/New condition: Dry eye/)).toBeInTheDocument();
    expect(screen.getByText("since 2026-07-01")).toBeInTheDocument();
  });
});
