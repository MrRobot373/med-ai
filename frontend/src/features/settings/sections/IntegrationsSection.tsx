import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, KeyRound, Plug, Plus, RefreshCw, Send, Trash2, Webhook } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Dialog, DialogContent, Field, Input, Segmented, Skeleton, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime, fmtRelative } from "@/lib/utils";
import { SettingsCard } from "../parts";

interface Catalog { scopes: Record<string, string>; events: Record<string, string> }
interface Token { id: string; name: string; prefix: string; scopes: string[]; created_at: string; expires_at: string | null; last_used_at: string | null; last_used_ip: string | null; revoked: boolean }
interface Hook { id: string; name: string; url: string; events: string[]; payload: "minimal" | "full"; active: boolean; last_status: string | null; last_delivery_at: string | null; pending: number; failed: number; delivered: number }
interface Delivery { id: string; event: string; status: string; attempts: number; response_code: number | null; error: string | null; created_at: string; delivered_at: string | null; next_attempt_at: string | null }

const copy = (t: string) => { void navigator.clipboard?.writeText(t); toast.success("Copied"); };

function Reveal({ title, value, hint, onClose }: { title: string; value: string; hint: string; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="md" title={title} description={hint} footer={<Button onClick={onClose}>I have stored it safely</Button>}>
        <div className="flex gap-2"><Input readOnly value={value} className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} /><Button size="icon-sm" variant="secondary" aria-label="Copy" onClick={() => copy(value)}><Copy /></Button></div>
        <p className="mt-3 text-xs text-danger">This is the only time it is shown. If it is lost, make a new one.</p>
      </DialogContent>
    </Dialog>
  );
}

