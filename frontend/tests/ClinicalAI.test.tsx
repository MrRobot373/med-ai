import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ClinicalAITab from "@/pages/PatientWorkspace/ClinicalAI";
import ClinicalAIPage from "@/pages/ClinicalAI";
import type { PatientOut } from "@/api/patients";
import type { ConversationOut, MessageOut } from "@/api/chat";

const NOW = "2026-08-16T10:00:00Z";

const PATIENT: PatientOut = {
  id: "p1",
  mrn: "DEMO-1001",
  first_name: "Margaret",
  last_name: "Wallace",
  preferred_name: null,
  date_of_birth: "1953-04-12",
  sex: "female",
  phone: null,
  email: null,
  notes: null,
  synthetic: true,
  archived: false,
  created_at: NOW,
  updated_at: NOW,
  age: 73,
};

const DOCTOR_ME = {
  id: "u1",
  email: "doctor@gms.local",
  display_name: "Dr. Demo",
  role: "doctor",
  active: true,
  last_login_at: null,
};

const VIEWER_ME = { ...DOCTOR_ME, id: "u2", email: "viewer@gms.local", role: "viewer" };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Builds a real streamed SSE Response — the frontend's streamMessage() reads this via
 * res.body.getReader(), same as it reads the live backend's text/event-stream body. */
