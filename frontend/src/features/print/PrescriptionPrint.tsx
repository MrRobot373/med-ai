import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useEffect } from "react";
import { useParams } from "react-router";
import { useBranding } from "@/api/hooks";
import type { PrescriptionDetail } from "@/api/types";
import { BrandMark } from "@/components/layout/BrandMark";
import { Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, sexLabel } from "@/lib/utils";

const FREQ: Record<string, string> = { OD: "Once a day", BD: "Twice a day", TDS: "Three times a day", QID: "Four times a day", HS: "At bedtime", SOS: "When needed", STAT: "Immediately, once", Weekly: "Once a week" };

/** A4 prescription for the patient. Opens in its own tab; the browser's print dialog does the rest. */
export default function PrescriptionPrint() {
  const { id = "" } = useParams();
  const { data: rx, error } = useQuery({ queryKey: ["rx-print", id], queryFn: () => api<PrescriptionDetail>(`/api/prescriptions/${id}`) });
  const { data: brand } = useBranding();
  useEffect(() => { if (rx) document.title = `Prescription — ${rx.patient.name}`; }, [rx]);
  if (error) return <div className="p-10 text-sm">This prescription could not be loaded. Sign in and try again.</div>;
  if (!rx) return <div className="flex justify-center p-16"><Spinner className="size-5" /></div>;
  const v = rx.encounter?.vitals ?? {};
  return (
    <div className="min-h-screen bg-slate-100 py-8 print:bg-white print:py-0">
      <div className="no-print mx-auto mb-4 flex max-w-[210mm] justify-end px-4"><Button variant="strong" className="rounded-full" onClick={() => window.print()}><Printer /> Print</Button></div>
      <article className="mx-auto min-h-[297mm] max-w-[210mm] bg-white p-[14mm] text-[11pt] text-slate-900 shadow-xl print:shadow-none">
        <header className="flex items-start justify-between border-b-2 border-slate-900 pb-4">
          <div className="flex items-center gap-3">
            <BrandMark showText={false} />
            <div>
              <div className="text-lg font-bold">{brand?.organization || brand?.product_name}</div>
              <div className="text-xs text-slate-500">{brand?.tagline}</div>
            </div>
          </div>
          <div className="text-right text-sm">
            <div className="font-semibold">{rx.clinician?.name ?? "—"}</div>
            <div className="text-xs text-slate-500">{rx.clinician?.email}</div>
          </div>
        </header>
        <section className="mt-4 grid grid-cols-[1fr_auto] gap-2 rounded-md bg-slate-50 p-3 text-sm">
          <div><b>{rx.patient.name}</b> · {rx.patient.age ?? "—"} y · {sexLabel(rx.patient.sex)} · {rx.patient.mrn}{rx.patient.phone ? ` · ${rx.patient.phone}` : ""}</div>
          <div className="text-right">Date: <b>{fmtDate(rx.finalized_at ?? rx.date)}</b></div>
          {(v.bp || v.hr || v.weight_kg || v.temp_f) && <div className="col-span-2 text-xs text-slate-600">{[v.bp && `BP ${v.bp}`, v.hr && `Pulse ${v.hr}`, v.temp_f && `Temp ${v.temp_f}°F`, v.weight_kg && `Weight ${v.weight_kg} kg`].filter(Boolean).join(" · ")}</div>}
        </section>
        {rx.encounter?.reason && <p className="mt-4 text-sm"><b>Complaint:</b> {rx.encounter.reason}</p>}
        {rx.diagnosis && <p className="mt-1 text-sm"><b>Diagnosis:</b> {rx.diagnosis}</p>}
        <div className="mt-5 text-3xl font-serif font-bold italic">℞</div>
        <table className="mt-2 w-full border-collapse text-sm">
          <thead><tr className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500"><th className="py-2 pr-2">#</th><th className="py-2 pr-2">Medicine</th><th className="py-2 pr-2">Dose</th><th className="py-2 pr-2">When</th><th className="py-2 pr-2">Days</th><th className="py-2">Instructions</th></tr></thead>
          <tbody>
            {rx.items.map((i, n) => (
              <tr key={i.id} className="border-b border-slate-200 align-top">
                <td className="py-2.5 pr-2 text-slate-500">{n + 1}</td>
                <td className="py-2.5 pr-2 font-semibold">{i.drug}{i.generic && <div className="text-[9pt] font-normal text-slate-500">{i.generic.split("+").map((g) => g.replace(/_/g, " ")).join(" + ")}</div>}</td>
                <td className="py-2.5 pr-2">{i.dose}</td>
                <td className="py-2.5 pr-2">{i.frequency}<div className="text-[9pt] text-slate-500">{FREQ[i.frequency] ?? ""}</div></td>
                <td className="py-2.5 pr-2">{i.duration_days ?? "—"}</td>
                <td className="py-2.5">{i.instructions}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rx.advice && <section className="mt-6 text-sm"><b>Advice</b><p className="mt-1 whitespace-pre-line">{rx.advice}</p></section>}
        {rx.follow_up_date && <p className="mt-4 text-sm"><b>Follow-up:</b> {fmtDate(rx.follow_up_date, "EEEE, d MMMM yyyy")} — please bring your reports.</p>}
        <footer className="mt-16 flex items-end justify-between text-xs text-slate-500">
          <span>Prescription ID {rx.id.slice(0, 8).toUpperCase()}</span>
          <span className="w-48 border-t border-slate-400 pt-1 text-center">Signature</span>
        </footer>
      </article>
    </div>
  );
}
