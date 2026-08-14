import { useState } from "react";
import { Upload } from "lucide-react";
import { Card } from "@/components/Card";
import { ReportCard } from "@/components/ReportCard";
import { UploadReportModal } from "@/components/UploadReportModal";
import { usePatientContext } from "@/layouts/PatientWorkspace";
import { usePatientReports } from "@/api/reports";
import { useCanWrite } from "@/api/auth";

export default function ReportsTab() {
  const patient = usePatientContext();
  const { data: reports, isLoading, isError, error } = usePatientReports(patient.id);
  const canWrite = useCanWrite();
  const [showUpload, setShowUpload] = useState(false);
  const patientName = patient.preferred_name || `${patient.first_name} ${patient.last_name}`;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-navy">Reports</h2>
        {canWrite && (
          <button
            type="button"
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-blue/90"
          >
            <Upload className="h-3.5 w-3.5" />
            Upload Report
          </button>
        )}
      </div>

      {isError && (
        <Card className="border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          Could not load reports: {(error as Error).message}
        </Card>
      )}

      {isLoading && <p className="text-sm text-muted-text">Loading reports…</p>}

      {!isLoading && reports?.length === 0 && (
        <Card className="p-8 text-center text-sm text-muted-text">
          No reports uploaded yet.
          {canWrite && " Upload a PDF, DOCX, XLSX, image, or DICOM file to get started."}
        </Card>
      )}

      <div className="space-y-3">
        {reports?.map((report) => (
          <ReportCard key={report.id} report={report} patientName={patientName} />
        ))}
      </div>

      {showUpload && <UploadReportModal patientId={patient.id} onClose={() => setShowUpload(false)} />}
    </div>
  );
}
