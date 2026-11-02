import { ArrowDownRight, ArrowUpRight, Check, FileText, FlaskConical, Minus, Plus } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { useInvalidatePatient, useTrends } from "@/api/hooks";
import type { TrendSeries } from "@/api/types";
import { Button, Card, CardHeader, Dialog, DialogContent, EmptyState, Field, Input, Skeleton, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { FlagBadge } from "@/components/clinical/badges";
import { Sparkline } from "@/components/clinical/Sparkline";
import { api, ApiError } from "@/lib/api";
import { cn, fmtDate, fmtNum, toDate } from "@/lib/utils";
import { useWorkspace } from "./context";

function TrendIcon({ s }: { s: TrendSeries }) {
  if (s.trend === "up") return <ArrowUpRight className="size-3.5" />;
  if (s.trend === "down") return <ArrowDownRight className="size-3.5" />;
  return <Minus className="size-3.5" />;
}

function AddResultDialog({ open, onOpenChange, patientId }: { open: boolean; onOpenChange: (o: boolean) => void; patientId: string }) {
  const [f, setF] = useState({ name: "", value: "", unit: "", low: "", high: "", at: new Date().toISOString().slice(0, 10) });
  const [busy, setBusy] = useState(false);
  const invalidate = useInvalidatePatient();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const num = Number(f.value);
      await api(`/api/patients/${patientId}/observations`, { method: "POST", body: {
        name: f.name, value_num: Number.isFinite(num) && f.value !== "" ? num : null, value_text: Number.isFinite(num) ? null : f.value,
        unit: f.unit || null, ref_low: f.low ? Number(f.low) : null, ref_high: f.high ? Number(f.high) : null, observed_at: new Date(f.at).toISOString(),
      } });
      toast.success("Result recorded");
      invalidate(patientId);
      onOpenChange(false);
    } catch (err) { toast.error(err instanceof ApiError ? err.message : "Could not save"); } finally { setBusy(false); }
  };
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Record a result" description="Manually entered values are labelled as such." icon={<FlaskConical />} footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" form="obs-form" loading={busy}>Save</Button></>}>
        <form id="obs-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Test" required className="sm:col-span-2"><Input required value={f.name} onChange={set("name")} placeholder="e.g. HbA1c" /></Field>
          <Field label="Value" required><Input required value={f.value} onChange={set("value")} /></Field>
          <Field label="Unit"><Input value={f.unit} onChange={set("unit")} placeholder="e.g. %" /></Field>
          <Field label="Reference low" hint="Only if stated by the lab"><Input type="number" step="any" value={f.low} onChange={set("low")} /></Field>
          <Field label="Reference high"><Input type="number" step="any" value={f.high} onChange={set("high")} /></Field>
          <Field label="Date"><Input type="date" value={f.at} onChange={set("at")} /></Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function ResultsTab() {
  const { patient, canWrite } = useWorkspace();
  const { data, isLoading } = useTrends(patient.id);
  const [selected, setSelected] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const invalidate = useInvalidatePatient();
  useEffect(() => { if (!selected && data?.length) setSelected(data[0].code); }, [data, selected]);
  const series = data?.find((s) => s.code === selected);
  const chartData = useMemo(() => (series?.points ?? []).filter((p) => p.value !== null).map((p) => ({ t: toDate(p.at)!.getTime(), value: p.value, flag: p.flag })), [series]);
  const ref = series?.points.slice().reverse().find((p) => p.ref_low !== null || p.ref_high !== null);

  const ack = async (id: string) => {
    try { await api(`/api/patients/${patient.id}/observations/${id}/acknowledge`, { method: "POST" }); toast.success("Acknowledged"); invalidate(patient.id); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };

  if (isLoading) return <div className="grid gap-4 lg:grid-cols-[320px_1fr]"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>;
  if (!data?.length) return <Card><EmptyState icon={<FlaskConical />} title="No results yet" description="Values are extracted automatically from uploaded lab reports, or can be recorded manually." action={canWrite && <Button onClick={() => setAddOpen(true)}><Plus /> Record result</Button>} /><AddResultDialog open={addOpen} onOpenChange={setAddOpen} patientId={patient.id} /></Card>;

  return (
    <div className="grid gap-[var(--gap)] lg:grid-cols-[340px_1fr]">
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">{data.length} tests</span>
          {canWrite && <Button size="xs" variant="secondary" onClick={() => setAddOpen(true)}><Plus /> Record</Button>}
        </div>
        <div className="max-h-[70vh] divide-y overflow-y-auto">
          {data.map((s) => {
            const values = s.points.map((p) => p.value).filter((v): v is number => v !== null);
            return (
              <button key={s.code} onClick={() => setSelected(s.code)} className={cn("flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/60", selected === s.code && "bg-primary-soft/60")}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5"><span className="truncate text-sm font-medium">{s.name}</span>{s.abnormal && <span className="size-1.5 rounded-full bg-danger" />}</div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="font-semibold text-foreground num">{s.latest.value !== null ? fmtNum(s.latest.value) : s.latest.text}</span>{s.unit}
                    {s.change !== null && <span className={cn("flex items-center num", s.trend === "up" ? "text-danger-foreground" : s.trend === "down" ? "text-info-foreground" : "")}><TrendIcon s={s} />{s.change > 0 ? "+" : ""}{fmtNum(s.change)}</span>}
                  </div>
                </div>
                <Sparkline values={values} tone={s.abnormal ? "danger" : "primary"} width={72} />
              </button>
            );
          })}
        </div>
      </Card>

      {series && (
        <div className="space-y-[var(--gap)]">
          <Card>
            <CardHeader
              title={series.name} icon={<FlaskConical />}
              description={<>{series.points.length} measurements{ref ? <> · reference {ref.ref_low ?? "—"} – {ref.ref_high ?? "—"} {series.unit} (as stated by the source)</> : " · no reference range stated in the source"}</>}
              actions={<FlagBadge flag={series.latest.flag} />}
            />
            <div className="h-72 px-2 pb-4 pt-5">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ left: -8, right: 16, top: 8 }}>
                  <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
                  {ref && <ReferenceArea ifOverflow="extendDomain" y1={ref.ref_low ?? undefined} y2={ref.ref_high ?? undefined} fill="hsl(var(--success))" fillOpacity={0.08} stroke="hsl(var(--success))" strokeOpacity={0.25} strokeDasharray="4 4" />}
                  <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={(t) => fmtDate(new Date(t), "d MMM yy")} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} padding={{ left: 20, right: 20 }} />
                  <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={48} />
                  <ChartTooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} labelFormatter={(t) => fmtDate(new Date(Number(t)))} formatter={(v) => [`${v} ${series.unit ?? ""}`, series.name]} />
                  <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2.25} isAnimationActive={false}
                    dot={(p: any) => <circle key={p.index} cx={p.cx} cy={p.cy} r={4.5} strokeWidth={2} stroke="hsl(var(--card))" fill={["high", "low", "abnormal"].includes(p.payload.flag) ? "hsl(var(--danger))" : "hsl(var(--primary))"} />} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card className="overflow-hidden">
            <Table>
              <THead><TR><TH>Date</TH><TH>Value</TH><TH>Range</TH><TH>Flag</TH><TH>Source</TH><TH /></TR></THead>
              <TBody>
                {series.points.slice().reverse().map((p) => (
                  <TR key={p.id}>
                    <TD className="whitespace-nowrap">{fmtDate(p.at)}</TD>
                    <TD className="whitespace-nowrap font-semibold num">{p.value !== null ? fmtNum(p.value) : p.text} <span className="font-normal text-muted-foreground">{series.unit}</span></TD>
                    <TD className="whitespace-nowrap text-muted-foreground num">{p.ref_low !== null || p.ref_high !== null ? `${p.ref_low ?? ""}–${p.ref_high ?? ""}` : "—"}</TD>
                    <TD><FlagBadge flag={p.flag} compact /></TD>
                    <TD className="max-w-[18rem]">
                      {p.document_id ? (
                        <Link to={`../documents?doc=${p.document_id}`} relative="path" className="group block text-xs" title={p.excerpt ?? ""}>
                          <span className="flex items-center gap-1 font-medium text-primary group-hover:underline"><FileText className="size-3" /> Report{p.page ? `, page ${p.page}` : ""}</span>
                          {p.excerpt && <span className="block truncate font-mono text-[0.68rem] text-muted-foreground">{p.excerpt}</span>}
                        </Link>
                      ) : <span className="text-xs text-muted-foreground">Entered manually</span>}
                    </TD>
                    <TD className="text-right">{canWrite && ["high", "low", "abnormal"].includes(p.flag ?? "") && (p.acknowledged ? <span className="text-xs text-muted-foreground">Acknowledged</span> : <Button size="xs" variant="secondary" onClick={() => ack(p.id)}><Check /> Acknowledge</Button>)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </Card>
        </div>
      )}
      <AddResultDialog open={addOpen} onOpenChange={setAddOpen} patientId={patient.id} />
    </div>
  );
}
