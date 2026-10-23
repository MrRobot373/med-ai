import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Spinner } from "@/components/ui";
import LoginPage from "@/features/auth/LoginPage";
import { RouteError } from "./RouteError";

const HomePage = lazy(() => import("@/features/home/HomePage"));
const InboxPage = lazy(() => import("@/features/inbox/InboxPage"));
const PatientsPage = lazy(() => import("@/features/patients/PatientsPage"));
const PatientWorkspace = lazy(() => import("@/features/workspace/PatientWorkspace"));
const OverviewTab = lazy(() => import("@/features/workspace/OverviewTab"));
const TimelineTab = lazy(() => import("@/features/workspace/TimelineTab"));
const DocumentsTab = lazy(() => import("@/features/workspace/DocumentsTab"));
const ResultsTab = lazy(() => import("@/features/workspace/ResultsTab"));
const MedicationsTab = lazy(() => import("@/features/workspace/MedicationsTab"));
const ProblemsTab = lazy(() => import("@/features/workspace/ProblemsTab"));
const EncountersTab = lazy(() => import("@/features/workspace/EncountersTab"));
const PatientAssistantTab = lazy(() => import("@/features/workspace/AssistantTab"));
const PatientToolsTab = lazy(() => import("@/features/workspace/ToolsTab"));
const AssistantPage = lazy(() => import("@/features/assistant/AssistantPage"));
const ToolsPage = lazy(() => import("@/features/tools/ToolsPage"));
const ResearchPage = lazy(() => import("@/features/research/ResearchPage"));
const LibraryPage = lazy(() => import("@/features/library/LibraryPage"));
const AuditPage = lazy(() => import("@/features/audit/AuditPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));

const page = (el: ReactNode) => (
  <Suspense fallback={<div className="flex justify-center py-24"><Spinner className="size-5" /></div>}>{el}</Suspense>
);

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage />, errorElement: <RouteError /> },
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: page(<HomePage />) },
      { path: "inbox", element: page(<InboxPage />) },
      { path: "patients", element: page(<PatientsPage />) },
      {
        path: "patients/:patientId",
        element: page(<PatientWorkspace />),
        children: [
          { index: true, element: page(<OverviewTab />) },
          { path: "timeline", element: page(<TimelineTab />) },
          { path: "documents", element: page(<DocumentsTab />) },
          { path: "results", element: page(<ResultsTab />) },
          { path: "medications", element: page(<MedicationsTab />) },
          { path: "problems", element: page(<ProblemsTab />) },
          { path: "encounters", element: page(<EncountersTab />) },
          { path: "assistant", element: page(<PatientAssistantTab />) },
          { path: "tools", element: page(<PatientToolsTab />) },
        ],
      },
      { path: "assistant", element: page(<AssistantPage />) },
      { path: "assistant/:conversationId", element: page(<AssistantPage />) },
      { path: "tools", element: page(<ToolsPage />) },
      { path: "research", element: page(<ResearchPage />) },
      { path: "library", element: page(<LibraryPage />) },
      { path: "audit", element: page(<AuditPage />) },
      { path: "settings", element: <Navigate to="/settings/profile" replace /> },
      { path: "settings/:section", element: page(<SettingsPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
