import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Globe, Info, Lock, Search } from "lucide-react";
import { Card } from "@/components/Card";
import { ApiError } from "@/api/client";
import {
  useResearchStatus,
  useResearchRuns,
  useRunResearchQuery,
  type DateRange,
  type ResearchCitation,
  type ResearchPayload,
  type WebSource,
} from "@/api/research";
import { usePatients } from "@/api/patients";
import { useCanWrite } from "@/api/auth";
import { useResearchMode } from "@/contexts/ResearchMode";
import { FeedbackControls } from "@/components/FeedbackControls";
import { ProvenanceDrawer } from "@/components/ProvenanceDrawer";
import { Bulleted, GenerationError, RunHistoryList, Section } from "@/pages/PatientWorkspace/ClinicalModules/shared";

const SOURCE_LABELS: { value: WebSource; label: string }[] = [
  { value: "pubmed", label: "PubMed" },
  { value: "fda", label: "FDA" },
  { value: "clinicaltrials", label: "ClinicalTrials.gov" },
  { value: "searxng", label: "General Web" },
];

function citationBadge(c: ResearchCitation): { label: string; className: string } {
  if (c.collection === "patient_documents") return { label: "PATIENT", className: "bg-primary-blue/10 text-primary-blue" };
  if (c.collection === "medical_knowledge") return { label: "LOCAL", className: "bg-light-blue text-navy" };
  return { label: c.section ?? "WEB", className: "bg-cyan/10 text-cyan" };
}

/** Deep-link state (Demo Scenarios, spec §89) — prefills the question/patient, same
 * "open the correct patient/context automatically" contract as chat's AskAINavState. */
export interface ResearchNavState {
  prefillQuestion: string;
  patientId?: string;
}

