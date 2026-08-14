import { type FormEvent, useState } from "react";
import { useNavigate, useLocation, Navigate } from "react-router-dom";
import { CheckCircle2, Plus } from "lucide-react";
import { useLogin, useMe } from "@/api/auth";
import { ApiError } from "@/api/client";

/** Turns a thrown login error into the specific, non-enumerating message spec §21
 * calls for. The backend deliberately returns one identical message for "wrong
 * password" / "unknown email" / "inactive account" (spec §17 anti-enumeration) —
 * this only adds distinct handling for cases the backend CAN safely reveal:
 * rate-limiting (IP-scoped, not account-scoped) and the backend being unreachable. */
function describeLoginError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return error.message;
    if (error.status === 401) return "Invalid email or password.";
    return error.message;
  }
  return "Local AI backend is unavailable. Confirm it's running and try again.";
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();

  // Already authenticated (e.g. back-button to /login) — don't show the form again.
  const me = useMe();
  if (me.data) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? "/overview";
    return <Navigate to={redirectTo} replace />;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          const redirectTo = (location.state as { from?: string } | null)?.from ?? "/overview";
          navigate(redirectTo, { replace: true });
        },
      },
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-gms-red text-white">
            <Plus className="h-6 w-6" strokeWidth={3} />
          </span>
          <h1 className="mt-3 text-xl font-bold text-gms-red">GMS</h1>
          <p className="text-sm text-muted-text">Clinical Decision Support</p>
        </div>

        <form onSubmit={handleSubmit} className="gms-card space-y-4 p-6">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-navy">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue"
              placeholder="doctor@gms.local"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-navy">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue"
              placeholder="••••••••"
            />
          </div>

          {login.isError && (
            <div role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
              {describeLoginError(login.error)}
            </div>
          )}

          <button
            type="submit"
            disabled={login.isPending}
            className="w-full rounded-lg bg-primary-blue py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-blue/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {login.isPending ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div className="mt-5 flex items-center justify-center gap-5 text-xs text-muted-text">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            Local AI
          </span>
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            Private Deployment
          </span>
        </div>
      </div>
    </div>
  );
}
