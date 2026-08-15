import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReconciliationModal } from "@/components/ReconciliationModal";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderModal() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ReconciliationModal reportId="r1" onClose={() => {}} />
    </QueryClientProvider>,
  );
}

describe("ReconciliationModal", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows newly-detected, unchanged, review, and not-in-document rows with non-committal wording", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/medication-reconciliation")) {
          return jsonResponse({
            report_id: "r1",
            report_title: "consult.pdf",
            items: [
              {
                status: "newly_detected",
                current_medication_id: null,
                current_medication_name: null,
                current_dose: null,
                current_frequency: null,
                document_medication_name: "Lisinopril",
                document_dose: "10mg",
                document_route: "oral",
                document_frequency: "once daily",
                source_page: 1,
                source_excerpt: "Lisinopril 10mg oral once daily",
              },
              {
                status: "matched_unchanged",
                current_medication_id: "m1",
                current_medication_name: "Aspirin",
                current_dose: "81mg",
                current_frequency: "once daily",
                document_medication_name: "Aspirin",
                document_dose: "81mg",
                document_route: "oral",
                document_frequency: "once daily",
                source_page: 1,
                source_excerpt: "Aspirin 81mg oral once daily",
              },
              {
                status: "matched_review",
                current_medication_id: "m2",
                current_medication_name: "Metformin",
                current_dose: "500mg",
                current_frequency: "twice daily",
                document_medication_name: "Metformin",
                document_dose: "1000mg",
                document_route: "oral",
                document_frequency: "twice daily",
                source_page: 1,
                source_excerpt: "Metformin 1000mg oral twice daily",
              },
              {
                status: "not_in_document",
                current_medication_id: "m3",
                current_medication_name: "Artificial tears",
                current_dose: "1 drop",
                current_frequency: "as needed",
                document_medication_name: null,
                document_dose: null,
                document_route: null,
                document_frequency: null,
                source_page: null,
                source_excerpt: null,
              },
            ],
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderModal();

    expect(await screen.findByText("Newly detected in this document")).toBeInTheDocument();
    expect(screen.getByText("No difference detected")).toBeInTheDocument();
    expect(screen.getByText("Possible difference — review")).toBeInTheDocument();
    // Non-committal — never claims the medication was discontinued just because this
    // one document didn't mention it.
    expect(screen.getByText("Not mentioned in this document")).toBeInTheDocument();
    expect(screen.queryByText(/discontinued/i)).not.toBeInTheDocument();
  });
});
