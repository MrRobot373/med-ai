import { Eye, RefreshCw } from "lucide-react";
import { StatusChip, type StatusTone } from "@/components/StatusChip";
import { useAnalyzeReport, useVisionAnalysis, type VisionAnalysisOut } from "@/api/vision";
import { useCanWrite } from "@/api/auth";
import type { ReportListItem } from "@/api/reports";

const STATUS_TONE: Record<VisionAnalysisOut["status"], StatusTone> = {
  success: "ok",
  failed: "down",
  not_applicable: "degraded",
};

const STATUS_LABEL: Record<VisionAnalysisOut["status"], string> = {
  success: "Analyzed",
  failed: "Analysis failed",
  not_applicable: "Not applicable",
};

function FindingList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-text">{title}</div>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-navy">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Structured vision findings for one image/DICOM report (spec §58-60). Ingestion
 * already runs this automatically for analyzable reports (same as OCR) — this panel
 * mostly just displays that result; the button is for a first run that hasn't
 * finished yet, or a retry after a failure.
 */
export function VisionAnalysisPanel({ report }: { report: ReportListItem }) {
  const canWrite = useCanWrite();
  const { data: analysis, isLoading } = useVisionAnalysis(report.id);
  const analyze = useAnalyzeReport(report.id);

  if (isLoading) {
    return <p className="text-xs text-muted-text">Checking vision analysis…</p>;
  }

  if (!analysis) {
    return canWrite ? (
      <button
        type="button"
        onClick={() => analyze.mutate()}
        disabled={analyze.isPending}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary-blue hover:underline disabled:opacity-60"
      >
        <Eye className="h-3.5 w-3.5" />
        {analyze.isPending ? "Analyzing…" : "Run Vision Analysis"}
      </button>
    ) : null;
  }

  return (
    <div className="space-y-2 rounded-md border border-border bg-light-blue/40 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-navy">
          <Eye className="h-3.5 w-3.5" />
          Vision Analysis
          {analysis.image_type && <span className="font-normal text-muted-text">— {analysis.image_type}</span>}
        </div>
        <StatusChip label={STATUS_LABEL[analysis.status]} tone={STATUS_TONE[analysis.status]} />
      </div>

      {analysis.status === "failed" && (
        <p className="text-xs text-danger">{analysis.analysis_error ?? "Analysis did not complete successfully."}</p>
      )}
      {analysis.status === "not_applicable" && (
        <p className="text-xs text-muted-text">{analysis.analysis_error ?? "This file cannot be analyzed."}</p>
      )}

      {analysis.status === "success" && (
        <div className="space-y-2">
          <FindingList title="Observations" items={analysis.observations} />
          <FindingList title="Measurements visible" items={analysis.measurements_visible} />
          <FindingList title="Clinical entities" items={analysis.clinical_entities} />
          <FindingList title="Quality limitations" items={analysis.quality_limitations} />
          <FindingList title="Uncertainties" items={analysis.uncertainties} />
          {analysis.observations.length === 0 &&
            analysis.measurements_visible.length === 0 &&
            analysis.clinical_entities.length === 0 && (
              <p className="text-xs text-muted-text">No specific findings were reported for this image.</p>
            )}
        </div>
      )}

      {canWrite && (
        <button
          type="button"
          onClick={() => analyze.mutate()}
          disabled={analyze.isPending}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary-blue hover:underline disabled:opacity-60"
        >
          <RefreshCw className="h-3 w-3" />
          {analyze.isPending ? "Re-analyzing…" : "Re-analyze"}
        </button>
      )}
    </div>
  );
}
