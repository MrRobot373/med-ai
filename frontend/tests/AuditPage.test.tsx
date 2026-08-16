import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AuditPage from "@/pages/Audit";

const ADMIN_ME = {
  id: "u1",
  email: "admin@gms.local",
  display_name: "Admin Demo",
  role: "admin",
  active: true,
  last_login_at: null,
};

const DOCTOR_ME = { ...ADMIN_ME, id: "u2", email: "doctor@gms.local", role: "doctor" };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderAuditPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/audit"]}>
        <Routes>
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Audit & Feedback page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("gates the page behind an admin account (spec §18 Review audits)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderAuditPage();
    expect(await screen.findByText(/requires an admin account/i)).toBeInTheDocument();
  });

  it("lists real audit log rows for an admin", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(ADMIN_ME);
        if (url.startsWith("/api/audit")) {
          return jsonResponse([
            {
              id: "a1",
              user_id: "u1",
              user_email: "admin@gms.local",
              action: "login",
              outcome: "success",
              object_type: null,
              object_id: null,
              detail: null,
              created_at: "2026-08-16T09:00:00Z",
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderAuditPage();
    // "Login" also appears as a <select> filter option — assert on the row's own
    // unique cell content instead.
    expect(await screen.findByText("admin@gms.local")).toBeInTheDocument();
    expect(screen.getByText("SUCCESS")).toBeInTheDocument();
    expect(screen.getAllByText("Login").length).toBeGreaterThan(0);
  });

  it("switches to the Feedback tab and lists real feedback rows", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(ADMIN_ME);
        if (url.startsWith("/api/audit")) return jsonResponse([]);
        if (url.startsWith("/api/feedback")) {
          return jsonResponse([
            {
              id: "f1",
              target_type: "message",
              target_id: "m1234567",
              user_id: "u2",
              rating: "incorrect",
              comment: "Wrong dose mentioned",
              created_at: "2026-08-16T09:00:00Z",
              updated_at: "2026-08-16T09:00:00Z",
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderAuditPage();
    await user.click(await screen.findByRole("button", { name: "Feedback" }));

    // "Incorrect" also appears as a <select> filter option — assert on the feedback
    // row's own unique comment text instead of the ambiguous label alone.
    expect(await screen.findByText(/Wrong dose mentioned/)).toBeInTheDocument();
    expect(screen.getAllByText("Incorrect").length).toBeGreaterThan(0);
  });
});
