import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, KeyRound, LogOut, MonitorSmartphone, PenLine, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { qk, useMe } from "@/api/hooks";
import type { User } from "@/api/types";
import { Avatar, Badge, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtRelative } from "@/lib/utils";
import { MfaCard } from "@/features/auth/Mfa";
import { SettingsCard } from "../parts";

export function ProfileSection() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [f, setF] = useState({ full_name: "", title: "", specialty: "", phone: "", qualifications: "", registration_no: "", registration_council: "" });
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: () => api<any[]>("/api/auth/sessions") });
  useEffect(() => { if (me) setF({ full_name: me.full_name, title: me.title ?? "", specialty: me.specialty ?? "", phone: me.phone ?? "", qualifications: me.qualifications ?? "", registration_no: me.registration_no ?? "", registration_council: me.registration_council ?? "" }); }, [me]);
  if (!me) return null;

  const saveProfile = async () => {
    setBusy("p");
    try { qc.setQueryData(qk.me, await api<User>("/api/auth/me", { method: "PATCH", body: { full_name: f.full_name, title: f.title || null, specialty: f.specialty || null, phone: f.phone || null, qualifications: f.qualifications || null, registration_no: f.registration_no || null, registration_council: f.registration_council || null } })); toast.success("Profile updated"); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(null); }
  };
  const { data: sig } = useQuery({ queryKey: ["signature"], queryFn: () => api<{ data_url: string | null }>("/api/auth/me/signature"), enabled: me?.role !== "viewer" });
  const saveSignature = async (dataUrl: string | null) => {
    try { await api("/api/auth/me/signature", { method: "PUT", body: { data_url: dataUrl } }); toast.success(dataUrl ? "Signature saved" : "Signature removed"); qc.invalidateQueries({ queryKey: ["signature"] }); qc.invalidateQueries({ queryKey: qk.me }); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };
  const pickSignature = async (file: File) => {
    const img = await createImageBitmap(file);
    const scale = Math.min(600 / img.width, 220 / img.height, 1);
    const c = Object.assign(document.createElement("canvas"), { width: Math.round(img.width * scale), height: Math.round(img.height * scale) });
    c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
    await saveSignature(c.toDataURL("image/png"));
  };
  const changePw = async () => {
    if (pw.next !== pw.confirm) return toast.error("New passwords don't match");
    setBusy("pw");
    try { await api("/api/auth/me/password", { method: "POST", body: { current_password: pw.current, new_password: pw.next } }); toast.success("Password changed"); setPw({ current: "", next: "", confirm: "" }); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(null); }
  };

  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard title={<span className="flex items-center gap-2"><UserRound className="size-4 text-primary" /> Profile</span>} footer={<Button size="sm" onClick={saveProfile} loading={busy === "p"}>Save profile</Button>}>
        <div className="flex items-center gap-4"><Avatar name={me.full_name} size="xl" /><div><div className="font-semibold">{me.full_name}</div><div className="text-sm text-muted-foreground">{me.email}</div><Badge tone="primary" className="mt-1 capitalize">{me.role}</Badge></div></div>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Title"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Dr." /></Field>
          <Field label="Full name" className="md:col-span-2"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="Specialty" className="md:col-span-3"><Input value={f.specialty} onChange={(e) => setF({ ...f, specialty: e.target.value })} placeholder="e.g. Internal Medicine" /></Field>
        </div>
      </SettingsCard>
      {me.role !== "viewer" && me.role !== "front_desk" && (
        <SettingsCard title={<span className="flex items-center gap-2"><BadgeCheck className="size-4 text-primary" /> Professional details</span>} description="Printed under your name on prescriptions and letters." footer={<Button size="sm" onClick={saveProfile} loading={busy === "p"}>Save details</Button>}>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Medical registration number" hint={!me.registration_no ? "Required to finalise prescriptions in production" : undefined}><Input value={f.registration_no} onChange={(e) => setF({ ...f, registration_no: e.target.value })} placeholder="e.g. MH-45821" /></Field>
            <Field label="Registering council"><Input value={f.registration_council} onChange={(e) => setF({ ...f, registration_council: e.target.value })} placeholder="e.g. Maharashtra Medical Council" /></Field>
            <Field label="Qualifications"><Input value={f.qualifications} onChange={(e) => setF({ ...f, qualifications: e.target.value })} placeholder="e.g. MBBS, MD (Medicine)" /></Field>
            <Field label="Phone"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          </div>
          <div className="flex items-center gap-4 border-t pt-4">
            <div className="flex h-16 w-40 items-center justify-center rounded-lg border bg-white">{sig?.data_url ? <img src={sig.data_url} alt="Your signature" className="max-h-14 max-w-36 object-contain" /> : <span className="text-xs text-muted-foreground">No signature</span>}</div>
            <div className="space-y-1.5">
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" asChild><label className="cursor-pointer"><PenLine /> {sig?.data_url ? "Replace" : "Upload"} signature<input type="file" accept="image/png,image/jpeg" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) void pickSignature(file); e.target.value = ""; }} /></label></Button>
                {sig?.data_url && <Button size="sm" variant="ghost" onClick={() => saveSignature(null)}><Trash2 /> Remove</Button>}
              </div>
              <p className="text-xs text-muted-foreground">A photo of your signature on white paper. Printed above the signature line.</p>
            </div>
          </div>
        </SettingsCard>
      )}
      <SettingsCard title={<span className="flex items-center gap-2"><KeyRound className="size-4 text-primary" /> Password</span>} footer={<Button size="sm" onClick={changePw} loading={busy === "pw"} disabled={!pw.current || pw.next.length < 10}>Change password</Button>}>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Current password"><Input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} autoComplete="current-password" /></Field>
          <Field label="New password" hint="At least 12 characters; not a common password, your name or a simple sequence"><Input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} autoComplete="new-password" /></Field>
          <Field label="Confirm new password"><Input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} autoComplete="new-password" /></Field>
        </div>
      </SettingsCard>
      <SettingsCard title={<span className="flex items-center gap-2"><ShieldCheck className="size-4 text-primary" /> Two-step verification</span>}>
        <MfaCard me={me} />
      </SettingsCard>
      <SettingsCard title={<span className="flex items-center gap-2"><MonitorSmartphone className="size-4 text-primary" /> Where you are signed in</span>}
        footer={sessions && sessions.length > 1 ? <Button size="sm" variant="secondary" onClick={async () => { const r = await api<{ revoked: number }>("/api/auth/sessions/revoke-others", { method: "POST" }); toast.success(`Signed out ${r.revoked} other device${r.revoked === 1 ? "" : "s"}`); qc.invalidateQueries({ queryKey: ["sessions"] }); }}><LogOut /> Sign out all other devices</Button> : undefined}>
        <div className="-my-2 divide-y">
          {sessions?.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
              <div className="min-w-0"><div className="truncate">{s.user_agent || "Unknown device"} {s.current && <Badge tone="success" className="ml-1.5">This device</Badge>}</div><div className="text-xs text-muted-foreground">{s.ip ?? "—"} · signed in {fmtRelative(s.created_at)} · active {fmtRelative(s.last_seen_at)}</div></div>
              {!s.current && <Button size="xs" variant="ghost" onClick={async () => { await api(`/api/auth/sessions/${s.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["sessions"] }); }}>Sign out</Button>}
            </div>
          ))}
        </div>
      </SettingsCard>
    </div>
  );
}
