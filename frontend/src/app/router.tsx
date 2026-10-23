import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router";
import { useMe } from "@/api/hooks";
import { isFrontDesk } from "@/lib/roles";
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
const LibraryPage = lazy(() => import("@/features/library/LibraryPage"));
const AuditPage = lazy(() => import("@/features/audit/AuditPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const ConsultationTab = lazy(() => import("@/features/consult/ConsultationTab"));
const OrdersTab = lazy(() => import("@/features/workspace/OrdersTab"));
const PrescriptionsTab = lazy(() => import("@/features/workspace/PrescriptionsTab"));
const FrontDeskHome = lazy(() => import("@/features/frontdesk/FrontDeskHome"));
const PrescriptionPrint = lazy(() => import("@/features/print/PrescriptionPrint"));

const page = (el: ReactNode) => (
  <Suspense fallback={<div className="flex justify-center py-24"><Spinner className="size-5" /></div>}>{el}</Suspense>
);

/** The front desk works from its own home and never sees clinical pages. */
function RoleHome() {
  const { data: me } = useMe();
  if (!me) return null;
  return isFrontDesk(me.role) ? <FrontDeskHome /> : <HomePage />;
}
function Clinical({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  if (me && isFrontDesk(me.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}
const clinical = (el: ReactNode) => page(<Clinical>{el}</Clinical>);

export const router = createBrowserRouter([
  { path: "/print/prescription/:id", element: page(<PrescriptionPrint />), errorElement: <RouteError /> },
  { path: "/login", element: <LoginPage />, errorElement: <RouteError /> },
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: page(<RoleHome />) },
      { path: "inbox", element: clinical(<InboxPage />) },
      { path: "patients", element: page(<PatientsPage />) },
      {
        path: "patients/:patientId",
        element: page(<PatientWorkspace />),
        children: [
          { index: true, element: page(<OverviewTab />) },
          { path: "consult", element: page(<ConsultationTab />) },
          { path: "orders", element: page(<OrdersTab />) },
          { path: "prescriptions", element: page(<PrescriptionsTab />) },
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
      { path: "assistant", element: clinical(<AssistantPage />) },
      { path: "assistant/:conversationId", element: clinical(<AssistantPage />) },
      { path: "tools", element: clinical(<ToolsPage />) },
      { path: "library", element: clinical(<LibraryPage />) },
      { path: "audit", element: page(<AuditPage />) },
      { path: "settings", element: <Navigate to="/settings/profile" replace /> },
      { path: "settings/:section", element: page(<SettingsPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
