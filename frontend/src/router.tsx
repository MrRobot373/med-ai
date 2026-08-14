import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { RequireAuth } from "@/components/RequireAuth";
import LoginPage from "@/pages/Login";
import OverviewPage from "@/pages/Overview";
import { NotYetBuilt } from "@/pages/NotYetBuilt";

export const router = createBrowserRouter(
  [
    { path: "/login", element: <LoginPage /> },
    {
      path: "/",
      element: (
        <RequireAuth>
          <AppShell />
        </RequireAuth>
      ),
      children: [
        { index: true, element: <Navigate to="/overview" replace /> },
        { path: "overview", element: <OverviewPage /> },
        { path: "patients", element: <NotYetBuilt title="Patients" phase="Phase 04" /> },
        { path: "clinical-ai", element: <NotYetBuilt title="Clinical AI" phase="Phases 08–10" /> },
        { path: "knowledge", element: <NotYetBuilt title="Knowledge" phase="Phase 12" /> },
        { path: "research", element: <NotYetBuilt title="Research" phase="Phase 11" /> },
        { path: "workflow", element: <NotYetBuilt title="Workflow" phase="Phase 06" /> },
        { path: "audit", element: <NotYetBuilt title="Audit" phase="Phase 13" /> },
        { path: "settings", element: <NotYetBuilt title="Settings" phase="Phase 12" /> },
      ],
    },
  ],
  {
    // Opt in to the v7 behaviors now so upgrading React Router later is a no-op
    // instead of a migration; also silences the future-flag console warnings.
    // (v7_startTransition is a RouterProvider-level flag in this version — see App.tsx.)
    future: { v7_relativeSplatPath: true },
  },
);
