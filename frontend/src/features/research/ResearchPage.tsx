import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Globe, Lock, Search, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { useMe } from "@/api/hooks";
import type { AIRun } from "@/api/types";
import { Badge, Button, Card, CardHeader, Checkbox, EmptyState, Field, PageHeader, Skeleton, Textarea } from "@/components/ui";
import { Markdown } from "@/components/clinical/Markdown";
import { PatientPicker } from "@/components/clinical/PatientPicker";
import { api, ApiError } from "@/lib/api";

interface Providers { enabled: boolean; providers: { id: string; name: string; tier: string; url: string; enabled: boolean }[] }

export default function ResearchPage() {
  const { data: me } = useMe();
  const { data: prov, isLoading } = useQuery({ queryKey: ["research-providers"], queryFn: () => api<Providers>("/api/research/providers") });
  const [question, setQuestion] = useState("");
  const [patient, setPatient] = useState<{ id: string; full_name: string; mrn: string } | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [preview, setPreview] = useState<{ outbound_query: string; keywords: string; removed: number; categories: string[] } | null>(null);
  const [run, setRun] = useState<AIRun | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (prov) setSources(prov.providers.filter((p) => p.enabled).map((p) => p.id)); }, [prov]);
  useEffect(() => {
    if (question.trim().length < 3) return setPreview(null);
    const t = setTimeout(() => api<any>("/api/research/preview", { method: "POST", body: { question, patient_id: patient?.id } }).then(setPreview).catch(() => undefined), 300);
    return () => clearTimeout(t);
  }, [question, patient]);

  const search = async () => {
    setBusy(true); setRun(null);
    try { setRun(await api<AIRun>("/api/research/search", { method: "POST", body: { question, patient_id: patient?.id, sources } })); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Research failed"); } finally { setBusy(false); }
  };

  if (isLoading) return <Skeleton className="h-96" />;
  if (!prov?.enabled) {
    return (
      <div>
        <PageHeader title="Research" description="Search trusted external medical sources." />
        <Card><EmptyState icon={<Lock />} title="Research Mode is off" description="This deployment is local-only: nothing is sent to external services. An administrator can enable de-identified searches of PubMed, openFDA and ClinicalTrials.gov." action={me?.role === "admin" && <Button asChild><Link to="/settings/research">Configure research</Link></Button>} /></Card>
      </div>
    );
  }
  const o = run?.output as any;
  return (
    <div className="space-y-[var(--gap)]">
      <PageHeader title="Research" description="Search current external evidence. Queries are de-identified before they leave this system — you can see exactly what is sent." />
      <div className="grid gap-[var(--gap)] lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader title="Question" icon={<Search />} />
          <div className="card-pad space-y-4">
            <Textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Latest evidence on SGLT2 inhibitors in CKD without diabetes" />
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Patient context (optional)" hint="Their identifiers are removed from the query"><PatientPicker value={patient} onChange={setPatient} placeholder="No patient" /></Field>
              <Field label="Sources">
                <div className="flex flex-wrap gap-3 pt-1.5">
                  {prov.providers.filter((p) => p.enabled).map((p) => (
                    <label key={p.id} className="flex items-center gap-2 text-sm"><Checkbox checked={sources.includes(p.id)} onCheckedChange={(v) => setSources((s) => (v ? [...s, p.id] : s.filter((x) => x !== p.id)))} /> {p.name}</label>
                  ))}
                </div>
              </Field>
            </div>
            <div className="flex justify-end"><Button onClick={search} loading={busy} disabled={question.trim().length < 3 || !sources.length}><Globe /> Search sources</Button></div>
          </div>
        </Card>
        <Card className="h-fit">
          <CardHeader title="What will be sent" icon={<ShieldCheck />} description="Preview of the outbound query" />
          <div className="card-pad space-y-3 text-sm">
            {preview ? (
              <>
                <code className="block rounded-lg bg-muted px-3 py-2 text-xs leading-relaxed">{preview.keywords || preview.outbound_query}</code>
                <div className="flex flex-wrap gap-1.5">
                  {preview.removed > 0 ? <Badge tone="success"><ShieldCheck /> {preview.removed} identifier(s) removed</Badge> : <Badge>No identifiers detected</Badge>}
                  {preview.categories.map((c) => <Badge key={c} tone="outline">{c.replace("_", " ")}</Badge>)}
                </div>
              </>
            ) : <p className="text-muted-foreground">Type a question to preview.</p>}
          </div>
        </Card>
      </div>

      {busy && <Skeleton className="h-64" />}
      {o && (
        <div className="grid gap-[var(--gap)] lg:grid-cols-[1fr_400px]">
          <Card>
            <CardHeader title="Evidence synthesis" icon={<Sparkles />} description="AI summary of the retrieved sources — verify against the originals" />
            <div className="card-pad">
              {o.synthesis?.text ? <Markdown>{o.synthesis.text}</Markdown> : o.synthesis?.error ? <p className="text-sm text-danger">{o.synthesis.error}</p> : <p className="text-sm text-muted-foreground">No results to summarise.</p>}
              <div className="mt-4 flex flex-wrap gap-1.5 border-t pt-3">{o.providers.map((p: any) => <Badge key={p.provider} tone={p.status === "error" ? "danger" : "neutral"}>{p.name}: {p.status === "error" ? "failed" : `${p.count} results${p.status === "cached" ? " · cached" : ""}`}</Badge>)}</div>
            </div>
          </Card>
          <Card>
            <CardHeader title={`Sources (${o.results.length})`} icon={<Globe />} />
            <div className="card-pad max-h-[70vh] space-y-3 overflow-y-auto">
              {o.results.length === 0 ? <p className="text-sm text-muted-foreground">No sources matched.</p> : o.results.map((r: any) => (
                <div key={r.label} className="rounded-lg border p-3">
                  <div className="flex items-start gap-2"><Badge tone="warning" square className="font-mono">{r.label}</Badge><a href={r.url} target="_blank" rel="noreferrer" className="text-sm font-medium leading-snug hover:underline">{r.title}</a></div>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-[0.7rem] text-muted-foreground"><span>{r.source}</span>{r.evidence_type && <Badge tone="primary">{r.evidence_type}</Badge>}{r.date && <span>{r.date}</span>}{r.journal && <span className="truncate">· {r.journal}</span>}</div>
                  {r.snippet && <p className="mt-2 line-clamp-4 text-xs text-muted-foreground">{r.snippet}</p>}
                  <a href={r.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">Open <ExternalLink className="size-3" /></a>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
