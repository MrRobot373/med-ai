import { BookOpenText, ClipboardList, ExternalLink, FileText, Globe, ListTree, ShieldCheck } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Source, Trace } from "@/api/types";
import { Badge, EmptyState, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { cn, fmtDate } from "@/lib/utils";

const SCOPE = {
  patient: { icon: FileText, label: "Patient document", chip: "bg-info-soft text-info-foreground" },
  knowledge: { icon: BookOpenText, label: "Knowledge library", chip: "bg-primary-soft text-primary-soft-foreground" },
  web: { icon: Globe, label: "Web evidence", chip: "bg-warning-soft text-warning-foreground" },
  record: { icon: ClipboardList, label: "Structured record", chip: "bg-success-soft text-success-foreground" },
};

function SourceCard({ s, active, onOpenDocument }: { s: Source; active: boolean; onOpenDocument?: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (active) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [active]);
  const meta = SCOPE[s.scope] ?? SCOPE.knowledge;
  return (
    <div ref={ref} className={cn("rounded-lg border bg-card p-3 transition-all", active && "border-primary ring-2 ring-primary/20", s.cited === false && "opacity-70")}>
      <div className="flex items-start gap-2">
        <span className={cn("mt-0.5 rounded px-1.5 py-0.5 font-mono text-[0.68rem] font-semibold", meta.chip)}>{s.label}</span>
        <div className="min-w-0 flex-1">
          <div className="text-[0.82rem] font-medium leading-snug">{s.document_title}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[0.7rem] text-muted-foreground">
            <meta.icon className="size-3" /> {meta.label}
            {s.page && <span>· page {s.page}</span>}
            {s.section && <span className="truncate">· {s.section}</span>}
            {s.document_date && <span>· {fmtDate(s.document_date)}</span>}
            {s.evidence_type && <span>· {s.evidence_type}</span>}
          </div>
        </div>
        {s.cited === false && <Badge tone="outline" className="shrink-0">not cited</Badge>}
      </div>
      {s.excerpt && <p className="mt-2 line-clamp-5 whitespace-pre-line text-[0.78rem] leading-relaxed text-muted-foreground">{s.excerpt.replace(/^#{1,6}\s*/gm, "").replace(/_([^_]+)_/g, "$1").trim()}</p>}
      <div className="mt-2 flex items-center gap-3 text-[0.7rem] text-muted-foreground">
        {s.rerank_score != null && <span className="num">rerank {s.rerank_score.toFixed(2)}</span>}
        {s.dense_rank != null && <span className="num">dense #{s.dense_rank}</span>}
        {s.lexical_rank != null && <span className="num">BM25 #{s.lexical_rank}</span>}
        {s.document_id && onOpenDocument && <button onClick={() => onOpenDocument(s.document_id!)} className="ml-auto font-medium text-primary hover:underline">Open document</button>}
        {s.url && <a href={s.url} target="_blank" rel="noreferrer" className="ml-auto flex items-center gap-1 font-medium text-primary hover:underline">Open source <ExternalLink className="size-3" /></a>}
      </div>
    </div>
  );
}

function Stage({ label, value, ms }: { label: string; value: number | string | undefined; ms?: number }) {
  return (
    <div className="flex flex-1 flex-col items-center rounded-lg border bg-subtle px-2 py-2 text-center">
      <span className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-base font-semibold num">{value ?? "—"}</span>
      {ms !== undefined && <span className="text-[0.65rem] text-muted-foreground num">{ms} ms</span>}
    </div>
  );
}

export function TraceView({ trace }: { trace: Trace }) {
  const c = trace.counts ?? {};
  const t = trace.timings ?? {};
  const g = trace.generation;
  return (
    <div className="space-y-4 text-sm">
      <div>
        <div className="text-label mb-2">Retrieval pipeline</div>
        <div className="flex items-stretch gap-1.5">
          <Stage label="Dense" value={c.dense} ms={(t.embed_ms ?? 0) + (t.dense_ms ?? 0)} />
          <Stage label="BM25" value={c.lexical} ms={t.lexical_ms} />
          <Stage label="Fused" value={c.fused} ms={t.fusion_ms} />
          <Stage label="Reranked" value={c.after_rerank} ms={t.rerank_ms} />
          <Stage label="Used" value={c.final} />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {c.context_tokens ?? 0} context tokens · {c.duplicates_removed ?? 0} duplicates removed · profile <span className="font-medium">{trace.profile}</span> · searched {trace.scopes?.join(" + ") || "—"}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border p-2.5"><div className="text-muted-foreground">Embedding model</div><div className="truncate font-medium">{trace.models?.embedding}</div></div>
        <div className="rounded-lg border p-2.5"><div className="text-muted-foreground">Reranker</div><div className="truncate font-medium">{trace.models?.reranker}</div></div>
        {g && <div className="rounded-lg border p-2.5"><div className="text-muted-foreground">Language model</div><div className="truncate font-medium">{g.model}</div></div>}
        {g && <div className="rounded-lg border p-2.5"><div className="text-muted-foreground">First token · total</div><div className="font-medium num">{g.first_token_ms ?? "—"} ms · {(g.generation_ms / 1000).toFixed(1)} s</div></div>}
      </div>
      {g && (
        <div className="rounded-lg border p-3">
          <div className="flex items-center gap-2 font-medium"><ShieldCheck className="size-4 text-success" /> Citation check</div>
          <p className="mt-1 text-xs text-muted-foreground">
            {g.citations_used.length} sources cited{g.citation_coverage != null ? ` · ${Math.round(g.citation_coverage * 100)}% of statements carry a citation` : ""}.
            {g.invalid_citations_removed.length > 0 && <span className="text-danger-foreground"> Removed {g.invalid_citations_removed.length} citation(s) that pointed to sources that were not provided: {g.invalid_citations_removed.join(", ")}.</span>}
          </p>
        </div>
      )}
      {trace.web && (
        <div className="rounded-lg border p-3">
          <div className="flex items-center gap-2 font-medium"><Globe className="size-4 text-warning" /> Web research</div>
          {trace.web.status === "searched" ? (
            <div className="mt-1 space-y-1 text-xs text-muted-foreground">
              <div>Outbound (de-identified) query: <code className="rounded bg-muted px-1">{trace.web.outbound_query}</code></div>
              <div>{trace.web.identifiers_removed} identifier(s) removed before sending.</div>
              <div className="flex flex-wrap gap-1">{trace.web.providers?.map((p: any) => <Badge key={p.provider} tone={p.status === "error" ? "danger" : "neutral"}>{p.name}: {p.status === "error" ? "failed" : `${p.count}${p.status === "cached" ? " (cached)" : ""}`}</Badge>)}</div>
            </div>
          ) : <p className="mt-1 text-xs text-muted-foreground">{trace.web.note}</p>}
        </div>
      )}
      {!!trace.candidates?.length && (
        <div>
          <div className="text-label mb-2">Candidates (top {trace.candidates.length})</div>
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-xs">
              <thead className="bg-subtle text-muted-foreground"><tr><th className="px-2 py-1.5 text-left font-medium">Passage</th><th className="px-2 py-1.5 text-right font-medium">Dense</th><th className="px-2 py-1.5 text-right font-medium">BM25</th><th className="px-2 py-1.5 text-right font-medium">Score</th></tr></thead>
              <tbody>
                {trace.candidates.map((cd) => (
                  <tr key={cd.chunk_id} className={cn("border-t", !cd.selected && "text-muted-foreground")}>
                    <td className="max-w-[12rem] truncate px-2 py-1.5">{cd.label && <span className="mr-1 font-mono font-semibold text-primary">{cd.label}</span>}{cd.document_title}{cd.page ? ` p${cd.page}` : ""}</td>
                    <td className="px-2 py-1.5 text-right num">{cd.dense_rank ?? "—"}</td>
                    <td className="px-2 py-1.5 text-right num">{cd.lexical_rank ?? "—"}</td>
                    <td className="px-2 py-1.5 text-right num">{cd.rerank_score != null ? cd.rerank_score.toFixed(2) : cd.fused_score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export function EvidencePanel({ sources, trace, activeLabel, tab, onTab, onOpenDocument }: { sources: Source[]; trace: Trace | null; activeLabel: string | null; tab: string; onTab: (t: string) => void; onOpenDocument?: (id: string) => void }) {
  const cited = sources.filter((s) => s.cited !== false);
  const other = sources.filter((s) => s.cited === false);
  return (
    <Tabs value={tab} onValueChange={onTab} className="flex h-full flex-col">
      <div className="border-b px-4 py-3">
        <TabsList className="w-full">
          <TabsTrigger value="sources" className="flex-1">Sources {sources.length > 0 && <span className="text-muted-foreground num">{sources.length}</span>}</TabsTrigger>
          <TabsTrigger value="trace" className="flex-1"><ListTree /> Why this answer</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="sources" className="flex-1 space-y-2 overflow-y-auto p-4">
        {sources.length === 0 ? <EmptyState compact icon={<BookOpenText />} title="No sources yet" description="Sources used for the selected answer appear here, labelled exactly as cited." /> : (
          <>
            {cited.map((s) => <SourceCard key={s.label} s={s} active={activeLabel === s.label} onOpenDocument={onOpenDocument} />)}
            {other.length > 0 && <div className="text-label pb-1 pt-3">Retrieved but not cited</div>}
            {other.map((s) => <SourceCard key={s.label} s={s} active={activeLabel === s.label} onOpenDocument={onOpenDocument} />)}
          </>
        )}
      </TabsContent>
      <TabsContent value="trace" className="flex-1 overflow-y-auto p-4">
        {trace ? <TraceView trace={trace} /> : <EmptyState compact icon={<ListTree />} title="No trace yet" description="Ask a question to see how evidence was retrieved, ranked and checked." />}
      </TabsContent>
    </Tabs>
  );
}
