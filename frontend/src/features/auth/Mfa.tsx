import { useQueryClient } from "@tanstack/react-query";
import { Copy, Download, ShieldCheck, ShieldOff, Smartphone } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { qk } from "@/api/hooks";
import type { User } from "@/api/types";
import { Badge, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

/** Recovery codes are shown once, with a way to keep them. */
export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const text = codes.join("\n");
  const download = () => {
    const url = URL.createObjectURL(new Blob([`Recovery codes — each works once.\n\n${text}\n`], { type: "text/plain" }));
    Object.assign(document.createElement("a"), { href: url, download: "recovery-codes.txt" }).click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-warning-foreground">
        <b>Save these recovery codes now.</b> Each works once if you lose your phone. They are not shown again.
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg border bg-subtle p-3 font-mono text-sm tracking-wider" aria-label="Recovery codes">
        {codes.map((c) => <span key={c}>{c}</span>)}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={() => { navigator.clipboard?.writeText(text); toast.success("Copied"); }}><Copy /> Copy</Button>
        <Button size="sm" variant="secondary" onClick={download}><Download /> Download</Button>
        <Button size="sm" className="ml-auto" onClick={onDone}>I have saved them</Button>
      </div>
    </div>
  );
}

/** Enrolment: scan the code → type the 6 digits → keep the recovery codes. */
export function MfaEnrol({ onFinished }: { onFinished: () => void }) {
  const qc = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [qr, setQr] = useState<string>("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);

  useEffect(() => {
    api<{ secret: string; otpauth_uri: string }>("/api/auth/mfa/setup", { method: "POST" })
      .then(async (s) => { setSetup(s); setQr(await QRCode.toDataURL(s.otpauth_uri, { margin: 1, width: 192 })); })
      .catch((e) => toast.error(e instanceof ApiError ? e.message : "Could not start setup"));
  }, []);

  const enable = async () => {
    setBusy(true);
    try {
      const r = await api<{ recovery_codes: string[] }>("/api/auth/mfa/enable", { method: "POST", body: { code } });
      setCodes(r.recovery_codes);
      qc.setQueryData<User>(qk.me, (u) => (u ? { ...u, mfa_enabled: true } : u));
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
    finally { setBusy(false); }
  };

  if (codes) return <RecoveryCodes codes={codes} onDone={onFinished} />;
  return (
    <div className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>Install an authenticator app (Google Authenticator, Microsoft Authenticator, Authy, 1Password…).</li>
        <li>Scan this code, or type the key in by hand.</li>
        <li>Enter the 6-digit code the app shows.</li>
      </ol>
      <div className="flex flex-wrap items-center gap-5">
        <div className="flex size-[192px] items-center justify-center rounded-xl border bg-white">
          {qr ? <img src={qr} alt="Authenticator QR code" className="size-[184px]" /> : <Smartphone className="size-8 text-muted-foreground" />}
        </div>
        <div className="min-w-0 space-y-3">
          <Field label="Key (if you cannot scan)"><code className="block break-all rounded-md border bg-subtle px-2.5 py-1.5 font-mono text-xs" data-testid="mfa-secret">{setup?.secret ?? "…"}</code></Field>
          <Field label="6-digit code" htmlFor="mfa-code">
            <Input id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\s/g, ""))} placeholder="123456" className="w-40 font-mono tracking-widest" />
          </Field>
          <Button onClick={enable} loading={busy} disabled={code.length < 6 || !setup}>Turn on two-step verification</Button>
        </div>
      </div>
    </div>
  );
}

/** Profile card: status, enrol, turn off. */
export function MfaCard({ me }: { me: User }) {
  const qc = useQueryClient();
  const [enrolling, setEnrolling] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const [f, setF] = useState({ password: "", code: "" });
  const [busy, setBusy] = useState(false);

  const disable = async () => {
    setBusy(true);
    try {
      await api("/api/auth/mfa/disable", { method: "POST", body: f });
      qc.setQueryData<User>(qk.me, { ...me, mfa_enabled: false });
      setDisabling(false); setF({ password: "", code: "" });
      toast.success("Two-step verification is off");
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`flex size-9 items-center justify-center rounded-full ${me.mfa_enabled ? "bg-success-soft text-success-foreground" : "bg-muted text-muted-foreground"}`}>{me.mfa_enabled ? <ShieldCheck className="size-[18px]" /> : <ShieldOff className="size-[18px]" />}</span>
          <div>
            <div className="text-sm font-medium">Two-step verification {me.mfa_enabled ? <Badge tone="success" className="ml-1">On</Badge> : <Badge tone={me.mfa_required ? "danger" : "neutral"} className="ml-1">{me.mfa_required ? "Required" : "Off"}</Badge>}</div>
            <p className="text-xs text-muted-foreground">A code from your phone in addition to your password. Strongly recommended for anyone who can see patient records.</p>
          </div>
        </div>
        {!me.mfa_enabled && !enrolling && <Button size="sm" onClick={() => setEnrolling(true)}>Set up</Button>}
        {me.mfa_enabled && !me.mfa_required && !disabling && <Button size="sm" variant="secondary" onClick={() => setDisabling(true)}>Turn off</Button>}
      </div>
      {enrolling && !me.mfa_enabled && <MfaEnrol onFinished={() => setEnrolling(false)} />}
      {disabling && (
        <div className="grid gap-3 rounded-lg border bg-subtle p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label="Password"><Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="current-password" /></Field>
          <Field label="Code or recovery code"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} className="font-mono" /></Field>
          <div className="flex gap-2"><Button variant="ghost" size="sm" onClick={() => setDisabling(false)}>Cancel</Button><Button variant="danger" size="sm" loading={busy} disabled={!f.password || f.code.length < 4} onClick={disable}>Turn off</Button></div>
        </div>
      )}
    </div>
  );
}
