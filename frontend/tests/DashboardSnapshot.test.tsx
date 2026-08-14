import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DashboardSnapshot } from "@/components/DashboardSnapshot";

describe("DashboardSnapshot", () => {
  it("states plainly that metrics aren't wired up yet, rather than showing fabricated numbers", () => {
    render(<DashboardSnapshot />);
    expect(screen.getByText(/Phase 04/)).toBeInTheDocument();
    // Spec §22: dashboard metrics must come from real data, never hardcoded fake
    // status — this component must not render standalone numeric stat tiles.
    expect(screen.queryByText(/^\d+\s+(Active Patients|New Reports)/)).not.toBeInTheDocument();
  });
});
