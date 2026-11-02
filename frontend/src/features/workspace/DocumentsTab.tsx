import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Image as ImageIcon, Info, ScanLine, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { usePatientDocuments } from "@/api/hooks";
import type { DocumentItem } from "@/api/types";
import { Button, Card, EmptyState, Input, Segmented, Select, Skeleton } from "@/components/ui";
import { DocStatusBadge, IdentityBadge, ReviewBadge } from "@/components/clinical/badges";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { ACCEPT, Dropzone } from "@/components/clinical/Dropzone";
import { ReportViewer } from "@/components/clinical/ReportViewer";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, titleCase } from "@/lib/utils";
import { useWorkspace } from "./context";

const IMAGING_KINDS = ["imaging", "ecg", "pathology"];
const iconFor = (d: DocumentItem) => (d.mime_type === "application/dicom" ? ScanLine : d.mime_type.startsWith("image/") ? ImageIcon : FileText);

export default function DocumentsTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = usePatientDocuments(patient.id);
  const { data: kinds } = useQuery({ queryKey: ["kinds"], queryFn: () => api<string[]>("/api/document-kinds"), staleTime: Infinity });
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | "reports" | "imaging">("all");
  const [uploadKind, setUploadKind] = useState("auto");
  const [details, setDetails] = useState<string | null>(null);
  const qc = useQueryClient();
  const selected = params.get("doc");

  const rows = useMemo(() => (data ?? []).filter((d) =>
    (filter === "all" || (filter === "imaging") === (IMAGING_KINDS.includes(d.kind) || d.mime_type === "application/dicom"))
    && (!q || d.title.toLowerCase().includes(q.toLowerCase()))), [data, filter, q]);
  useEffect(() => { if (!selected && rows.length) setParams({ doc: rows[0].id }, { replace: true }); }, [rows, selected, setParams]);
  useEffect(() => {
    if (params.get("details") === "1" && selected) {
      setDetails(selected);
      params.delete("details");
      setParams(params, { replace: true });
    }
  }, [params, selected, setParams]);

  const upload = async (files: File[]) => {
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      if (uploadKind !== "auto") form.append("kind", uploadKind);
      try {
        const d = await api<DocumentItem>(`/api/patients/${patient.id}/documents`, { method: "POST", body: form });
        toast.success(`Uploaded ${file.name}`, { description: "Reading, checking identity and indexing…" });
        setParams({ doc: d.id });
      } catch (e) {
        toast.error(`${file.name}: ${e instanceof ApiError ? e.message : "upload failed"}`);
      }
    }
    qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    qc.invalidateQueries({ queryKey: ["inbox"] });
  };

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_400px]">
      <ReportViewer className="h-[calc(100vh-220px)] min-h-[560px] min-w-0" documents={rows} selectedId={selected} onSelect={(id) => setParams({ doc: id })} onDetails={setDetails} />
      <div className="min-w-0 space-y-[var(--gap)]">
        {canWrite && (
          <Card className="card-pad space-y-3">
            <Dropzone onFiles={upload} compact accept={`${ACCEPT},.dcm,.dicom`} hint="Reports, scans, photos, ECGs and DICOM (X-ray, CT, MRI)" />
            <Select size="sm" value={uploadKind} onValueChange={setUploadKind} options={[{ value: "auto", label: "Detect document type automatically" }, ...(kinds ?? []).filter((k) => !["guideline", "protocol", "drug_reference", "textbook"].includes(k)).map((k) => ({ value: k, label: titleCase(k) }))]} />
          </Card>
        )}
        <Card className="overflow-hidden">
          <div className="space-y-2.5 border-b border-border/70 p-3">
            <Segmented value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "reports", label: "Reports" }, { value: "imaging", label: "Imaging" }]} />
            <Input icon={<Search />} placeholder="Filter…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="max-h-[calc(100vh-460px)] min-h-48 space-y-1.5 overflow-y-auto p-2">
            {isLoading ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />) : rows.length === 0 ? (
              <EmptyState compact icon={<FileText />} title="No documents" description="Upload reports, radiology, ECGs or photos." />
            ) : rows.map((d) => {
              const Icon = iconFor(d);
              return (
                <button key={d.id} onClick={() => setParams({ doc: d.id })} className={cn("group flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition-colors", selected === d.id ? "bg-primary-soft/70 ring-1 ring-primary/30" : "hover:bg-muted/70")}>
                  <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", d.mime_type === "application/dicom" ? "bg-slate-900 text-white" : "bg-card text-primary shadow-xs")}><Icon className="size-4" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[0.84rem] font-medium">{d.title}</span>
                    <span className="block text-[0.7rem] text-muted-foreground">{titleCase(d.kind)} · {fmtDate(d.document_date ?? d.created_at)}</span>
                    <span className="mt-1 flex flex-wrap gap-1">{d.status !== "ready" && <DocStatusBadge status={d.status} />}<IdentityBadge status={d.identity_status} detail={d.identity_detail} />{d.status === "ready" && <ReviewBadge status={d.review_status} />}</span>
                  </span>
                  <Button size="icon-xs" variant="ghost" className="opacity-0 group-hover:opacity-100" onClick={(e) => { e.stopPropagation(); setDetails(d.id); }} aria-label="Details"><Info /></Button>
                </button>
              );
            })}
          </div>
        </Card>
      </div>
      <DocumentDrawer docId={details} onClose={() => setDetails(null)} canWrite={canWrite} kinds={kinds} />
    </div>
  );
}
