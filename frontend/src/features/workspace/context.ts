import { useOutletContext } from "react-router";
import type { Patient } from "@/api/types";

export interface WorkspaceCtx {
  patient: Patient;
  canWrite: boolean;
}

export const useWorkspace = () => useOutletContext<WorkspaceCtx>();
