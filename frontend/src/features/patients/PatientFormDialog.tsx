import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, UserPlus, UserRoundPen } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import type { Patient } from "@/api/types";
import { Button, Dialog, DialogContent, Field, Input, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

interface Match { id: string; mrn: string; name: string; date_of_birth: string | null; phone: string | null; score: number; strong: boolean; reasons: string[] }

const EMPTY = { mrn: "", first_name: "", last_name: "", date_of_birth: "", sex: "unknown", phone: "", email: "", address: "", blood_group: "", notes: "", tags: "" };

export function PatientFormDialog({ open, onOpenChange, patient }: { open: boolean; onOpenChange: (o: boolean) => void; patient?: Patient }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [matches, setMatches] = useState<Match[]>([]);
  const [blocked, setBlocked] = useState(false);
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

  // While registering, look for the same person already in the clinic.
  useEffect(() => {
    setBlocked(false);
    if (!open || patient) { setMatches([]); return; }
    const t = setTimeout(async () => {
      try { setMatches(await api<Match[]>("/api/patients/duplicates/check", { method: "POST", body: { first_name: form.first_name, last_name: form.last_name, date_of_birth: form.date_of_birth || null, phone: form.phone || null, email: form.email || null } })); }
      catch { setMatches([]); }
    }, 400);
    return () => clearTimeout(t);
  }, [open, patient, form.first_name, form.last_name, form.date_of_birth, form.phone, form.email]);

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent, allowDuplicate = false) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      ...form,
      ...(allowDuplicate ? { allow_duplicate: true } : {}),
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
      setBlocked(err instanceof ApiError && err.code === "possible_duplicate");
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
        footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>{blocked && <Button variant="secondary" loading={busy} onClick={(e) => submit(e as unknown as FormEvent, true)}>Register as a new patient anyway</Button>}<Button type="submit" form="patient-form" loading={busy}>{patient ? "Save changes" : "Register patient"}</Button></>}
      >
        <form id="patient-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          {error && <div className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-foreground sm:col-span-2">{error}</div>}
          {matches.length > 0 && (
            <div className="rounded-lg border border-warning/40 bg-warning-soft/50 p-3 text-sm sm:col-span-2" role="status">
              <div className="mb-1.5 flex items-center gap-1.5 font-semibold"><AlertTriangle className="size-4 text-warning" /> {matches.some((m) => m.strong) ? "This person may already be registered" : "Someone with a similar name is already registered"}</div>
              <ul className="space-y-1">
                {matches.slice(0, 3).map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span><b>{m.name}</b> · {m.mrn}{m.date_of_birth ? ` · born ${fmtDate(m.date_of_birth)}` : ""}{m.phone ? ` · ${m.phone}` : ""} <span className="text-xs text-muted-foreground">({m.reasons.join(", ")})</span></span>
                    <Link to={`/patients/${m.id}`} onClick={() => onOpenChange(false)} className="text-xs font-semibold text-primary hover:underline">Open this chart</Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Field label="First name" required htmlFor="fn"><Input id="fn" required value={form.first_name} onChange={set("first_name")} autoFocus /></Field>
          <Field label="Last name" required htmlFor="ln"><Input id="ln" required value={form.last_name} onChange={set("last_name")} /></Field>
          <Field label="MRN" required={!!patient} htmlFor="mrn" hint={patient ? "Must be unique" : "Leave blank to number automatically"}><Input id="mrn" required={!!patient} value={form.mrn} onChange={set("mrn")} placeholder={patient ? "e.g. MRN-20481" : "Automatic"} /></Field>
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
