import { createContext, useContext, useState, type ReactNode } from "react";

interface ResearchModeState {
  /** True only while the clinician is actively using Research Mode (on the Research
   * page, with at least one external source enabled) — spec §128 "Research Mode
   * should not be visually ambiguous." Reverts to false automatically when the
   * Research page unmounts, so the header badge never shows a stale "Research" state
   * after navigating away. */
  active: boolean;
  setActive: (active: boolean) => void;
}

const ResearchModeContext = createContext<ResearchModeState | null>(null);

export function ResearchModeProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState(false);
  return <ResearchModeContext.Provider value={{ active, setActive }}>{children}</ResearchModeContext.Provider>;
}

export function useResearchMode(): ResearchModeState {
  const ctx = useContext(ResearchModeContext);
  if (!ctx) throw new Error("useResearchMode must be used within a ResearchModeProvider");
  return ctx;
}
