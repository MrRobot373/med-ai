import type { ReactNode } from "react";
import type { ProvenanceOut } from "@/api/chat";
import { Modal } from "@/components/Modal";

// Spec §80's "technical drawer" — real, observed retrieval-stage counts, laid out in
// the same Patient context / Local RAG / Web / Final evidence / Generation model
// grouping the spec's own example shows. "This is provenance, not hidden
// chain-of-thought" — every number here traces back to a real stage size computed in
// rag/pipeline.py's RetrievalStats, never a fabricated figure.
function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-muted-text">{label}</span>
      <span className="font-medium text-navy">{value}</span>
    </div>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-border p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-text">{title}</h3>
      <div className="mt-1 divide-y divide-border">{children}</div>
    </div>
  );
}

export function ProvenanceDrawer({
  provenance,
  webSourceCounts,
  onClose,
}: {
  provenance: ProvenanceOut;
  webSourceCounts?: Record<string, number>;
  onClose: () => void;
}) {
  const hasWeb = webSourceCounts && Object.keys(webSourceCounts).length > 0;

  return (
    <Modal title="Why This Answer?" onClose={onClose}>
      <div className="space-y-3">
        <Group title="Patient Context">
          <Row label="Structured records used" value={provenance.patient_context_records} />
        </Group>

        <Group title="Local RAG">
          <Row label="Dense candidates" value={provenance.dense_candidates} />
          <Row label="BM25 candidates" value={provenance.bm25_candidates} />
          <Row label="Fused candidates" value={provenance.fused_candidates} />
          <Row label="Reranked" value={provenance.reranked} />
        </Group>

        {hasWeb && (
          <Group title="Web">
            {Object.entries(webSourceCounts!).map(([source, count]) => (
              <Row key={source} label={source} value={count} />
            ))}
          </Group>
        )}

        <Group title="Final Evidence">
          <Row label="Sources offered to the model" value={provenance.final_evidence} />
        </Group>

        <Group title="Generation Model">
          <Row label="Model" value={provenance.generation_model ?? "Not recorded"} />
        </Group>

        <p className="text-[11px] text-muted-text">
          This is retrieval provenance — real, observed pipeline counts. It never exposes hidden model reasoning.
        </p>
      </div>
    </Modal>
  );
}
