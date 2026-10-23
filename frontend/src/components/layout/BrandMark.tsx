import { Link } from "react-router";
import { useBranding } from "@/api/hooks";
import { cn } from "@/lib/utils";

export function BrandMark({ className, showText = true }: { className?: string; showText?: boolean }) {
  const { data: b } = useBranding();
  const name = b?.product_name ?? "GMS Clinical AI";
  return (
    <Link to="/" className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <img src={b?.logo_data_url || "/brand-mark.webp"} alt="" className="size-9 shrink-0 rounded-xl bg-white object-contain p-0.5 shadow-xs ring-1 ring-black/5" />
      {showText && (
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[1.05rem] font-semibold tracking-tight">{name}</div>
          <div className="truncate text-[0.7rem] text-muted-foreground">{b?.organization ?? ""}</div>
        </div>
      )}
    </Link>
  );
}
