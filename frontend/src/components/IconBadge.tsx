import type { LucideIcon } from "lucide-react";

export type IconTone = "blue" | "cyan" | "green" | "purple" | "amber" | "navy";

// A restrained set of soft accent tones layered on top of the core GMS brand palette
// (tailwind.config.ts) — used only to visually distinguish capability cards from one
// another, the way the reference dashboard screenshot does. Brand blue/cyan/navy stay
// dominant everywhere else in the app.
const TONE_STYLES: Record<IconTone, string> = {
  blue: "bg-light-blue text-primary-blue",
  cyan: "bg-cyan/10 text-cyan",
  green: "bg-success/10 text-success",
  purple: "bg-violet-100 text-violet-600",
  amber: "bg-amber-100 text-amber-600",
  navy: "bg-navy/10 text-navy",
};

export function IconBadge({ icon: Icon, tone = "blue" }: { icon: LucideIcon; tone?: IconTone }) {
  return (
    <div className={`inline-flex h-10 w-10 items-center justify-center rounded-lg ${TONE_STYLES[tone]}`}>
      <Icon className="h-5 w-5" />
    </div>
  );
}
