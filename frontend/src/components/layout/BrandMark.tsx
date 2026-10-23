import { useBranding } from "@/api/hooks";
import { cn } from "@/lib/utils";

export function BrandMark({ className, showText = true, subtle }: { className?: string; showText?: boolean; subtle?: boolean }) {
  const { data: b } = useBranding();
  const name = b?.product_name ?? "GMS Clinical AI";
  return (
    <div className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <img src={b?.logo_data_url || "/brand-mark.webp"} alt="" className="size-8 shrink-0 rounded-lg object-contain" />
      {showText && (
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[0.92rem] font-semibold tracking-tight">{name}</div>
          {!subtle && <div className="truncate text-[0.7rem] text-muted-foreground">{b?.organization ?? ""}</div>}
        </div>
      )}
    </div>
  );
}
