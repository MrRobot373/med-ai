import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, MonitorSmartphone, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { qk, useMe } from "@/api/hooks";
import type { User } from "@/api/types";
import { Avatar, Badge, Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtRelative } from "@/lib/utils";
import { SettingsCard } from "../parts";

export function ProfileSection() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [f, setF] = useState({ full_name: "", title: "", specialty: "" });
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: () => api<any[]>("/api/auth/sessions") });
  useEffect(() => { if (me) setF({ full_name: me.full_name, title: me.title ?? "", specialty: me.specialty ?? "" }); }, [me]);
  if (!me) return null;

  const saveProfile = async () => {
    setBusy("p");
    try { qc.setQueryData(qk.me, await api<User>("/api/auth/me", { method: "PATCH", body: { full_name: f.full_name, title: f.title || null, specialty: f.specialty || null } })); toast.success("Profile updated"); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setBusy(null); }
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
      <SettingsCard title={<span className="flex items-center gap-2"><KeyRound className="size-4 text-primary" /> Password</span>} footer={<Button size="sm" onClick={changePw} loading={busy === "pw"} disabled={!pw.current || pw.next.length < 8}>Change password</Button>}>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Current password"><Input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} autoComplete="current-password" /></Field>
          <Field label="New password" hint="At least 8 characters"><Input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} autoComplete="new-password" /></Field>
          <Field label="Confirm new password"><Input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} autoComplete="new-password" /></Field>
        </div>
      </SettingsCard>
      <SettingsCard title={<span className="flex items-center gap-2"><MonitorSmartphone className="size-4 text-primary" /> Active sessions</span>}>
        <div className="-my-2 divide-y">
          {sessions?.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
              <div className="min-w-0"><div className="truncate">{s.user_agent || "Unknown device"}</div><div className="text-xs text-muted-foreground">{s.ip ?? "—"} · signed in {fmtRelative(s.created_at)}</div></div>
              <span className="shrink-0 text-xs text-muted-foreground">active {fmtRelative(s.last_seen_at)}</span>
            </div>
          ))}
        </div>
      </SettingsCard>
    </div>
  );
}
