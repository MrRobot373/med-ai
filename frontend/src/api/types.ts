export type Role = "admin" | "clinician" | "viewer" | "front_desk";

export interface Preferences {
  theme?: "light" | "dark" | "system";
  accent?: string | null;
  density?: "comfortable" | "compact";
  radius?: "sharp" | "default" | "round";
  font_scale?: "sm" | "md" | "lg";
  font_family?: "inter" | "system";
  contrast?: "normal" | "high";
  reduce_motion?: boolean;
  sidebar_collapsed?: boolean;
  chat_show_trace?: boolean;
}

export interface User {
  id: string; email: string; full_name: string; title: string | null; specialty: string | null; role: Role;
  is_active: boolean; preferences: Preferences; last_login_at: string | null; created_at: string;
}

export interface Branding {
  product_name: string; tagline: string; organization: string; logo_data_url: string | null;
  default_accent: string; default_theme: "light" | "dark" | "system"; disclaimer: string; login_message: string;
  show_demo_accounts?: boolean;
}

export interface Patient {
  id: string; mrn: string; first_name: string; last_name: string; full_name: string; date_of_birth: string | null;
  age: number | null; sex: string; phone: string | null; email: string | null; address: string | null;
  blood_group: string | null; notes: string | null; tags: string[]; status: "active" | "archived"; synthetic: boolean;
  created_at: string; updated_at: string;
}

export interface PatientListItem extends Patient {
  active_conditions: string[]; last_encounter_at: string | null; open_alerts: number; document_count: number;
}

export interface Condition { id: string; patient_id: string; name: string; code: string | null; status: string; onset_date: string | null; notes: string | null; encounter_id: string | null; created_at: string }
export interface Allergy { id: string; patient_id: string; substance: string; reaction: string | null; severity: string; status: string; notes: string | null; created_at: string }
export interface Medication { id: string; patient_id: string; name: string; dose: string | null; route: string | null; frequency: string | null; indication: string | null; start_date: string | null; end_date: string | null; status: string; notes: string | null; source: string; source_document_id: string | null; encounter_id: string | null; created_at: string; prescription_id?: string | null; generic?: string | null }
export interface Diagnosis { name: string; code?: string | null; add_to_problems?: boolean }
export interface Encounter { id: string; patient_id: string; type: string; status: string; started_at: string; ended_at: string | null; reason: string | null; notes: string | null; vitals: Record<string, any>; clinician_id: string | null; created_at?: string; history?: string | null; examination?: string | null; assessment?: string | null; plan?: string | null; diagnoses?: Diagnosis[] }

export interface Observation {
  id: string; patient_id: string; document_id: string | null; name: string; code: string; value_num: number | null;
  value_text: string | null; unit: string | null; ref_low: number | null; ref_high: number | null; ref_text: string | null;
  flag: string | null; observed_at: string; source_page: number | null; source_excerpt: string | null; method: string; acknowledged: boolean;
}

export interface TrendPoint { id: string; at: string; value: number | null; text: string | null; flag: string | null; ref_low: number | null; ref_high: number | null; document_id: string | null; page: number | null; excerpt: string | null; acknowledged: boolean }
export interface TrendSeries { code: string; name: string; unit: string | null; points: TrendPoint[]; latest: TrendPoint; change: number | null; trend: "up" | "down" | "flat" | null; abnormal: boolean }

export interface DocumentItem {
  id: string; scope: "patient" | "knowledge"; patient_id: string | null; encounter_id: string | null; title: string;
  filename: string; mime_type: string; size_bytes: number; kind: string; domain: string | null; source_org: string | null;
  version: string | null; document_date: string | null; status: "processing" | "ready" | "failed" | "archived";
  is_active: boolean; error: string | null; identity_status: string; identity_detail: string | null; review_status: string;
  page_count: number; chunk_count: number; extraction: Record<string, any>; created_at: string; updated_at: string;
}

export interface ChunkItem { id: string; ordinal: number; page: number | null; section: string | null; text: string; token_count: number }

export interface Alert { type: string; severity: "info" | "warning" | "danger"; title: string; detail: string; id: string | null }

export interface AIRun {
  id: string; tool: string; patient_id: string | null; encounter_id: string | null; input: Record<string, any>;
  output: Record<string, any> | null; citations: any[]; status: "draft" | "accepted" | "discarded" | "error";
  error: string | null; model: string | null; latency_ms: number | null; created_at: string; reviewed_at: string | null;
}

export interface PatientOverview {
  patient: Patient; conditions: Condition[]; allergies: Allergy[]; medications: Medication[]; encounters: Encounter[];
  documents: DocumentItem[]; latest_observations: Observation[]; alerts: Alert[];
  summary: { id: string; output: Record<string, any>; created_at: string; status: string } | null;
  counts: { documents: number; encounters: number; observations: number };
}

