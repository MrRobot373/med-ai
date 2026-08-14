import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";

// Mirrors backend/app/schemas/auth.py UserOut / app/models/user.py UserRole.
export type UserRole = "admin" | "doctor" | "viewer";

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  active: boolean;
  last_login_at: string | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export const ME_QUERY_KEY = ["auth", "me"] as const;

/** Source of truth for "is anyone logged in" — a 401 here IS the "not authenticated"
 * signal, not an exceptional error to alert on (see RequireAuth). */
export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: () => apiFetch<CurrentUser>("/api/auth/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) =>
      apiFetch<CurrentUser>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (user) => {
      queryClient.setQueryData(ME_QUERY_KEY, user);
    },
  });
}

/** Spec §18: viewer is read-only. Backend enforces this for real (403 on any write) —
 * this hook lets the UI hide write controls for viewers instead of showing a button
 * that always fails, which would be exactly the "dummy control" this project avoids
 * everywhere else. The backend check remains authoritative; this is presentation only. */
export function useCanWrite(): boolean {
  const { data: user } = useMe();
  return user?.role === "admin" || user?.role === "doctor";
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      // Clear everything, not just the `me` entry — cached data from the previous
      // session must never leak into whichever account logs in next on this browser.
      queryClient.clear();
    },
  });
}
