import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUp, BookOpenText, Check, Copy, ListTree, PanelRightClose, PanelRightOpen, Sparkles, Square, ThumbsDown, ThumbsUp, User as UserIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useConversation, useMe } from "@/api/hooks";
import type { ChatMessage, Source, Trace } from "@/api/types";
import { Avatar, Badge, Button, Spinner, Tooltip } from "@/components/ui";
import { DocumentDrawer } from "@/components/clinical/DocumentDrawer";
import { Markdown } from "@/components/clinical/Markdown";
import { api, ApiError, streamSSE } from "@/lib/api";
import { cn, fmtRelative } from "@/lib/utils";
import { EvidencePanel } from "./EvidencePanel";

interface Pending { user: string; userId: string | null; text: string; stage: string; sources: Source[]; trace: Trace | null }

const PATIENT_SUGGESTIONS = [
  "Summarise what has changed since the previous visit",
  "Which results are outside the reference range, and how are they trending?",
  "Are there medication concerns given the current kidney function?",
  "What information is missing from this chart?",
];
const KNOWLEDGE_SUGGESTIONS = [
  "When should the apixaban dose be reduced?",
  "What are the four pillars of HFrEF therapy?",
  "How should levothyroxine be taken alongside iron supplements?",
  "Which drugs need dose review as eGFR falls?",
];