function sseResponse(events: object[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function renderClinicalAITab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients/p1/clinical-ai"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<Outlet context={PATIENT} />}>
            <Route path="clinical-ai" element={<ClinicalAITab />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderGlobalClinicalAI() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/clinical-ai"]}>
        <Routes>
          <Route path="/clinical-ai" element={<ClinicalAIPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Clinical AI — patient-scoped tab", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts a conversation, sends a suggested question, streams the answer, and shows evidence", async () => {
    const user = userEvent.setup();
    let conversations: ConversationOut[] = [];
    let messages: MessageOut[] = [];
    let submittedFeedback: Record<string, unknown> | null = null;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.includes("/api/patients/p1/reports")) return jsonResponse([]);
        if (url.includes("/api/patients/p1/encounters")) return jsonResponse([]);
        // FeedbackControls (Phase 13) queries this for every rendered assistant
        // message — no feedback has been submitted in this test, so an honest null.
        if (url.startsWith("/api/feedback/mine")) return jsonResponse(null);
        if (url === "/api/feedback" && method === "POST") {
          const body = JSON.parse((init?.body as string) ?? "{}");
          submittedFeedback = body;
          return jsonResponse(
            { id: "fb1", target_type: body.target_type, target_id: body.target_id, user_id: "u1", rating: body.rating, comment: body.comment ?? null, created_at: NOW, updated_at: NOW },
            201,
          );
        }
        if (url.startsWith("/api/conversations?") && method === "GET") return jsonResponse(conversations);
        if (url === "/api/conversations" && method === "POST") {
          const created: ConversationOut = {
            id: "c1",
            user_id: "u1",
            patient_id: "p1",
            encounter_id: null,
            selected_report_id: null,
            scope: "current_patient",
            title: null,
            created_at: NOW,
            updated_at: NOW,
          };
          conversations = [created];
          return jsonResponse(created, 201);
        }
        if (url === "/api/conversations/c1/messages" && method === "GET") return jsonResponse(messages);
        if (url === "/api/conversations/c1/messages" && method === "POST") {
          messages = [
            {
              id: "m-user",
              conversation_id: "c1",
              role: "user",
              content: "Summarize this patient's active problems and current medications.",
              model: null,
              generation_error: null,
              created_at: NOW,
              citations: [],
              evidence_quality: null,
              grounding: null,
              provenance: null,
            },
            {
              id: "m-assistant",
              conversation_id: "c1",
              role: "assistant",
              content: "Latanoprost is prescribed for glaucoma [P1].",
              model: "qwen3.5:9b",
              generation_error: null,
              created_at: NOW,
              citations: [
                {
                  id: "cit1",
                  label: "P1",
                  source_type: "patient_report",
                  chunk_id: null,
                  report_id: "r1",
                  source_title: "OCT Report",
                  page: 1,
                  section: null,
                  source_excerpt: "Latanoprost 0.005% nightly for open-angle glaucoma.",
                  relevance_score: 1.2,
                },
              ],
              evidence_quality: "moderate",
              grounding: [{ claim: "Latanoprost is prescribed for glaucoma", cited_labels: ["P1"], status: "supported" }],
              provenance: {
                patient_context_records: 3,
                dense_candidates: 8,
                bm25_candidates: 6,
                fused_candidates: 5,
                reranked: 3,
                final_evidence: 1,
                generation_model: "qwen3.5:9b",
              },
            },
          ];
          return sseResponse([
            { type: "token", content: "Latanoprost " },
            { type: "token", content: "is prescribed for glaucoma [P1]." },
            {
              type: "final",
              message_id: "m-assistant",
              citations: messages[1].citations,
              evidence_quality: "moderate",
              grounding: messages[1].grounding,
            },
          ]);
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderClinicalAITab();

    await user.click(await screen.findByRole("button", { name: "New Chat" }));
    await user.click(screen.getByRole("button", { name: /Start Chat/i }));

    const suggestion = await screen.findByRole("button", {
      name: "Summarize this patient's active problems and current medications.",
    });
    await user.click(suggestion);

    // The persisted assistant answer (after streaming completes and the message list
    // refetches) contains the same text the mock streamed token-by-token. It appears
    // twice: once in the chat bubble, once in the evidence panel's claim check.
    expect(await screen.findAllByText(/Latanoprost is prescribed for glaucoma/)).toHaveLength(2);

    // Evidence panel: deterministic quality label, never a fabricated percentage.
    expect(screen.getByText("Moderate evidence")).toBeInTheDocument();
    expect(screen.getByText("OCT Report")).toBeInTheDocument();
    expect(screen.getByText(/Latanoprost 0.005% nightly/)).toBeInTheDocument();
    expect(screen.getByText(/Supported/)).toBeInTheDocument();

    // The [P1] marker renders as a clickable citation badge, not raw bracket text.
    expect(screen.getByRole("button", { name: "P1" })).toBeInTheDocument();

    // Phase 13: real retrieval provenance is available and feedback can be submitted.
    await user.click(screen.getByRole("button", { name: "Why This Answer?" }));
    expect(await screen.findByText("Dense candidates")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("qwen3.5:9b")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Close"));

    await user.click(screen.getByRole("button", { name: "Mark as helpful" }));
    await screen.findByText("Helpful");
    expect(submittedFeedback).toEqual({ target_type: "message", target_id: "m-assistant", rating: "helpful" });
  });

  it("hides write controls and shows a read-only notice for a viewer", async () => {
    const user = userEvent.setup();
    const existingConversation: ConversationOut = {
      id: "c1",
      user_id: "u2",
      patient_id: "p1",
      encounter_id: null,
      selected_report_id: null,
      scope: "current_patient",
      title: "Prior question",
      created_at: NOW,
      updated_at: NOW,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(VIEWER_ME);
        if (url.includes("/api/patients/p1/reports")) return jsonResponse([]);
        if (url.includes("/api/patients/p1/encounters")) return jsonResponse([]);
        if (url.startsWith("/api/conversations?")) return jsonResponse([existingConversation]);
        if (url === "/api/conversations/c1/messages") return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderClinicalAITab();

    expect(await screen.findByText("Prior question")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Chat" })).not.toBeInTheDocument();

    await user.click(screen.getByText("Prior question"));

    expect(await screen.findByText(/Read-only access/)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Ask a clinical question/i)).not.toBeInTheDocument();
  });
});

describe("Clinical AI — global page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("only offers patient-independent scopes when starting a new chat", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        if (url.startsWith("/api/conversations")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderGlobalClinicalAI();

    await user.click(await screen.findByRole("button", { name: "New Chat" }));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("General")).toBeInTheDocument();
    expect(within(dialog).getByText("Local Knowledge Only")).toBeInTheDocument();
    expect(within(dialog).queryByText("This Patient")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("This Report")).not.toBeInTheDocument();
  });
});
