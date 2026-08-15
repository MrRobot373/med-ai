import { useState } from "react";
import { AlertTriangle, FileText, Pill, ScanEye } from "lucide-react";
import { Card } from "@/components/Card";
import { StatusChip, type StatusTone } from "@/components/StatusChip";
import { ReconciliationModal } from "@/components/ReconciliationModal";
import {
  reportFileUrl,
  reportPreviewUrl,
  useArchiveReport,
  useConfirmReportMatch,
  type ReportListItem,
} from "@/api/reports";
import { useCanWrite } from "@/api/auth";

const REPORT_TYPE_LABEL: Record<ReportListItem["report_type"], string> = {
  lab_report: "Lab Report",
  imaging_report: "Imaging Report",
  consultation_note: "Consultation Note",
  discharge_summary: "Discharge Summary",
  referral_letter: "Referral Letter",
  other: "Other",
};

const INGESTION_TONE: Record<ReportListItem["ingestion_status"], StatusTone> = {
  queued: "loading",
  processing: "loading",
  completed: "ok",
  failed: "down",
};

const INGESTION_LABEL: Record<ReportListItem["ingestion_status"], string> = {
  queued: "Queued",
  processing: "Processing…",
  completed: "Processed",
  failed: "Processing failed",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ReportCard({ report, patientName }: { report: ReportListItem; patientName: string }) {
  const canWrite = useCanWrite();
  const confirmMatch = useConfirmReportMatch(report.patient_id);
  const archive = useArchiveReport(report.patient_id);
  const [showReconciliation, setShowReconciliation] = useState(false);

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-light-blue text-primary-blue">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-medium text-navy">{report.title}</div>
            <div className="text-xs text-muted-text">
              {REPORT_TYPE_LABEL[report.report_type]}
              {report.report_date && <> · {report.report_date}</>}
              {" · "}
              {formatSize(report.file_size_bytes)}
              {report.ocr_used && " · OCR"}
            </div>
          </div>
        </div>
        <StatusChip label={INGESTION_LABEL[report.ingestion_status]} tone={INGESTION_TONE[report.ingestion_status]} />
      </div>

      {report.ingestion_status === "failed" && (
        <div className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-xs text-danger">
          Processing failed. The original file is still safely stored — try re-uploading, or contact support if
          this repeats.
        </div>
      )}

      {report.patient_match_status === "mismatch" && (
        <div className="mt-3 rounded-md border border-danger/30 bg-danger/5 p-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-danger">
            <AlertTriangle className="h-4 w-4" />
            Patient mismatch detected
          </div>
          <p className="mt-1 text-xs text-muted-text">
            Current patient: <span className="font-medium text-navy">{patientName}</span>
            <br />
            Detected in document: <span className="font-medium text-navy">{report.source_patient_name ?? "—"}</span>
          </p>
          <p className="mt-1 text-xs text-muted-text">This document was not attached automatically.</p>
          {canWrite && (
            <div className="mt-2 flex gap-3">
              <button
                type="button"
                onClick={() => confirmMatch.mutate(report.id)}
                disabled={confirmMatch.isPending}
                className="text-xs font-medium text-primary-blue hover:underline disabled:opacity-60"
              >
                Confirm this is {patientName}
              </button>
              <button
                type="button"
                onClick={() => archive.mutate(report.id)}
                disabled={archive.isPending}
                className="text-xs font-medium text-danger hover:underline disabled:opacity-60"
              >
                Cancel (archive)
              </button>
            </div>
          )}
        </div>
      )}

      {report.patient_match_status === "unconfirmed" && report.ingestion_status === "completed" && (
        <p className="mt-3 text-xs text-muted-text">Patient identity not confirmed from document content.</p>
      )}

      <div className="mt-3 flex items-center gap-3 border-t border-border pt-3 text-xs font-medium">
        <a href={reportFileUrl(report.id)} target="_blank" rel="noreferrer" className="text-primary-blue hover:underline">
          View
        </a>
        {report.mime_type === "application/dicom" && (
          <a
            href={reportPreviewUrl(report.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary-blue hover:underline"
          >
            <ScanEye className="h-3.5 w-3.5" />
            Preview
          </a>
        )}
        {report.ingestion_status === "completed" && report.patient_match_status !== "mismatch" && (
          <button
            type="button"
            onClick={() => setShowReconciliation(true)}
            className="inline-flex items-center gap-1 text-primary-blue hover:underline"
          >
            <Pill className="h-3.5 w-3.5" />
            Reconcile Medications
          </button>
        )}
        {canWrite && report.patient_match_status !== "mismatch" && (
          <button
            type="button"
            onClick={() => archive.mutate(report.id)}
            disabled={archive.isPending}
            className="ml-auto text-muted-text hover:text-danger disabled:opacity-60"
          >
            Archive
          </button>
        )}
      </div>

      {showReconciliation && <ReconciliationModal reportId={report.id} onClose={() => setShowReconciliation(false)} />}
    </Card>
  );
}