export function IntegrationsSection() {
  const qc = useQueryClient();
  const { data: cat } = useQuery({ queryKey: ["int-catalog"], queryFn: () => api<Catalog>("/api/integrations/catalog") });
  const { data: tokens } = useQuery({ queryKey: ["int-tokens"], queryFn: () => api<Token[]>("/api/integrations/tokens") });
  const { data: hooks } = useQuery({ queryKey: ["int-hooks"], queryFn: () => api<Hook[]>("/api/integrations/webhooks"), refetchInterval: 15000 });
  const [reveal, setReveal] = useState<{ title: string; value: string; hint: string } | null>(null);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [hookOpen, setHookOpen] = useState(false);
  const [log, setLog] = useState<Hook | null>(null);
  const [range, setRange] = useState({ start: new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10), end: new Date().toISOString().slice(0, 10) });
  if (!cat || !tokens || !hooks) return <Skeleton className="h-64" />;
  const refresh = () => { qc.invalidateQueries({ queryKey: ["int-tokens"] }); qc.invalidateQueries({ queryKey: ["int-hooks"] }); };

  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard title={<span className="flex items-center gap-2"><Plug className="size-4 text-primary" /> Connecting billing and pharmacy systems</span>}
        description="Billing and dispensing stay in the software that is built for them. This system hands them what they need — and nothing more — in a controlled way.">
        <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
          <li><b>Pharmacy</b>: scan the QR code on a prescription, or read issued prescriptions with an API key; the pharmacy marks it dispensed.</li>
          <li><b>Billing</b>: read completed visits and the services given, or download them as a spreadsheet below. Prices stay in your billing software.</li>
          <li>Keys can only <i>read</i> what you tick, can expire, and can be switched off at any time. Every use is recorded.</li>
        </ul>
      </SettingsCard>

      <SettingsCard title={<span className="flex items-center gap-2"><KeyRound className="size-4 text-primary" /> API keys</span>} footer={<Button size="sm" onClick={() => setTokenOpen(true)}><Plus /> New key</Button>}>
        {tokens.length === 0 ? <p className="text-sm text-muted-foreground">No keys yet.</p> : (
          <Table>
            <THead><TR><TH>Name</TH><TH>Can</TH><TH>Last used</TH><TH /></TR></THead>
            <TBody>
              {tokens.map((t) => (
                <TR key={t.id}>
                  <TD><div className="font-medium">{t.name}</div><div className="font-mono text-xs text-muted-foreground">{t.prefix}…</div></TD>
                  <TD><div className="flex flex-wrap gap-1">{t.scopes.map((s) => <Badge key={s} tone="neutral">{s}</Badge>)}</div></TD>
                  <TD className="text-xs text-muted-foreground">{t.last_used_at ? `${fmtRelative(t.last_used_at)}${t.last_used_ip ? ` · ${t.last_used_ip}` : ""}` : "Never"}{t.expires_at && <div>expires {fmtDateTime(t.expires_at)}</div>}</TD>
                  <TD className="text-right">{t.revoked ? <Badge tone="neutral">Revoked</Badge> : <Button size="xs" variant="ghost" onClick={async () => { await api(`/api/integrations/tokens/${t.id}`, { method: "DELETE" }); toast.success("Key revoked"); refresh(); }}><Trash2 /> Revoke</Button>}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        <details className="rounded-lg border bg-muted/30 p-3 text-xs"><summary className="cursor-pointer font-semibold">How a partner uses a key</summary>
          <pre className="mt-2 overflow-auto font-mono">{`curl -H "Authorization: Bearer gms_…" \\
  "https://<this server>/api/integration/v1/prescriptions?since=2026-11-01T00:00:00Z"
curl -X POST -H "Authorization: Bearer gms_…" -H "Content-Type: application/json" \\
  -d '{"dispensed_by":"City Pharmacy"}' \\
  "https://<this server>/api/integration/v1/prescriptions/<id>/dispensed"`}</pre>
        </details>
      </SettingsCard>

      <SettingsCard title={<span className="flex items-center gap-2"><Webhook className="size-4 text-primary" /> Webhooks</span>} description="This system tells a partner the moment something happens. Messages are signed, and retried for about two days if the partner is down." footer={<Button size="sm" onClick={() => setHookOpen(true)}><Plus /> New webhook</Button>}>
        {hooks.length === 0 ? <p className="text-sm text-muted-foreground">No webhooks yet.</p> : hooks.map((h) => (
          <div key={h.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
            <div className="min-w-0"><div className="flex items-center gap-2 font-medium">{h.name} {!h.active && <Badge tone="neutral">Off</Badge>}{h.failed > 0 && <Badge tone="danger">{h.failed} failed</Badge>}{h.pending > 0 && <Badge tone="warning">{h.pending} waiting</Badge>}</div>
              <div className="truncate font-mono text-xs text-muted-foreground">{h.url}</div>
              <div className="mt-1 flex flex-wrap gap-1">{h.events.map((e) => <Badge key={e} tone="neutral">{e}</Badge>)}<Badge tone="outline">{h.payload === "full" ? "includes details" : "IDs only"}</Badge></div>
              {h.last_status && <div className="mt-1 text-xs text-muted-foreground">Last: {h.last_status}{h.last_delivery_at ? ` · ${fmtRelative(h.last_delivery_at)}` : ""}</div>}</div>
            <div className="flex flex-wrap gap-1">
              <Button size="xs" variant="secondary" onClick={async () => { try { const r = await api<{ status: string; response_code: number | null; error: string | null }>(`/api/integrations/webhooks/${h.id}/test`, { method: "POST" }); r.status === "delivered" ? toast.success(`The receiver answered ${r.response_code}`) : toast.error(r.error ?? "No answer"); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } refresh(); }}><Send /> Test</Button>
              <Button size="xs" variant="ghost" onClick={() => setLog(h)}>Log</Button>
              <Button size="xs" variant="ghost" onClick={async () => { await api(`/api/integrations/webhooks/${h.id}`, { method: "PATCH", body: { active: !h.active } }); refresh(); }}>{h.active ? "Turn off" : "Turn on"}</Button>
              <Button size="xs" variant="ghost" title="New signing secret" onClick={async () => { const r = await api<{ secret: string }>(`/api/integrations/webhooks/${h.id}/rotate-secret`, { method: "POST" }); setReveal({ title: "New signing secret", value: r.secret, hint: "Give it to the partner. The old one stops working now." }); }}><RefreshCw /></Button>
              <Button size="xs" variant="ghost" aria-label="Delete" onClick={async () => { await api(`/api/integrations/webhooks/${h.id}`, { method: "DELETE" }); refresh(); }}><Trash2 /></Button>
            </div>
          </div>
        ))}
      </SettingsCard>

      <SettingsCard title={<span className="flex items-center gap-2"><Download className="size-4 text-primary" /> Download for billing staff</span>} description="Spreadsheets (open directly in Excel) of completed visits and issued prescriptions for a period.">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="From"><Input type="date" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} /></Field>
          <Field label="To"><Input type="date" value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} /></Field>
          <div className="flex items-end gap-2 sm:col-span-2">
            <Button variant="secondary" asChild><a href={`/api/exports/visits.csv?start=${range.start}&end=${range.end}`}><Download /> Visits</a></Button>
            <Button variant="secondary" asChild><a href={`/api/exports/prescriptions.csv?start=${range.start}&end=${range.end}`}><Download /> Prescriptions</a></Button>
          </div>
        </div>
      </SettingsCard>

      {tokenOpen && <TokenDialog cat={cat} onClose={() => setTokenOpen(false)} onCreated={(t) => { setTokenOpen(false); setReveal({ title: `Key for ${t.name}`, value: t.token, hint: "Give this to the partner's technician. Treat it like a password." }); refresh(); }} />}
      {hookOpen && <HookDialog cat={cat} onClose={() => setHookOpen(false)} onCreated={(h) => { setHookOpen(false); setReveal({ title: `Signing secret for ${h.name}`, value: h.secret, hint: "The partner uses this to check that messages really come from this clinic." }); refresh(); }} />}
      {reveal && <Reveal {...reveal} onClose={() => setReveal(null)} />}
      {log && <LogDialog hook={log} onClose={() => setLog(null)} />}
    </div>
  );
}

function TokenDialog({ cat, onClose, onCreated }: { cat: Catalog; onClose: () => void; onCreated: (t: { name: string; token: string }) => void }) {
  const [name, setName] = useState(""); const [scopes, setScopes] = useState<string[]>([]); const [days, setDays] = useState("365"); const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { onCreated(await api("/api/integrations/tokens", { method: "POST", body: { name, scopes, expires_in_days: days ? Number(days) : null } })); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(false); } };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title="New API key" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} disabled={name.trim().length < 2 || scopes.length === 0} onClick={save}>Create key</Button></>}>
        <div className="space-y-4">
          <Field label="Who is it for?"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. City Pharmacy" autoFocus /></Field>
          <Field label="What may it do?"><div className="space-y-1">{Object.entries(cat.scopes).map(([k, v]) => <label key={k} className="flex items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"><input type="checkbox" className="mt-1" checked={scopes.includes(k)} onChange={(e) => setScopes((s) => e.target.checked ? [...s, k] : s.filter((x) => x !== k))} /><span><span className="font-mono text-xs">{k}</span><span className="block text-muted-foreground">{v}</span></span></label>)}</div></Field>
          <Field label="Valid for (days)" hint="Leave empty for no expiry"><Input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function HookDialog({ cat, onClose, onCreated }: { cat: Catalog; onClose: () => void; onCreated: (h: { name: string; secret: string }) => void }) {
  const [f, setF] = useState({ name: "", url: "", payload: "minimal" }); const [events, setEvents] = useState<string[]>([]); const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { onCreated(await api("/api/integrations/webhooks", { method: "POST", body: { ...f, events } })); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(false); } };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title="New webhook" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} disabled={f.name.trim().length < 2 || !f.url || events.length === 0} onClick={save}>Create webhook</Button></>}>
        <div className="space-y-4">
          <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Billing software" autoFocus /></Field>
          <Field label="Address to send to" hint="A server on the clinic's network, e.g. http://192.168.1.20:9000/gms"><Input value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} /></Field>
          <Field label="Tell it when…"><div className="space-y-1">{Object.entries(cat.events).map(([k, v]) => <label key={k} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"><input type="checkbox" checked={events.includes(k)} onChange={(e) => setEvents((s) => e.target.checked ? [...s, k] : s.filter((x) => x !== k))} /><span><span className="font-mono text-xs">{k}</span> <span className="text-muted-foreground">— {v}</span></span></label>)}</div></Field>
          <Field label="What is sent" hint="“IDs only” is safest: the partner then fetches details with an API key."><Segmented value={f.payload} onChange={(v) => setF({ ...f, payload: v })} options={[{ value: "minimal", label: "IDs only" }, { value: "full", label: "Include details" }]} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LogDialog({ hook, onClose }: { hook: Hook; onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["int-log", hook.id], queryFn: () => api<Delivery[]>(`/api/integrations/webhooks/${hook.id}/deliveries`), refetchInterval: 10000 });
  const tone = { delivered: "success", pending: "warning", failed: "danger" } as const;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg" title={`Messages to ${hook.name}`} description="The most recent messages and what the receiver answered.">
        {!data ? <Skeleton className="h-32" /> : data.length === 0 ? <p className="text-sm text-muted-foreground">Nothing sent yet.</p> : (
          <div className="max-h-96 divide-y overflow-auto rounded-lg border text-sm">
            {data.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div><span className="font-mono text-xs">{d.event}</span> <span className="text-xs text-muted-foreground">{fmtRelative(d.created_at)} · {d.attempts} attempt{d.attempts === 1 ? "" : "s"}{d.response_code ? ` · ${d.response_code}` : ""}</span>{d.error && <div className="text-xs text-danger">{d.error}</div>}{d.next_attempt_at && <div className="text-xs text-muted-foreground">next try {fmtRelative(d.next_attempt_at)}</div>}</div>
                <div className="flex items-center gap-2"><Badge tone={tone[d.status as keyof typeof tone] ?? "neutral"}>{d.status}</Badge>{d.status !== "delivered" && <Button size="xs" variant="ghost" onClick={async () => { await api(`/api/integrations/deliveries/${d.id}/retry`, { method: "POST" }); qc.invalidateQueries({ queryKey: ["int-log", hook.id] }); }}>Retry</Button>}</div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
