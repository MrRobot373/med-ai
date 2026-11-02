import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardCheck, FlaskConical, PenLine, ShieldAlert, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useMe } from "@/api/hooks";
import { Badge, Button, Dialog, DialogContent, Field, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime } from "@/lib/utils";
import { SettingsCard } from "../parts";

interface Signoff { id: string; role: string; role_label: string; name: string; registration_no: string; registration_council: string | null; statement: string; signed_at: string; tests: string; current: boolean; revoked: boolean; revoked_reason: string | null }
interface Area { key: string; label: string; what: string; roles: { role: string; label: string }[]; content_hash: string; status: "signed" | "partial" | "changed" | "unsigned"; missing: { role: string; label: string }[]; signoffs: Signoff[] }
interface Overview { areas: Area[]; overall: string; selftest: { at: string; passed: number; total: number } | null }
interface Case { id: string; title: string; why: string; ok: boolean; problems: string[] }
interface SelfTest { total: number; passed: number; failed: number; ok: boolean; cases: Case[] }
interface Evaluation { at: string; models: Record<string, string | null>; ok: boolean; suites: { suite: string; status: string; pass?: boolean; target?: string; reason?: string; recall?: number; precision?: number; recall_at_5?: number; rate?: number; with_citations?: number; no_invented_citations?: number; values_found?: number; values_expected?: number }[] }

const STATE: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  signed: { label: "Approved for this version", tone: "success" }, partial: { label: "Waiting for another approval", tone: "warning" },
  changed: { label: "Changed since it was reviewed", tone: "danger" }, unsigned: { label: "Not reviewed", tone: "danger" },
};

