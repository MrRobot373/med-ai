import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border bg-card text-card-foreground shadow-card", className)} {...props} />;
}

export function CardHeader({
  title, description, icon, actions, className,
}: { title: ReactNode; description?: ReactNode; icon?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-[var(--card-pad)] pt-[var(--card-pad)]", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-foreground [&_svg]:size-4">{icon}</div>}
        <div className="min-w-0">
          <h3 className="truncate text-[0.95rem] font-semibold tracking-tight">{title}</h3>
          {description && <p className="mt-0.5 text-[0.8rem] text-muted-foreground">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card-pad", className)} {...props} />;
}
