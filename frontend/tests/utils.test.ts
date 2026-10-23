import { accentVars, hexToHsl } from "@/lib/color";
import { fmtNum, initials, toDate } from "@/lib/utils";

describe("color", () => {
  it("converts hex to hsl", () => {
    expect(hexToHsl("#246BFD")).toEqual([220, 98, 57]);
    expect(hexToHsl("#fff")).toEqual([0, 0, 100]);
    expect(hexToHsl("nope")).toBeNull();
  });
  it("keeps text readable on any accent", () => {
    expect(accentVars("#FDE047", false)["--primary-foreground"]).toBe("222 47% 11%");
    expect(accentVars("#FDE047", true)["--primary-foreground"]).toBe("222 47% 11%");
    expect(accentVars("#246BFD", false)["--primary-foreground"]).toBe("0 0% 100%");
    expect(accentVars("#4F46E5", true)["--primary-foreground"]).toBe("0 0% 100%");
  });
});

describe("utils", () => {
  it("treats naive timestamps as UTC and date-only strings as calendar dates", () => {
    expect(toDate("2026-01-02T03:04:05")!.toISOString()).toBe("2026-01-02T03:04:05.000Z");
    expect(toDate("2026-01-02")!.getDate()).toBe(2);
  });
  it("formats numbers and initials", () => {
    expect(fmtNum(1.23456)).toBe("1.235");
    expect(fmtNum(null)).toBe("—");
    expect(initials("Ananya Rao")).toBe("AR");
    expect(initials("Dr. Ananya Rao")).toBe("AR");
    expect(initials("Harish Chandra Gupta")).toBe("HG");
  });
});
