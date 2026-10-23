import { fireEvent, render, screen } from "@testing-library/react";
import { Markdown } from "@/components/clinical/Markdown";

describe("Markdown citations", () => {
  it("renders citation labels as clickable chips", () => {
    const onCite = vi.fn();
    render(<Markdown onCite={onCite}>{"Creatinine rose to **1.58** [P1, K2] per the record [R]."}</Markdown>);
    expect(screen.getByText("1.58").tagName).toBe("STRONG");
    fireEvent.click(screen.getByRole("button", { name: "K2" }));
    expect(onCite).toHaveBeenCalledWith("K2");
    expect(screen.getByRole("button", { name: "P1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "R" })).toBeInTheDocument();
  });
  it("leaves ordinary brackets alone", () => {
    render(<Markdown>{"Range [normal] stays text"}</Markdown>);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
