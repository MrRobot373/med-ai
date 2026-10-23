import { useQueryClient } from "@tanstack/react-query";
import { UserPlus, UserRoundPen } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import type { Patient } from "@/api/types";
import { Button, Dialog, DialogContent, Field, Input, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

const EMPTY = { mrn: "", first_name: "", last_name: "", date_of_birth: "", sex: "unknown", phone: "", email: "", address: "", blood_group: "", notes: "", tags: "" };

export function PatientFormDialog({ open, onOpenChange, patient }: { open: boolean; onOpenChange: (o: boolean) => void; patient?: Patient }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setError(null);
      setForm(patient ? {
        mrn: patient.mrn, first_name: patient.first_name, last_name: patient.last_name, date_of_birth: patient.date_of_birth ?? "",
        sex: patient.sex, phone: patient.phone ?? "", email: patient.email ?? "", address: patient.address ?? "",
        blood_group: patient.blood_group ?? "", notes: patient.notes ?? "", tags: patient.tags.join(", "),
      } : EMPTY);
    }
  }, [open, patient]);

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      ...form,
      date_of_birth: form.date_of_birth || null,
      tags: form.tags.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean),
      ...Object.fromEntries(["phone", "email", "address", "blood_group", "notes"].map((k) => [k, (form as any)[k] || null])),
    };
    try {
      const saved = await api<Patient>(patient ? `/api/patients/${patient.id}` : "/api/patients", { method: patient ? "PATCH" : "POST", body });
      qc.invalidateQueries({ queryKey: ["patients"] });
      qc.invalidateQueries({ queryKey: ["patient", saved.id] });
      toast.success(patient ? "Patient updated" : `${saved.full_name} registered`);
      onOpenChange(false);
      if (!patient) navigate(`/patients/${saved.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        size="lg" icon={patient ? <UserRoundPen /> : <UserPlus />}
        title={patient ? "Edit patient" : "Register patient"}
        description={patient ? "Update demographic details." : "Create a new chart. Clinical history can be added after."}
        footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" form="patient-form" loading={busy}>{patient ? "Save changes" : "Register patient"}</Button></>}
      >
        <form id="patient-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          {error && <div className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-foreground sm:col-span-2">{error}</div>}
          <Field label="First name" required htmlFor="fn"><Input id="fn" required value={form.first_name} onChange={set("first_name")} autoFocus /></Field>
          <Field label="Last name" required htmlFor="ln"><Input id="ln" required value={form.last_name} onChange={set("last_name")} /></Field>
          <Field label="MRN" required htmlFor="mrn" hint="Must be unique"><Input id="mrn" required value={form.mrn} onChange={set("mrn")} placeholder="e.g. MRN-20481" /></Field>
          <Field label="Date of birth" htmlFor="dob"><Input id="dob" type="date" value={form.date_of_birth} onChange={set("date_of_birth")} /></Field>
          <Field label="Sex">
            <Select value={form.sex} onValueChange={(v) => setForm((f) => ({ ...f, sex: v }))} options={[{ value: "female", label: "Female" }, { value: "male", label: "Male" }, { value: "other", label: "Other" }, { value: "unknown", label: "Not recorded" }]} />
          </Field>
          <Field label="Blood group" htmlFor="bg"><Input id="bg" value={form.blood_group} onChange={set("blood_group")} placeholder="e.g. O+" /></Field>
          <Field label="Phone" htmlFor="ph"><Input id="ph" value={form.phone} onChange={set("phone")} /></Field>
          <Field label="Email" htmlFor="em"><Input id="em" type="email" value={form.email} onChange={set("email")} /></Field>
          <Field label="Address" htmlFor="ad" className="sm:col-span-2"><Input id="ad" value={form.address} onChange={set("address")} /></Field>
          <Field label="Tags" htmlFor="tg" hint="Comma-separated, e.g. diabetes, high-risk" className="sm:col-span-2"><Input id="tg" value={form.tags} onChange={set("tags")} /></Field>
          <Field label="Notes" htmlFor="nt" className="sm:col-span-2"><Textarea id="nt" value={form.notes} onChange={set("notes")} rows={3} /></Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
