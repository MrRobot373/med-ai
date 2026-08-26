import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { PatientWorkspace } from "@/layouts/PatientWorkspace";
import { RequireAuth } from "@/components/RequireAuth";
import LoginPage from "@/pages/Login";
import OverviewPage from "@/pages/Overview";
import DashboardPage from "@/pages/Dashboard";
import PatientsPage from "@/pages/Patients";
import PatientOverviewTab from "@/pages/PatientWorkspace/Overview";
import PatientTimelineTab from "@/pages/PatientWorkspace/Timeline";
import PatientReportsTab from "@/pages/PatientWorkspace/Reports";
import PatientLabsTab from "@/pages/PatientWorkspace/Labs";
import PatientConditionsTab from "@/pages/PatientWorkspace/Conditions";
import PatientMedicationsTab from "@/pages/PatientWorkspace/Medications";
import PatientClinicalAITab from "@/pages/PatientWorkspace/ClinicalAI";
import ClinicalAIPage from "@/pages/ClinicalAI";
import SettingsPage from "@/pages/Settings";
import DemoScenariosPage from "@/pages/Demo";

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
        { path: "dashboard", element: <DashboardPage /> },
        { path: "patients", element: <PatientsPage /> },
        {
          path: "patients/:patientId",
          element: <PatientWorkspace />,
          children: [
            { index: true, element: <Navigate to="overview" replace /> },
            { path: "overview", element: <PatientOverviewTab /> },
            { path: "timeline", element: <PatientTimelineTab /> },
            { path: "reports", element: <PatientReportsTab /> },
            { path: "labs", element: <PatientLabsTab /> },
            { path: "medications", element: <PatientMedicationsTab /> },
            { path: "conditions", element: <PatientConditionsTab /> },
            { path: "clinical-ai", element: <PatientClinicalAITab /> },
          ],
        },
        { path: "clinical-ai", element: <ClinicalAIPage /> },
        { path: "knowledge", element: <SettingsPage initialTab="knowledge" /> },
        { path: "demo", element: <DemoScenariosPage /> },
        { path: "audit", element: <SettingsPage initialTab="audit" /> },
        { path: "settings", element: <SettingsPage /> },
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
