import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusChip } from "@/components/StatusChip";

describe("StatusChip", () => {
  it("renders the given label", () => {
    render(<StatusChip label="Ready" tone="ok" />);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("renders a degraded label distinctly from ok", () => {
    render(<StatusChip label="Model missing" tone="degraded" />);
    expect(screen.getByText("Model missing")).toBeInTheDocument();
  });
});
