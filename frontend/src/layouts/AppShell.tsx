import { NavLink, Outlet, useLocation } from "react-router-dom";
import { UserMenu } from "@/components/UserMenu";
import gmsLogo from "@/assets/GMS-LOGO.webp";

// Nav order matches spec §19 exactly. Only "Overview" has a real feature behind it in
// Phase 01 — the rest route to an explicit NotYetBuilt placeholder (see router.tsx)
// rather than being hidden, so the intended information architecture is visible from
// the start of the build.
const NAV_ITEMS = [
  { to: "/overview", label: "Overview" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/patients", label: "Patients" },
  { to: "/clinical-ai", label: "Clinical AI" },
  { to: "/settings", label: "Settings" },
];

export function AppShell() {
  const location = useLocation();
  const isClinicalAI = location.pathname === "/clinical-ai";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
          <div className="flex shrink-0 items-center gap-2.5">
            <img src={gmsLogo} alt="GMS Logo" className="h-8 w-8 object-contain rounded" />
            <div className="leading-tight">
              <div className="text-base font-bold text-gms-red">MED AI</div>
              <div className="text-[11px] font-medium text-muted-text">Ophthalmology</div>
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
            <UserMenu />
          </div>
        </div>
      </header>

      <main className={`w-full flex-1 ${isClinicalAI ? "px-6 py-4" : "mx-auto max-w-7xl px-6 py-8"}`}>
        <Outlet />
      </main>
    </div>
  );
}
