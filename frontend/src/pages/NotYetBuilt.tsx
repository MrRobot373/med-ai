import { Construction } from "lucide-react";

/**
 * Explicit "not implemented yet" placeholder for nav sections that don't have a real
 * feature behind them in the current build phase. Per spec §130: an honest "Not
 * Configured" / "not yet built" screen is preferable to a fake working screen or a
 * broken link — this is never meant to ship as-is once the relevant phase lands.
 */
export function NotYetBuilt({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <div className="rounded-full bg-light-blue p-3">
        <Construction className="h-6 w-6 text-primary-blue" />
      </div>
      <h1 className="text-lg font-semibold text-navy">{title}</h1>
      <p className="max-w-sm text-sm text-muted-text">
        This module is not implemented yet. It arrives in {phase} of the build plan.
      </p>
    </div>
  );
}
