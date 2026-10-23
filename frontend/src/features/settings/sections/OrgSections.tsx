import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, ImagePlus, KeyRound, Lock, MoreHorizontal, Palette, RefreshCw, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useHealth, useMe } from "@/api/hooks";
import type { User } from "@/api/types";
import {
  Avatar, Badge, Button, Card, Checkbox, Dialog, DialogContent, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  Field, Input, KeyValue, Segmented, Select, Skeleton, SwitchRow, Table, TBody, TD, TH, THead, TR, Textarea,
} from "@/components/ui";
import { ComponentRow, STATUS_TONE } from "@/components/layout/StatusIndicator";
import { ACCENT_PRESETS } from "@/lib/color";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDateTime, fmtRelative } from "@/lib/utils";
import { useSection } from "../useSection";
import { NumberField, SaveBar, SecretField, SettingsCard } from "../parts";

async function resizeLogo(file: File): Promise<string> {
  const img = await createImageBitmap(file);
  const size = 128;
  const scale = Math.min(size / img.width, size / img.height, 1);
  const canvas = Object.assign(document.createElement("canvas"), { width: Math.round(img.width * scale), height: Math.round(img.height * scale) });
  canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

export function BrandingSection() {
  const s = useSection("branding");
  if (!s.server) return null;
  const d = s.draft;
  return (
    <SettingsCard title={<span className="flex items-center gap-2"><Palette className="size-4 text-primary" /> Organisation &amp; branding</span>} description="White-label the product for your organisation. Applies to every user and the sign-in page." footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} />}>
      <div className="flex items-center gap-4">
        <img src={d.logo_data_url || "/brand-mark.webp"} alt="" className="size-16 rounded-xl border bg-card object-contain p-1" />
        <div className="space-y-1.5">
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" asChild><label className="cursor-pointer"><ImagePlus /> Upload logo<input type="file" accept="image/*" className="hidden" onChange={async (e) => { const f = e.target.files?.[0]; if (f) s.set({ logo_data_url: await resizeLogo(f) }); }} /></label></Button>
            {d.logo_data_url && <Button size="sm" variant="ghost" onClick={() => s.set({ logo_data_url: null })}><Trash2 /> Remove</Button>}
          </div>
          <p className="text-xs text-muted-foreground">Square image recommended. Resized to 128 px and used as the favicon too.</p>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Product name"><Input value={d.product_name} onChange={(e) => s.set({ product_name: e.target.value })} /></Field>
        <Field label="Organisation"><Input value={d.organization} onChange={(e) => s.set({ organization: e.target.value })} /></Field>
        <Field label="Tagline" className="md:col-span-2" hint="Shown on the sign-in page"><Input value={d.tagline} onChange={(e) => s.set({ tagline: e.target.value })} /></Field>
        <Field label="Sign-in message" className="md:col-span-2"><Input value={d.login_message} onChange={(e) => s.set({ login_message: e.target.value })} /></Field>
        <Field label="Clinical disclaimer" className="md:col-span-2" hint="Shown persistently in the app footer"><Textarea rows={2} value={d.disclaimer} onChange={(e) => s.set({ disclaimer: e.target.value })} /></Field>
      </div>
      <div className="grid gap-4 border-t pt-5 md:grid-cols-2">
        <Field label="Default accent colour" hint="Users can override in their own appearance settings">
          <div className="flex flex-wrap items-center gap-2">
            {ACCENT_PRESETS.map((p) => <button key={p.hex} onClick={() => s.set({ default_accent: p.hex })} title={p.name} className={cn("size-7 rounded-full ring-offset-2 ring-offset-card", d.default_accent?.toLowerCase() === p.hex.toLowerCase() && "ring-2 ring-foreground/60")} style={{ background: p.hex }} />)}
            <Input value={d.default_accent} onChange={(e) => s.set({ default_accent: e.target.value })} className="w-28 font-mono text-xs" />
          </div>
        </Field>
        <Field label="Default theme"><Segmented value={d.default_theme} onChange={(v) => s.set({ default_theme: v })} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }, { value: "system", label: "System" }]} /></Field>
      </div>
    </SettingsCard>
  );
}

const SOURCES = [
  { id: "pubmed", name: "PubMed", text: "Peer-reviewed literature (NCBI E-utilities)" },
  { id: "openfda", name: "openFDA", text: "FDA drug labelling" },
  { id: "clinicaltrials", name: "ClinicalTrials.gov", text: "Trial registry" },
];

export function ResearchSection() {
  const s = useSection("research");
  if (!s.server) return null;
  const d = s.draft;
  return (
    <SettingsCard title={<span className="flex items-center gap-2"><Globe className="size-4 text-primary" /> Research sources</span>} description="Optional external evidence. Off by default — the platform is fully local until you enable this." badge={<Badge tone={s.server.enabled ? "warning" : "success"}>{s.server.enabled ? "Online research enabled" : "Local-only"}</Badge>} footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} />}>
      <SwitchRow label="Enable Research Mode" description="Allows clinicians to opt in to web evidence per conversation and use the Research page." checked={d.enabled} onCheckedChange={(v) => s.set({ enabled: v })} />
      <div className="rounded-lg border bg-subtle p-3 text-xs text-muted-foreground"><ShieldCheck className="mr-1 inline size-3.5 text-success" /> Every outbound query is de-identified first: the active patient's name, MRN, phone and email, plus emails, phone numbers, dates and addresses, are stripped. Clinicians can preview exactly what is sent, and every search is audited.</div>
      <Field label="Sources">
        <div className="grid gap-2 md:grid-cols-3">
          {SOURCES.map((src) => (
            <label key={src.id} className={cn("flex cursor-pointer items-start gap-2.5 rounded-lg border p-3", d.sources.includes(src.id) && "border-primary/50 bg-primary-soft/40")}>
              <Checkbox checked={d.sources.includes(src.id)} onCheckedChange={(v) => s.set({ sources: v ? [...d.sources, src.id] : d.sources.filter((x: string) => x !== src.id) })} className="mt-0.5" />
              <span><span className="block text-sm font-medium">{src.name}</span><span className="text-xs text-muted-foreground">{src.text}</span></span>
            </label>
          ))}
        </div>
      </Field>
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Results per source"><NumberField value={d.max_results_per_source} onChange={(v) => s.set({ max_results_per_source: v })} min={1} max={20} /></Field>
        <Field label="Cache freshness" hint="Reuse identical searches"><NumberField value={d.cache_hours} onChange={(v) => s.set({ cache_hours: v })} min={0} suffix="hours" /></Field>
        <Field label="Timeout"><NumberField value={d.timeout_seconds} onChange={(v) => s.set({ timeout_seconds: v })} min={3} suffix="sec" /></Field>
      </div>
      <Field label="NCBI API key" hint="Optional — raises PubMed's rate limit from 3 to 10 requests/s."><SecretField has={d.has_pubmed_api_key} preview={d.pubmed_api_key_preview} value={s.secrets.pubmed_api_key} onChange={(v) => s.setSecret("pubmed_api_key", v)} /></Field>
    </SettingsCard>
  );
}

export function SecuritySection() {
  const s = useSection("security");
  if (!s.server) return null;
  return (
    <SettingsCard title={<span className="flex items-center gap-2"><Lock className="size-4 text-primary" /> Security</span>} description="Session and access policies." footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} />}>
      <Field label="Idle session timeout" hint="Sessions slide forward while in use." className="max-w-xs"><NumberField value={s.draft.session_timeout_minutes} onChange={(v) => s.set({ session_timeout_minutes: v })} min={5} suffix="minutes" /></Field>
      <SwitchRow label="Viewers may use AI features" description="Viewer accounts are always read-only for records; this controls access to the assistant and tools." checked={s.draft.allow_viewer_ai} onCheckedChange={(v) => s.set({ allow_viewer_ai: v })} />
    </SettingsCard>
  );
}

function UserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ email: "", full_name: "", title: "", specialty: "", role: "clinician", password: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { await api("/api/users", { method: "POST", body: { ...f, title: f.title || null, specialty: f.specialty || null } }); toast.success("User created"); qc.invalidateQueries({ queryKey: ["users"] }); onOpenChange(false); setF({ email: "", full_name: "", title: "", specialty: "", role: "clinician", password: "" }); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(false); }
  };
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Add user" icon={<UserPlus />} footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!f.email || !f.full_name || f.password.length < 8}>Create user</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" required><Input value={f.full_name} onChange={set("full_name")} /></Field>
          <Field label="Email" required><Input type="email" value={f.email} onChange={set("email")} /></Field>
          <Field label="Title"><Input value={f.title} onChange={set("title")} placeholder="e.g. Dr." /></Field>
          <Field label="Specialty"><Input value={f.specialty} onChange={set("specialty")} /></Field>
          <Field label="Role"><Select value={f.role} onValueChange={(v) => setF((x) => ({ ...x, role: v }))} options={[{ value: "clinician", label: "Clinician", description: "Full clinical access" }, { value: "viewer", label: "Viewer", description: "Read-only" }, { value: "front_desk", label: "Front desk", description: "Registration, today's list and report uploads — no clinical content" }, { value: "admin", label: "Administrator", description: "Clinical access + settings, users, audit" }]} /></Field>
          <Field label="Temporary password" required hint="At least 8 characters"><Input type="password" value={f.password} onChange={set("password")} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function UsersSection() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/api/users") });
  const [open, setOpen] = useState(false);
  const [resetFor, setResetFor] = useState<User | null>(null);
  const [pw, setPw] = useState("");
  const patch = async (u: User, body: object, msg: string) => {
    try { await api(`/api/users/${u.id}`, { method: "PATCH", body }); toast.success(msg); qc.invalidateQueries({ queryKey: ["users"] }); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b px-[var(--card-pad)] py-4">
        <div><h3 className="flex items-center gap-2 text-[0.95rem] font-semibold"><Users className="size-4 text-primary" /> Users &amp; roles</h3><p className="text-[0.8rem] text-muted-foreground">Administrators manage settings and users; clinicians work with records; viewers are read-only.</p></div>
        <Button size="sm" onClick={() => setOpen(true)}><UserPlus /> Add user</Button>
      </div>
      {isLoading ? <div className="p-4"><Skeleton className="h-40" /></div> : (
        <Table>
          <THead><TR><TH>User</TH><TH>Role</TH><TH>Status</TH><TH>Last sign-in</TH><TH /></TR></THead>
          <TBody>
            {data?.map((u) => (
              <TR key={u.id}>
                <TD><div className="flex items-center gap-3"><Avatar name={u.full_name} size="sm" /><div><div className="font-medium">{u.full_name}{u.id === me?.id && <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>}</div><div className="text-xs text-muted-foreground">{u.email}{u.specialty ? ` · ${u.specialty}` : ""}</div></div></div></TD>
                <TD className="w-44"><Select size="sm" value={u.role} disabled={u.id === me?.id} onValueChange={(v) => patch(u, { role: v }, "Role updated")} options={[{ value: "admin", label: "Administrator" }, { value: "clinician", label: "Clinician" }, { value: "viewer", label: "Viewer" }, { value: "front_desk", label: "Front desk" }]} /></TD>
                <TD><Badge tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Deactivated"}</Badge></TD>
                <TD className="text-xs text-muted-foreground">{u.last_login_at ? fmtRelative(u.last_login_at) : "Never"}</TD>
                <TD className="text-right">
                  {u.id !== me?.id && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild><Button size="icon-xs" variant="ghost" aria-label="User actions"><MoreHorizontal /></Button></DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem onSelect={() => { setResetFor(u); setPw(""); }}><KeyRound /> Reset password</DropdownMenuItem>
                        <DropdownMenuItem danger={u.is_active} onSelect={() => patch(u, { is_active: !u.is_active }, u.is_active ? "User deactivated — sessions ended" : "User reactivated")}>{u.is_active ? "Deactivate" : "Reactivate"}</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      <UserDialog open={open} onOpenChange={setOpen} />
      <Dialog open={!!resetFor} onOpenChange={(o) => !o && setResetFor(null)}>
        <DialogContent size="sm" title={`Reset password · ${resetFor?.full_name}`} description="All of their sessions will be signed out." footer={<><Button variant="secondary" onClick={() => setResetFor(null)}>Cancel</Button><Button disabled={pw.length < 8} onClick={async () => { try { await api(`/api/users/${resetFor!.id}/reset-password`, { method: "POST", body: { new_password: pw } }); toast.success("Password reset"); setResetFor(null); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } }}>Reset password</Button></>}>
          <Field label="New password" hint="At least 8 characters"><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus /></Field>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function SystemSection() {
  const { data: health, isFetching } = useHealth();
  const qc = useQueryClient();
  const { data: info } = useQuery({ queryKey: ["system-info"], queryFn: () => api<any>("/api/system/info") });
  return (
    <div className="grid gap-[var(--gap)] lg:grid-cols-2">
      <SettingsCard title="Service health" description={`Checked ${fmtDateTime(health?.checked_at)}`} badge={health && <Badge tone={STATUS_TONE[health.status]} className="capitalize">{health.status}</Badge>}
        footer={<Button size="sm" variant="secondary" loading={isFetching} onClick={async () => qc.setQueryData(["health"], await api("/api/system/health", { query: { refresh: true } }))}><RefreshCw /> Re-check now</Button>}>
        <div className="-my-2 divide-y">{health?.components.map((c) => <div key={c.component} className="py-1"><ComponentRow c={c} /><div className="pl-[18px] text-[0.7rem] text-muted-foreground">{c.latency_ms} ms</div></div>) ?? <Skeleton className="h-40" />}</div>
      </SettingsCard>
      <SettingsCard title="About this deployment">
        {info ? (
          <div className="-my-2 divide-y">
            <KeyValue label="Version" value={info.version} />
            <KeyValue label="Language model" value={`${info.llm.model} · ${info.llm.provider}`} />
            <KeyValue label="Embeddings" value={`${info.embeddings.model}${info.embeddings.dimension ? ` · ${info.embeddings.dimension}-d` : ""}`} />
            <KeyValue label="Reranker" value={info.reranker.provider === "none" ? "Off" : info.reranker.model || info.reranker.provider} />
            <KeyValue label="Vector store" value={info.vector_store} />
            <KeyValue label="Research mode" value={info.research_enabled ? "Enabled" : "Local-only"} />
            <KeyValue label="Patients · documents · users" value={`${info.counts.patients} · ${info.counts.documents} · ${info.counts.users}`} />
            <KeyValue label="Python" value={info.python} />
            <KeyValue label="API reference" value={<a href="/api/docs" target="_blank" rel="noreferrer" className="text-primary hover:underline">/api/docs</a>} />
          </div>
        ) : <Skeleton className="h-48" />}
      </SettingsCard>
    </div>
  );
}
