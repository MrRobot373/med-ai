import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OverviewPage from "@/pages/Overview";

// This test proves the Overview page renders whatever the backend reports — including
// a degraded/unreachable state — rather than a hardcoded "Ready" (spec §84/§103).
describe("OverviewPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            status: "degraded",
            backend: true,
            database: { reachable: true, error: null },
            ollama: {
              reachable: false,
              version: null,
              configured_model: "qwen3.5:9b",
              model_available: false,
              error: "Ollama unreachable at http://localhost:11434",
            },
            qdrant: { reachable: false, collections: [], error: "Qdrant unreachable" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reflects a real degraded backend status rather than faking Ready", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <OverviewPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Two chips ("Unreachable") render simultaneously once loading resolves, so this
    // must use getAllByText from the start — getByText throws on multiple matches.
    await waitFor(() => expect(screen.getAllByText("Unreachable")).toHaveLength(2));
    expect(screen.getByText("Ready")).toBeInTheDocument(); // database only
  });
});
