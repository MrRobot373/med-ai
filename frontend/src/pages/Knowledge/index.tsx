import { useRef, useState } from "react";
import { Archive, BookOpen, Lock, RefreshCw, Upload } from "lucide-react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import { useIsAdmin } from "@/api/auth";
import {
  useActivateKnowledgeVersion,
  useArchiveKnowledgeDocument,
  useCreateKnowledgeDocument,
  useKnowledgeDocument,
  useKnowledgeDocuments,
  useReindexKnowledgeDocument,
  useUploadKnowledgeVersion,
  type AuthorityTier,
  type IngestionStatus,
  type KnowledgeVersionOut,
} from "@/api/knowledge";
import { GenerationError, relativeTime } from "@/pages/PatientWorkspace/ClinicalModules/shared";

const TIER_OPTIONS: { value: AuthorityTier; label: string }[] = [
  { value: "a", label: "A — Official guidelines / regulatory" },
  { value: "b", label: "B — Systematic reviews / meta-analyses" },
  { value: "c", label: "C — Peer-reviewed clinical studies" },
  { value: "d", label: "D — Authoritative medical references" },
  { value: "e", label: "E — General medical webpages" },
  { value: "f", label: "F — General internet" },
];

const STATUS_BADGE: Record<IngestionStatus, { label: string; className: string }> = {
  queued: { label: "QUEUED", className: "bg-light-blue text-navy" },
  processing: { label: "PROCESSING", className: "bg-primary-blue/10 text-primary-blue" },
  completed: { label: "COMPLETED", className: "bg-success/10 text-success" },
  failed: { label: "FAILED", className: "bg-danger/10 text-danger" },
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function NewDocumentForm({ onDone }: { onDone: (documentId: string) => void }) {
  const create = useCreateKnowledgeDocument();
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [tier, setTier] = useState<AuthorityTier>("d");
  const [tags, setTags] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!title.trim()) return;
    setError(null);
    create.mutate(
      { title: title.trim(), source: source.trim() || undefined, specialty: specialty.trim() || undefined, authority_tier: tier, tags: tags.trim() || undefined },
      {
        onSuccess: (doc) => {
          setTitle("");
          setSource("");
          setSpecialty("");
          setTags("");
          onDone(doc.id);
        },
        onError: (err) => setError(err instanceof ApiError ? err.message : "Could not create the document."),
      },
    );
  }

  return (
    <Card className="space-y-3 p-4">
      <h3 className="text-sm font-semibold text-navy">New Knowledge Document</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-muted-text">Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm" placeholder="e.g. ICO Glaucoma Guidelines" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-muted-text">Source / Publisher</span>
          <input value={source} onChange={(e) => setSource(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm" placeholder="e.g. International Council of Ophthalmology" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-muted-text">Specialty</span>
          <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm" placeholder="e.g. Glaucoma" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-muted-text">Authority Tier</span>
          <select value={tier} onChange={(e) => setTier(e.target.value as AuthorityTier)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm">
            {TIER_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block text-xs font-medium text-muted-text">Tags (comma-separated)</span>
          <input value={tags} onChange={(e) => setTags(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm" placeholder="e.g. glaucoma, surgical, referral" />
        </label>
      </div>
      <button
        type="button"
        onClick={submit}
        disabled={create.isPending || !title.trim()}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
      >
        {create.isPending ? "Creating…" : "Create Document"}
      </button>
      {error && <GenerationError message={error} />}
    </Card>
  );
}

function VersionRow({ documentId, version }: { documentId: string; version: KnowledgeVersionOut }) {
  const activate = useActivateKnowledgeVersion(documentId);
  const badge = STATUS_BADGE[version.ingestion_status];
  const canActivate = !version.is_active && version.ingestion_status === "completed";

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2 text-xs">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 font-medium text-navy">
          <span>v{version.version_number}</span>
          <span className="truncate text-muted-text">{version.source_filename}</span>
          {version.is_active && <span className="rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold text-success">ACTIVE</span>}
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.className}`}>{badge.label}</span>
        </div>
        <div className="mt-0.5 text-muted-text">
          {formatBytes(version.file_size_bytes)} · {version.chunk_count} chunks · uploaded {relativeTime(version.created_at)}
          {version.effective_date && ` · effective ${version.effective_date}`}
          {version.review_date && ` · review by ${version.review_date}`}
        </div>
        {version.ingestion_error && <p className="mt-1 text-danger">{version.ingestion_error}</p>}
      </div>
      {canActivate && (
        <button
          type="button"
          onClick={() => activate.mutate(version.id)}
          disabled={activate.isPending}
          className="rounded-md border border-border px-2 py-1 font-semibold text-navy hover:bg-light-blue disabled:opacity-60"
        >
          {activate.isPending ? "Activating…" : "Activate"}
        </button>
      )}
    </div>
  );
}

function DocumentDetail({ documentId }: { documentId: string }) {
  const { data: document, isLoading } = useKnowledgeDocument(documentId);
  const uploadVersion = useUploadKnowledgeVersion(documentId);
  const reindex = useReindexKnowledgeDocument(documentId);
  const archive = useArchiveKnowledgeDocument(documentId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !document) {
    return <Card className="p-4 text-sm text-muted-text">Loading document…</Card>;
  }

  function handleFileChosen(file: File) {
    setError(null);
    uploadVersion.mutate(
      { file, effectiveDate: effectiveDate || undefined, reviewDate: reviewDate || undefined },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Upload failed.") },
    );
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <Card className="space-y-4 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-navy">{document.title}</h3>
          <p className="text-xs text-muted-text">
            {document.source && `${document.source} · `}
            {document.specialty && `${document.specialty} · `}
            Tier {document.authority_tier.toUpperCase()}
            {document.tags && ` · ${document.tags}`}
          </p>
        </div>
        {!document.archived && (
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => reindex.mutate()}
              disabled={reindex.isPending || document.versions.length === 0}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-semibold text-navy hover:bg-light-blue disabled:opacity-60"
            >
              <RefreshCw className="h-3 w-3" />
              Reindex
            </button>
            <button
              type="button"
              onClick={() => archive.mutate()}
              disabled={archive.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-semibold text-danger hover:bg-danger/5 disabled:opacity-60"
            >
              <Archive className="h-3 w-3" />
              Archive
            </button>
          </div>
        )}
        {document.archived && <span className="rounded-full bg-light-blue px-2 py-0.5 text-[10px] font-semibold text-muted-text">ARCHIVED</span>}
      </div>

      {!document.archived && (
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <label className="text-xs">
            <span className="mb-1 block font-medium text-muted-text">Effective date</span>
            <input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} className="rounded-md border border-border px-2 py-1 text-xs" />
          </label>
          <label className="text-xs">
            <span className="mb-1 block font-medium text-muted-text">Review date</span>
            <input type="date" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} className="rounded-md border border-border px-2 py-1 text-xs" />
          </label>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadVersion.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary-blue px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            <Upload className="h-3.5 w-3.5" />
            {uploadVersion.isPending ? "Uploading…" : "Upload New Version"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileChosen(file);
            }}
          />
        </div>
      )}
      {error && <GenerationError message={error} />}

      <div className="space-y-2">
        {document.versions.length === 0 && <p className="text-sm text-muted-text">No versions uploaded yet.</p>}
        {document.versions.map((v) => (
          <VersionRow key={v.id} documentId={document.id} version={v} />
        ))}
      </div>
    </Card>
  );
}

export default function KnowledgePage() {
  const isAdmin = useIsAdmin();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const { data: documents, isLoading } = useKnowledgeDocuments(includeArchived, search);

  if (!isAdmin) {
    return (
      <Card className="mx-auto max-w-2xl p-6 text-center text-sm text-muted-text">
        <Lock className="mx-auto mb-2 h-5 w-5 text-muted-text" />
        <p className="font-medium text-navy">Knowledge Administration requires an admin account.</p>
        <p className="mt-1">Only admins can curate the shared medical knowledge base every patient's Clinical AI draws from.</p>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary-blue" />
          <h1 className="text-lg font-semibold text-navy">Knowledge Administration</h1>
        </div>
        <button
          type="button"
          onClick={() => setShowNewForm((v) => !v)}
          className="rounded-md bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90"
        >
          {showNewForm ? "Cancel" : "New Document"}
        </button>
      </div>
      <p className="text-sm text-muted-text">
        Guidelines, protocols, and reference documents indexed into the shared <code className="rounded bg-light-blue px-1 py-0.5">medical_knowledge</code> collection.
        Uploading a new version automatically becomes the active, retrievable one once indexing finishes.
      </p>

      {showNewForm && <NewDocumentForm onDone={(id) => { setShowNewForm(false); setSelectedId(id); }} />}

      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title…"
            className="min-w-[200px] flex-1 rounded-md border border-border px-2 py-1.5 text-sm"
          />
          <label className="flex items-center gap-1.5 text-xs text-muted-text">
            <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
            Include archived
          </label>
        </div>

        {isLoading && <p className="text-sm text-muted-text">Loading documents…</p>}
        {!isLoading && documents?.length === 0 && <p className="text-sm text-muted-text">No knowledge documents yet.</p>}

        <div className="divide-y divide-border">
          {documents?.map((doc) => (
            <button
              key={doc.id}
              type="button"
              onClick={() => setSelectedId(doc.id === selectedId ? null : doc.id)}
              className={`flex w-full items-center justify-between gap-2 py-2 text-left text-sm hover:bg-light-blue/50 ${selectedId === doc.id ? "bg-light-blue/60" : ""}`}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-navy">
                  {doc.title}
                  {doc.archived && <span className="ml-2 rounded-full bg-light-blue px-2 py-0.5 text-[10px] font-semibold text-muted-text">ARCHIVED</span>}
                </div>
                <div className="truncate text-xs text-muted-text">
                  {doc.source && `${doc.source} · `}Tier {doc.authority_tier.toUpperCase()}
                  {doc.specialty && ` · ${doc.specialty}`}
                </div>
              </div>
            </button>
          ))}
        </div>
      </Card>

      {selectedId && <DocumentDetail documentId={selectedId} />}
    </div>
  );
}
