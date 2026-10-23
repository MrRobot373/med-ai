import { useQueryClient } from "@tanstack/react-query";
import { BookOpenText, CheckCircle2, FlaskConical, Layers, Loader2, Play, Search, Upload, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { useDomains, useKnowledge, useMe } from "@/api/hooks";
import type { Trace } from "@/api/types";
import {
  Badge, Button, Card, CardHeader, Dialog, DialogContent, EmptyState, Field, Input, PageHeader, Select, Skeleton, Switch,
  Table, TBody, TD, TH, THead, TR, Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui";
import { DocStatusBadge } from "@/components/clinical/badges";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { Dropzone } from "@/components/clinical/Dropzone";
import { PatientPicker } from "@/components/clinical/PatientPicker";
import { TraceView } from "@/features/assistant/EvidencePanel";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, titleCase } from "@/lib/utils";

const KN_KINDS = ["guideline", "protocol", "drug_reference", "textbook", "other"];

function UploadDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { data: domains } = useDomains();
  const qc = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [domain, setDomain] = useState("general_medicine");
  const [custom, setCustom] = useState("");
  const [kind, setKind] = useState("guideline");
  const [source, setSource] = useState("");
  const [version, setVersion] = useState("");
  const [status, setStatus] = useState<Record<string, "pending" | "uploading" | "done" | "error">>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setFiles([]); setStatus({}); } }, [open]);

  const upload = async () => {
    setBusy(true);
    const dom = domain === "__custom" ? custom.trim().toLowerCase().replace(/\s+/g, "_") : domain;
    for (const f of files) {
      setStatus((s) => ({ ...s, [f.name]: "uploading" }));
      const form = new FormData();
      form.append("file", f);
      form.append("domain", dom);
      form.append("kind", kind);
      if (source) form.append("source_org", source);
      if (version) form.append("version", version);
      try { await api("/api/knowledge", { method: "POST", body: form }); setStatus((s) => ({ ...s, [f.name]: "done" })); }
      catch (e) { setStatus((s) => ({ ...s, [f.name]: "error" })); toast.error(`${f.name}: ${e instanceof ApiError ? e.message : "failed"}`); }
    }
    setBusy(false);
    qc.invalidateQueries({ queryKey: ["knowledge"] });
    qc.invalidateQueries({ queryKey: ["domains"] });
    toast.success("Upload complete — documents are being indexed");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg" icon={<Upload />} title="Add to knowledge library" description="Guidelines, protocols, drug references and policies. Everything is chunked and indexed for hybrid search." footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button onClick={upload} loading={busy} disabled={!files.length || (domain === "__custom" && !custom.trim())}>Upload {files.length || ""} file{files.length === 1 ? "" : "s"}</Button></>}>
        <div className="space-y-4">
          <Dropzone onFiles={(f) => setFiles((cur) => [...cur, ...f.filter((x) => !cur.some((c) => c.name === x.name))])} compact />
          {files.length > 0 && (
            <div className="max-h-36 divide-y overflow-y-auto rounded-lg border">
              {files.map((f) => (
                <div key={f.name} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                  <span className="flex-1 truncate">{f.name}</span>
                  {status[f.name] === "uploading" ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : status[f.name] === "done" ? <CheckCircle2 className="size-4 text-success" /> : status[f.name] === "error" ? <XCircle className="size-4 text-danger" /> : <button className="text-xs text-muted-foreground hover:text-danger" onClick={() => setFiles((c) => c.filter((x) => x !== f))}>Remove</button>}
                </div>
              ))}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Specialty / domain">
              <Select value={domain} onValueChange={setDomain} options={[...(domains ?? []).map((d) => ({ value: d.id, label: d.name, group: d.group })), { value: "__custom", label: "Custom domain…", group: "Other" }]} />
            </Field>
            {domain === "__custom" ? <Field label="Custom domain name"><Input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="e.g. Sports medicine" /></Field> : (
              <Field label="Document type"><Select value={kind} onValueChange={setKind} options={KN_KINDS.map((k) => ({ value: k, label: titleCase(k) }))} /></Field>
            )}
            <Field label="Source / publisher" hint="e.g. ADA, KDIGO, Hospital P&T committee"><Input value={source} onChange={(e) => setSource(e.target.value)} /></Field>
            <Field label="Version"><Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="e.g. 2026" /></Field>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Playground() {
  const [query, setQuery] = useState("");
  const [patient, setPatient] = useState<{ id: string; full_name: string; mrn: string } | null>(null);
  const [result, setResult] = useState<{ passages: any[]; trace: Trace } | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setResult(await api("/api/knowledge/search", { method: "POST", body: { query, patient_id: patient?.id, include_knowledge: true } })); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Search failed"); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_400px]">
      <Card>
        <CardHeader title="Retrieval playground" description="Run the exact retrieval pipeline the assistant uses — without generating an answer. Ideal for tuning Settings → Retrieval." icon={<FlaskConical />} />
        <div className="card-pad space-y-4">
          <div className="flex flex-col gap-2 md:flex-row">
            <Input icon={<Search />} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && query && run()} placeholder="Type a query…" className="flex-1" />
            <PatientPicker value={patient} onChange={setPatient} placeholder="+ patient documents (optional)" className="md:w-72" />
            <Button onClick={run} loading={busy} disabled={!query.trim()}><Play /> Retrieve</Button>
          </div>
          {busy ? <Skeleton className="h-48" /> : result && (result.passages.length === 0 ? <EmptyState compact title="No passages retrieved" /> : (
            <div className="space-y-2">
              {result.passages.map((p) => (
                <div key={p.chunk_id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge tone={p.scope === "patient" ? "info" : "primary"} square className="font-mono">{p.label}</Badge>
                    <span className="font-medium">{p.document_title}</span>
                    {p.section && <span className="text-xs text-muted-foreground">· {p.section}</span>}
                    <span className="ml-auto flex gap-3 text-[0.7rem] text-muted-foreground num">
                      {p.dense_rank && <span>dense #{p.dense_rank}</span>}{p.lexical_rank && <span>BM25 #{p.lexical_rank}</span>}<span>RRF {p.fused_score.toFixed(4)}</span>{p.rerank_score != null && <span>rerank {p.rerank_score.toFixed(3)}</span>}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-4 whitespace-pre-line text-xs text-muted-foreground">{p.excerpt}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Card>
      <Card className="h-fit"><CardHeader title="Pipeline trace" icon={<Layers />} /><div className="card-pad">{result ? <TraceView trace={result.trace} /> : <p className="text-sm text-muted-foreground">Run a query to see each stage.</p>}</div></Card>
    </div>
  );
}

export default function LibraryPage() {
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";
  const [params, setParams] = useSearchParams();
  const [domain, setDomain] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [uploadOpen, setUploadOpen] = useState(params.get("upload") === "1");
  const [docId, setDocId] = useState<string | null>(null);
  const { data: domains } = useDomains();
  const { data, isLoading } = useKnowledge({ q: q || undefined, domain: domain ?? undefined, status: status === "all" ? undefined : status });
  const qc = useQueryClient();
  const grouped = useMemo(() => {
    const out: Record<string, NonNullable<typeof domains>> = {};
    for (const d of domains ?? []) (out[d.group] ||= []).push(d);
    return Object.entries(out);
  }, [domains]);
  const total = (domains ?? []).reduce((a, d) => a + d.count, 0);

  const toggle = async (id: string, active: boolean) => {
    try { await api(`/api/knowledge/${id}/activate`, { method: "POST", query: { active } }); qc.invalidateQueries({ queryKey: ["knowledge"] }); toast.success(active ? "Included in retrieval" : "Excluded from retrieval"); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };

  return (
    <div>
      <PageHeader title="Knowledge library" description="The shared reference corpus behind every answer: guidelines, protocols and drug references, organised by specialty." actions={isAdmin && <Button onClick={() => setUploadOpen(true)}><Upload /> Add documents</Button>} />
      <Tabs defaultValue="documents">
        <TabsList className="mb-4"><TabsTrigger value="documents"><BookOpenText /> Documents</TabsTrigger><TabsTrigger value="playground"><FlaskConical /> Retrieval playground</TabsTrigger></TabsList>
        <TabsContent value="documents">
          <div className="grid gap-[var(--gap)] lg:grid-cols-[250px_1fr]">
            <Card className="h-fit p-2">
              <button onClick={() => setDomain(null)} className={cn("flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-sm", !domain ? "bg-primary-soft font-medium text-primary-soft-foreground" : "hover:bg-muted")}>All specialties <span className="text-xs num">{total}</span></button>
              {grouped.map(([group, list]) => (
                <div key={group} className="mt-3">
                  <div className="text-label px-2.5 pb-1 !text-[0.64rem]">{group}</div>
                  {list.map((d) => (
                    <button key={d.id} onClick={() => setDomain(d.id)} className={cn("flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[0.8rem]", domain === d.id ? "bg-primary-soft font-medium text-primary-soft-foreground" : d.count ? "hover:bg-muted" : "text-muted-foreground hover:bg-muted")}>
                      <span className="truncate">{d.name}</span>{d.count > 0 && <span className="text-xs num">{d.count}</span>}
                    </button>
                  ))}
                </div>
              ))}
            </Card>
            <Card className="overflow-hidden">
              <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
                <Input icon={<Search />} placeholder="Search title or source…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
                <Select size="sm" className="ml-auto w-40" value={status} onValueChange={setStatus} options={[{ value: "all", label: "All" }, { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }, { value: "processing", label: "Processing" }, { value: "failed", label: "Failed" }]} />
              </div>
              {isLoading ? <div className="space-y-2 p-4">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : !data?.length ? (
                <EmptyState icon={<BookOpenText />} title="No documents here" description={isAdmin ? "Add guidelines and references for this specialty." : "Ask an administrator to add references."} action={isAdmin && <Button size="sm" onClick={() => setUploadOpen(true)}><Upload /> Add documents</Button>} />
              ) : (
                <Table>
                  <THead><TR><TH>Document</TH><TH>Specialty</TH><TH>Status</TH><TH className="text-right">Chunks</TH><TH className="text-right">In retrieval</TH></TR></THead>
                  <TBody>
                    {data.map((d) => (
                      <TR key={d.id} data-clickable="true" onClick={() => setDocId(d.id)}>
                        <TD><div className="font-medium">{d.title}</div><div className="text-xs text-muted-foreground">{[titleCase(d.kind), d.source_org, d.version && `v${d.version}`, fmtDate(d.created_at)].filter(Boolean).join(" · ")}</div></TD>
                        <TD>{d.domain ? <Badge tone="primary">{domains?.find((x) => x.id === d.domain)?.name ?? titleCase(d.domain)}</Badge> : <span className="text-xs text-muted-foreground">—</span>}</TD>
                        <TD><DocStatusBadge status={d.status} /></TD>
                        <TD className="text-right num text-muted-foreground">{d.chunk_count}</TD>
                        <TD className="text-right" onClick={(e) => e.stopPropagation()}><Switch checked={d.is_active} disabled={!isAdmin} onCheckedChange={(v) => toggle(d.id, v)} aria-label="Include in retrieval" /></TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="playground"><Playground /></TabsContent>
      </Tabs>
      <UploadDialog open={uploadOpen} onOpenChange={(o) => { setUploadOpen(o); if (!o && params.get("upload")) { params.delete("upload"); setParams(params, { replace: true }); } }} />
      <DocumentDrawer docId={docId} onClose={() => setDocId(null)} canWrite={isAdmin} />
    </div>
  );
}
