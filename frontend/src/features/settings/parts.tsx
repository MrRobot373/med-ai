import { CheckCircle2, KeyRound, ListRestart, RefreshCw, Save, Undo2, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Badge, Button, Card, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function SettingsCard({ title, description, children, footer, badge }: { title: ReactNode; description?: ReactNode; children: ReactNode; footer?: ReactNode; badge?: ReactNode }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b px-[var(--card-pad)] py-4">
        <div><h3 className="text-[0.95rem] font-semibold tracking-tight">{title}</h3>{description && <p className="mt-0.5 text-[0.8rem] text-muted-foreground">{description}</p>}</div>
        {badge}
      </div>
      <div className="card-pad space-y-5">{children}</div>
      {footer && <div className="flex flex-wrap items-center justify-end gap-2 border-t bg-subtle px-[var(--card-pad)] py-3">{footer}</div>}
    </Card>
  );
}

export function SaveBar({ dirty, saving, onSave, onReset, extra }: { dirty: boolean; saving: boolean; onSave: () => void; onReset: () => void; extra?: ReactNode }) {
  return (
    <>
      {extra}
      <div className="ml-auto flex items-center gap-2">
        {dirty && <span className="text-xs text-warning-foreground">Unsaved changes</span>}
        <Button variant="ghost" size="sm" disabled={!dirty} onClick={onReset}><Undo2 /> Discard</Button>
        <Button size="sm" disabled={!dirty} loading={saving} onClick={onSave}><Save /> Save changes</Button>
      </div>
    </>
  );
}

export function TestResult({ result }: { result: Record<string, any> | null }) {
  if (!result) return null;
  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm", result.ok ? "border-success/30 bg-success-soft text-success-foreground" : "border-danger/30 bg-danger-soft text-danger-foreground")}>
      {result.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
      <div className="min-w-0">
        <div className="font-medium">{result.ok ? "Connection successful" : "Connection failed"}{result.latency_ms !== undefined && <span className="font-normal opacity-80"> · {result.latency_ms} ms</span>}</div>
        <div className="break-words opacity-90">{result.error ?? result.detail ?? (result.sample ? `Model replied: “${result.sample}”` : null)}</div>
        {result.warning && <div className="mt-1 font-medium text-warning-foreground">{result.warning}</div>}
      </div>
    </div>
  );
}

export function SecretField({ has, preview, value, onChange, placeholder = "Paste API key" }: { has: boolean; preview?: string | null; value: string | null | undefined; onChange: (v: string | null | undefined) => void; placeholder?: string }) {
  const replacing = value !== undefined;
  if (has && !replacing) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex h-9 flex-1 items-center gap-2 rounded-md border bg-muted/50 px-3 text-sm"><KeyRound className="size-4 text-muted-foreground" /><span className="font-mono text-xs">{preview}</span><Badge tone="success" className="ml-auto">Stored encrypted</Badge></div>
        <Button size="sm" variant="secondary" onClick={() => onChange("")}>Replace</Button>
        <Button size="sm" variant="danger-ghost" onClick={() => onChange(null)}>Remove</Button>
      </div>
    );
  }
  if (value === null) {
    return <div className="flex items-center gap-2 text-sm text-danger-foreground">Key will be removed on save. <Button size="xs" variant="ghost" onClick={() => onChange(undefined)}>Undo</Button></div>;
  }
  return (
    <div className="flex items-center gap-2">
      <Input type="password" autoComplete="off" value={value ?? ""} onChange={(e) => onChange(e.target.value || (has ? "" : undefined))} placeholder={has ? "Enter new key" : placeholder} className="flex-1" />
      {replacing && has && <Button size="sm" variant="ghost" onClick={() => onChange(undefined)}>Cancel</Button>}
    </div>
  );
}

export function ModelInput({ value, onChange, fetchBody, placeholder }: { value: string; onChange: (v: string) => void; fetchBody: Record<string, any>; placeholder?: string }) {
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = `models-${fetchBody.section}`;
  const fetchModels = async () => {
    setBusy(true); setError(null);
    const r = await api<{ ok: boolean; models: string[]; error?: string }>("/api/settings/models", { method: "POST", body: fetchBody }).catch((e) => ({ ok: false, models: [], error: e.message }));
    setModels(r.models); if (!r.ok) setError(r.error ?? "Failed"); else if (!r.models.length) setError("The endpoint returned no models.");
    setBusy(false);
  };
  return (
    <div className="space-y-1.5">
      <div className="flex gap-2">
        <Input list={id} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="flex-1 font-mono text-[0.82rem]" />
        <datalist id={id}>{models.map((m) => <option key={m} value={m} />)}</datalist>
        <Button size="sm" variant="secondary" onClick={fetchModels} loading={busy} className="h-9"><RefreshCw /> Fetch models</Button>
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : models.length > 0 && (
        <div className="flex flex-wrap gap-1">{models.slice(0, 24).map((m) => <button key={m} type="button" onClick={() => onChange(m)} className={cn("rounded-md border px-2 py-0.5 font-mono text-[0.7rem] transition-colors hover:border-primary/50", m === value ? "border-primary bg-primary-soft text-primary-soft-foreground" : "bg-card text-muted-foreground")}>{m}</button>)}</div>
      )}
    </div>
  );
}

export function PresetPicker<T extends { id: string; name: string; hint?: string }>({ presets, active, onPick }: { presets: T[]; active?: string; onPick: (p: T) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {presets.map((p) => (
        <button key={p.id} type="button" onClick={() => onPick(p)} title={p.hint} className={cn("rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all hover:border-primary/50", active === p.id ? "border-primary bg-primary-soft text-primary-soft-foreground" : "bg-card text-muted-foreground hover:text-foreground")}>
          {p.name}
        </button>
      ))}
    </div>
  );
}

export function NumberField({ value, onChange, min, max, step = 1, suffix }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; suffix?: string }) {
  return <Input type="number" value={Number.isFinite(value) ? value : ""} min={min} max={max} step={step} onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))} suffix={suffix && <span className="pr-1 text-xs text-muted-foreground">{suffix}</span>} />;
}

export function ResetHint() {
  return <ListRestart className="size-4" />;
}
