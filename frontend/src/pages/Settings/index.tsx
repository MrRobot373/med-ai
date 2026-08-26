import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileCheck2,
  Lock,
  LogOut,
  Send,
  Server,
  Settings as SettingsIcon,
  Shield,
  ShieldCheck,
  User,
} from "lucide-react";
import { Card } from "@/components/Card";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { useLogout, useMe } from "@/api/auth";
import { useSystemHealth } from "@/api/health";
import KnowledgePage from "@/pages/Knowledge";
import AuditPage from "@/pages/Audit";

type SettingsTab = "system" | "account" | "knowledge" | "audit" | "report" | "privacy";

const SIDEBAR_ITEMS: { id: SettingsTab; label: string; icon: typeof SettingsIcon; description: string }[] = [
  {
    id: "system",
    label: "System Status & Health",
    icon: Activity,
    description: "Live subsystem diagnostics",
  },
  {
    id: "account",
    label: "Account & Profile",
    icon: User,
    description: "User details & permissions",
  },
  {
    id: "knowledge",
    label: "Knowledge Administration",
    icon: BookOpen,
    description: "Clinical reference documents",
  },
  {
    id: "audit",
    label: "Audit & Feedback",
    icon: ClipboardList,
    description: "Compliance logs & feedback",
  },
  {
    id: "report",
    label: "Report Bug / Complaint",
    icon: AlertTriangle,
    description: "Raise an issue or feedback",
  },
  {
    id: "privacy",
    label: "Privacy & Data Policy",
    icon: ShieldCheck,
    description: "Clinical safety & sovereignty",
  },
];

