import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ResearchPage from "@/pages/Research";
import { ResearchModeProvider, useResearchMode } from "@/contexts/ResearchMode";

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

function ResearchModeSpy() {
  const { active } = useResearchMode();
  return <div data-testid="research-mode-spy">{active ? "research" : "local"}</div>;
}

function renderResearchPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ResearchModeProvider>
        <ResearchModeSpy />
        <MemoryRouter initialEntries={["/research"]}>
          <Routes>
            <Route path="/research" element={<ResearchPage />} />
          </Routes>
        </MemoryRouter>
      </ResearchModeProvider>
    </QueryClientProvider>,
  );
}

describe("Research page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an honest not-configured message when Research Mode is disabled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/research/status")) return jsonResponse({ enabled: false, searxng_reachable: false, sources_available: [] });
        if (url.includes("/api/patients")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderResearchPage();

    expect(await screen.findByText(/Research Mode is not configured/i)).toBeInTheDocument();
    expect(screen.getByText(/ENABLE_RESEARCH=true/)).toBeInTheDocument();
  });

  it("allows a local-only question even when Research Mode is disabled, and shows results with LOCAL badges", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/research/status")) return jsonResponse({ enabled: false, searxng_reachable: false, sources_available: [] });
        if (url.includes("/api/patients")) return jsonResponse([]);
        if (url.includes("/api/research/runs")) return jsonResponse([]);
        // FeedbackControls (Phase 13) queries this once a research run renders.
        if (url.startsWith("/api/feedback/mine")) return jsonResponse(null);
        if (url.includes("/api/research/query") && method === "POST") {
          return jsonResponse({
            id: "run1",
            module_type: "research",
            patient_id: null,
            encounter_id: null,
            input_params: {},
            payload: {
              evidence_summary: "Local guideline supports SLT as first-line therapy [L1].",
              consensus: "Local knowledge base agrees on first-line SLT.",
              conflicting_evidence: [],
              patient_applicability: "No patient context was given.",
              exclusion_criteria: [],
              limitations: ["Only local knowledge was searched."],
              evidence_quality: "moderate",
              citations: [{ label: "L1", source_title: "ICO Guidelines", url: null, collection: "medical_knowledge", page: 5, section: "Glaucoma", excerpt: "SLT excerpt" }],
              research_mode_used: false,
              deidentification: { removed_count: 0, removed_categories: [] },
            },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderResearchPage();

    const textarea = await screen.findByPlaceholderText(/Recent evidence for SLT/);
    await user.type(textarea, "Is SLT first-line for open-angle glaucoma?");
    await user.click(screen.getByRole("button", { name: "Research" }));

    expect(await screen.findByText(/Local guideline supports SLT/)).toBeInTheDocument();
    expect(screen.getByText("LOCAL")).toBeInTheDocument();
    expect(screen.getByTestId("research-mode-spy")).toHaveTextContent("local");
  });

  it("checking an external source enables Research Mode in the header and includes it in the query", async () => {
    const user = userEvent.setup();
    let capturedBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/research/status")) return jsonResponse({ enabled: true, searxng_reachable: false, sources_available: ["pubmed", "fda", "clinicaltrials"] });
        if (url.includes("/api/patients")) return jsonResponse([]);
        if (url.includes("/api/research/runs")) return jsonResponse([]);
        // FeedbackControls (Phase 13) queries this once a research run renders.
        if (url.startsWith("/api/feedback/mine")) return jsonResponse(null);
        if (url.includes("/api/research/query") && method === "POST") {
          capturedBody = JSON.parse((init?.body as string) ?? "{}");
          return jsonResponse({
            id: "run2",
            module_type: "research",
            patient_id: null,
            encounter_id: null,
            input_params: {},
            payload: {
              evidence_summary: "PubMed evidence found [W1].",
              consensus: "",
              conflicting_evidence: [],
              patient_applicability: "",
              exclusion_criteria: [],
              limitations: [],
              evidence_quality: "moderate",
              citations: [{ label: "W1", source_title: "A Recent Trial", url: "https://pubmed.ncbi.nlm.nih.gov/1/", collection: "web_cache", page: null, section: "PUBMED", excerpt: "trial excerpt" }],
              research_mode_used: true,
              deidentification: { removed_count: 0, removed_categories: [] },
            },
            model: "qwen3.5:9b",
            generation_error: null,
            created_at: "2026-08-16T00:00:00Z",
          });
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderResearchPage();

    await screen.findByText("PubMed");
    expect(screen.getByTestId("research-mode-spy")).toHaveTextContent("local");

    await user.click(screen.getByRole("checkbox", { name: "PubMed" }));
    expect(screen.getByTestId("research-mode-spy")).toHaveTextContent("research");
    expect(await screen.findByText(/de-identified clinical queries/)).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/Recent evidence for SLT/);
    await user.type(textarea, "Latest evidence for SLT");
    await user.click(screen.getByRole("button", { name: "Research" }));

    expect(await screen.findByText(/PubMed evidence found/)).toBeInTheDocument();
    expect(screen.getByText("PUBMED")).toBeInTheDocument();
    expect(capturedBody).not.toBeNull();
    expect((capturedBody as unknown as { sources: string[] }).sources).toEqual(["pubmed"]);
  });
});
