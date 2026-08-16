import { Eye, FileText, Library } from "lucide-react";
import type { CitationOut, EvidenceQuality, GroundingClaim } from "@/api/chat";

const SOURCE_ICON: Record<CitationOut["source_type"], typeof FileText> = {
  patient_report: FileText,
  patient_vision: Eye,
  knowledge_document: Library,
  external: Library,
};

// Deterministic labels, never a fabricated confidence percentage (spec §54) — these
// map 1:1 to app/chat/evidence_quality.py's EvidenceQuality enum.
const QUALITY_STYLE: Record<EvidenceQuality, { label: string; className: string }> = {
  strong: { label: "Strong evidence", className: "bg-success/10 text-success" },
  moderate: { label: "Moderate evidence", className: "bg-primary-blue/10 text-primary-blue" },
  limited: { label: "Limited evidence", className: "bg-amber-100 text-amber-700" },
  insufficient: { label: "Insufficient evidence", className: "bg-danger/10 text-danger" },
};

const GROUNDING_STYLE: Record<GroundingClaim["status"], string> = {
  supported: "text-success",
  partially_supported: "text-amber-600",
  unsupported: "text-danger",
};

const GROUNDING_LABEL: Record<GroundingClaim["status"], string> = {
  supported: "Supported",
  partially_supported: "Partially supported",
  unsupported: "Unsupported",
};

export function EvidencePanel({
  citations,
  evidenceQuality,
  grounding,
}: {
  citations: CitationOut[] | undefined;
  evidenceQuality: EvidenceQuality | null | undefined;
  grounding: GroundingClaim[] | null | undefined;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <h2 className="text-sm font-semibold text-navy">Evidence</h2>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        {!evidenceQuality && (
          <p className="text-xs text-muted-text">
            Evidence supporting the assistant's most recent answer will appear here.
          </p>
        )}

        {evidenceQuality && (
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${QUALITY_STYLE[evidenceQuality].className}`}
          >
            {QUALITY_STYLE[evidenceQuality].label}
          </span>
        )}

        {grounding && grounding.length > 0 && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">Claim check</h3>
            <ul className="space-y-1.5">
              {grounding.map((claim, i) => (
                <li key={i} className="text-xs">
                  <span className={`font-medium ${GROUNDING_STYLE[claim.status]}`}>
                    {GROUNDING_LABEL[claim.status]}
                  </span>
                  <span className="text-muted-text"> — {claim.claim}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {citations && citations.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">Sources</h3>
            {citations.map((c) => {
              const SourceIcon = SOURCE_ICON[c.source_type];
              return (
                <div key={c.id} id={`evidence-${c.label}`} className="scroll-mt-3 rounded-md border border-border p-2.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-navy">
                    <span className="rounded bg-light-blue px-1.5 py-0.5 text-primary-blue">{c.label}</span>
                    <SourceIcon className="h-3.5 w-3.5 text-muted-text" />
                    <span className="truncate">{c.source_title}</span>
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted-text">
                    {c.page && <>Page {c.page}</>}
                    {c.page && c.section && " · "}
                    {c.section}
                  </div>
                  <p className="mt-1.5 line-clamp-4 text-xs text-muted-text">&ldquo;{c.source_excerpt}&rdquo;</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
