import type { LucideIcon } from "lucide-react";

interface HowItWorksStepProps {
  index: number;
  icon: LucideIcon;
  label: string;
  description: string;
  isLast?: boolean;
}

export function HowItWorksStep({ index, icon: Icon, label, description, isLast }: HowItWorksStepProps) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-blue text-sm font-semibold text-white">
          {index}
        </div>
        {!isLast && <div className="w-px flex-1 bg-border" />}
      </div>
      <div className={isLast ? "pb-0" : "pb-6"}>
        <div className="flex items-center gap-1.5 text-sm font-semibold text-navy">
          <Icon className="h-4 w-4 text-primary-blue" />
          {label}
        </div>
        <p className="mt-1 text-xs text-muted-text">{description}</p>
      </div>
    </div>
  );
}
