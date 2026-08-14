import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import OverviewPage from "@/pages/Overview";
import { NotYetBuilt } from "@/pages/NotYetBuilt";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      { path: "overview", element: <OverviewPage /> },
      { path: "patients", element: <NotYetBuilt title="Patients" phase="Phase 04" /> },
      { path: "clinical-ai", element: <NotYetBuilt title="Clinical AI" phase="Phase 08" /> },
      { path: "knowledge", element: <NotYetBuilt title="Knowledge" phase="Phase 12" /> },
      { path: "research", element: <NotYetBuilt title="Research" phase="Phase 11" /> },
      { path: "workflow", element: <NotYetBuilt title="Workflow" phase="Phase 06" /> },
      { path: "audit", element: <NotYetBuilt title="Audit" phase="Phase 13" /> },
      { path: "settings", element: <NotYetBuilt title="Settings" phase="Phase 12" /> },
    ],
  },
]);
