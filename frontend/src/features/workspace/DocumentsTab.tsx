import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { usePatientDocuments } from "@/api/hooks";
import { Badge, Card, EmptyState, Input, Select, Skeleton, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { DocStatusBadge, IdentityBadge, ReviewBadge } from "@/components/clinical/badges";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { Dropzone } from "@/components/clinical/Dropzone";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtDate, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

export default function DocumentsTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = usePatientDocuments(patient.id);
  const { data: kinds } = useQuery({ queryKey: ["kinds"], queryFn: () => api<string[]>("/api/document-kinds"), staleTime: Infinity });
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [uploadKind, setUploadKind] = useState("auto");
  const qc = useQueryClient();
  const openId = params.get("doc");

  const upload = async (files: File[]) => {
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      if (uploadKind !== "auto") form.append("kind", uploadKind);
      try {
        await api(`/api/patients/${patient.id}/documents`, { method: "POST", body: form });
        toast.success(`Uploaded ${file.name}`, { description: "Reading, checking identity and indexing…" });
      } catch (e) {
        toast.error(`${file.name}: ${e instanceof ApiError ? e.message : "upload failed"}`);
      }
    }
    qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    qc.invalidateQueries({ queryKey: ["inbox"] });
  };

  const rows = useMemo(() => (data ?? []).filter((d) => (kind === "all" || d.kind === kind) && (!q || d.title.toLowerCase().includes(q.toLowerCase()))), [data, kind, q]);

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <Dropzone onFiles={upload} compact />
          <Card className="card-pad flex flex-col justify-center gap-2 lg:w-64">
            <div className="text-[0.8rem] font-medium">Document type for new uploads</div>
            <Select value={uploadKind} onValueChange={setUploadKind} options={[{ value: "auto", label: "Detect automatically" }, ...(kinds ?? []).filter((k) => !["guideline", "protocol", "drug_reference", "textbook"].includes(k)).map((k) => ({ value: k, label: titleCase(k) }))]} />
            <p className="text-xs text-muted-foreground">Each upload is checked against this patient's name and MRN.</p>
          </Card>
        </div>
      )}
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
          <Input icon={<Search />} placeholder="Filter documents…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
          <Select size="sm" className="ml-auto w-48" value={kind} onValueChange={setKind} options={[{ value: "all", label: "All types" }, ...Array.from(new Set((data ?? []).map((d) => d.kind))).map((k) => ({ value: k, label: titleCase(k) }))]} />
        </div>
        {isLoading ? <div className="space-y-2 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : rows.length === 0 ? (
          <EmptyState icon={<FileText />} title="No documents" description="Upload lab reports, discharge summaries, imaging reports, scans or photos." />
        ) : (
          <Table>
            <THead><TR><TH>Document</TH><TH>Type</TH><TH>Date</TH><TH>Status</TH><TH>Checks</TH></TR></THead>
            <TBody>
              {rows.map((d) => (
                <TR key={d.id} data-clickable="true" onClick={() => setParams({ doc: d.id })}>
                  <TD>
                    <div className="flex items-center gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><FileText className="size-4" /></div>
                      <div className="min-w-0"><div className="truncate font-medium">{d.title}</div><div className="truncate text-xs text-muted-foreground">{d.filename} · {fmtBytes(d.size_bytes)}</div></div>
                    </div>
                  </TD>
                  <TD><Badge>{titleCase(d.kind)}</Badge></TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{fmtDate(d.document_date ?? d.created_at)}</TD>
                  <TD><DocStatusBadge status={d.status} /></TD>
                  <TD><div className="flex flex-wrap gap-1"><IdentityBadge status={d.identity_status} detail={d.identity_detail} />{d.status === "ready" && <ReviewBadge status={d.review_status} />}</div></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
      <DocumentDrawer docId={openId} onClose={() => { params.delete("doc"); setParams(params); }} canWrite={canWrite} kinds={kinds} />
    </div>
  );
}
