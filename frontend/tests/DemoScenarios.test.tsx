import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import DemoScenariosPage from "@/pages/Demo";

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

/** Captures wherever a scenario's "Run Scenario" button actually navigated to, real
 * router state included — proves each card deep-links with real context, not just a
 * label. */
function NavSpy() {
  const location = useLocation();
  return (
    <div data-testid="nav-spy">
      {location.pathname}
      {JSON.stringify(location.state)}
    </div>
  );
}

function renderDemoPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/demo"]}>
        <Routes>
          <Route path="/demo" element={<DemoScenariosPage />} />
          <Route path="/patients/:patientId/clinical-modules" element={<NavSpy />} />
          <Route path="/patients/:patientId/labs" element={<NavSpy />} />
          <Route path="/patients/:patientId/clinical-ai" element={<NavSpy />} />
          <Route path="/patients/:patientId/reports" element={<NavSpy />} />
          <Route path="/research" element={<NavSpy />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Scopes to the one Card whose heading matches — several scenarios below reuse the
 * same demo patient, so a plain screen-wide "Run Scenario" query would be ambiguous. */
async function runScenarioCard(title: string) {
  const heading = await screen.findByText(title);
  const card = heading.closest("div.gms-card") as HTMLElement;
  const user = userEvent.setup();
  // findByRole (not getByRole) — the button only renders once the demo-patient list
  // has actually loaded, same async gap the "honest empty state" itself depends on.
  await user.click(await within(card).findByRole("button", { name: /Run Scenario/ }));
}

const ALL_DEMO_PATIENTS = [
  { id: "p1001", mrn: "DEMO-1001", first_name: "Margaret", last_name: "Wallace", preferred_name: null, sex: "female", date_of_birth: "1953-04-12", synthetic: true, archived: false, last_encounter_at: null, active_condition_names: [], age: 73 },
  { id: "p1002", mrn: "DEMO-1002", first_name: "Robert", last_name: "Klein", preferred_name: null, sex: "male", date_of_birth: "1958-09-03", synthetic: true, archived: false, last_encounter_at: null, active_condition_names: [], age: 67 },
  { id: "p1003", mrn: "DEMO-1003", first_name: "Elena", last_name: "Novak", preferred_name: null, sex: "female", date_of_birth: "1970-11-20", synthetic: true, archived: false, last_encounter_at: null, active_condition_names: [], age: 55 },
  { id: "p1004", mrn: "DEMO-1004", first_name: "Priya", last_name: "Patel", preferred_name: null, sex: "female", date_of_birth: "1948-06-02", synthetic: true, archived: false, last_encounter_at: null, active_condition_names: [], age: 78 },
  { id: "p1005", mrn: "DEMO-1005", first_name: "Thomas", last_name: "Ferreira", preferred_name: null, sex: "male", date_of_birth: "1949-02-17", synthetic: true, archived: false, last_encounter_at: null, active_condition_names: [], age: 77 },
];

describe("Demo Scenarios page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists all six real scenarios once demo patients are found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients")) return jsonResponse(ALL_DEMO_PATIENTS);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderDemoPage();

    expect(await screen.findByText("Patient Report Comparison")).toBeInTheDocument();
    expect(screen.getByText("Longitudinal Lab Analysis")).toBeInTheDocument();
    expect(screen.getByText("Vision + Guideline RAG")).toBeInTheDocument();
    expect(screen.getByText("Medication Reconciliation")).toBeInTheDocument();
    expect(screen.getByText("Current Evidence Research")).toBeInTheDocument();
    expect(screen.getByText("Clinical Note Generation")).toBeInTheDocument();

    expect(await screen.findAllByRole("button", { name: /Run Scenario/ })).toHaveLength(6);
  });

  it("deep-links Patient Report Comparison to the right patient with the compare module preselected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients")) return jsonResponse(ALL_DEMO_PATIENTS);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderDemoPage();
    await runScenarioCard("Patient Report Comparison");

    const spy = await screen.findByTestId("nav-spy");
    expect(spy.textContent).toContain("/patients/p1003/clinical-modules");
    expect(spy.textContent).toContain('"module":"compare"');
  });

  it("deep-links Current Evidence Research with a prefilled question and patient", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients")) return jsonResponse(ALL_DEMO_PATIENTS);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderDemoPage();
    await runScenarioCard("Current Evidence Research");

    const spy = await screen.findByTestId("nav-spy");
    expect(spy.textContent).toContain("/research");
    expect(spy.textContent).toContain("selective laser trabeculoplasty");
    expect(spy.textContent).toContain('"patientId":"p1002"');
  });

  it("deep-links Vision + Guideline RAG into a prefilled current_patient chat question", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients")) return jsonResponse(ALL_DEMO_PATIENTS);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderDemoPage();
    await runScenarioCard("Vision + Guideline RAG");

    const spy = await screen.findByTestId("nav-spy");
    expect(spy.textContent).toContain("/patients/p1004/clinical-ai");
    expect(spy.textContent).toContain('"scope":"current_patient"');
    expect(spy.textContent).toContain("macular degeneration");
  });

  it("shows an honest warning instead of a dead button when a demo patient isn't seeded yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients")) return jsonResponse([]); // nothing seeded
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderDemoPage();
    expect(await screen.findAllByText(/not found — run start-demo\.bat/)).toHaveLength(6);
    expect(screen.queryByRole("button", { name: /Run Scenario/ })).not.toBeInTheDocument();
  });
});
