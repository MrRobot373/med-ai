import { ChevronLeft, ChevronRight, ExternalLink, FileText, Info, Maximize2, Minimize2, Minus, Plus, ScanLine } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useChunks } from "@/api/hooks";
import type { DocumentItem } from "@/api/types";
import { Badge, Spinner, Tooltip } from "@/components/ui";
import { cn, fmtDate, titleCase } from "@/lib/utils";

export const isVisual = (d: DocumentItem) => d.mime_type === "application/pdf" || d.mime_type.startsWith("image/") || d.mime_type === "application/dicom";
const isRadiology = (d: DocumentItem) => d.mime_type === "application/dicom" || d.kind === "imaging" && d.mime_type.startsWith("image/");

function Thumb({ d, active, onClick }: { d: DocumentItem; active: boolean; onClick: () => void }) {
  return (
    <Tooltip content={`${d.title} · ${fmtDate(d.document_date ?? d.created_at)}`}>
      <button onClick={onClick} className={cn("relative h-14 w-11 shrink-0 overflow-hidden rounded-lg border-2 bg-card shadow-xs transition-all hover:-translate-y-0.5", active ? "border-primary ring-2 ring-primary/30" : "border-white/80 opacity-80 hover:opacity-100 dark:border-white/10")}>
        {isVisual(d) && d.status !== "failed" ? (
          <img src={`/api/documents/${d.id}/preview?width=120`} alt="" loading="lazy" className={cn("size-full object-cover", d.mime_type === "application/dicom" && "bg-black object-contain")} />
        ) : <span className="flex size-full items-center justify-center text-muted-foreground"><FileText className="size-4" /></span>}
      </button>
    </Tooltip>
  );
}

function TextPage({ doc }: { doc: DocumentItem }) {
  const { data } = useChunks(doc.status === "ready" ? doc.id : null);
  return (
    <div className="mx-auto max-w-2xl rounded-lg bg-white p-8 text-[0.8rem] leading-relaxed text-slate-800 shadow-float">
      {!data ? <Spinner /> : data.map((c) => <p key={c.id} className="mb-3 whitespace-pre-wrap">{c.text}</p>)}
    </div>
  );
}

