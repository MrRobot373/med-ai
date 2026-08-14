import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { FileText } from "lucide-react";
import { CapabilityCard } from "@/components/CapabilityCard";

describe("CapabilityCard", () => {
  it("links to a real in-app route rather than a dead/fake href", () => {
    render(
      <MemoryRouter>
        <CapabilityCard
          icon={FileText}
          tone="blue"
          title="Note Summarization"
          description="Concise, structured summaries."
          to="/clinical-ai"
        />
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: /Note Summarization/i });
    expect(link).toHaveAttribute("href", "/clinical-ai");
  });
});
