import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { qk } from "@/api/hooks";
import type { User } from "@/api/types";
import { Button, Card, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { MfaEnrol } from "./Mfa";

function Frame({ icon, title, text, children }: { icon: React.ReactNode; title: string; text: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg p-7">
        <div className="mb-5 flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-soft-foreground [&_svg]:size-5">{icon}</span>
          <div><h1 className="text-lg font-semibold tracking-tight">{title}</h1><p className="mt-0.5 text-sm text-muted-foreground">{text}</p></div>
        </div>
        {children}
      </Card>
    </div>
  );
}

/** Shown instead of the app until the person has chosen their own password. */
export function ForcePasswordChange({ me }: { me: User }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (f.next !== f.confirm) return toast.error("The new passwords don't match");
    setBusy(true);
    try {
      await api("/api/auth/me/password", { method: "POST", body: { current_password: f.current, new_password: f.next } });
      qc.setQueryData<User>(qk.me, { ...me, must_change_password: false });
      qc.invalidateQueries();
      toast.success("Password changed");
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <Frame icon={<KeyRound />} title="Choose a new password" text="Your administrator set a temporary password. Choose your own before continuing.">
      <div className="space-y-4">
        <Field label="Temporary password"><Input type="password" value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} autoComplete="current-password" autoFocus /></Field>
        <Field label="New password" hint="At least 12 characters. Avoid common words, your name and simple sequences."><Input type="password" value={f.next} onChange={(e) => setF({ ...f, next: e.target.value })} autoComplete="new-password" /></Field>
        <Field label="Confirm new password"><Input type="password" value={f.confirm} onChange={(e) => setF({ ...f, confirm: e.target.value })} autoComplete="new-password" /></Field>
        <Button className="w-full" onClick={submit} loading={busy} disabled={!f.current || f.next.length < 10}>Save and continue</Button>
      </div>
    </Frame>
  );
}

/** Shown instead of the app until a person whose role requires it has set up two-step verification. */
export function MfaEnrolmentRequired({ me }: { me: User }) {
  const qc = useQueryClient();
  return (
    <Frame icon={<ShieldCheck />} title="Set up two-step verification" text={`${me.role === "admin" ? "Administrator" : "Your"} accounts must use a code from a phone app in addition to a password.`}>
      <MfaEnrol onFinished={() => qc.invalidateQueries()} />
    </Frame>
  );
}
