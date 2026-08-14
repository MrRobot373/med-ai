import { useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import { useUploadReport } from "@/api/reports";
import { ApiError } from "@/api/client";

const ACCEPTED = ".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.dcm";

export function UploadReportModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [isDuplicate, setIsDuplicate] = useState(false);
  const upload = useUploadReport(patientId);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    upload.mutate(
      { file, allowDuplicate: isDuplicate },
      {
        onSuccess: () => onClose(),
        onError: (err) => {
          if (err instanceof ApiError && err.status === 409) {
            setIsDuplicate(true);
          }
        },
      },
    );
  }

  return (
    <Modal title="Upload Report" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="report_file" className="mb-1 block text-sm font-medium text-navy">
            File
          </label>
          <input
            id="report_file"
            type="file"
            accept={ACCEPTED}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setIsDuplicate(false);
            }}
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-navy file:mr-3 file:rounded-md file:border-0 file:bg-light-blue file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-blue"
          />
          <p className="mt-1 text-xs text-muted-text">PDF, DOCX, XLSX, PNG, JPEG, WebP, or DICOM (.dcm).</p>
        </div>

        {upload.isError && !isDuplicate && (
          <div role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
            {(upload.error as Error).message}
          </div>
        )}

        {isDuplicate && (
          <div role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
            An identical file has already been uploaded for this patient. Submit again to upload it anyway.
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium text-muted-text hover:bg-light-blue hover:text-navy"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!file || upload.isPending}
            className="rounded-md bg-primary-blue px-4 py-2 text-sm font-semibold text-white hover:bg-primary-blue/90 disabled:opacity-60"
          >
            {upload.isPending ? "Uploading…" : isDuplicate ? "Upload Anyway" : "Upload"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
