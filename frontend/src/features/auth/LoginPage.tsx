import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, Cpu, Eye, EyeOff, FileSearch, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { qk, useBranding } from "@/api/hooks";
import type { User } from "@/api/types";
import { Button, Field, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

const FEATURES = [
  { icon: ShieldCheck, title: "Private by design", text: "Runs on your own infrastructure. Patient data never leaves it without your say." },
  { icon: FileSearch, title: "Evidence you can verify", text: "Every answer cites the exact report, page or guideline it came from." },
  { icon: Cpu, title: "Your models, your choice", text: "Use local Ollama models or any OpenAI-compatible endpoint." },
];

const DEMO = [
  { label: "Clinician", email: "doctor@gms.local", password: "Doctor@12345" },
  { label: "Administrator", email: "admin@gms.local", password: "Admin@12345" },
  { label: "Viewer", email: "viewer@gms.local", password: "Viewer@12345" },
];

export default function LoginPage() {
  const { data: b } = useBranding();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const qc = useQueryClient();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const user = await api<User>("/api/auth/login", { method: "POST", body: { email, password } });
      qc.setQueryData(qk.me, user);
      const next = params.get("next");
      navigate(next && next.startsWith("/") && !next.startsWith("//") ? next : "/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-primary lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(255,255,255,0.18),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(0,0,0,0.25),transparent_60%)]" />
        <div className="absolute inset-0 opacity-[0.12] [background-image:linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] [background-size:36px_36px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
        <div className="relative flex flex-1 flex-col justify-between p-12 text-primary-foreground">
          <div className="flex items-center gap-3">
            <img src={b?.logo_data_url || "/brand-mark.webp"} alt="" className="size-10 rounded-xl bg-white/95 object-contain p-1 shadow-lg" />
            <div>
              <div className="text-lg font-semibold tracking-tight">{b?.product_name ?? "GMS Clinical AI"}</div>
              <div className="text-sm opacity-80">{b?.organization}</div>
            </div>
          </div>
          <div className="max-w-lg">
            <h1 className="text-[2.4rem] font-semibold leading-[1.1] tracking-tight">{b?.tagline ?? "Clinical intelligence, grounded in evidence"}</h1>
            <div className="mt-10 space-y-6">
              {FEATURES.map((f) => (
                <div key={f.title} className="flex gap-4">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/20 backdrop-blur"><f.icon className="size-5" /></div>
                  <div>
                    <div className="font-semibold">{f.title}</div>
                    <div className="text-sm opacity-80">{f.text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="max-w-md text-xs opacity-70">{b?.disclaimer}</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[380px] animate-slide-up">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <img src={b?.logo_data_url || "/brand-mark.webp"} alt="" className="size-9 rounded-lg object-contain" />
            <span className="text-lg font-semibold">{b?.product_name}</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">{b?.login_message ?? "Use your clinical account to continue."}</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-danger-foreground">
                <AlertCircle className="mt-0.5 size-4 shrink-0" /> {error}
              </div>
            )}
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@hospital.org" autoFocus />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input
                id="password" type={show ? "text" : "password"} autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                suffix={
                  <button type="button" onClick={() => setShow((s) => !s)} className="rounded p-1 text-muted-foreground hover:text-foreground" aria-label={show ? "Hide password" : "Show password"}>
                    {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                }
              />
            </Field>
            <Button type="submit" size="lg" className="w-full" loading={loading}>
              Continue <ArrowRight />
            </Button>
          </form>

          {b?.show_demo_accounts && (
            <div className="mt-8 rounded-xl border bg-subtle p-3">
              <div className="text-label mb-2 px-1">Demo accounts</div>
              <div className="grid gap-1">
                {DEMO.map((d) => (
                  <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword(d.password); }}
                    className="flex items-center justify-between rounded-md px-2 py-1.5 text-left text-xs hover:bg-card">
                    <span className="font-medium">{d.label}</span>
                    <span className="text-muted-foreground">{d.email}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