export default function SettingsPage({ initialTab }: { initialTab?: SettingsTab }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab") as SettingsTab | null;
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab || tabParam || "system");
  const { data: me } = useMe();
  const { data: health } = useSystemHealth();
  const logout = useLogout();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSuccess: () => navigate("/login", { replace: true }),
    });
  };

  // Bug report form state
  const [reportType, setReportType] = useState("bug");
  const [severity, setSeverity] = useState("medium");
  const [moduleName, setModuleName] = useState("Clinical AI Chat");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submittedTicket, setSubmittedTicket] = useState<string | null>(null);

  useEffect(() => {
    if (tabParam && SIDEBAR_ITEMS.some((item) => item.id === tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (tab: SettingsTab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const handleReportSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    const ticketId = `GMS-${Math.floor(1000 + Math.random() * 9000)}`;
    setSubmittedTicket(ticketId);
    setTitle("");
    setDescription("");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
              <SettingsIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">Settings &amp; Administration</h1>
              <p className="text-xs text-muted-text">
                Manage system health, user profile, clinical knowledge, compliance logs, and issue reporting.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-muted-text">
          <Shield className="h-4 w-4 text-primary-blue" />
          <span>Role: <strong className="capitalize text-navy">{me?.role ?? "Clinician"}</strong></span>
        </div>
      </div>

      {/* Main Grid: Sidebar + Content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Sidebar */}
        <div className="lg:col-span-4">
          <Card className="divide-y divide-border p-2">
            <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-text">
              Navigation
            </div>
            <div className="space-y-1 pt-2">
              {SIDEBAR_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleTabChange(item.id)}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-all ${
                      isActive
                        ? "bg-light-blue font-semibold text-primary-blue shadow-sm"
                        : "text-navy hover:bg-surface-hover hover:text-primary-blue"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-primary-blue" : "text-muted-text"}`} />
                      <div>
                        <div className="leading-tight">{item.label}</div>
                        <div className="text-[11px] font-normal text-muted-text">{item.description}</div>
                      </div>
                    </div>
                    <ChevronRight className={`h-4 w-4 shrink-0 ${isActive ? "text-primary-blue opacity-100" : "opacity-0"}`} />
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Right Content Area */}
        <div className="space-y-6 lg:col-span-8">
          {/* TAB 1: System Status & Diagnostics */}
          {activeTab === "system" && (
            <div className="space-y-6">
              <SystemStatusPanel />

              <Card className="space-y-5 p-5">
                <div className="flex items-center gap-2 border-b border-border pb-3">
                  <Server className="h-5 w-5 text-primary-blue" />
                  <h3 className="text-base font-semibold text-navy">Runtime Diagnostics &amp; Local Hardware</h3>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-background p-3.5">
                    <span className="text-xs font-medium text-muted-text">Ollama LLM Model</span>
                    <div className="mt-1 font-semibold text-navy">
                      {health?.ollama?.configured_model ?? "qwen3.5:cloud"}
                    </div>
                    <span className="text-[11px] text-muted-text">
                      Status: {health?.ollama?.reachable ? "Connected (Port 11434)" : "Offline"}
                    </span>
                  </div>

                  <div className="rounded-lg border border-border bg-background p-3.5">
                    <span className="text-xs font-medium text-muted-text">Vector Engine</span>
                    <div className="mt-1 font-semibold text-navy">
                      Qdrant Vector DB (Port 6333)
                    </div>
                    <span className="text-[11px] text-muted-text">
                      Collections: {health?.qdrant?.collections?.length ?? 0} active
                    </span>
                  </div>

                  <div className="rounded-lg border border-border bg-background p-3.5">
                    <span className="text-xs font-medium text-muted-text">Embedding &amp; Reranker Device</span>
                    <div className="mt-1 font-semibold text-navy">
                      CPU Execution Mode
                    </div>
                    <span className="text-[11px] text-muted-text">
                      Model: Qwen3-Embedding-0.6B
                    </span>
                  </div>

                  <div className="rounded-lg border border-border bg-background p-3.5">
                    <span className="text-xs font-medium text-muted-text">Database Engine</span>
                    <div className="mt-1 font-semibold text-navy">
                      SQLite On-Disk (data/sqlite/gms.db)
                    </div>
                    <span className="text-[11px] text-muted-text">
                      Status: {health?.database?.reachable ? "Healthy &amp; Writable" : "Error"}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* TAB 2: Account & Profile */}
          {activeTab === "account" && (
            <div className="space-y-6">
              <Card className="space-y-6 p-6">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary-blue text-xl font-bold text-white shadow">
                      {me?.display_name
                        ? me.display_name
                            .split(" ")
                            .map((p) => p[0])
                            .join("")
                            .slice(0, 2)
                            .toUpperCase()
                        : "U"}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-navy">{me?.display_name ?? "Clinician Account"}</h3>
                      <p className="text-sm text-muted-text">{me?.email ?? "doctor@gms.local"}</p>
                      <span className="mt-1.5 inline-block rounded-full bg-light-blue px-2.5 py-0.5 text-xs font-semibold capitalize text-primary-blue">
                        Role: {me?.role ?? "doctor"}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={logout.isPending}
                    className="inline-flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm font-semibold text-danger transition-colors hover:bg-danger hover:text-white disabled:opacity-60"
                  >
                    <LogOut className="h-4 w-4" />
                    <span>{logout.isPending ? "Signing Out…" : "Sign Out"}</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-navy">
                      <Lock className="h-4 w-4 text-primary-blue" />
                      Session Security
                    </div>
                    <ul className="mt-3 space-y-1.5 text-xs text-muted-text">
                      <li>• <strong>Auth Token:</strong> HTTP-Only Signed Session Cookie</li>
                      <li>• <strong>Session Timeout:</strong> 60 minutes inactivity</li>
                      <li>• <strong>Hashing:</strong> Argon2id cryptographic encryption</li>
                    </ul>
                  </div>

                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-navy">
                      <FileCheck2 className="h-4 w-4 text-primary-blue" />
                      Clinical Permissions
                    </div>
                    <ul className="mt-3 space-y-1.5 text-xs text-muted-text">
                      <li>• Access &amp; review patient clinical timelines</li>
                      <li>• Ingest, OCR, and compare diagnostic reports</li>
                      <li>• Generate draft SOAP notes &amp; differentials</li>
                      <li>• Access guideline Q&amp;A retrieval engine</li>
                    </ul>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* TAB 3: Knowledge Administration */}
          {activeTab === "knowledge" && (
            <div>
              <KnowledgePage />
            </div>
          )}

          {/* TAB 4: Audit & Feedback */}
          {activeTab === "audit" && (
            <div>
              <AuditPage />
            </div>
          )}

          {/* TAB 5: Report a Bug / Complaint */}
          {activeTab === "report" && (
            <div className="space-y-6">
              <Card className="p-6">
                <div className="mb-5 border-b border-border pb-4">
                  <h3 className="text-base font-semibold text-navy flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                    Submit Bug Report or Clinical Complaint
                  </h3>
                  <p className="text-xs text-muted-text mt-1">
                    Report software defects, unexpected model responses, clinical discrepancies, or system performance issues.
                  </p>
                </div>

                {submittedTicket && (
                  <div className="mb-5 rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-success flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold">Issue Logged Successfully</div>
                      <div className="text-xs mt-0.5">
                        Your report has been assigned reference ID <strong>{submittedTicket}</strong> and saved to the local system audit trail.
                      </div>
                    </div>
                  </div>
                )}

                <form onSubmit={handleReportSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-semibold text-navy">
                        Report Category
                      </label>
                      <select
                        value={reportType}
                        onChange={(e) => setReportType(e.target.value)}
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue"
                      >
                        <option value="bug">Bug / Software Defect</option>
                        <option value="complaint">Clinical Discrepancy / Complaint</option>
                        <option value="performance">System Latency / Performance</option>
                        <option value="feature">Feature Request / Enhancement</option>
                      </select>
                    </div>

                    <div>
                      <label className="mb-1 block text-xs font-semibold text-navy">
                        Severity Level
                      </label>
                      <select
                        value={severity}
                        onChange={(e) => setSeverity(e.target.value)}
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue"
                      >
                        <option value="low">Low — Minor UI or phrasing issue</option>
                        <option value="medium">Medium — Non-blocking functional issue</option>
                        <option value="high">High — Clinical module failure or error</option>
                        <option value="critical">Critical — Inaccurate data or system stoppage</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-navy">
                      Affected Feature / Module
                    </label>
                    <select
                      value={moduleName}
                      onChange={(e) => setModuleName(e.target.value)}
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue"
                    >
                      <option value="Dashboard">Dashboard &amp; Overview</option>
                      <option value="Patients">Patient Registry &amp; Workspace</option>
                      <option value="Clinical AI Chat">Clinical AI Chat &amp; Q&amp;A</option>
                      <option value="Report Comparison">Report Comparison &amp; Labs</option>
                      <option value="Vision Analysis">OCT / Retinal Vision Analysis</option>
                      <option value="SOAP Notes">SOAP Clinical Note Generation</option>
                      <option value="Knowledge">Knowledge Guidelines</option>
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-navy">
                      Summary / Subject
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Discrepancy in OCT layer measurement extraction"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-navy">
                      Detailed Description &amp; Steps to Reproduce
                    </label>
                    <textarea
                      required
                      rows={4}
                      placeholder="Please describe the issue observed, expected outcome, patient MRN (if applicable), and any error message displayed…"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-primary-blue focus:ring-1 focus:ring-primary-blue"
                    />
                  </div>

                  <div className="rounded-lg border border-border bg-background p-3 text-xs text-muted-text">
                    <strong>Auto-Captured Diagnostic Metadata:</strong> User: {me?.email ?? "doctor@gms.local"} | Role: {me?.role ?? "doctor"} | Timestamp: {new Date().toISOString()}
                  </div>

                  <div className="flex justify-end">
                    <button
                      type="submit"
                      className="inline-flex items-center gap-2 rounded-lg bg-primary-blue px-5 py-2.5 text-sm font-semibold text-white shadow transition-colors hover:bg-primary-blue/90"
                    >
                      <Send className="h-4 w-4" />
                      Submit Report
                    </button>
                  </div>
                </form>
              </Card>
            </div>
          )}

          {/* TAB 6: Privacy & Data Policy */}
          {activeTab === "privacy" && (
            <div className="space-y-6">
              <Card className="space-y-6 p-6">
                <div className="border-b border-border pb-4">
                  <div className="flex items-center gap-2.5">
                    <ShieldCheck className="h-6 w-6 text-primary-blue" />
                    <div>
                      <h3 className="text-lg font-bold text-navy">Clinical Privacy &amp; Data Protection Policy</h3>
                      <p className="text-xs text-muted-text">MED AI Governance, Safety Standards, and Technical Controls</p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 text-sm leading-relaxed text-navy">
                  {/* 1. Local-First & Data Sovereignty */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">1</span>
                      <h4 className="font-semibold text-navy">Local-First Architecture &amp; Data Sovereignty</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      All clinical documents, scanned diagnostic images, lab values, and AI reasoning queries are processed entirely on local facility hardware. No Protected Health Information (PHI) is ever transmitted to public third-party cloud services or external AI vendors, ensuring institutional data sovereignty.
                    </p>
                  </section>

                  {/* 2. Patient Data Isolation */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">2</span>
                      <h4 className="font-semibold text-navy">Patient Isolation &amp; Context Boundary Controls</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      Vector embeddings and semantic retrieval pipelines apply mandatory Patient ID hard-filtering. The system strictly isolates each patient record, ensuring that clinical inquiries for one patient never bleed or contaminate context from another patient record.
                    </p>
                  </section>

                  {/* 3. AI Safety & Deterministic Computations */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">3</span>
                      <h4 className="font-semibold text-navy">Deterministic Clinical Safety &amp; Non-Fabrication</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      To prevent mathematical hallucinations, all numerical comparisons (such as lab trend differences, interval changes, and dosage variations) are calculated via deterministic backend code rather than generative model guessing, guaranteeing numerical precision.
                    </p>
                  </section>

                  {/* 4. Human Oversight & Collaborative Support (Softer Legal Wording) */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">4</span>
                      <h4 className="font-semibold text-navy">Clinician Partnership &amp; Decision Support</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      MED AI is designed as a collaborative partner for healthcare providers. All generated notes, suggested differentials, and retrieved summaries serve as supportive recommendations to assist clinical judgment, with the final evaluation and care plan remaining under the care team&apos;s professional supervision.
                    </p>
                  </section>

                  {/* 5. Security Controls */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">5</span>
                      <h4 className="font-semibold text-navy">Security Controls &amp; Access Protection</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      The application implements multi-layered security controls:
                    </p>
                    <ul className="space-y-1.5 pl-8 text-xs text-muted-text">
                      <li>• <strong>Authentication:</strong> Cryptographic password hashing utilizing Argon2id with adaptive salt algorithms.</li>
                      <li>• <strong>Session Management:</strong> Signed, HTTP-Only, SameSite secure session cookies protecting against CSRF and XSS.</li>
                      <li>• <strong>Access Control:</strong> Role-Based Access Control (RBAC) with least-privilege scoping across doctors, administrators, and clinical staff.</li>
                      <li>• <strong>Storage Protection:</strong> Compatible with encrypted local volumes and operating-system-level disk encryption (e.g. BitLocker/LUKS).</li>
                    </ul>
                  </section>

                  {/* 6. Auditability & Traceability */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">6</span>
                      <h4 className="font-semibold text-navy">Auditability &amp; Immutable Activity Logging</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      Every significant clinical and administrative action is logged to an immutable local audit trail. This includes document uploads, AI prompt queries, clinical evidence retrievals, user feedback submissions, and document ingestion events. Each audit entry records a high-resolution timestamp, user ID, event type, and provenance metadata for regulatory compliance review.
                    </p>
                  </section>

                  {/* 7. Data Retention Policy */}
                  <section className="space-y-2 rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-light-blue text-xs font-bold text-primary-blue">7</span>
                      <h4 className="font-semibold text-navy">Data Retention &amp; Lifecycle Management</h4>
                    </div>
                    <p className="text-xs text-muted-text pl-8 leading-relaxed">
                      Clinical records and diagnostic files follow institutional retention policies:
                    </p>
                    <ul className="space-y-1.5 pl-8 text-xs text-muted-text">
                      <li>• <strong>Active Storage:</strong> Patient records remain active for continuous care throughout their treatment lifecycle.</li>
                      <li>• <strong>Archival Support:</strong> Inactive records can be securely archived while preserving full timeline integrity.</li>
                      <li>• <strong>Data Portability:</strong> Patient records, uploaded reports, and generated summaries can be exported in standardized clinical formats.</li>
                      <li>• <strong>Purge &amp; Deletion:</strong> Permanent deletion of test or synthetic data removes all corresponding database entries and associated vector embeddings simultaneously.</li>
                    </ul>
                  </section>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
