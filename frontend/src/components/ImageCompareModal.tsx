import { useState } from "react";
import { Modal } from "@/components/Modal";
import { reportFileUrl, reportPreviewUrl, type ReportListItem } from "@/api/reports";
import { useCompareVision, type VisionCompareResponse } from "@/api/vision";
import { ApiError } from "@/api/client";

function thumbnailUrl(report: ReportListItem): string {
  return report.mime_type === "application/dicom" ? reportPreviewUrl(report.id) : reportFileUrl(report.id);
}

function FindingList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-text">{title}</div>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-navy">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** Previous vs. current image comparison (spec §61) — two images selected from this
 * patient's own analyzable reports, compared in one real joint vision-model call. */
export function ImageCompareModal({
  patientId,
  images,
  onClose,
}: {
  patientId: string;
  images: ReportListItem[];
  onClose: () => void;
}) {
  const [previousId, setPreviousId] = useState(images[0]?.id ?? "");
  const [currentId, setCurrentId] = useState(images[1]?.id ?? images[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisionCompareResponse | null>(null);
  const compare = useCompareVision(patientId);

  const previousReport = images.find((r) => r.id === previousId);
  const currentReport = images.find((r) => r.id === currentId);

  function runCompare() {
    setError(null);
    setResult(null);
    compare.mutate(
      { previous_report_id: previousId, current_report_id: currentId },
      {
        onSuccess: setResult,
        onError: (err) => setError(err instanceof ApiError ? err.message : "Comparison failed."),
      },
    );
  }

  return (
    <Modal title="Compare Images" onClose={onClose}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Previous</span>
            <select
              value={previousId}
              onChange={(e) => setPreviousId(e.target.value)}
              className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
            >
              {images.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-navy">Current</span>
            <select
              value={currentId}
              onChange={(e) => setCurrentId(e.target.value)}
              className="w-full rounded-md border border-border px-2 py-1.5 text-sm"
            >
              {images.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        {previousReport && currentReport && (
          <div className="grid grid-cols-2 gap-3">
            <img
              src={thumbnailUrl(previousReport)}
              alt={`Previous — ${previousReport.title}`}
              className="h-32 w-full rounded-md border border-border object-contain bg-light-blue/30"
            />
            <img
              src={thumbnailUrl(currentReport)}
              alt={`Current — ${currentReport.title}`}
              className="h-32 w-full rounded-md border border-border object-contain bg-light-blue/30"
            />
          </div>
        )}

        <button
          type="button"
          onClick={runCompare}
          disabled={compare.isPending || !previousId || !currentId || previousId === currentId}
          className="w-full rounded-md bg-primary-blue px-3 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
        >
          {compare.isPending ? "Comparing… this can take a while on CPU/local hardware" : "Compare"}
        </button>
        {previousId === currentId && (
          <p className="text-xs text-muted-text">Select two different reports to compare.</p>
        )}
        {error && <p className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}

        {result && (
          <div className="space-y-3 border-t border-border pt-3">
            <div className="grid grid-cols-2 gap-4">
              <FindingList title="Previous findings" items={result.previous_findings} />
              <FindingList title="Current findings" items={result.current_findings} />
            </div>
            <FindingList title="Observable changes" items={result.observable_changes} />
            <FindingList title="Differences" items={result.differences} />
            <FindingList title="Limitations" items={result.limitations} />

            {result.clinical_evidence.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-text">
                  Clinical evidence
                </div>
                <div className="mt-1 space-y-2">
                  {result.clinical_evidence.map((e, i) => (
                    <div key={i} className="rounded-md border border-border p-2 text-xs">
                      <div className="font-medium text-navy">
                        {e.source_title}
                        {e.page && <> · page {e.page}</>}
                        {e.section && <> · {e.section}</>}
                      </div>
                      <p className="mt-0.5 text-muted-text">&ldquo;{e.excerpt}&rdquo;</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
