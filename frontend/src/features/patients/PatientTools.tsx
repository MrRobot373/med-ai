import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, GitMerge, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Dialog, DialogContent, EmptyState, Field, Input, Select, Skeleton, SwitchRow } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

const FIELD_LABELS: Record<string, string> = {
  mrn: "MRN / UHID", full_name: "Full name", first_name: "First name", last_name: "Last name", date_of_birth: "Date of birth", sex: "Sex",
  phone: "Phone", email: "Email", address: "Address", blood_group: "Blood group", notes: "Notes",
};
interface ImportRow { row: number; status: string; errors: string[]; person: Record<string, any>; match: { mrn: string; name: string; reasons: string[] } | null }
interface ImportResult { headers: string[]; mapping: Record<string, number | null>; summary: Record<string, number> | null; total: number; rows: ImportRow[]; sample?: Record<string, any>[]; committed: boolean; created?: number; needs_mapping: boolean }
const STATUS: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  new: { label: "Will be added", tone: "success" }, exists: { label: "MRN already in the clinic — skipped", tone: "neutral" },
  possible_duplicate: { label: "May already be registered", tone: "warning" }, duplicate_in_file: { label: "Repeated in this file — skipped", tone: "neutral" }, error: { label: "Needs fixing — skipped", tone: "danger" },
};

