import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import KnowledgePage from "@/pages/Knowledge";

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

function renderKnowledgePage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/knowledge"]}>
        <Routes>
          <Route path="/knowledge" element={<KnowledgePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Knowledge Administration page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("gates the page behind an admin account", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(DOCTOR_ME);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderKnowledgePage();
    expect(await screen.findByText(/requires an admin account/i)).toBeInTheDocument();
  });

  it("lists existing documents for an admin", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(ADMIN_ME);
        if (url.includes("/api/knowledge/documents")) {
          return jsonResponse([
            { id: "d1", title: "ICO Glaucoma Guidelines", source: "ICO", specialty: "Glaucoma", authority_tier: "a", tags: null, archived: false, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderKnowledgePage();
    expect(await screen.findByText("ICO Glaucoma Guidelines")).toBeInTheDocument();
    expect(screen.getByText(/Tier A/)).toBeInTheDocument();
  });

  it("creates a new document from the form", async () => {
    const user = userEvent.setup();
    let created = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (url.includes("/api/auth/me")) return jsonResponse(ADMIN_ME);
        if (url.includes("/api/knowledge/documents") && method === "POST") {
          created = true;
          const body = JSON.parse((init?.body as string) ?? "{}");
          return jsonResponse(
            { id: "d2", title: body.title, source: body.source ?? null, specialty: body.specialty ?? null, authority_tier: body.authority_tier, tags: body.tags ?? null, archived: false, created_at: "2026-08-16T00:00:00Z", updated_at: "2026-08-16T00:00:00Z" },
            201,
          );
        }
        if (url.includes("/api/knowledge/documents/d2") && !url.includes("versions")) {
          return jsonResponse({ id: "d2", title: "New Guideline", source: null, specialty: null, authority_tier: "d", tags: null, archived: false, created_at: "2026-08-16T00:00:00Z", updated_at: "2026-08-16T00:00:00Z", versions: [] });
        }
        if (url.includes("/api/knowledge/documents")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderKnowledgePage();
    await user.click(await screen.findByRole("button", { name: "New Document" }));
    await user.type(screen.getByPlaceholderText(/ICO Glaucoma Guidelines/), "New Guideline");
    await user.click(screen.getByRole("button", { name: "Create Document" }));

    await waitFor(() => expect(created).toBe(true));
  });

  it("shows a selected document's versions with status badges", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/auth/me")) return jsonResponse(ADMIN_ME);
        if (url.includes("/api/knowledge/documents/d1")) {
          return jsonResponse({
            id: "d1",
            title: "ICO Glaucoma Guidelines",
            source: "ICO",
            specialty: "Glaucoma",
            authority_tier: "a",
            tags: null,
            archived: false,
            created_at: "2026-08-01T00:00:00Z",
            updated_at: "2026-08-01T00:00:00Z",
            versions: [
              {
                id: "v1",
                document_id: "d1",
                version_number: 1,
                source_filename: "guideline.pdf",
                mime_type: "application/pdf",
                file_size_bytes: 20480,
                effective_date: "2024-01-15",
                review_date: null,
                is_active: true,
                ingestion_status: "completed",
                ingestion_error: null,
                chunk_count: 12,
                created_at: "2026-08-01T00:00:00Z",
              },
            ],
          });
        }
        if (url.includes("/api/knowledge/documents")) {
          return jsonResponse([
            { id: "d1", title: "ICO Glaucoma Guidelines", source: "ICO", specialty: "Glaucoma", authority_tier: "a", tags: null, archived: false, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" },
          ]);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderKnowledgePage();
    await user.click(await screen.findByText("ICO Glaucoma Guidelines"));

    expect(await screen.findByText("guideline.pdf")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });
});
