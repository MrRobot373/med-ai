import { Lock, Plus } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useSystemHealth } from "@/api/health";
import { StatusChip, type StatusTone } from "@/components/StatusChip";
import { UserMenu } from "@/components/UserMenu";

// Nav order matches spec §19 exactly. Only "Overview" has a real feature behind it in
// Phase 01 — the rest route to an explicit NotYetBuilt placeholder (see router.tsx)
// rather than being hidden, so the intended information architecture is visible from
// the start of the build.
const NAV_ITEMS = [
  { to: "/overview", label: "Overview" },
  { to: "/patients", label: "Patients" },
  { to: "/clinical-ai", label: "Clinical AI" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/research", label: "Research" },
  { to: "/workflow", label: "Workflow" },
  { to: "/audit", label: "Audit" },
  { to: "/settings", label: "Settings" },
];

function overallTone(status: "ok" | "degraded" | undefined, isLoading: boolean, isError: boolean): StatusTone {
  if (isLoading) return "loading";
  if (isError) return "down";
  return status === "ok" ? "ok" : "degraded";
}

export function AppShell() {
  const { data, isLoading, isError } = useSystemHealth();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
          <div className="flex shrink-0 items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gms-red text-white">
              <Plus className="h-4 w-4" strokeWidth={3} />
            </span>
            <div className="leading-tight">
              <div className="text-base font-bold text-gms-red">GMS</div>
              <div className="text-[11px] font-medium text-muted-text">Clinical AI</div>
            </div>
          </div>

          <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-light-blue text-primary-blue"
                      : "text-muted-text hover:bg-light-blue hover:text-navy"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex shrink-0 items-center gap-3">
            {/* Honest per spec §128: Research Mode isn't built yet (Phase 11), so this
               deployment cannot do anything other than local processing right now —
               this badge reflects that real, current constraint, not a togglable UI. */}
            <span className="hidden items-center gap-1 text-xs font-medium text-muted-text sm:inline-flex">
              <Lock className="h-3.5 w-3.5" />
              Local Mode
            </span>
            <StatusChip
              label={
                isLoading ? "Checking…" : isError ? "Backend Offline" : data?.status === "ok" ? "Online" : "Degraded"
              }
              tone={overallTone(data?.status, isLoading, isError)}
            />
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
