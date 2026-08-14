import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AddPatientModal } from "@/components/AddPatientModal";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderModal(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients"]}>
        <Routes>
          <Route path="/patients" element={<AddPatientModal onClose={onClose} />} />
          <Route path="/patients/:id" element={<div>Patient workspace placeholder</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onClose };
}

describe("AddPatientModal", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates the patient and navigates to their new workspace on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ id: "new-patient-1", mrn: "MRN-ABCD1234" })),
    );
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Date of birth"), "1990-01-01");
    await user.click(screen.getByRole("button", { name: "Add Patient" }));

    expect(await screen.findByText("Patient workspace placeholder")).toBeInTheDocument();
  });

  it("shows the real backend error instead of silently failing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Not permitted" }, 403)),
    );
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Date of birth"), "1990-01-01");
    await user.click(screen.getByRole("button", { name: "Add Patient" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Not permitted");
  });
});