export function ClinicalContentSection() {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { data } = useQuery({ queryKey: ["clinical-content"], queryFn: () => api<Overview>("/api/clinical-content") });
  const { data: evaluation } = useQuery({ queryKey: ["clinical-eval"], queryFn: () => api<Evaluation | null>("/api/clinical-content/evaluation") });
  const [test, setTest] = useState<SelfTest | null>(null);
  const [running, setRunning] = useState(false);
  const [signing, setSigning] = useState<Area | null>(null);
  if (!data) return <Skeleton className="h-64" />;
  const refresh = () => qc.invalidateQueries({ queryKey: ["clinical-content"] });
  const runTest = async () => {
    setRunning(true);
    try { setTest(await api<SelfTest>("/api/clinical-content/selftest", { method: "POST" })); refresh(); } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); } finally { setRunning(false); }
  };
  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard title={<span className="flex items-center gap-2"><ClipboardCheck className="size-4 text-primary" /> Clinical review</span>}
        description="The prescription safety rules, drug data, calculators and reference library are medical content. A named doctor and a pharmacist read them and sign. A signature applies only to the exact version they reviewed — when anything changes, it asks to be reviewed again."
        badge={<Badge tone={data.overall === "signed" ? "success" : "warning"}>{data.overall === "signed" ? "All approved" : "Review incomplete"}</Badge>}>
        {!me?.registration_no && <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning-soft/50 px-3 py-2 text-sm"><ShieldAlert className="mt-0.5 size-4 shrink-0" /> To sign, add your professional registration number in Settings → Profile.</div>}
      </SettingsCard>

      {data.areas.map((a) => {
        const s = STATE[a.status];
        return (
          <SettingsCard key={a.key} title={a.label} description={a.what} badge={<Badge tone={s.tone}>{s.label}</Badge>}
            footer={a.missing.length > 0 && me && me.role !== "front_desk" ? <Button size="sm" onClick={() => setSigning(a)}><PenLine /> Review and sign…</Button> : undefined}>
            <div className="flex flex-wrap gap-2 text-sm">
              {a.roles.map((r) => {
                const done = a.signoffs.find((x) => x.role === r.role && x.current && !x.revoked);
                return <span key={r.role} className="flex items-center gap-1.5 rounded-full border px-2.5 py-1">{done ? <CheckCircle2 className="size-4 text-success" /> : <XCircle className="size-4 text-muted-foreground" />}{r.label}{done && <span className="text-xs text-muted-foreground">— {done.name}, reg. {done.registration_no}, {fmtDateTime(done.signed_at)}{done.tests !== "0/0" ? ` · tests ${done.tests}` : ""}</span>}</span>;
              })}
            </div>
            <div className="text-xs text-muted-foreground">Version fingerprint <span className="font-mono">{a.content_hash.slice(0, 12)}</span></div>
            {a.signoffs.some((x) => !x.current) && (
              <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">Earlier approvals</summary>
                <ul className="mt-1 space-y-0.5">{a.signoffs.filter((x) => !x.current).map((x) => <li key={x.id}>{x.role_label}: {x.name} ({fmtDateTime(x.signed_at)}) — {x.revoked ? `withdrawn: ${x.revoked_reason}` : "an earlier version"}</li>)}</ul></details>
            )}
          </SettingsCard>
        );
      })}

      <SettingsCard title={<span className="flex items-center gap-2"><FlaskConical className="size-4 text-primary" /> Clinical tests</span>}
        description="Known patients and prescriptions with the alerts a pharmacist expects, including cases that must stay quiet. The rules cannot be signed while any fails."
        badge={data.selftest ? <Badge tone={data.selftest.passed === data.selftest.total ? "success" : "danger"}>{data.selftest.passed} of {data.selftest.total} passed</Badge> : undefined}
        footer={<Button size="sm" variant="secondary" loading={running} onClick={runTest}>Run the clinical tests</Button>}>
        {test ? (
          <div className="max-h-80 divide-y overflow-auto rounded-lg border text-sm">
            {test.cases.map((c) => (
              <div key={c.id} className="px-3 py-2">
                <div className="flex items-center gap-2">{c.ok ? <CheckCircle2 className="size-4 shrink-0 text-success" /> : <XCircle className="size-4 shrink-0 text-danger" />}<span className="font-medium">{c.title}</span></div>
                <div className="ml-6 text-xs text-muted-foreground">{c.why}</div>
                {c.problems.map((p) => <div key={p} className="ml-6 text-xs text-danger">{p}</div>)}
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-muted-foreground">Press the button to run every case now.</p>}
      </SettingsCard>

      <SettingsCard title="Measured quality" description="How accurately the system reads reports, finds the right source and declines what it cannot support. Run from the server with: python -m app.cli eval — so a new model can be compared with the same yardstick before switching to it.">
        {!evaluation ? <p className="text-sm text-muted-foreground">No measurement has been run yet.</p> : (
          <div className="space-y-2 text-sm">
            <div className="text-xs text-muted-foreground">{fmtDateTime(evaluation.at)} · {Object.entries(evaluation.models).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>
            {evaluation.suites.map((s) => (
              <div key={s.suite} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2">
                <div><div className="font-medium capitalize">{s.suite}</div><div className="text-xs text-muted-foreground">{s.status === "ok" ? s.target : s.reason}</div></div>
                <div className="flex items-center gap-3 text-xs">
                  {s.recall !== undefined && <span>reads {Math.round(s.recall * 1000) / 10}% of values · {Math.round((s.precision ?? 0) * 1000) / 10}% precise</span>}
                  {s.recall_at_5 !== undefined && <span>right source in top 5: {Math.round(s.recall_at_5 * 100)}%</span>}
                  {s.rate !== undefined && <span>declined {Math.round(s.rate * 100)}%</span>}
                  {s.with_citations !== undefined && <span>cited {Math.round(s.with_citations * 100)}%</span>}
                  <Badge tone={s.status !== "ok" ? "neutral" : s.pass ? "success" : "warning"}>{s.status !== "ok" ? s.status : s.pass ? "meets target" : "below target"}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </SettingsCard>

      {signing && <SignDialog area={signing} onClose={() => setSigning(null)} onDone={() => { setSigning(null); refresh(); }} />}
    </div>
  );
}

function SignDialog({ area, onClose, onDone }: { area: Area; onClose: () => void; onDone: () => void }) {
  const [role, setRole] = useState(area.missing[0].role);
  const [password, setPassword] = useState("");
  const [statement, setStatement] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { await api(`/api/clinical-content/${area.key}/sign`, { method: "POST", body: { role, password, statement: statement || null } }); toast.success("Signed"); onDone(); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not sign"); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`Sign: ${area.label}`} description="Your name, registration number and the time are recorded with this exact version. A different person must sign for the other role."
        footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} disabled={!password} onClick={submit}><PenLine /> Sign</Button></>}>
        <div className="space-y-4">
          <Field label="I am signing as"><Select value={role} onValueChange={setRole} options={area.missing.map((m) => ({ value: m.role, label: m.label }))} /></Field>
          <Field label="Statement" hint="Leave blank to use the standard wording"><Textarea rows={3} value={statement} onChange={(e) => setStatement(e.target.value)} placeholder={`I have reviewed the ${area.label.toLowerCase()} in this version and consider them appropriate for use in clinical practice in this clinic.`} /></Field>
          <Field label="Your password" hint="Confirms it is really you"><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
