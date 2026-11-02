import { render, screen } from "@testing-library/react";
import { FlagBadge, IdentityBadge } from "@/components/clinical/badges";

describe("clinical badges", () => {
  it("never shows a flag when the source gave no range", () => {
    render(<FlagBadge flag={null} compact />);
    expect(screen.queryByText(/high|low|normal/i)).toBeNull();
  });
  it("flags suspected wrong-patient documents", () => {
    render(<IdentityBadge status="mismatch" detail="Document lists EXT-1" />);
    expect(screen.getByText("Wrong patient?")).toBeInTheDocument();
  });
});
