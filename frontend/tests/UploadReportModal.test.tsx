import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UploadReportModal } from "@/components/UploadReportModal";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderModal(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <UploadReportModal patientId="p1" onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onClose };
}

async function selectFile(user: ReturnType<typeof userEvent.setup>) {
  const file = new File(["%PDF-1.4 fake content"], "report.pdf", { type: "application/pdf" });
  const input = screen.getByLabelText("File") as HTMLInputElement;
  await user.upload(input, file);
}

describe("UploadReportModal", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads the file and closes on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ id: "r1", ingestion_status: "queued" }, 201)),
    );
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await selectFile(user);
    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(onClose).toHaveBeenCalled();
  });

  it("offers 'Upload Anyway' on a duplicate-file conflict instead of silently failing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () => jsonResponse({ detail: "An identical file has already been uploaded for this patient" }, 409),
      ),
    );
    const user = userEvent.setup();
    renderModal();

    await selectFile(user);
    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already been uploaded");
    expect(screen.getByRole("button", { name: "Upload Anyway" })).toBeInTheDocument();
  });
});