export function ReportViewer({
  documents, selectedId, onSelect, onDetails, overlay, className, emptyAction,
}: {
  documents: DocumentItem[]; selectedId: string | null; onSelect: (id: string) => void; onDetails?: (id: string) => void;
  overlay?: ReactNode; className?: string; emptyAction?: ReactNode;
}) {
  const doc = documents.find((d) => d.id === selectedId) ?? documents[0] ?? null;
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(true);
  const [full, setFull] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const pages = doc?.mime_type === "application/pdf" ? Math.max(doc.page_count, 1) : 1;
  const dark = !!doc && isRadiology(doc);

  useEffect(() => { setPage(1); setZoom(1); setLoading(true); }, [doc?.id]);
  useEffect(() => { setLoading(true); }, [page]);
  useEffect(() => {
    const fn = () => setFull(document.fullscreenElement === box.current);
    document.addEventListener("fullscreenchange", fn);
    return () => document.removeEventListener("fullscreenchange", fn);
  }, []);
  const sorted = useMemo(() => [...documents].sort((a, b) => (b.document_date ?? b.created_at).localeCompare(a.document_date ?? a.created_at)), [documents]);

  const toggleFull = () => (document.fullscreenElement ? document.exitFullscreen() : box.current?.requestFullscreen());
  const roundBtn = "flex size-9 items-center justify-center rounded-full bg-white/90 text-slate-700 shadow-float ring-1 ring-black/5 transition hover:bg-white disabled:opacity-40 dark:bg-slate-800/90 dark:text-slate-200 dark:ring-white/10";

  return (
    <div ref={box} className={cn("relative flex min-h-[420px] flex-col overflow-hidden rounded-3xl border border-white/70 shadow-card dark:border-white/[0.06]", dark ? "bg-[radial-gradient(ellipse_at_center,#1e293b,#020617)]" : "bg-[radial-gradient(ellipse_at_30%_20%,hsl(var(--primary)/0.10),transparent_55%),linear-gradient(180deg,hsl(var(--subtle)),hsl(var(--muted)))]", className)}>
      {/* header */}
      <div className="relative z-10 flex items-start gap-3 p-4">
        <div className={cn("min-w-0 flex-1", dark && "text-white")}>
          <div className="flex items-center gap-2">
            <span className={cn("flex size-8 items-center justify-center rounded-full", dark ? "bg-white/10" : "bg-card shadow-xs")}>{dark ? <ScanLine className="size-4" /> : <FileText className="size-4 text-primary" />}</span>
            <div className="min-w-0">
              <div className="truncate text-[0.95rem] font-semibold tracking-tight">{doc?.title ?? "Reports & imaging"}</div>
              {doc && <div className={cn("text-xs", dark ? "text-white/60" : "text-muted-foreground")}>{titleCase(doc.kind)} · {fmtDate(doc.document_date ?? doc.created_at)}{pages > 1 ? ` · page ${page} of ${pages}` : ""}</div>}
            </div>
          </div>
        </div>
        {doc && (
          <div className="flex items-center gap-1.5">
            {doc.identity_status === "mismatch" && <Badge tone="danger">Quarantined</Badge>}
            {pages > 1 && (
              <div className="flex items-center gap-1">
                <button className={roundBtn} disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="size-4" /></button>
                <button className={roundBtn} disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="size-4" /></button>
              </div>
            )}
            {onDetails && <Tooltip content="Details & extracted values"><button className={roundBtn} onClick={() => onDetails(doc.id)} aria-label="Document details"><Info className="size-4" /></button></Tooltip>}
            <Tooltip content="Open original"><a className={roundBtn} href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer" aria-label="Open original"><ExternalLink className="size-4" /></a></Tooltip>
          </div>
        )}
      </div>

      {doc?.identity_status === "mismatch" && (
        <div className="relative z-10 mx-4 -mt-1 mb-2 rounded-xl border border-danger/30 bg-danger-soft/95 px-3 py-2 text-xs text-danger-foreground backdrop-blur">
          <b>Possible wrong-patient document.</b> {doc.identity_detail} Excluded from AI answers and results until confirmed{onDetails ? " — open details to review." : "."}
        </div>
      )}
      {sorted.length > 1 && (
        <div className="relative z-10 flex justify-center px-4 pb-3">
          <div className="glass flex max-w-full gap-1.5 overflow-x-auto rounded-2xl border border-white/70 p-1.5 shadow-card dark:border-white/10">
            {sorted.map((d) => <Thumb key={d.id} d={d} active={d.id === doc?.id} onClick={() => onSelect(d.id)} />)}
          </div>
        </div>
      )}
      {/* stage */}
      <div className="relative min-h-0 flex-1 overflow-auto px-4 pb-5 sm:px-14">
        {!doc ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-card shadow-card"><ScanLine className="size-6 text-primary" /></div>
            <div><div className="font-medium text-foreground">No reports or imaging yet</div>Upload lab reports, radiology, ECGs or scans to view them here.</div>
            {emptyAction}
          </div>
        ) : doc.status === "processing" ? (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><Spinner /> Processing document…</div>
        ) : isVisual(doc) ? (
          <div className={cn("flex justify-center", zoom === 1 ? "h-full items-center" : "min-h-full items-start")}>
            {loading && <Spinner className={cn("absolute size-5", dark && "text-white/60")} />}
            <img
              key={`${doc.id}-${page}`}
              src={`/api/documents/${doc.id}/preview?page=${page}&width=1400`}
              alt={doc.title}
              onLoad={() => setLoading(false)}
              onError={() => setLoading(false)}
              style={{ width: zoom === 1 ? undefined : `${zoom * 100}%`, maxWidth: zoom === 1 ? "100%" : "none" }}
              className={cn("select-none transition-[width] duration-200", zoom === 1 && "max-h-full object-contain", !dark && "rounded-md bg-white shadow-float", dark && "drop-shadow-2xl", loading && "opacity-0")}
              draggable={false}
            />
          </div>
        ) : <TextPage doc={doc} />}
      </div>


      {/* controls */}
      {doc && isVisual(doc) && (
        <div className="absolute bottom-4 right-4 z-10 flex flex-col gap-2">
          <button className={roundBtn} onClick={() => setZoom((z) => Math.min(4, +(z + 0.5).toFixed(1)))} aria-label="Zoom in"><Plus className="size-4" /></button>
          <button className={roundBtn} disabled={zoom <= 1} onClick={() => setZoom((z) => Math.max(1, +(z - 0.5).toFixed(1)))} aria-label="Zoom out"><Minus className="size-4" /></button>
          <button className={roundBtn} onClick={toggleFull} aria-label="Full screen">{full ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}</button>
        </div>
      )}
      {overlay && <div className="absolute bottom-4 left-4 z-10 max-w-[calc(100%-5rem)]">{overlay}</div>}
    </div>
  );
}

/** Dark frosted call-out floated over the viewer. */
export function InsightCard({ count, title, text, primary, onDismiss, icon }: { count: number; title: string; text: string; primary?: ReactNode; onDismiss?: () => void; icon?: ReactNode }) {
  return (
    <div className="w-64 rounded-2xl bg-slate-900/75 sm:w-72 p-4 text-white shadow-float ring-1 ring-white/10 backdrop-blur-xl animate-slide-up">
      <div className="flex items-start gap-2.5">
        <span className="mt-1 text-white/70">{icon}</span>
        <div className="flex-1"><span className="text-3xl font-semibold leading-none num">{count}</span> <span className="text-[0.95rem] font-medium">{title}</span></div>
        {onDismiss && <button onClick={onDismiss} className="flex size-6 items-center justify-center rounded-full bg-white/10 text-white/70 hover:bg-white/20" aria-label="Dismiss">×</button>}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-white/70">{text}</p>
      {primary && <div className="mt-3 space-y-1.5">{primary}</div>}
    </div>
  );
}
