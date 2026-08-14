import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PatientWorkspace } from "@/layouts/PatientWorkspace";

const SAMPLE_PATIENT = {
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

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderWorkspace(initialPath = "/patients/p1/overview") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/patients/:patientId" element={<PatientWorkspace />}>
            <Route path="overview" element={<div>Overview tab content</div>} />
            <Route path="timeline" element={<div>Timeline tab content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PatientWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("always shows the current patient's identity so the clinician can't lose context (spec §24)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(SAMPLE_PATIENT)),
    );

    renderWorkspace();

    expect(await screen.findByText("Robert Klein")).toBeInTheDocument();
    expect(screen.getByText(/DEMO-1002/)).toBeInTheDocument();
    expect(screen.getByText(/67 years/)).toBeInTheDocument();
    expect(screen.getByText("SYNTHETIC DEMO DATA — NOT A REAL PATIENT")).toBeInTheDocument();
  });

  it("switches tab content on navigation without losing the patient header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(SAMPLE_PATIENT)),
    );
    const user = userEvent.setup();

    renderWorkspace();
    expect(await screen.findByText("Overview tab content")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Timeline" }));

    expect(await screen.findByText("Timeline tab content")).toBeInTheDocument();
    expect(screen.getByText("Robert Klein")).toBeInTheDocument(); // header persists
  });

  it("shows a not-found state instead of a blank/broken page for an unknown patient", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Patient not found" }, 404)),
    );

    renderWorkspace();

    expect(await screen.findByText("Patient not found.")).toBeInTheDocument();
  });
});