export interface TimelineEvent { at: string; kind: string; title: string; detail: string | null; ref: Record<string, string> | null; tone: string }

export interface Source {
  label: string; scope: "patient" | "knowledge" | "web" | "record"; document_title: string; document_id?: string;
  chunk_id?: string; page?: number | null; section?: string | null; excerpt?: string; kind?: string; domain?: string | null;
  document_date?: string | null; source_org?: string | null; url?: string; evidence_type?: string; cited?: boolean;
  dense_rank?: number | null; lexical_rank?: number | null; fused_score?: number; rerank_score?: number | null;
}

export interface Trace {
  query?: string; scopes?: string[]; profile?: string; params?: Record<string, number>; models?: Record<string, string>;
  counts?: Record<string, number>; timings?: Record<string, number>;
  candidates?: { chunk_id: string; document_title: string; scope: string; page: number | null; dense_rank: number | null; lexical_rank: number | null; fused_score: number; rerank_score: number | null; selected: boolean; label: string | null }[];
  generation?: { model: string; first_token_ms: number | null; generation_ms: number; citations_used: string[]; invalid_citations_removed: string[]; citation_coverage: number | null };
  web?: { status: string; outbound_query?: string; identifiers_removed?: number; categories?: string[]; providers?: any[]; note?: string };
  error?: string;
}

export interface ChatMessage {
  id: string; role: "user" | "assistant"; content: string; status: "complete" | "abstained" | "error" | "streaming";
  citations: Source[]; trace: Trace; model: string | null; latency_ms: number | null; feedback: "up" | "down" | null; created_at: string;
}

export interface Conversation { id: string; patient_id: string | null; scope: string; title: string; pinned: boolean; use_web: boolean; created_at: string; updated_at: string }
export interface ConversationDetail extends Conversation { patient: { id: string; full_name: string; mrn: string } | null; messages: ChatMessage[] }

export interface HealthComponent { component: string; status: "online" | "offline" | "degraded" | "disabled"; detail?: string; error?: string; latency_ms: number; model?: string; stats?: any }
export interface Health { status: "online" | "offline" | "degraded"; checked_at: string; components: HealthComponent[] }

export interface InboxItem { id: string; type: "identity" | "ingestion" | "lab" | "review" | "draft" | "result" | "follow_up"; priority: "high" | "medium" | "low"; title: string; detail: string | null; patient_id: string | null; patient_name: string | null; mrn: string | null; ref_id: string; at: string }

export interface Domain { id: string; name: string; group: string; count: number }

export interface ScoreInput { label: string; value: string; source: string; date: string | null; document_id: string | null }
export interface ClinicalScore {
  id: string; kind: "score" | "check"; name: string; value: string; category: string; level: number; levels: string[];
  summary: string; reference: string; inputs: ScoreInput[]; missing: string[]; note: string | null;
}

export interface QueueDocument extends DocumentItem { patient_name: string; patient_mrn: string }
export interface AttentionPatient {
  id: string; full_name: string; mrn: string; age: number | null; sex: string; abnormal: number; mismatches: number;
  pending_documents: number; severity: number;
  marker: { name: string; value: number | null; unit: string | null; ref_low: number | null; ref_high: number | null; flag: string | null; observed_at: string } | null;
  score: { name: string; value: string; category: string; level: number; levels: string[] } | null;
}

/* ---- Point of care ---------------------------------------------------------------------- */

export type Severity = "ok" | "info" | "warning" | "critical";

export interface Appointment {
  id: string; day: string; time: string | null; reason: string | null; status: "expected" | "arrived" | "seen" | "cancelled";
  encounter_id: string | null; patient_id: string;
  patient: { id: string; name: string; mrn: string; age: number | null; sex: string; phone: string | null } | null;
  clinical?: { conditions: string[]; abnormal: number; results_back: number; pending_orders: number; last_visit: string | null; last_reason: string | null; has_brief: boolean };
}
export interface TodayList { date: string; appointments: Appointment[]; counts: Record<"expected" | "arrived" | "seen", number> }

/** An AI tool run as returned by the consultation endpoints. */
export interface CopilotRun<T = Record<string, any>> {
  id: string; tool: string; status: "draft" | "error" | "accepted" | "discarded"; output: T | null; error: string | null;
  model: string | null; latency_ms: number | null; created_at: string; input: Record<string, any>;
}