export default function ResearchPage() {
  const { data: status, isLoading: statusLoading } = useResearchStatus();
  const { data: patients } = usePatients("", false);
  const { setActive } = useResearchMode();
  const canWrite = useCanWrite();
  const location = useLocation();
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [patientId, setPatientId] = useState("");
  const [sources, setSources] = useState<Set<WebSource>>(new Set());
  const [dateRange, setDateRange] = useState<DateRange>("any");
  const [preferReviews, setPreferReviews] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [consentSeen, setConsentSeen] = useState(false);

  const run = useRunResearchQuery();
  const { data: history } = useResearchRuns();
  const payload = run.data?.payload as ResearchPayload | null | undefined;
  const [showProvenance, setShowProvenance] = useState(false);

  // Spec §128: header badge reflects real state — only while sources are actually
  // enabled on this page. Reverts on unmount so it never shows a stale "Research"
  // state after navigating away (spec §129's "not visually ambiguous").
  useEffect(() => {
    setActive(sources.size > 0);
    return () => setActive(false);
  }, [sources.size, setActive]);

  useEffect(() => {
    const navState = location.state as ResearchNavState | null;
    if (navState?.prefillQuestion) {
      setQuestion(navState.prefillQuestion);
      if (navState.patientId) setPatientId(navState.patientId);
      navigate(location.pathname, { replace: true, state: null });
    }
    // location.key (not just mount) so a second Demo Scenario click while already on
    // this page still gets consumed, not silently ignored by an already-mounted page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  function toggleSource(source: WebSource) {
    setSources((prev) => {
      const next = new Set(prev);
      if (next.has(source)) next.delete(source);
      else next.add(source);
      if (next.size > 0) setConsentSeen(true);
      return next;
    });
  }

  function submit() {
    if (!question.trim()) return;
    setError(null);
    run.mutate(
      { question, patient_id: patientId || undefined, sources: Array.from(sources), date_range: dateRange, prefer_reviews: preferReviews },
      { onError: (err) => setError(err instanceof ApiError ? err.message : "Could not complete the research query.") },
    );
  }

  if (statusLoading) {
    return <p className="text-sm text-muted-text">Checking Research Mode availability…</p>;
  }

  const researchEnabled = status?.enabled ?? false;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Globe className="h-5 w-5 text-primary-blue" />
        <h1 className="text-lg font-semibold text-navy">Research</h1>
      </div>
      <p className="text-sm text-muted-text">
        Local Knowledge is always searched. External sources are off by default — spec's privacy-first rule — and
        only queried when a source below is enabled.
      </p>

      {!researchEnabled && (
        <Card className="p-6 text-center text-sm text-muted-text">
          <Lock className="mx-auto mb-2 h-5 w-5 text-muted-text" />
          <p className="font-medium text-navy">Research Mode is not configured for this deployment.</p>
          <p className="mt-1">
            An administrator must set <code className="rounded bg-light-blue px-1 py-0.5">ENABLE_RESEARCH=true</code> to
            enable external evidence lookup. Local Knowledge questions can still be asked from Clinical AI or the
            Workflow page.
          </p>
        </Card>
      )}

      <Card className="space-y-4 p-4">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-navy">Question</span>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!canWrite}
            rows={2}
            placeholder="e.g. Recent evidence for SLT vs. topical therapy as first-line treatment for open-angle glaucoma"
            className="w-full rounded-md border border-border px-3 py-2 text-sm disabled:bg-light-blue/50"
          />
        </label>

        {patients && patients.length > 0 && (
          <label className="block max-w-sm text-sm">
            <span className="mb-1 block font-medium text-navy">Patient context (optional)</span>
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)} className="w-full rounded-md border border-border px-2 py-1.5 text-sm">
              <option value="">None — general question</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.mrn})
                </option>
              ))}
            </select>
          </label>
        )}

        <div>
          <span className="mb-1.5 block text-sm font-medium text-navy">Sources</span>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <label className="flex items-center gap-1.5 text-muted-text">
              <input type="checkbox" checked disabled />
              Local Knowledge
            </label>
            {SOURCE_LABELS.map((s) => {
              const available = researchEnabled && (status?.sources_available.includes(s.value) ?? false);
              return (
                <label key={s.value} className={`flex items-center gap-1.5 ${available ? "text-navy" : "text-muted-text"}`}>
                  <input type="checkbox" checked={sources.has(s.value)} disabled={!available} onChange={() => toggleSource(s.value)} />
                  {s.label}
                  {researchEnabled && !available && s.value === "searxng" && (
                    <span className="text-[11px] text-muted-text">(not running)</span>
                  )}
                </label>
              );
            })}
          </div>
        </div>

        {sources.size > 0 && consentSeen && (
          <p className="rounded-md bg-light-blue px-3 py-2 text-xs text-navy">
            🌐 External searches use de-identified clinical queries. Patient-identifying fields remain local.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <span className="mb-1.5 block text-sm font-medium text-navy">Date Range</span>
            <div className="flex flex-col gap-1 text-sm">
              {(["any", "5y", "1y"] as DateRange[]).map((r) => (
                <label key={r} className="flex items-center gap-1.5">
                  <input type="radio" checked={dateRange === r} onChange={() => setDateRange(r)} />
                  {r === "any" ? "Any" : r === "5y" ? "Last 5 Years" : "Last Year"}
                </label>
              ))}
            </div>
          </div>
          <div>
            <span className="mb-1.5 block text-sm font-medium text-navy">Evidence Preference</span>
            <div className="flex flex-col gap-1 text-sm">
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={preferReviews} onChange={() => setPreferReviews(true)} />
                Guidelines &amp; Reviews First
              </label>
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={!preferReviews} onChange={() => setPreferReviews(false)} />
                Any Relevant Evidence
              </label>
            </div>
          </div>
        </div>

        {canWrite ? (
          <button
            type="button"
            onClick={submit}
            disabled={run.isPending || !question.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            <Search className="h-3.5 w-3.5" />
            {run.isPending ? "Researching…" : "Research"}
          </button>
        ) : (
          <p className="text-xs text-muted-text">Running a research query requires a doctor or admin account.</p>
        )}
        {error && <GenerationError message={error} />}
      </Card>

      {payload && run.data && (
        <Card className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-2">
            <FeedbackControls targetType="clinical_module_run" targetId={run.data.id} />
            {payload.provenance && (
              <button
                type="button"
                onClick={() => setShowProvenance(true)}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-primary-blue hover:bg-light-blue"
              >
                <Info className="h-3.5 w-3.5" />
                Why This Answer?
              </button>
            )}
          </div>
          {showProvenance && payload.provenance && (
            <ProvenanceDrawer
              provenance={payload.provenance}
              webSourceCounts={payload.provenance.web_source_counts}
              onClose={() => setShowProvenance(false)}
            />
          )}
          <Section title="Evidence Summary">
            <p className="whitespace-pre-wrap text-sm text-navy">{payload.evidence_summary}</p>
          </Section>
          <Section title="Consensus">
            <p className="text-sm text-navy">{payload.consensus}</p>
          </Section>
          <Section title="Conflicting Evidence">
            <Bulleted items={payload.conflicting_evidence} />
          </Section>
          <Section title="Patient Applicability">
            <p className="text-sm text-navy">{payload.patient_applicability}</p>
          </Section>
          <Section title="Exclusion Criteria">
            <Bulleted items={payload.exclusion_criteria} />
          </Section>
          <Section title="Limitations">
            <Bulleted items={payload.limitations} />
          </Section>

          {payload.citations.length > 0 && (
            <Section title="References">
              <div className="space-y-2">
                {payload.citations.map((c) => {
                  const badge = citationBadge(c);
                  return (
                    <div key={c.label} className="rounded-md border border-border p-2 text-xs">
                      <div className="flex items-center gap-1.5 font-medium text-navy">
                        <span className="rounded bg-light-blue px-1.5 py-0.5 text-primary-blue">{c.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.className}`}>{badge.label}</span>
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer" className="truncate text-primary-blue hover:underline">
                            {c.source_title}
                          </a>
                        ) : (
                          <span className="truncate">{c.source_title}</span>
                        )}
                      </div>
                      <p className="mt-1 text-muted-text">&ldquo;{c.excerpt}&rdquo;</p>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}
        </Card>
      )}

      <RunHistoryList runs={history} moduleLabel="research" />
    </div>
  );
}
