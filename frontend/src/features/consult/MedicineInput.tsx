import { useQuery } from "@tanstack/react-query";
import { Pill, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { FormularyOption, MedicineImage } from "@/api/types";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Free text with formulary suggestions: brands ("Dolo 650") and generics. Anything can be typed. */
export function MedicineInput({ value, onChange, onPick, disabled, autoFocus }: {
  value: string; onChange: (v: string) => void; onPick: (o: FormularyOption) => void; disabled?: boolean; autoFocus?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { const t = setTimeout(() => setQ(value.trim()), 150); return () => clearTimeout(t); }, [value]);
  const { data = [] } = useQuery({
    queryKey: ["formulary-search", q], enabled: open && q.length >= 2, staleTime: 5 * 60_000,
    queryFn: () => api<FormularyOption[]>("/api/formulary/search", { query: { q, limit: 10 } }),
  });
  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const pick = (o: FormularyOption) => { onPick(o); setOpen(false); };
  const show = open && q.length >= 2 && data.length > 0 && !(data.length === 1 && data[0].label === value);

  return (
    <div ref={box} className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <input
        value={value} disabled={disabled} autoFocus={autoFocus} placeholder="Medicine — e.g. Dolo 650, Pan-D, metformin 500"
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (!show) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, data.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); pick(data[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
        className="h-9 w-full rounded-md border border-input bg-card pl-8 pr-2 text-[0.85rem] font-medium shadow-xs placeholder:font-normal placeholder:text-muted-foreground focus:border-primary/60 focus:outline-none focus:ring-[3px] focus:ring-ring/15 disabled:opacity-70"
      />
      {show && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-40 max-h-72 overflow-y-auto rounded-lg border bg-popover p-1 shadow-pop">
          {data.map((o, i) => (
            <button key={o.label} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(o)} onMouseEnter={() => setActive(i)}
              className={cn("flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left", i === active && "bg-muted")}>
              <Pill className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0">
                <span className="block text-[0.82rem] font-medium">{o.label} <span className="font-normal text-muted-foreground">· {o.form}</span></span>
                <span className="block truncate text-[0.72rem] text-muted-foreground">{o.brand ? o.generic_label : o.class}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Reference picture from Wikimedia Commons when enabled; a neutral pill icon otherwise. */
export function MedicineThumb({ genericId, size = "md" }: { genericId?: string | null; size?: "sm" | "md" }) {
  const { data } = useQuery({
    queryKey: ["med-image", genericId], enabled: !!genericId, staleTime: Infinity, retry: false,
    queryFn: () => api<{ enabled: boolean; image: MedicineImage | null }>(`/api/formulary/generics/${genericId}/image-info`),
  });
  const img = data?.image;
  const dim = size === "sm" ? "size-8" : "size-10";
  return (
    <div className={cn("flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border/70 bg-subtle text-muted-foreground", dim)}
      title={img ? `${img.title ?? ""} — ${img.author ?? "Wikimedia Commons"}${img.license ? ` (${img.license})` : ""}` : undefined}>
      {img ? <img src={img.url} alt="" className="size-full object-cover" loading="lazy" /> : <Pill className="size-4" />}
    </div>
  );
}