export interface BriefOutput { headline: string; since_last_visit: string[]; ask_about: { question: string; why: string }[]; watch_outs: string[]; consider_today: string[] }
export interface DiagnosisCheckOutput {
  verdict: "consistent" | "partly_consistent" | "inconsistent" | "insufficient_information"; summary: string; supporting: string[]; against: string[];
  consider: { diagnosis: string; why: string; how_to_check: string }[]; red_flags: string[]; suggested_tests: { test: string; why: string }[]; history_links: string[];
}
export interface RxReviewOutput {
  overall: "appropriate" | "review" | "unsafe"; summary: string;
  items: { index: number; drug: string; verdict: "appropriate" | "adjust" | "avoid"; dose_assessment: "adequate" | "low" | "high" | "unclear"; comment: string; suggestion: string | null }[];
  diagnosis_fit: string; missing: string[]; monitoring: string[]; counselling: string[];
}
export interface ResultReviewOutput {
  answers_question: string; key_findings: string[]; abnormal: { finding: string; significance: string }[]; change_from_previous: string | null;
  next_steps: string[]; urgency: "routine" | "soon" | "urgent"; patient_explanation: string;
}

export interface PrevisitFacts {
  last_visit: { id: string; date: string; reason: string | null; assessment: string | null; diagnoses: Diagnosis[]; plan: string | null } | null;
  days_since_last_visit: number | null;
  new_documents: { id: string; title: string; kind: string; date: string }[];
  abnormal_results: { id: string; name: string; value: number | string | null; unit: string | null; flag: string | null; date: string }[];
  orders: { id: string; test_name: string; status: string; ordered_at: string; reason: string | null }[];
  last_prescription: Prescription | null;
  follow_up: { date: string; overdue_days: number } | null;
}

export interface Finding { code: string; severity: Exclude<Severity, "ok">; title: string; detail: string; generic: string | null; basis: string | null }
export interface RxItem {
  id?: string; position?: number; drug: string; generic?: string | null; strength_mg?: number | null; dose: string; route?: string | null;
  frequency: string; duration_days: number | null; instructions: string | null; override_reason?: string | null; line?: string; checks?: Finding[];
}
export interface CheckItem {
  index: number; drug: string; recognised: boolean; description: string; generics: { id: string; name: string; class: string; unit: string }[];
  form: string; frequency_label: string; per_dose: Record<string, number>; per_day: Record<string, number>; status: Severity; findings: Finding[];
}
export interface FactValue { value: number | string | boolean | null; source: string; date: string | null; document_id: string | null }
export interface CheckResult {
  region: string; formulary_version: string; source_note: string; status: Severity; summary: Record<"critical" | "warning" | "info", number>; items: CheckItem[];
  patient: {
    age: number | null; sex: string; elderly: boolean; pregnant: boolean; weight: FactValue | null; egfr: FactValue | null; creatinine: FactValue | null; hepatic: FactValue | null;
    conditions: string[]; allergies: { substance: string; reaction: string | null }[]; current_meds: { name: string; dose: string | null; frequency: string | null }[];
    labs: Record<string, { name: string; value: number; unit: string | null; date: string }>;
  };
}
export interface Prescription {
  id: string; patient_id: string; encounter_id: string | null; status: "draft" | "final" | "cancelled"; diagnosis: string | null; advice: string | null;
  follow_up_date: string | null; finalized_at: string | null; date: string; clinician_id: string | null; items: RxItem[];
  context?: { patient?: CheckResult["patient"]; summary?: CheckResult["summary"]; status?: Severity }; created_at?: string; check?: CheckResult;
}
export interface PrescriptionDetail extends Prescription {
  patient: { id: string; name: string; mrn: string; age: number | null; sex: string; phone: string | null; address: string | null };
  clinician: { name: string; email: string } | null; encounter: Encounter | null; review: CopilotRun<RxReviewOutput> | null;
}

export interface Order {
  id: string; patient_id: string; encounter_id: string | null; category: "lab" | "radiology" | "cardiology" | "other"; test_name: string;
  urgency: "routine" | "urgent"; status: "ordered" | "result_received" | "reviewed" | "cancelled"; ordered_at: string; result_at: string | null; reviewed_at: string | null;
  result_document: { id: string; title: string; status: string; kind: string } | null;
  reason?: string | null; review_note?: string | null; ai_review?: CopilotRun<ResultReviewOutput> | null;
}

export interface Consultation {
  encounter: Encounter; prescription: Prescription | null; orders: Order[];
  diagnosis_check: CopilotRun<DiagnosisCheckOutput> | null; rx_review: CopilotRun<RxReviewOutput> | null;
}

export interface FormularyOption { label: string; drug: string; frequency: string; generic: string; generic_label: string; strength: number | null; form: string; brand: string | null; class: string; unit: string }
export interface MedicineImage { url: string; title: string | null; author: string | null; license: string | null; source_url: string | null }
