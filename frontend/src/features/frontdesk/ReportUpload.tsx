import { useQueryClient } from "@tanstack/react-query";
import { FileUp, Link2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useOrders } from "@/api/hooks";
import type { DocumentItem } from "@/api/types";
import { Dropzone } from "@/components/clinical/Dropzone";
import { Field, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

/** Upload a report the patient brought in, optionally against the doctor's open order. */
export function ReportUpload({ patientId, compact }: { patientId: string; compact?: boolean }) {
  const { data: orders } = useOrders(patientId, "ordered");
  const [orderId, setOrderId] = useState("auto");
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const upload = async (files: File[]) => {
    setBusy(true);
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      if (orderId !== "auto") form.append("order_id", orderId);
      try {
        await api<DocumentItem>(`/api/patients/${patientId}/documents`, { method: "POST", body: form });
        toast.success(`Uploaded ${file.name}`, { description: orderId === "auto" ? "It will be matched to the doctor's order if one fits." : "Linked to the order — the doctor will see it for review." });
      } catch (e) {
        toast.error(`${file.name}: ${e instanceof ApiError ? e.message : "upload failed"}`);
      }
    }
    setBusy(false);
    setOrderId("auto");
    qc.invalidateQueries({ queryKey: ["patient", patientId] });
    qc.invalidateQueries({ queryKey: ["today"] });
  };
  const open = orders ?? [];
  return (
    <div className="space-y-3">
      <Field label="This report is for" hint={open.length ? "Pick the test the doctor ordered, or let it match automatically." : "No open orders — the report is filed and the doctor is notified."}>
        <Select value={orderId} onValueChange={setOrderId} options={[
          { value: "auto", label: "Match automatically", description: "Recommended" },
          ...open.map((o) => ({ value: o.id, label: o.test_name, description: `Ordered ${fmtDate(o.ordered_at)}` })),
        ]} />
      </Field>
      <Dropzone compact={compact} onFiles={upload}>
        <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-card text-primary shadow-xs ring-1 ring-border">{orderId === "auto" ? <FileUp className="size-5" /> : <Link2 className="size-5" />}</div>
        <p className="text-sm font-medium">{busy ? "Uploading…" : <>Drop the report or scan here, or <span className="text-primary">browse</span></>}</p>
        <p className="mt-1 text-xs text-muted-foreground">PDF, photos of printed reports, Word, DICOM</p>
      </Dropzone>
    </div>
  );
}
