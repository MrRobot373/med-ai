import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import PatientsPage from "@/pages/Patients";

const SAMPLE_PATIENT = {
  id: "p1",
  mrn: "DEMO-1001",
  first_name: "Margaret",
  last_name: "Wallace",
  preferred_name: null,
  sex: "female",
  date_of_birth: "1953-04-12",
  synthetic: true,
  archived: false,
  last_encounter_at: "2026-08-01T10:00:00Z",
  active_condition_names: ["Cataract, bilateral"],
  age: 73,
};

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PatientsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PatientsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders real patient cards from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([SAMPLE_PATIENT])),
    );

    renderPage();

    expect(await screen.findByText("Margaret Wallace")).toBeInTheDocument();
    expect(screen.getByText("DEMO-1001")).toBeInTheDocument();
    expect(screen.getByText("Cataract, bilateral")).toBeInTheDocument();
  });

  it("shows an honest empty state rather than a broken/blank screen when there are no matches", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );

    renderPage();

    expect(await screen.findByText("No patients yet — add one to get started.")).toBeInTheDocument();
  });

  it("re-queries the API with the search term as the clinician types", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPage();
    await user.type(screen.getByLabelText("Search patients"), "Wallace");

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("q=Wallace"), expect.anything()),
    );
  });
});
