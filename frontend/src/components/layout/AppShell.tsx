import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { useBranding, useMe } from "@/api/hooks";
import { Spinner } from "@/components/ui";
import { CommandPaletteProvider } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

/** Keyboard "go to" shortcuts: G then H/I/P/A/L/S. */
function useGoShortcuts() {
  const navigate = useNavigate();
  const pending = useRef(false);
  useEffect(() => {
    const map: Record<string, string> = { h: "/", i: "/inbox", p: "/patients", a: "/assistant", l: "/library", s: "/settings" };
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (pending.current && map[k]) {
        navigate(map[k]);
        pending.current = false;
        return;
      }
      pending.current = k === "g";
      if (pending.current) setTimeout(() => (pending.current = false), 1200);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);
}

export function AppShell() {
  const { data: me, isLoading, isError } = useMe();
  const { data: branding } = useBranding();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  useGoShortcuts();

  useEffect(() => {
    const onUnauthorized = () => {
      qc.removeQueries({ queryKey: ["me"] });
      navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, { replace: true });
    };
    window.addEventListener("gms:unauthorized", onUnauthorized);
    return () => window.removeEventListener("gms:unauthorized", onUnauthorized);
  }, [navigate, location, qc]);

  useEffect(() => {
    if (isError) navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, { replace: true });
  }, [isError, navigate, location]);

  if (isLoading || !me) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="size-5" />
      </div>
    );
  }

  const fullBleed = location.pathname.startsWith("/assistant");
  return (
    <CommandPaletteProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className={fullBleed ? "flex min-h-0 flex-1 flex-col" : "mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-8 md:py-8"}>
            <Outlet />
          </main>
          {!fullBleed && (
            <footer className="no-print mx-auto w-full max-w-[1400px] px-4 pb-6 text-[0.7rem] text-muted-foreground md:px-8">
              {branding?.disclaimer}
            </footer>
          )}
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
