export type Role = "admin" | "clinician" | "viewer";

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
export interface Medication { id: string; patient_id: string; name: string; dose: string | null; route: string | null; frequency: string | null; indication: string | null; start_date: string | null; end_date: string | null; status: string; notes: string | null; source: string; source_document_id: string | null; encounter_id: string | null; created_at: string }
export interface Encounter { id: string; patient_id: string; type: string; status: string; started_at: string; ended_at: string | null; reason: string | null; notes: string | null; vitals: Record<string, any>; clinician_id: string | null; created_at: string }

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

export interface InboxItem { id: string; type: "identity" | "ingestion" | "lab" | "review" | "draft"; priority: "high" | "medium" | "low"; title: string; detail: string | null; patient_id: string | null; patient_name: string | null; mrn: string | null; ref_id: string; at: string }

export interface Domain { id: string; name: string; group: string; count: number }

export interface ScoreInput { label: string; value: string; source: string; date: string | null; document_id: string | null }
export interface ClinicalScore {
  id: string; kind: "score" | "check"; name: string; value: string; category: string; level: number; levels: string[];
  summary: string; reference: string; inputs: ScoreInput[]; missing: string[]; note: string | null;
}
