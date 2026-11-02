import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Download, ExternalLink, FileText, RotateCw, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useChunks, useDocument, useObservations } from "@/api/hooks";
import { Badge, Button, KeyValue, Select, SheetContent, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtDate, fmtDateTime, fmtNum, titleCase } from "@/lib/utils";
import { ConfirmDialog } from "./ConfirmDialog";
import { DocStatusBadge, FlagBadge, IdentityBadge, ReviewBadge } from "./badges";

export function DocumentDrawer({ docId, onClose, canWrite, kinds }: { docId: string | null; onClose: () => void; canWrite: boolean; kinds?: string[] }) {
  const { data: doc } = useDocument(docId);
  const { data: chunks, isLoading: chunksLoading } = useChunks(doc?.status === "ready" ? docId : null);
  const { data: obs } = useObservations(doc?.patient_id ?? "");
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const docObs = (obs ?? []).filter((o) => o.document_id === docId);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["document", docId] });
    if (doc?.patient_id) qc.invalidateQueries({ queryKey: ["patient", doc.patient_id] });
    qc.invalidateQueries({ queryKey: ["knowledge"] });
    qc.invalidateQueries({ queryKey: ["inbox"] });
  };
  const act = async (key: string, fn: () => Promise<unknown>, msg: string) => {
    setBusy(key);
    try { await fn(); toast.success(msg); refresh(); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Action failed"); } finally { setBusy(null); }
  };
  const patch = (body: object, msg: string, key = "patch") => act(key, () => api(`/api/documents/${docId}`, { method: "PATCH", body }), msg);
  const isPdf = doc?.mime_type === "application/pdf";
  const isImage = doc?.mime_type.startsWith("image/");

  return (
    <DialogPrimitive.Root open={!!docId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        width="max-w-3xl"
        title={doc?.title ?? "Document"}
        description={doc && <div className="flex flex-wrap items-center gap-1.5"><DocStatusBadge status={doc.status} />{doc.scope === "patient" && <><IdentityBadge status={doc.identity_status} detail={doc.identity_detail} /><ReviewBadge status={doc.review_status} /></>}{doc.domain && <Badge tone="primary">{titleCase(doc.domain)}</Badge>}</div>}
        footer={doc && canWrite && (
          <>
            <ConfirmDialog danger title="Delete document?" description="The file, its extracted text and any values extracted from it will be removed." confirmLabel="Delete" onConfirm={async () => { await api(`/api/documents/${docId}`, { method: "DELETE" }); toast.success("Document deleted"); refresh(); onClose(); }} trigger={<Button variant="danger-ghost" size="sm" className="mr-auto"><Trash2 /> Delete</Button>} />
            <Button variant="secondary" size="sm" loading={busy === "re"} onClick={() => act("re", () => api(`/api/documents/${docId}/reprocess`, { method: "POST" }), "Re-processing started")}><RotateCw /> Re-process</Button>
            {doc.scope === "patient" && doc.review_status !== "reviewed" && <Button size="sm" loading={busy === "patch"} onClick={() => patch({ review_status: "reviewed" }, "Marked as reviewed")}><Check /> Mark reviewed</Button>}
          </>
        )}
      >
        {!doc ? <div className="space-y-3 p-5"><Skeleton className="h-6" /><Skeleton className="h-64" /></div> : (
          <div className="space-y-5 p-5">
            {doc.identity_status === "mismatch" && (
              <div className="rounded-lg border border-danger/30 bg-danger-soft p-3.5 text-sm text-danger-foreground">
                <div className="font-semibold">This document may belong to another patient</div>
                <p className="mt-1 opacity-90">{doc.identity_detail} It is quarantined: its contents are excluded from AI answers and no values were added to the chart.</p>
                {canWrite && <Button size="sm" variant="secondary" className="mt-3" loading={busy === "id"} onClick={() => patch({ identity_status: "confirmed" }, "Identity confirmed — re-processing", "id")}><ShieldCheck /> I've verified it belongs to this patient</Button>}
              </div>
            )}
            {doc.status === "failed" && <div className="rounded-lg border border-danger/30 bg-danger-soft p-3.5 text-sm text-danger-foreground"><div className="font-semibold">Processing failed</div><p className="mt-1">{doc.error}</p></div>}
            <Tabs defaultValue="preview">
              <TabsList>
                <TabsTrigger value="preview">Preview</TabsTrigger>
                <TabsTrigger value="text">Extracted text {chunks && <span className="text-muted-foreground">({chunks.length})</span>}</TabsTrigger>
                {doc.scope === "patient" && <TabsTrigger value="values">Values {docObs.length > 0 && <span className="text-muted-foreground">({docObs.length})</span>}</TabsTrigger>}
                <TabsTrigger value="details">Details</TabsTrigger>
              </TabsList>
              <TabsContent value="preview" className="mt-4">
                {isPdf ? <iframe title="Document preview" src={`/api/documents/${doc.id}/file`} className="h-[65vh] w-full rounded-lg border bg-muted" />
                  : isImage ? <img src={`/api/documents/${doc.id}/file`} alt={doc.title} className="max-h-[65vh] w-full rounded-lg border bg-muted object-contain" />
                  : <div className="flex flex-col items-center gap-3 rounded-lg border bg-subtle py-12 text-sm text-muted-foreground"><FileText className="size-8" /> Preview not available for this file type — see “Extracted text”.</div>}
                <div className="mt-3 flex gap-2">
                  <Button size="xs" variant="secondary" asChild><a href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer"><ExternalLink /> Open in new tab</a></Button>
                  <Button size="xs" variant="ghost" asChild><a href={`/api/documents/${doc.id}/file?download=true`}><Download /> Download</a></Button>
                </div>
              </TabsContent>
              <TabsContent value="text" className="mt-4 space-y-3">
                {doc.status !== "ready" ? <p className="text-sm text-muted-foreground">Available once processing completes.</p> : chunksLoading ? <Skeleton className="h-40" /> : chunks?.map((c) => (
                  <div key={c.id} className="rounded-lg border">
                    <div className="flex items-center gap-2 border-b bg-subtle px-3 py-1.5 text-[0.7rem] text-muted-foreground"><span className="font-mono">#{c.ordinal + 1}</span>{c.page && <span>page {c.page}</span>}{c.section && <span className="truncate">· {c.section}</span>}<span className="ml-auto">{c.token_count} tokens</span></div>
                    <pre className="whitespace-pre-wrap px-3 py-2.5 font-sans text-[0.8rem] leading-relaxed">{c.text}</pre>
                  </div>
                ))}
              </TabsContent>
              <TabsContent value="values" className="mt-4">
                {docObs.length === 0 ? <p className="text-sm text-muted-foreground">No measured values were extracted from this document.</p> : (
                  <div className="divide-y rounded-lg border">
                    {docObs.map((o) => (
                      <div key={o.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                        <span className="flex-1 font-medium">{o.name}</span>
                        <span className="num">{o.value_num !== null ? fmtNum(o.value_num) : o.value_text} <span className="text-muted-foreground">{o.unit}</span></span>
                        <span className="w-24 text-right text-xs text-muted-foreground">{o.ref_text ?? "no range"}</span>
                        <span className="w-20 text-right"><FlagBadge flag={o.flag} compact /></span>
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>
              <TabsContent value="details" className="mt-4 space-y-4">
                <div className="rounded-lg border px-4 py-2">
                  <KeyValue label="File" value={doc.filename} />
                  <KeyValue label="Size" value={fmtBytes(doc.size_bytes)} />
                  <KeyValue label="Pages · chunks" value={`${doc.page_count} · ${doc.chunk_count}`} />
                  <KeyValue label="Document date" value={fmtDate(doc.document_date)} />
                  <KeyValue label="Uploaded" value={fmtDateTime(doc.created_at)} />
                  {doc.source_org && <KeyValue label="Source" value={doc.source_org} />}
                  {doc.version && <KeyValue label="Version" value={doc.version} />}
                  {doc.extraction?.page_methods && <KeyValue label="Text extraction" value={Object.values(doc.extraction.page_methods).includes("vision") ? "Text layer + vision model" : "Text layer"} />}
                </div>
                {canWrite && kinds && (
                  <div className="max-w-xs"><div className="mb-1.5 text-[0.8rem] font-medium">Document type</div>
                    <Select value={doc.kind} onValueChange={(v) => patch({ kind: v }, "Type updated")} options={kinds.map((k) => ({ value: k, label: titleCase(k) }))} />
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>
        )}
      </SheetContent>
    </DialogPrimitive.Root>
  );
}
