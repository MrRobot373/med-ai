import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { FilePlus2, MessageSquarePlus, Monitor, Moon, Palette, Search, Settings2, Sun, UserPlus, Users } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { useMe } from "@/api/hooks";
import type { PatientListItem } from "@/api/types";
import { useAppearance } from "@/app/appearance";
import { Avatar, Kbd } from "@/components/ui";
import { api } from "@/lib/api";
import { NAV } from "./nav";

const PaletteContext = createContext<{ open: () => void }>({ open: () => undefined });
export const usePalette = () => useContext(PaletteContext);

const SETTINGS_PAGES = [
  ["profile", "Profile"], ["appearance", "Appearance"], ["branding", "Organization & branding"], ["models", "AI models"],
  ["embeddings", "Embeddings & reranking"], ["retrieval", "Retrieval tuning"], ["vector", "Vector store"],
  ["research", "Research sources"], ["users", "Users & roles"], ["security", "Security"], ["system", "System status"],
];

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { update } = useAppearance();
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 150);
    return () => clearTimeout(t);
  }, [search]);

  const patients = useQuery({
    queryKey: ["palette-patients", debounced],
    queryFn: () => api<PatientListItem[]>("/api/patients", { query: { q: debounced, limit: 8 } }),
    enabled: open,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = useCallback((to: string) => {
    setOpen(false);
    setSearch("");
    navigate(to);
  }, [navigate]);

  const run = (fn: () => void) => {
    setOpen(false);
    setSearch("");
    fn();
  };

  const item = "flex cursor-default items-center gap-2.5 rounded-md px-2.5 py-2 text-sm aria-selected:bg-muted [&_svg]:size-4 [&_svg]:text-muted-foreground";
  const group = "px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[0.68rem] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-muted-foreground";

  return (
    <PaletteContext.Provider value={{ open: () => setOpen(true) }}>
      {children}
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Command palette"
        shouldFilter={true}
        overlayClassName="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px]"
        contentClassName="fixed left-1/2 top-[14vh] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border bg-popover shadow-pop animate-scale-in"
      >
        <div className="flex items-center gap-2 border-b px-3.5">
          <Search className="size-4 text-muted-foreground" />
          <Command.Input value={search} onValueChange={setSearch} placeholder="Search patients, pages and actions…" className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
          <Kbd>Esc</Kbd>
        </div>
        <Command.List className="max-h-[60vh] overflow-y-auto p-1.5">
          <Command.Empty className="py-10 text-center text-sm text-muted-foreground">No results.</Command.Empty>
          {(patients.data?.length ?? 0) > 0 && (
            <Command.Group heading="Patients" className={group}>
              {patients.data!.map((p) => (
                <Command.Item key={p.id} value={`patient ${p.full_name} ${p.mrn}`} onSelect={() => go(`/patients/${p.id}`)} className={item}>
                  <Avatar name={p.full_name} size="xs" />
                  <span className="font-medium">{p.full_name}</span>
                  <span className="text-xs text-muted-foreground">{p.mrn}</span>
                  {p.age !== null && <span className="ml-auto text-xs text-muted-foreground">{p.age} y</span>}
                </Command.Item>
              ))}
            </Command.Group>
          )}
          <Command.Group heading="Actions" className={group}>
            {me?.role !== "viewer" && <Command.Item value="new patient register" onSelect={() => go("/patients?new=1")} className={item}><UserPlus /> Register new patient</Command.Item>}
            <Command.Item value="new conversation ask assistant question" onSelect={() => go("/assistant?new=1")} className={item}><MessageSquarePlus /> New assistant conversation</Command.Item>
            {me?.role === "admin" && <Command.Item value="upload knowledge document library" onSelect={() => go("/library?upload=1")} className={item}><FilePlus2 /> Add to knowledge library</Command.Item>}
            <Command.Item value="theme light" onSelect={() => run(() => update({ theme: "light" }))} className={item}><Sun /> Switch to light theme</Command.Item>
            <Command.Item value="theme dark" onSelect={() => run(() => update({ theme: "dark" }))} className={item}><Moon /> Switch to dark theme</Command.Item>
            <Command.Item value="theme system" onSelect={() => run(() => update({ theme: "system" }))} className={item}><Monitor /> Use system theme</Command.Item>
          </Command.Group>
          <Command.Group heading="Go to" className={group}>
            {NAV.flatMap((g) => g.items)
              .filter((i) => !i.roles || (me && i.roles.includes(me.role)))
              .map((i) => (
                <Command.Item key={i.to} value={`go ${i.label}`} onSelect={() => go(i.to)} className={item}>
                  <i.icon /> {i.label}
                  {i.shortcut && <span className="ml-auto text-[0.7rem] text-muted-foreground">{i.shortcut}</span>}
                </Command.Item>
              ))}
            <Command.Item value="go all patients list" onSelect={() => go("/patients")} className={item}><Users /> All patients</Command.Item>
          </Command.Group>
          <Command.Group heading="Settings" className={group}>
            {SETTINGS_PAGES.map(([id, label]) => (
              <Command.Item key={id} value={`settings ${label}`} onSelect={() => go(`/settings/${id}`)} className={item}>
                {id === "appearance" ? <Palette /> : <Settings2 />} {label}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
        <div className="flex items-center gap-3 border-t bg-subtle px-3.5 py-2 text-[0.7rem] text-muted-foreground">
          <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
          <span className="flex items-center gap-1"><Kbd>↵</Kbd> open</span>
          <span className="ml-auto flex items-center gap-1"><Kbd>Ctrl</Kbd><Kbd>K</Kbd> toggle</span>
        </div>
      </Command.Dialog>
    </PaletteContext.Provider>
  );
}
