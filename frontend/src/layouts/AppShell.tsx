import { NavLink, Outlet } from "react-router-dom";
import { useSystemHealth } from "@/api/health";
import { StatusChip, type StatusTone } from "@/components/StatusChip";

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
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-gms-red">GMS</span>
            <span className="text-sm text-muted-text">Clinical AI</span>
          </div>

          <nav className="flex flex-1 items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
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

          <StatusChip
            label={
              isLoading ? "Checking…" : isError ? "Backend Offline" : data?.status === "ok" ? "Online" : "Degraded"
            }
            tone={overallTone(data?.status, isLoading, isError)}
          />
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
