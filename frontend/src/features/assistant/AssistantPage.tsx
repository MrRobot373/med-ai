import { useQueryClient } from "@tanstack/react-query";
import { BookOpenText, MessageSquarePlus, MoreHorizontal, Pencil, Pin, PinOff, Search, Trash2, User as UserIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { useConversations } from "@/api/hooks";
import type { Conversation } from "@/api/types";
import { Button, Dialog, DialogContent, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, EmptyState, Field, Input, Segmented, Skeleton } from "@/components/ui";
import { PatientPicker } from "@/components/clinical/PatientPicker";
import { api } from "@/lib/api";
import { cn, toDate } from "@/lib/utils";
import { ChatView } from "./ChatView";

function bucket(c: Conversation) {
  if (c.pinned) return "Pinned";
  const d = toDate(c.updated_at)!;
  const days = (Date.now() - d.getTime()) / 86_400_000;
  return days < 1 ? "Today" : days < 7 ? "Previous 7 days" : days < 30 ? "Previous 30 days" : "Older";
}

export function ConversationList({ items, activeId, onSelect, loading }: { items: Conversation[]; activeId: string | null; onSelect: (id: string) => void; loading?: boolean }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [title, setTitle] = useState("");
  const groups = useMemo(() => {
    const out: Record<string, Conversation[]> = {};
    for (const c of items) (out[bucket(c)] ||= []).push(c);
    return ["Pinned", "Today", "Previous 7 days", "Previous 30 days", "Older"].filter((g) => out[g]).map((g) => [g, out[g]] as const);
  }, [items]);
  const patch = async (c: Conversation, body: object) => { await api(`/api/conversations/${c.id}`, { method: "PATCH", body }); qc.invalidateQueries({ queryKey: ["conversations"] }); qc.invalidateQueries({ queryKey: ["conversation", c.id] }); };
  const remove = async (c: Conversation) => { await api(`/api/conversations/${c.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["conversations"] }); toast.success("Conversation deleted"); if (c.id === activeId) navigate("/assistant"); };

  if (loading) return <div className="space-y-2 p-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div>;
  if (!items.length) return <EmptyState compact title="No conversations" description="Start one with the button above." />;
  return (
    <div className="space-y-4 p-2">
      {groups.map(([g, list]) => (
        <div key={g}>
          <div className="text-label px-2 pb-1 !text-[0.65rem]">{g}</div>
          {list.map((c) => (
            <div key={c.id} className={cn("group flex items-center rounded-lg pr-1 transition-colors", c.id === activeId ? "bg-primary-soft text-primary-soft-foreground" : "hover:bg-muted")}>
              <button onClick={() => onSelect(c.id)} className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2 text-left text-[0.82rem]">
                {c.patient_id ? <UserIcon className="size-3.5 shrink-0 opacity-60" /> : <BookOpenText className="size-3.5 shrink-0 opacity-60" />}
                <span className="truncate">{c.title}</span>
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild><button className="rounded p-1 opacity-0 hover:bg-card group-hover:opacity-100 data-[state=open]:opacity-100" aria-label="Conversation actions"><MoreHorizontal className="size-3.5" /></button></DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onSelect={() => { setRenaming(c); setTitle(c.title); }}><Pencil /> Rename</DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => patch(c, { pinned: !c.pinned })}>{c.pinned ? <><PinOff /> Unpin</> : <><Pin /> Pin</>}</DropdownMenuItem>
                  <DropdownMenuItem danger onSelect={() => remove(c)}><Trash2 /> Delete</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>
      ))}
      <Dialog open={!!renaming} onOpenChange={(o) => !o && setRenaming(null)}>
        <DialogContent size="sm" title="Rename conversation" footer={<><Button variant="secondary" onClick={() => setRenaming(null)}>Cancel</Button><Button onClick={async () => { if (renaming && title.trim()) await patch(renaming, { title: title.trim() }); setRenaming(null); }}>Save</Button></>}>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function AssistantPage() {
  const { conversationId = null } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { data, isLoading } = useConversations();
  const [q, setQ] = useState("");
  const [newOpen, setNewOpen] = useState(params.get("new") === "1");
  const [scope, setScope] = useState<"knowledge" | "patient">("knowledge");
  const [patient, setPatient] = useState<{ id: string; full_name: string; mrn: string } | null>(null);
  const [draft, setDraft] = useState<{ patient: typeof patient } | null>(null);
  // The chat view's identity must survive the URL change that happens when a draft
  // conversation is created mid-stream; it only changes on an explicit switch.
  const createdRef = useRef<string | null>(null);
  const [viewKey, setViewKey] = useState(conversationId ?? "draft");
  useEffect(() => { if (conversationId && conversationId !== createdRef.current) setViewKey(conversationId); }, [conversationId]);

  useEffect(() => { if (params.get("new") === "1") { setNewOpen(true); params.delete("new"); setParams(params, { replace: true }); } }, [params, setParams]);
  const items = (data ?? []).filter((c) => !q || c.title.toLowerCase().includes(q.toLowerCase()));

  const start = () => {
    setDraft({ patient: scope === "patient" ? patient : null });
    setNewOpen(false);
    createdRef.current = null;
    setViewKey(`draft-${Date.now()}`);
    navigate("/assistant");
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-h-0">
      <aside className="hidden w-72 shrink-0 flex-col border-r bg-subtle md:flex">
        <div className="space-y-2 border-b p-3">
          <Button className="w-full" onClick={() => setNewOpen(true)}><MessageSquarePlus /> New conversation</Button>
          <Input icon={<Search />} placeholder="Search conversations" value={q} onChange={(e) => setQ(e.target.value)} className="[&_input]:h-8" />
        </div>
        <div className="flex-1 overflow-y-auto"><ConversationList items={items} activeId={conversationId} onSelect={(id) => { setDraft(null); navigate(`/assistant/${id}`); }} loading={isLoading} /></div>
      </aside>
      <ChatView
        key={viewKey}
        conversationId={conversationId}
        patient={draft?.patient ?? null}
        onCreated={(id) => { createdRef.current = id; navigate(`/assistant/${id}`, { replace: true }); }}
      />
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent title="New conversation" description="Choose what the assistant may draw on." icon={<MessageSquarePlus />} footer={<><Button variant="secondary" onClick={() => setNewOpen(false)}>Cancel</Button><Button onClick={start} disabled={scope === "patient" && !patient}>Start</Button></>}>
          <div className="space-y-4">
            <Segmented value={scope} onChange={setScope} options={[{ value: "knowledge", label: "Knowledge library", icon: <BookOpenText /> }, { value: "patient", label: "A specific patient", icon: <UserIcon /> }]} />
            {scope === "patient" ? (
              <Field label="Patient" hint="The assistant will only ever see this patient's record and documents, plus the shared library."><PatientPicker value={patient} onChange={setPatient} allowClear={false} /></Field>
            ) : <p className="text-sm text-muted-foreground">General clinical questions answered from your organisation's knowledge library. No patient data is used.</p>}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