export function ImportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<ImportResult | null>(null);
  const [mapping, setMapping] = useState<Record<string, number | null>>({});
  const [includePossible, setIncludePossible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setFile(null); setRes(null); setMapping({}); setIncludePossible(false); setError(null); };
  const run = async (f: File, map: Record<string, number | null> | null, commit: boolean) => {
    setBusy(true); setError(null);
    const body = new FormData();
    body.set("file", f);
    if (map) body.set("mapping", JSON.stringify(map));
    body.set("commit", String(commit));
    body.set("include_possible", String(includePossible));
    try {
      const r = await api<ImportResult>("/api/patients/import", { method: "POST", body });
      setRes(r); setMapping(r.mapping);
      if (r.committed) { toast.success(`${r.created} patient${r.created === 1 ? "" : "s"} added`); qc.invalidateQueries({ queryKey: ["patients"] }); }
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not read the file"); } finally { setBusy(false); }
  };
  const cols = res?.headers.map((h, i) => ({ value: String(i), label: h || `Column ${i + 1}` })) ?? [];
  const add = res?.summary?.new ?? 0;
  const willAdd = add + (includePossible ? res?.summary?.possible_duplicate ?? 0 : 0);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent size="lg" icon={<FileSpreadsheet />} title="Import patients" description="Bring in patients from an Excel or CSV file exported from your previous system. Nothing is saved until you confirm."
        footer={res?.committed ? <Button onClick={() => { reset(); onOpenChange(false); }}>Done</Button> : <>
          <Button variant="secondary" onClick={() => { reset(); onOpenChange(false); }}>Cancel</Button>
          {res && !res.needs_mapping && <Button variant="secondary" loading={busy} onClick={() => file && run(file, mapping, false)}>Check again</Button>}
          {res && !res.needs_mapping && <Button loading={busy} disabled={willAdd === 0} onClick={() => file && run(file, mapping, true)}>Add {willAdd} patient{willAdd === 1 ? "" : "s"}</Button>}
        </>}>
        {error && <div className="mb-3 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-foreground">{error}</div>}
        {!res && (
          <button type="button" onClick={() => input.current?.click()} className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-10 text-center hover:border-primary/50 hover:bg-primary-soft/20">
            <Upload className="size-6 text-primary" />
            <span className="font-medium">{busy ? "Reading…" : "Choose a .xlsx or .csv file"}</span>
            <span className="text-xs text-muted-foreground">The first row must be the column headings. Up to 5,000 patients. Dates as dd/mm/yyyy.</span>
            <input ref={input} type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); void run(f, null, false); } e.target.value = ""; }} />
          </button>
        )}
        {res && (res.needs_mapping || res.summary === null) && (
          <p className="mb-3 text-sm">We could not find a name column. Choose which column holds the patient’s name below, then check again.</p>
        )}
        {res && (
          <div className="space-y-4">
            <div>
              <div className="text-label mb-1.5">Which column is which?</div>
              <div className="grid gap-2 sm:grid-cols-3">
                {Object.keys(FIELD_LABELS).map((f) => (
                  <Field key={f} label={FIELD_LABELS[f]}><Select size="sm" value={mapping[f] == null ? "none" : String(mapping[f])} onValueChange={(v) => setMapping((m) => ({ ...m, [f]: v === "none" ? null : Number(v) }))} options={[{ value: "none", label: "— not in the file —" }, ...cols]} /></Field>
                ))}
              </div>
              {res.needs_mapping && file && <Button className="mt-3" size="sm" loading={busy} onClick={() => run(file, mapping, false)}>Use these columns</Button>}
            </div>
            {res.summary && (
              <>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(res.summary).map(([k, n]) => <Badge key={k} tone={STATUS[k]?.tone ?? "neutral"}>{n} · {STATUS[k]?.label ?? k}</Badge>)}
                </div>
                {(res.summary.possible_duplicate ?? 0) > 0 && !res.committed && <SwitchRow label="Also add the ones that may already be registered" description="Off by default. Review them in the list below first." checked={includePossible} onCheckedChange={setIncludePossible} />}
                {res.committed ? (
                  <div className="flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm"><CheckCircle2 className="size-4 text-success" /> {res.created} added. Patients without an MRN were numbered automatically and tagged “imported”.</div>
                ) : (
                  <div className="max-h-64 overflow-auto rounded-lg border text-sm">
                    {res.rows.length === 0 ? <p className="p-3 text-muted-foreground">Every row is ready to be added.</p> : res.rows.map((r) => (
                      <div key={r.row} className="flex items-start justify-between gap-3 border-b px-3 py-2 last:border-0">
                        <div className="min-w-0"><span className="text-xs text-muted-foreground">Row {r.row}</span> <b>{[r.person.first_name, r.person.last_name].filter(Boolean).join(" ") || "—"}</b>{r.person.mrn ? ` · ${r.person.mrn}` : ""}
                          {r.errors.length > 0 && <div className="text-xs text-danger">{r.errors.join("; ")}</div>}
                          {r.match && <div className="text-xs text-muted-foreground">Looks like {r.match.name} ({r.match.mrn}) — {r.match.reasons.join(", ")}</div>}</div>
                        <Badge tone={STATUS[r.status]?.tone ?? "neutral"}>{STATUS[r.status]?.label ?? r.status}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

interface Side { id: string; mrn: string; name: string; date_of_birth: string | null; phone: string | null; visits: number; prescriptions: number; created_at: string }
interface Pair { a: Side; b: Side; score: number; reasons: string[] }

export function DuplicatesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { data, isLoading, refetch } = useQuery({ queryKey: ["patient-duplicates"], queryFn: () => api<Pair[]>("/api/patients/duplicates"), enabled: open });
  const [pick, setPick] = useState<{ pair: Pair; keep: "a" | "b" } | null>(null);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const away = pick ? (pick.keep === "a" ? pick.pair.b : pick.pair.a) : null;
  const keepSide = pick ? pick.pair[pick.keep] : null;
  const doMerge = async () => {
    if (!pick || !away || !keepSide) return;
    setBusy(true);
    try {
      await api("/api/patients/merge", { method: "POST", body: { keep_id: keepSide.id, merge_id: away.id, confirm_mrn: confirm } });
      toast.success(`${away.mrn} merged into ${keepSide.mrn}`);
      setPick(null); setConfirm(""); qc.invalidateQueries({ queryKey: ["patients"] }); void refetch();
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not merge"); } finally { setBusy(false); }
  };
  const card = (s: Side, which: "a" | "b", pair: Pair) => (
    <div className="rounded-lg border p-3 text-sm">
      <div className="font-semibold">{s.name}</div>
      <div className="text-xs text-muted-foreground">{s.mrn}{s.date_of_birth ? ` · born ${fmtDate(s.date_of_birth)}` : ""}{s.phone ? ` · ${s.phone}` : ""}</div>
      <div className="mt-1 text-xs">{s.visits} visit{s.visits === 1 ? "" : "s"} · {s.prescriptions} prescription{s.prescriptions === 1 ? "" : "s"} · registered {fmtDate(s.created_at)}</div>
      <Button size="xs" variant="secondary" className="mt-2" onClick={() => { setPick({ pair, keep: which }); setConfirm(""); }}>Keep this chart</Button>
    </div>
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg" icon={<GitMerge />} title="Possible duplicate charts" description="Pairs that look like the same person. Merging moves everything — visits, prescriptions, reports, results — into the chart you keep. It cannot be undone.">
        {isLoading ? <Skeleton className="h-40" /> : !data?.length ? <EmptyState icon={<CheckCircle2 />} title="No duplicates found" description="No two active charts share a name together with a date of birth or phone number." /> : (
          <div className="max-h-[28rem] space-y-3 overflow-auto">
            {data.map((p) => (
              <div key={p.a.id + p.b.id} className="space-y-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground"><Badge tone="warning">{p.score}% match</Badge>{p.reasons.join(" · ")}</div>
                <div className="grid gap-2 sm:grid-cols-2">{card(p.a, "a", p)}{card(p.b, "b", p)}</div>
              </div>
            ))}
          </div>
        )}
        <Dialog open={!!pick} onOpenChange={(o) => !o && setPick(null)}>
          <DialogContent size="sm" title="Merge these charts?" description={away && keepSide ? `${away.name} (${away.mrn}) will be merged into ${keepSide.name} (${keepSide.mrn}). The ${away.mrn} chart is archived and stays in the audit trail.` : ""}
            footer={<><Button variant="secondary" onClick={() => setPick(null)}>Cancel</Button><Button loading={busy} disabled={confirm.trim().toLowerCase() !== away?.mrn.toLowerCase()} onClick={doMerge}>Merge charts</Button></>}>
            <Field label={`Type ${away?.mrn} to confirm`}><Input value={confirm} onChange={(e) => setConfirm(e.target.value)} autoFocus /></Field>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
