import type { ConversationScope } from "@/api/chat";

/** Human labels for every scope value, including the two not implemented until
 * later phases (kept here so the picker can show them as explicitly disabled
 * rather than omitting them, per spec §130 — honest "not yet" beats a missing
 * option that looks like an oversight). */
export const SCOPE_LABEL: Record<ConversationScope, string> = {
  general: "General",
  current_patient: "This Patient",
  current_encounter: "This Encounter",
  selected_report: "This Report",
  selected_reports_comparison: "Compare Reports",
  local_knowledge_only: "Local Knowledge Only",
  research_mode: "Research Mode",
};

export const SCOPE_DESCRIPTION: Record<ConversationScope, string> = {
  general: "A general conversation, not tied to any patient record.",
  current_patient: "Searches this patient's documents and the local medical knowledge base.",
  current_encounter: "Focused on one encounter's details, plus this patient's documents and knowledge base.",
  selected_report: "Focused only on the contents of one selected report.",
  selected_reports_comparison: "Arrives in Phase 10 — compare findings across multiple reports.",
  local_knowledge_only: "Searches only the local medical knowledge base, no patient data.",
  research_mode: "Arrives in Phase 11 — includes web research alongside local sources.",
};

export const UNIMPLEMENTED_SCOPES: ConversationScope[] = ["selected_reports_comparison", "research_mode"];

/** Suggested clinical questions (spec §42) — clicking one sends it as a real message,
 * it is never decorative. Kept generic enough to apply across specialties/patients
 * rather than assuming a particular condition is present. */
export const PATIENT_SUGGESTED_QUESTIONS = [
  "Summarize this patient's active problems and current medications.",
  "What are the key findings from their most recent reports?",
  "Are there any potential medication or allergy concerns to flag?",
  "Find guideline evidence relevant to this case.",
];

export const REPORT_SUGGESTED_QUESTIONS = [
  "Summarize this report in plain terms.",
  "What are the key abnormal findings in this report?",
  "Does this report suggest any change to the current treatment plan?",
];

export const GENERAL_SUGGESTED_QUESTIONS = [
  "What local knowledge sources are available to you?",
  "How should I phrase questions to get the most reliable answers?",
];
