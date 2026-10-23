import { ArrowLeftRight, Eye, FileSearch, FileSignature, GitCompare, ListChecks, Pill, Sparkles, Stethoscope, type LucideIcon } from "lucide-react";

export interface ToolMeta { id: string; name: string; description: string; icon: LucideIcon; needs: string }

export const PATIENT_TOOLS: ToolMeta[] = [
  { id: "summary", name: "Case summary", description: "Longitudinal summary with gaps and follow-ups", icon: Sparkles, needs: "Chart + documents" },
  { id: "soap", name: "SOAP note", description: "Draft a structured note for an encounter", icon: FileSignature, needs: "An encounter" },
  { id: "differential", name: "Differential support", description: "Considerations with supporting and opposing evidence", icon: Stethoscope, needs: "A presentation" },
  { id: "comparison", name: "Report comparison", description: "What changed between two reports", icon: GitCompare, needs: "Two documents" },
  { id: "med_reconciliation", name: "Medication reconciliation", description: "Chart medications vs. a document", icon: Pill, needs: "A document" },
  { id: "entities", name: "Entity extraction", description: "Problems, drugs, allergies, labs with quotes", icon: ListChecks, needs: "A document" },
  { id: "vision", name: "Image analysis", description: "Describe a clinical image or scan", icon: Eye, needs: "An image" },
];

export const GLOBAL_TOOLS: ToolMeta[] = [
  { id: "guideline_qa", name: "Guideline Q&A", description: "Answers strictly from the knowledge library", icon: FileSearch, needs: "A question" },
  { id: "vision", name: "Image analysis", description: "Describe a clinical image or scan", icon: Eye, needs: "An image" },
  { id: "patient", name: "Patient tools", description: "Summaries, SOAP notes, comparisons and more", icon: ArrowLeftRight, needs: "Choose a patient" },
];
