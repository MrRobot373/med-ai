import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardSnapshot } from "@/components/DashboardSnapshot";

function renderSnapshot() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardSnapshot />
    </QueryClientProvider>,
  );
}

describe("DashboardSnapshot", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows real counts from GET /api/dashboard/summary once it loads", async () => {
    // Regression test — Phase 16's live UI review found this component still showed
    // a stale "Not available yet — arrives in Phase 05/08-10" placeholder against a
    // real running app that already had real reports and AI-generated output. It's
    // now backed by one real summary endpoint instead of re-deriving counts from
    // Patient Management's list response.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ active_patients: 5, total_reports: 23, total_ai_analyses: 10 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    renderSnapshot();

    expect(await screen.findByText("5")).toBeInTheDocument();
    expect(screen.getByText("Active Patients")).toBeInTheDocument();
    expect(screen.getByText("23")).toBeInTheDocument();
    expect(screen.getByText("Reports Processed")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("AI Analyses")).toBeInTheDocument();
    expect(screen.queryByText(/not available yet/i)).not.toBeInTheDocument();
  });

  it("shows real zeros rather than fabricating a number when nothing exists yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ active_patients: 0, total_reports: 0, total_ai_analyses: 0 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    renderSnapshot();

    const zeros = await screen.findAllByText("0");
    expect(zeros).toHaveLength(3);
  });
});
