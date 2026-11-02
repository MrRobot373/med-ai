import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, ChevronDown, History, LayoutTemplate, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Dialog, DialogContent, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Field, Input, SwitchRow } from "@/components/ui";
import { useMe } from "@/api/hooks";
import { api, ApiError } from "@/lib/api";

export interface ShortItem { drug: string; dose?: string | null; frequency?: string | null; duration_days?: number | null; instructions?: string | null; route?: string | null; strength_mg?: number | null }
interface Template { id: string; name: string; diagnosis: string | null; advice: string | null; items: ShortItem[]; is_shared: boolean; mine: boolean; use_count: number }
interface Favourite extends ShortItem { id: string }
interface Frequent extends ShortItem { times: number }
interface Last { prescription_id: string | null; date?: string; diagnosis?: string | null; advice?: string | null; items: ShortItem[] }

/** Templates, favourite and most-used medicines, and "same as last visit" — they only fill the form; every line is still checked. */
export function RxShortcuts({ patientId, current, onApply }: {
  patientId: string; current: () => { diagnosis: string; advice: string; items: ShortItem[] };
  onApply: (items: ShortItem[], extra?: { diagnosis?: string | null; advice?: string | null }) => void;
}) {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { data: templates } = useQuery({ queryKey: ["rx-templates"], queryFn: () => api<Template[]>("/api/rx/templates") });
  const { data: favourites } = useQuery({ queryKey: ["rx-favourites"], queryFn: () => api<Favourite[]>("/api/rx/favourites") });
  const { data: frequent } = useQuery({ queryKey: ["rx-frequent"], queryFn: () => api<Frequent[]>("/api/rx/frequent?limit=8") });
  const { data: last } = useQuery({ queryKey: ["rx-last", patientId], queryFn: () => api<Last>(`/api/rx/patients/${patientId}/last`) });
  const [saveOpen, setSaveOpen] = useState(false);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [busy, setBusy] = useState(false);

  const quick = [...(favourites ?? []).map((f) => ({ ...f, fav: true })), ...(frequent ?? []).filter((f) => !(favourites ?? []).some((x) => x.drug.toLowerCase() === f.drug.toLowerCase())).map((f) => ({ ...f, fav: false }))].slice(0, 12);

  const useTemplate = (t: Template) => {
    onApply(t.items, { diagnosis: t.diagnosis, advice: t.advice });
    void api(`/api/rx/templates/${t.id}/used`, { method: "POST" }).then(() => qc.invalidateQueries({ queryKey: ["rx-templates"] }));
    toast.success(`Added “${t.name}”`, { description: "Each medicine is checked against this patient." });
  };
  const saveTemplate = async () => {
    const c = current();
    setBusy(true);
    try {
      await api("/api/rx/templates", { method: "POST", body: { name, diagnosis: c.diagnosis || null, advice: c.advice || null, is_shared: shared, items: c.items } });
      toast.success("Template saved"); setSaveOpen(false); setName(""); setShared(false);
      qc.invalidateQueries({ queryKey: ["rx-templates"] });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not save"); } finally { setBusy(false); }
  };
  const removeTemplate = async (t: Template) => {
    await api(`/api/rx/templates/${t.id}`, { method: "DELETE" });
    qc.invalidateQueries({ queryKey: ["rx-templates"] });
  };
  const hasItems = current().items.length > 0;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button size="sm" variant="secondary" className="rounded-full"><LayoutTemplate /> Templates <ChevronDown /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-80 w-72 overflow-auto">
            {templates?.length ? templates.map((t) => (
              <DropdownMenuItem key={t.id} onSelect={() => useTemplate(t)} className="flex items-start justify-between gap-2">
                <span className="min-w-0"><span className="block truncate font-medium">{t.name}</span><span className="block truncate text-xs text-muted-foreground">{t.items.map((i) => i.drug).join(", ")}{t.is_shared ? " · clinic" : ""}</span></span>
                {(t.mine || me?.role === "admin") && <button aria-label={`Delete ${t.name}`} className="shrink-0 rounded p-1 text-muted-foreground hover:text-danger" onClick={(e) => { e.stopPropagation(); void removeTemplate(t); }}><Trash2 className="size-3.5" /></button>}
              </DropdownMenuItem>
            )) : <div className="px-3 py-2 text-sm text-muted-foreground">No templates yet. Write a prescription you use often, then choose “Save as template”.</div>}
          </DropdownMenuContent>
        </DropdownMenu>
        {last?.prescription_id && (
          <Button size="sm" variant="secondary" className="rounded-full" onClick={() => { onApply(last.items, { diagnosis: last.diagnosis, advice: last.advice }); toast.success("Copied the last prescription", { description: `From ${last.date}. Review the doses, then continue.` }); }}>
            <History /> Same as last visit
          </Button>
        )}
        <Button size="sm" variant="ghost" className="rounded-full" disabled={!hasItems} onClick={() => { setName(current().diagnosis); setSaveOpen(true); }}><BookmarkPlus /> Save as template</Button>
      </div>
      {quick.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[0.72rem] text-muted-foreground">Quick add:</span>
          {quick.map((q) => (
            <button key={q.drug} onClick={() => onApply([q])} title={[q.dose, q.frequency, q.duration_days ? `${q.duration_days} days` : ""].filter(Boolean).join(" · ")}
              className="inline-flex items-center gap-1 rounded-full border bg-card px-2.5 py-1 text-[0.76rem] hover:border-primary/50 hover:bg-primary-soft/40">
              {q.fav && <Star className="size-3 fill-warning text-warning" />}{q.drug}
            </button>
          ))}
        </div>
      )}
      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent size="sm" title="Save as template" description="Saves the medicines, diagnosis and advice on this prescription." footer={<><Button variant="secondary" onClick={() => setSaveOpen(false)}>Cancel</Button><Button onClick={saveTemplate} loading={busy} disabled={!name.trim()}>Save template</Button></>}>
          <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acute gastritis" autoFocus /></Field>
          {me?.role === "admin" && <SwitchRow label="Share with the whole clinic" description="Every clinician can use it" checked={shared} onCheckedChange={setShared} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Star toggle for one medicine row. */
export function FavouriteStar({ item }: { item: ShortItem }) {
  const qc = useQueryClient();
  const { data: favourites } = useQuery({ queryKey: ["rx-favourites"], queryFn: () => api<Favourite[]>("/api/rx/favourites") });
  const existing = favourites?.find((f) => f.drug.toLowerCase() === item.drug.trim().toLowerCase());
  const toggle = async () => {
    try {
      if (existing) await api(`/api/rx/favourites/${existing.id}`, { method: "DELETE" });
      else await api("/api/rx/favourites", { method: "POST", body: { drug: item.drug.trim(), dose: item.dose, frequency: item.frequency, duration_days: item.duration_days, instructions: item.instructions || null } });
      qc.invalidateQueries({ queryKey: ["rx-favourites"] });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };
  return <Button size="icon-xs" variant="ghost" aria-label={existing ? "Remove from favourites" : "Add to favourites"} title={existing ? "Remove from favourites" : "Add to favourites with this dose"} onClick={toggle}><Star className={existing ? "fill-warning text-warning" : ""} /></Button>;
}
