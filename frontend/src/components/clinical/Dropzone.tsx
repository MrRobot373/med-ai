import { UploadCloud } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export const ACCEPT = ".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.dcm";

export function Dropzone({ onFiles, multiple = true, accept = ACCEPT, hint, className, compact, children }: { onFiles: (files: File[]) => void; multiple?: boolean; accept?: string; hint?: ReactNode; className?: string; compact?: boolean; children?: ReactNode }) {
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
      onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-input bg-subtle text-center transition-colors hover:border-primary/50 hover:bg-primary-soft/40",
        compact ? "px-4 py-5" : "px-6 py-10", drag && "border-primary bg-primary-soft/60", className,
      )}
    >
      <input ref={input} type="file" className="hidden" multiple={multiple} accept={accept} onChange={(e) => { const f = Array.from(e.target.files ?? []); if (f.length) onFiles(f); e.target.value = ""; }} />
      {children ?? (
        <>
          <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-card text-primary shadow-xs ring-1 ring-border"><UploadCloud className="size-5" /></div>
          <p className="text-sm font-medium">Drop files here or <span className="text-primary">browse</span></p>
          <p className="mt-1 text-xs text-muted-foreground">{hint ?? "PDF, Word, Excel, CSV, text, JSON or images · scanned pages are read by the vision model"}</p>
        </>
      )}
    </div>
  );
}
