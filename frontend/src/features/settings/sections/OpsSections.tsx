import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Copy, DatabaseBackup, Download, FileKey, ShieldCheck, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Field, Input, SwitchRow, Table, TBody, TD, TH, THead, TR, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime, fmtRelative } from "@/lib/utils";
import { useSection } from "../useSection";
import { SaveBar, SettingsCard } from "../parts";

interface LicenceState {
  mode: "evaluation" | "licensed" | "grace" | "expired" | "invalid"; customer: string | null; licence_id?: string; install_id: string; message: string;
  limits: { clinicians: number; staff: number; branches: number }; enforced: boolean; can_add: boolean; expires_at: string | null; days_left: number | null;
  usage: { clinicians: number; staff: number; admins: number; branches: number; patients: number; documents: number; storage_bytes: number; ai_runs_30d: number };
}
const MODE: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  licensed: { label: "Licensed", tone: "success" }, evaluation: { label: "Evaluation", tone: "warning" }, grace: { label: "Renew now", tone: "warning" }, expired: { label: "Expired", tone: "danger" }, invalid: { label: "Not valid", tone: "danger" },
};
const gb = (n: number) => (n > 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GB` : `${(n / 1024 ** 2).toFixed(1)} MB`);

function Meter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 100;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm"><span>{label}</span><span className="num text-muted-foreground">{used} of {limit}</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${pct >= 100 ? "bg-danger" : pct >= 80 ? "bg-warning" : "bg-primary"}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

export function LicenceSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["licence"], queryFn: () => api<LicenceState>("/api/system/licence") });
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  if (isLoading || !data) return <Skeleton className="h-64" />;
  const m = MODE[data.mode];
  const upload = async (file: File) => {
    setBusy(true);
    try {
      await api("/api/system/licence", { method: "POST", body: JSON.parse(await file.text()) });
      toast.success("Licence installed"); qc.invalidateQueries({ queryKey: ["licence"] });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "That file is not a licence file"); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard title={<span className="flex items-center gap-2"><BadgeCheck className="size-4 text-primary" /> Licence</span>} badge={<Badge tone={m.tone}>{m.label}</Badge>}
        description={data.message}
        footer={<div className="flex flex-wrap gap-2">
          <Button size="sm" loading={busy} onClick={() => input.current?.click()}><FileKey /> Install licence file</Button>
          <input ref={input} type="file" accept=".json,application/json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
          <Button size="sm" variant="secondary" asChild><a href="/api/system/usage-report"><Download /> Usage report</a></Button>
          {data.customer && <Button size="sm" variant="ghost" onClick={async () => { await api("/api/system/licence", { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["licence"] }); toast.success("Licence removed"); }}><Trash2 /> Remove</Button>}
        </div>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Installation ID" hint="Give this to your supplier when ordering or renewing a licence">
            <div className="flex gap-2"><Input readOnly value={data.install_id} className="font-mono" /><Button size="icon-sm" variant="secondary" aria-label="Copy" onClick={() => { void navigator.clipboard?.writeText(data.install_id); toast.success("Copied"); }}><Copy /></Button></div>
          </Field>
          <Field label="Licensed to">{data.customer ? <div className="pt-1.5 text-sm font-medium">{data.customer}{data.licence_id ? <span className="ml-2 text-xs text-muted-foreground">{data.licence_id}</span> : null}</div> : <div className="pt-1.5 text-sm text-muted-foreground">Not licensed yet</div>}</Field>
          {data.expires_at && <Field label="Valid until"><div className="pt-1.5 text-sm">{fmtDateTime(data.expires_at)}{data.days_left !== null && <span className="ml-2 text-xs text-muted-foreground">{data.days_left >= 0 ? `${data.days_left} days left` : `${-data.days_left} days ago`}</span>}</div></Field>}
        </div>
        {!data.can_add && <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm"><AlertTriangle className="mt-0.5 size-4 shrink-0" /> New people and branches cannot be added until the licence is renewed. Everyone can keep working with patients as normal.</div>}
      </SettingsCard>
      <SettingsCard title="What you are using" description={data.enforced ? "Limits that apply to this installation." : "Limits are shown for reference — they are not enforced outside production."}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Meter label="Doctors (clinicians)" used={data.usage.clinicians} limit={data.limits.clinicians} />
          <Meter label="Front desk & viewers" used={data.usage.staff} limit={data.limits.staff} />
          <Meter label="Branches" used={data.usage.branches} limit={data.limits.branches} />
        </div>
        <div className="grid gap-3 border-t pt-4 text-sm sm:grid-cols-4">
          {[["Active patients", data.usage.patients], ["Documents", data.usage.documents], ["Stored files", gb(data.usage.storage_bytes)], ["AI runs (30 days)", data.usage.ai_runs_30d]].map(([k, v]) => <div key={String(k)}><div className="text-xs text-muted-foreground">{k}</div><div className="num text-lg font-semibold">{v}</div></div>)}
        </div>
        <p className="text-xs text-muted-foreground">Administrators do not use a seat. The usage report contains counts only — no patient information.</p>
      </SettingsCard>
    </div>
  );
}

interface BackupState {
  config: { enabled: boolean; time: string; keep: number; include_vectors: boolean }; encrypted: boolean; directory: string; supported: boolean;
  last_ok_at?: string; last_error?: string | null; last_size?: number; last_verify_at?: string; last_verify_ok?: boolean; last_verify_message?: string; last_verify_file?: string;
  backups: { file: string; size: number; created_at: string; encrypted: boolean }[];
}

export function BackupSection() {
  const qc = useQueryClient();
  const s = useSection("backup");
  const { data } = useQuery({ queryKey: ["backup"], queryFn: () => api<BackupState>("/api/system/backup"), refetchInterval: 30000 });
  const [busy, setBusy] = useState<string | null>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["backup"] }); qc.invalidateQueries({ queryKey: ["security-posture"] }); };
  const act = async (id: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(id);
    try { await fn(); toast.success(ok); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(null); refresh(); }
  };
  if (!s.server || !data) return <Skeleton className="h-64" />;
  const d = s.draft;
  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard title={<span className="flex items-center gap-2"><DatabaseBackup className="size-4 text-primary" /> Backups</span>}
        description="A full copy of patients, reports, prescriptions and settings, taken without stopping the system."
        badge={data.last_ok_at ? <Badge tone="success">Last backup {fmtRelative(data.last_ok_at)}</Badge> : <Badge tone="danger">No backup yet</Badge>}
        footer={<Button size="sm" loading={busy === "run"} disabled={!data.supported} onClick={() => act("run", () => api("/api/system/backup/run", { method: "POST" }), "Backup complete")}><DatabaseBackup /> Back up now</Button>}>
        {!data.supported && <p className="rounded-lg border bg-muted/40 px-3 py-2 text-sm">This installation uses an external database. Back it up with that database’s own tools.</p>}
        {data.last_error && <div className="flex gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm"><AlertTriangle className="mt-0.5 size-4 shrink-0" /> The last backup failed: {data.last_error}</div>}
        {!data.encrypted && <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning-soft/50 px-3 py-2 text-sm"><AlertTriangle className="mt-0.5 size-4 shrink-0" /> Backups are <b>not encrypted</b>. Set BACKUP_ENCRYPTION_KEY on the server so a lost or stolen copy cannot be read.</div>}
        <div className="grid gap-x-8 md:grid-cols-2">
          <SwitchRow label="Daily backup" description="Taken automatically at the time below" checked={!!d.enabled} onCheckedChange={(v) => s.set({ enabled: v })} />
          <SwitchRow label="Include the search index" description="Faster to restore; can be rebuilt if left out" checked={!!d.include_vectors} onCheckedChange={(v) => s.set({ include_vectors: v })} />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Time of day" hint="Clinic local time"><Input type="time" value={d.time ?? "02:00"} onChange={(e) => s.set({ time: e.target.value })} /></Field>
          <Field label="Backups to keep" hint="Older ones are removed automatically"><Input type="number" min={1} max={365} value={d.keep ?? 14} onChange={(e) => s.set({ keep: Number(e.target.value) })} /></Field>
        </div>
        <SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} />
        <p className="text-xs text-muted-foreground">Stored in <span className="font-mono">{data.directory}</span> on the server. Copy them to a different device regularly — a backup on the same disk does not survive a failed disk.</p>
      </SettingsCard>
      <SettingsCard title={<span className="flex items-center gap-2"><ShieldCheck className="size-4 text-primary" /> Available backups</span>}
        description={data.last_verify_at ? `Last check: ${data.last_verify_ok ? "passed" : "FAILED"} ${fmtRelative(data.last_verify_at)}${data.last_verify_message ? ` — ${data.last_verify_message}` : ""}` : "Check a backup at least once a month. A check opens it and confirms every file is intact, without changing anything."}>
        {data.backups.length === 0 ? <p className="text-sm text-muted-foreground">No backups yet.</p> : (
          <Table>
            <THead><TR><TH>Backup</TH><TH>Size</TH><TH /></TR></THead>
            <TBody>
              {data.backups.map((b) => (
                <TR key={b.file}>
                  <TD><div className="font-mono text-xs">{b.file}</div><div className="text-xs text-muted-foreground">{fmtDateTime(b.created_at)} · {b.encrypted ? "encrypted" : "not encrypted"}</div></TD>
                  <TD className="num text-sm">{gb(b.size)}</TD>
                  <TD className="space-x-1 text-right">
                    <Button size="xs" variant="secondary" loading={busy === `v${b.file}`} onClick={() => act(`v${b.file}`, () => api("/api/system/backup/verify", { method: "POST", body: { file: b.file } }), "Backup is intact")}>Check</Button>
                    <Button size="xs" variant="ghost" asChild><a href={`/api/system/backup/download/${b.file}`}><Download /></a></Button>
                    <Button size="xs" variant="ghost" aria-label="Delete" onClick={() => act(`d${b.file}`, () => api(`/api/system/backup/${b.file}`, { method: "DELETE" }), "Deleted")}><Trash2 /></Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        <div className="rounded-lg border bg-muted/30 p-3 text-xs">
          <div className="mb-1 font-semibold">Restoring</div>
          Restoring replaces everything with the chosen backup, so it is done on the server with the system stopped, not from this page:
          <pre className="mt-1.5 overflow-auto rounded bg-background p-2 font-mono">docker compose stop app{"\n"}docker compose run --rm app python -m app.cli restore {data.backups[0]?.file ?? "&lt;backup file&gt;"} --yes{"\n"}docker compose start app</pre>
          The same APP_SECRET_KEY and BACKUP_ENCRYPTION_KEY are needed. Keep both somewhere other than this server.
        </div>
      </SettingsCard>
    </div>
  );
}
