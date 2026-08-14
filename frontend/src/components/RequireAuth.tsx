import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useMe } from "@/api/auth";

/**
 * Protected-route gate (spec §17 "Protected routes"). GET /api/auth/me is the single
 * source of truth for "is anyone logged in" — a 401 from it is treated as the normal
 * "not authenticated" signal (redirect to /login), not an exceptional error to show.
 * The attempted path is passed through router state so Login can send the clinician
 * back to where they were headed after a successful sign-in.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-text">
        Checking session…
      </div>
    );
  }

  if (me.isError || !me.data) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
