import { AlertTriangle, LayoutGrid, List, Search, UserPlus, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useMe, usePatients } from "@/api/hooks";
import type { PatientListItem } from "@/api/types";
import { Avatar, Badge, Button, Card, EmptyState, Input, PageHeader, Segmented, Select, Skeleton, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtRelative, sexLabel } from "@/lib/utils";
import { PatientFormDialog } from "./PatientFormDialog";

function ConditionChips({ items, max = 2 }: { items: string[]; max?: number }) {
  if (!items.length) return <span className="text-xs text-muted-foreground">No active problems</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.slice(0, max).map((c) => <Badge key={c} tone="neutral" className="max-w-[14rem] truncate">{c}</Badge>)}
      {items.length > max && <Badge tone="outline">+{items.length - max}</Badge>}
    </div>
  );
}

function PatientCardItem({ p }: { p: PatientListItem }) {
  return (
    <Link to={`/patients/${p.id}`}>
      <Card className="card-pad group h-full transition-all hover:-translate-y-0.5 hover:shadow-pop">
        <div className="flex items-start gap-3">
          <Avatar name={p.full_name} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-semibold group-hover:text-primary">{p.full_name}</span>
              {p.open_alerts > 0 && <Badge tone="danger"><AlertTriangle /> {p.open_alerts}</Badge>}
            </div>
            <div className="text-xs text-muted-foreground">{p.mrn} · {p.age ?? "—"} y · {sexLabel(p.sex)}</div>
          </div>
        </div>
        <div className="mt-4"><ConditionChips items={p.active_conditions} max={3} /></div>
        <div className="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
          <span>Last visit {fmtRelative(p.last_encounter_at)}</span>
          <span>{p.document_count} documents</span>
        </div>
      </Card>
    </Link>
  );
}

export default function PatientsPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("active");
  const [tag, setTag] = useState("all");
  const [sort, setSort] = useState("recent");
  const [view, setView] = useState<"table" | "grid">(() => (localStorage.getItem("gms.patients.view") as "table" | "grid") || "table");
  const [formOpen, setFormOpen] = useState(params.get("new") === "1");
  const { data: me } = useMe();
  const navigate = useNavigate();
  const { data, isLoading } = usePatients({ q: debounced, status, tag: tag === "all" ? undefined : tag, sort });
  const { data: tags } = useQuery({ queryKey: ["patient-tags"], queryFn: () => api<{ tag: string; count: number }[]>("/api/patients/tags") });

  useEffect(() => { const t = setTimeout(() => setDebounced(q), 200); return () => clearTimeout(t); }, [q]);
  useEffect(() => { if (params.get("new") === "1") setFormOpen(true); }, [params]);
  useEffect(() => { try { localStorage.setItem("gms.patients.view", view); } catch { /* ignore */ } }, [view]);

  return (
    <div>
      <PageHeader
        title="Patients"
        description="Search the patient directory, open a chart, or register someone new."
        actions={me?.role !== "viewer" && <Button onClick={() => setFormOpen(true)}><UserPlus /> Register patient</Button>}
      />
      <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center">
        <Input icon={<Search />} placeholder="Search by name or MRN…" value={q} onChange={(e) => setQ(e.target.value)} className="lg:max-w-sm" />
        <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
          <Select size="sm" className="w-36" value={status} onValueChange={setStatus} options={[{ value: "active", label: "Active" }, { value: "archived", label: "Archived" }, { value: "all", label: "All statuses" }]} />
          <Select size="sm" className="w-40" value={tag} onValueChange={setTag} options={[{ value: "all", label: "All tags" }, ...(tags ?? []).map((t) => ({ value: t.tag, label: `${t.tag} (${t.count})` }))]} />
          <Select size="sm" className="w-44" value={sort} onValueChange={setSort} options={[{ value: "recent", label: "Recently active" }, { value: "name", label: "Name A–Z" }, { value: "mrn", label: "MRN" }, { value: "created", label: "Newest charts" }]} />
          <Segmented size="sm" value={view} onChange={setView} options={[{ value: "table", label: "", icon: <List /> }, { value: "grid", label: "", icon: <LayoutGrid /> }]} />
        </div>
      </div>

      {isLoading ? (
        <Card className="p-4"><div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div></Card>
      ) : (data ?? []).length === 0 ? (
        <Card><EmptyState icon={<Users />} title={q ? "No matching patients" : "No patients yet"} description={q ? "Try a different name or MRN." : "Register your first patient to get started."} action={me?.role !== "viewer" && !q && <Button onClick={() => setFormOpen(true)}><UserPlus /> Register patient</Button>} /></Card>
      ) : view === "grid" ? (
        <div className="grid gap-[var(--gap)] sm:grid-cols-2 xl:grid-cols-3">{data!.map((p) => <PatientCardItem key={p.id} p={p} />)}</div>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <THead><TR><TH>Patient</TH><TH>Age / sex</TH><TH>Active problems</TH><TH>Last visit</TH><TH className="text-right">Alerts</TH></TR></THead>
            <TBody>
              {data!.map((p) => (
                <TR key={p.id} data-clickable="true" onClick={() => navigate(`/patients/${p.id}`)}>
                  <TD>
                    <div className="flex items-center gap-3">
                      <Avatar name={p.full_name} size="sm" />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{p.full_name}</div>
                        <div className="text-xs text-muted-foreground">{p.mrn}{p.tags.length ? ` · ${p.tags.slice(0, 2).join(", ")}` : ""}</div>
                      </div>
                    </div>
                  </TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{p.age ?? "—"} y · {sexLabel(p.sex)}</TD>
                  <TD><ConditionChips items={p.active_conditions} /></TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{fmtRelative(p.last_encounter_at)}</TD>
                  <TD className="text-right">{p.open_alerts > 0 ? <Badge tone="danger"><AlertTriangle /> {p.open_alerts}</Badge> : <span className="text-xs text-muted-foreground">—</span>}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
      <PatientFormDialog open={formOpen} onOpenChange={(o) => { setFormOpen(o); if (!o && params.get("new")) { params.delete("new"); setParams(params, { replace: true }); } }} />
    </div>
  );
}
