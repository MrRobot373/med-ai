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

  it("shows the real active-patient count once Patient Management data loads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify([{ id: "1" }, { id: "2" }, { id: "3" }]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    renderSnapshot();

    expect(await screen.findByText("3")).toBeInTheDocument();
    expect(screen.getByText("Active Patients")).toBeInTheDocument();
  });

  it("states plainly that report/AI-analysis metrics aren't available yet, rather than fabricating numbers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })),
    );

    renderSnapshot();

    const notAvailable = await screen.findAllByText("Not available yet");
    expect(notAvailable).toHaveLength(2); // reports + AI analyses
    expect(screen.getByText(/Phase 05/)).toBeInTheDocument();
    expect(screen.getByText(/Phases 08–10/)).toBeInTheDocument();
  });
});