function AssistantBubble({ m, onCite, activeCite, selected, onSelect, onFeedback, onTrace }: { m: ChatMessage; onCite: (l: string) => void; activeCite: string | null; selected: boolean; onSelect: () => void; onFeedback: (r: "up" | "down" | null) => void; onTrace: () => void }) {
  const [copied, setCopied] = useState(false);
  const gen = m.trace?.generation;
  return (
    <div className="group flex gap-3" onClick={onSelect}>
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs"><Sparkles className="size-3.5" /></div>
      <div className={cn("min-w-0 flex-1 rounded-xl border px-4 py-3 transition-colors", selected ? "border-primary/30 bg-card" : "border-transparent bg-transparent")}>
        {m.status === "abstained" && <Badge tone="warning" className="mb-2"><AlertTriangle /> Insufficient evidence</Badge>}
        {m.status === "error" ? (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3 text-sm text-danger-foreground"><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><div className="font-medium">No answer was generated</div><div className="opacity-90">{m.trace?.error ?? "The AI service failed."} Nothing was answered without evidence.</div></div></div>
        ) : <Markdown onCite={onCite} activeCitation={selected ? activeCite : null}>{m.content}</Markdown>}
        {m.status !== "error" && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[0.7rem] text-muted-foreground">
            {m.citations.length > 0 && <Button size="xs" variant="ghost" className="h-6 px-1.5" onClick={(e) => { e.stopPropagation(); onSelect(); }}><BookOpenText /> {m.citations.filter((c) => c.cited).length} cited · {m.citations.length} retrieved</Button>}
            <Button size="xs" variant="ghost" className="h-6 px-1.5" onClick={(e) => { e.stopPropagation(); onTrace(); }}><ListTree /> Why this answer</Button>
            {gen?.citation_coverage != null && <span className="px-1">{Math.round(gen.citation_coverage * 100)}% cited</span>}
            {m.model && <span className="px-1">{m.model}{m.latency_ms ? ` · ${(m.latency_ms / 1000).toFixed(1)}s` : ""}</span>}
            <span className="px-1">{fmtRelative(m.created_at)}</span>
            <div className="ml-auto flex items-center gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
              <Tooltip content="Copy"><Button size="icon-xs" variant="ghost" onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(m.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check /> : <Copy />}</Button></Tooltip>
              <Tooltip content="Helpful"><Button size="icon-xs" variant="ghost" className={cn(m.feedback === "up" && "text-success")} onClick={(e) => { e.stopPropagation(); onFeedback(m.feedback === "up" ? null : "up"); }}><ThumbsUp /></Button></Tooltip>
              <Tooltip content="Not helpful"><Button size="icon-xs" variant="ghost" className={cn(m.feedback === "down" && "text-danger")} onClick={(e) => { e.stopPropagation(); onFeedback(m.feedback === "down" ? null : "down"); }}><ThumbsDown /></Button></Tooltip>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function UserBubble({ text, name }: { text: string; name: string }) {
  return (
    <div className="flex justify-end gap-3">
      <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tr-md bg-primary-soft px-4 py-2.5 text-[0.92rem] text-foreground">{text}</div>
      <Avatar name={name} size="sm" className="mt-0.5" />
    </div>
  );
}

export function ChatView({ conversationId, patient, onCreated, className }: { conversationId: string | null; patient?: { id: string; full_name: string; mrn: string } | null; onCreated?: (id: string) => void; className?: string }) {
  const { data: conv } = useConversation(conversationId);
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeCite, setActiveCite] = useState<string | null>(null);
  const [tab, setTab] = useState("sources");
  const [showEvidence, setShowEvidence] = useState(() => window.innerWidth > 1280);
  const [docId, setDocId] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const scopePatient = conv?.patient ?? patient ?? null;
  const messages = useMemo(() => (conv?.messages ?? []).filter((m) => m.id !== pending?.userId), [conv, pending?.userId]);
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const selected = messages.find((m) => m.id === selectedId) ?? lastAssistant;
  const evidenceSources = pending ? pending.sources : selected?.citations ?? [];
  const evidenceTrace = pending ? pending.trace : selected?.trace ?? null;

  useEffect(() => { setSelectedId(null); setActiveCite(null); }, [conversationId]);
  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: pending ? "auto" : "smooth" }); }, [messages.length, pending]);
  useEffect(() => {
    const el = textarea.current;
    if (el) { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 200)}px`; }
  }, [input]);

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || pending) return;
    setInput("");
    let id = conversationId;
    try {
      if (!id) {
        const c = await api<{ id: string }>("/api/conversations", { method: "POST", body: { patient_id: patient?.id ?? null } });
        id = c.id;
        qc.invalidateQueries({ queryKey: ["conversations"] });
        onCreated?.(c.id);
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start conversation");
      return;
    }
    setPending({ user: content, userId: null, text: "", stage: "Starting…", sources: [], trace: null });
    setTab("sources");
    abort.current = new AbortController();
    let finalId: string | null = null;
    try {
      await streamSSE(`/api/conversations/${id}/messages`, { content }, (event, data) => {
        if (event === "user_message") setPending((p) => p && { ...p, userId: data.id });
        else if (event === "status") setPending((p) => p && { ...p, stage: data.label });
        else if (event === "sources") setPending((p) => p && { ...p, sources: data.sources, trace: data.trace });
        else if (event === "token") setPending((p) => p && { ...p, text: p.text + data.text, stage: "" });
        else if (event === "done") finalId = data.id;
        else if (event === "error") { toast.error(data.message ?? "The assistant failed"); finalId = data.id ?? null; }
      }, abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== "AbortError") toast.error(e instanceof ApiError ? e.message : "Connection lost");
    }
    await qc.refetchQueries({ queryKey: ["conversation", id] });
    qc.invalidateQueries({ queryKey: ["conversations"] });
    setPending(null);
    if (finalId) setSelectedId(finalId);
  };

  const feedback = async (m: ChatMessage, rating: "up" | "down" | null) => {
    await api(`/api/messages/${m.id}/feedback`, { method: "POST", body: { rating } });
    qc.invalidateQueries({ queryKey: ["conversation", conversationId] });
    if (rating) toast.success("Thanks — feedback recorded for quality review");
  };

  const onCite = (m: ChatMessage) => (label: string) => { setSelectedId(m.id); setActiveCite(label); setTab("sources"); setShowEvidence(true); };
  const empty = messages.length === 0 && !pending;
  const suggestions = scopePatient ? PATIENT_SUGGESTIONS : KNOWLEDGE_SUGGESTIONS;

  return (
    <div className={cn("flex min-h-0 flex-1", className)}>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-4 py-2.5 md:px-6">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{conv?.title && conv.title !== "New conversation" ? conv.title : "New conversation"}</div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {scopePatient ? <><UserIcon className="size-3" /> Patient: <span className="font-medium text-foreground/80">{scopePatient.full_name}</span> · {scopePatient.mrn} · record + documents + library</> : <><BookOpenText className="size-3" /> Knowledge library only — no patient data</>}
            </div>
          </div>
          <Tooltip content={showEvidence ? "Hide evidence" : "Show evidence"}>
            <Button size="icon-sm" variant="ghost" onClick={() => setShowEvidence((s) => !s)} className="hidden lg:inline-flex">{showEvidence ? <PanelRightClose /> : <PanelRightOpen />}</Button>
          </Tooltip>
        </div>

        <div ref={scroller} className="flex-1 overflow-y-auto">
          {empty ? (
            <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-6 py-10 text-center">
              <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-card"><Sparkles className="size-5" /></div>
              <h2 className="text-lg font-semibold tracking-tight">{scopePatient ? `Ask about ${scopePatient.full_name}` : "Ask the clinical knowledge library"}</h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">Answers are built only from {scopePatient ? "this patient's record, their documents and" : ""} your knowledge library, with every statement linked to its source. When the evidence isn't there, the assistant says so.</p>
              <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-xl border bg-card px-3.5 py-3 text-left text-[0.82rem] shadow-xs transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card">{s}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 md:px-6">
              {messages.map((m) => m.role === "user"
                ? <UserBubble key={m.id} text={m.content} name={me?.full_name ?? "You"} />
                : <AssistantBubble key={m.id} m={m} onCite={onCite(m)} activeCite={activeCite} selected={selected?.id === m.id && !pending} onSelect={() => setSelectedId(m.id)} onFeedback={(r) => feedback(m, r)} onTrace={() => { setSelectedId(m.id); setTab("trace"); setShowEvidence(true); }} />)}
              {pending && (
                <>
                  <UserBubble text={pending.user} name={me?.full_name ?? "You"} />
                  <div className="flex gap-3">
                    <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Sparkles className="size-3.5" /></div>
                    <div className="min-w-0 flex-1 px-4 py-3">
                      {pending.stage && <div className="mb-2 flex items-center gap-2 text-[0.8rem] text-muted-foreground"><Spinner className="size-3.5" /> {pending.stage}{pending.sources.length > 0 && ` · ${pending.sources.length} sources found`}</div>}
                      {pending.text && <Markdown>{pending.text + " ▍"}</Markdown>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="border-t bg-background px-4 pb-4 pt-3 md:px-6">
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 pl-4 shadow-card transition-colors focus-within:border-primary/50 focus-within:ring-[3px] focus-within:ring-ring/10">
              <textarea
                ref={textarea} value={input} onChange={(e) => setInput(e.target.value)} rows={1}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input); } }}
                placeholder={scopePatient ? `Ask about ${scopePatient.full_name}'s record…` : "Ask a clinical question…"}
                className="max-h-[200px] min-h-[36px] flex-1 resize-none bg-transparent py-2 text-[0.92rem] outline-none placeholder:text-muted-foreground"
              />
              {pending ? (
                <Button type="button" size="icon" variant="secondary" onClick={() => abort.current?.abort()} aria-label="Stop"><Square className="!size-3.5 fill-current" /></Button>
              ) : (
                <Button type="submit" size="icon" disabled={!input.trim()} aria-label="Send" className="rounded-xl"><ArrowUp /></Button>
              )}
            </div>
            <p className="mt-2 text-center text-[0.7rem] text-muted-foreground">Enter to send · Shift+Enter for a new line · AI output is decision support and must be verified against the cited sources.</p>
          </form>
        </div>
      </div>

      {showEvidence && (
        <aside className="hidden w-[380px] shrink-0 border-l bg-subtle lg:block">
          <EvidencePanel sources={evidenceSources} trace={evidenceTrace} activeLabel={activeCite} tab={tab} onTab={setTab} onOpenDocument={setDocId} />
        </aside>
      )}
      <DocumentDrawer docId={docId} onClose={() => setDocId(null)} canWrite={me?.role !== "viewer"} />
    </div>
  );
}
