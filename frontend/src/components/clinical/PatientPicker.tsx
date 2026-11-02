import { Check, ChevronsUpDown, X } from "lucide-react";
import { useState } from "react";
import { usePatients } from "@/api/hooks";
import { Avatar, Input, Popover, PopoverContent, PopoverTrigger } from "@/components/ui";
import { cn } from "@/lib/utils";

export function PatientPicker({ value, onChange, placeholder = "Select a patient", allowClear = true, className }: { value: { id: string; full_name: string; mrn: string } | null; onChange: (p: { id: string; full_name: string; mrn: string } | null) => void; placeholder?: string; allowClear?: boolean; className?: string }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data } = usePatients({ q });
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className={cn("flex h-9 w-full items-center gap-2 rounded-md border border-input bg-card px-3 text-left text-sm shadow-xs", className)}>
          {value ? (<><Avatar name={value.full_name} size="xs" /><span className="truncate font-medium">{value.full_name}</span><span className="text-xs text-muted-foreground">{value.mrn}</span></>) : <span className="text-muted-foreground">{placeholder}</span>}
          <span className="ml-auto flex items-center gap-1">
            {value && allowClear && <span role="button" aria-label="Clear" onClick={(e) => { e.stopPropagation(); onChange(null); }} className="rounded p-0.5 text-muted-foreground hover:bg-muted"><X className="size-3.5" /></span>}
            <ChevronsUpDown className="size-4 text-muted-foreground" />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] min-w-72 p-2">
        <Input autoFocus placeholder="Search name or MRN…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-2" />
        <div className="max-h-64 overflow-y-auto">
          {(data ?? []).map((p) => (
            <button key={p.id} onClick={() => { onChange({ id: p.id, full_name: p.full_name, mrn: p.mrn }); setOpen(false); }} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted">
              <Avatar name={p.full_name} size="xs" />
              <span className="font-medium">{p.full_name}</span>
              <span className="text-xs text-muted-foreground">{p.mrn}</span>
              {value?.id === p.id && <Check className="ml-auto size-4 text-primary" />}
            </button>
          ))}
          {data?.length === 0 && <p className="px-2 py-4 text-center text-xs text-muted-foreground">No patients found</p>}
        </div>
      </PopoverContent>
    </Popover>
  );
}
