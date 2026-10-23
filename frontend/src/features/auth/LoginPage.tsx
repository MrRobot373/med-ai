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
    <div className="flex min-h-screen items-center justify-center p-4 md:p-8">
      <div className="glass grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/70 shadow-float dark:border-white/[0.06] lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-strong lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(var(--primary)/0.55),transparent_60%),radial-gradient(ellipse_at_bottom_left,rgba(0,0,0,0.35),transparent_60%)]" />
        <svg className="absolute -right-24 top-0 h-full w-[140%] opacity-25" viewBox="0 0 600 600" fill="none" aria-hidden>
          {Array.from({ length: 22 }).map((_, i) => { const y = 20 + i * 26; const a = Math.sin(i / 2.2) * 120; return <g key={i}><line x1={300 - a} y1={y} x2={300 + a} y2={y} stroke="white" strokeOpacity="0.5" /><circle cx={300 - a} cy={y} r="4" fill="white" /><circle cx={300 + a} cy={y} r="4" fill="white" fillOpacity="0.6" /></g>; })}
        </svg>
        <div className="relative flex flex-1 flex-col justify-between p-10 text-white">
          <div className="flex items-center gap-3">
            <img src={b?.logo_data_url || "/brand-mark.webp"} alt="" className="size-10 rounded-xl bg-white object-contain p-1 shadow-lg" />
            <div>
              <div className="text-lg font-semibold tracking-tight">{b?.product_name ?? "GMS Clinical AI"}</div>
              <div className="text-sm opacity-75">{b?.organization}</div>
            </div>
          </div>
          <div className="max-w-md">
            <h1 className="text-[2.1rem] font-semibold leading-[1.12] tracking-tight">{b?.tagline ?? "Clinical intelligence, grounded in evidence"}</h1>
            <div className="mt-8 space-y-5">
              {FEATURES.map((f) => (
                <div key={f.title} className="flex gap-3.5">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/12 ring-1 ring-white/20 backdrop-blur"><f.icon className="size-[18px]" /></div>
                  <div>
                    <div className="font-semibold">{f.title}</div>
                    <div className="text-sm opacity-75">{f.text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="max-w-md text-xs opacity-60">{b?.disclaimer}</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12 sm:px-12">
        <div className="w-full max-w-[360px] animate-slide-up">
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
            <Button type="submit" size="lg" variant="strong" className="w-full rounded-full" loading={loading}>
              Continue <ArrowRight />
            </Button>
          </form>

        </div>
      </div>
      </div>
    </div>
  );
}
