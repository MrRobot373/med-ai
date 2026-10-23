import { Database, Gauge, PlugZap, SlidersHorizontal } from "lucide-react";
import { Badge, Button, Field, Input, Segmented, Slider, SwitchRow } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useSection } from "../useSection";
import { NumberField, SaveBar, SecretField, SettingsCard, TestResult } from "../parts";

const PROFILES = [
  { id: "fast", name: "Fast", text: "Small candidate pools, compact context. Best for local GPUs." },
  { id: "balanced", name: "Balanced", text: "More candidates and context for harder questions." },
  { id: "thorough", name: "Thorough", text: "Large pools and context. Needs a big context window." },
  { id: "custom", name: "Custom", text: "Your own numbers below." },
];

function SliderField({ label, value, onChange, min, max, step = 1, hint }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number; hint?: string }) {
  return (
    <Field label={<span className="flex w-full justify-between"><span>{label}</span><span className="font-mono text-xs text-muted-foreground">{value}</span></span>} hint={hint}>
      <Slider value={[value]} min={min} max={max} step={step} onValueChange={([v]) => onChange(v)} />
    </Field>
  );
}

export function RetrievalSection() {
  const s = useSection("retrieval");
  if (!s.server) return null;
  const d = s.draft;
  const pickProfile = (id: string) => s.set(id === "custom" ? { profile: "custom" } : { profile: id, ...(s.data?.profiles?.[id] ?? {}) });
  const num = (k: string) => (v: number) => s.set({ [k]: v, profile: "custom" });
  return (
    <SettingsCard
      title={<span className="flex items-center gap-2"><SlidersHorizontal className="size-4 text-primary" /> Retrieval tuning</span>}
      description="How evidence is found and packed into the prompt. Test changes in Knowledge library → Retrieval playground."
      footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} />}
    >
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {PROFILES.map((p) => (
          <button key={p.id} onClick={() => pickProfile(p.id)} className={cn("rounded-xl border p-3 text-left transition-all hover:border-primary/50", d.profile === p.id && "border-primary bg-primary-soft/50 ring-2 ring-primary/15")}>
            <div className="flex items-center gap-2 text-sm font-semibold"><Gauge className="size-4 text-primary" /> {p.name}</div>
            <p className="mt-1 text-xs text-muted-foreground">{p.text}</p>
          </button>
        ))}
      </div>
      <div className="grid gap-x-8 gap-y-5 border-t pt-5 md:grid-cols-2">
        <SliderField label="Dense candidates" value={d.dense_top_k} onChange={num("dense_top_k")} min={1} max={200} hint="Nearest neighbours from the vector index" />
        <SliderField label="BM25 candidates" value={d.lexical_top_k} onChange={num("lexical_top_k")} min={0} max={200} hint="Keyword matches — 0 disables lexical search" />
        <SliderField label="Fused candidates" value={d.fusion_top_k} onChange={num("fusion_top_k")} min={1} max={200} hint="Kept after reciprocal-rank fusion (sent to the reranker)" />
        <SliderField label="Final passages" value={d.final_top_k} onChange={num("final_top_k")} min={1} max={40} hint="Maximum passages given to the model" />
        <SliderField label="Dense weight" value={d.dense_weight} onChange={(v) => s.set({ dense_weight: v })} min={0} max={3} step={0.1} />
        <SliderField label="BM25 weight" value={d.lexical_weight} onChange={(v) => s.set({ lexical_weight: v })} min={0} max={3} step={0.1} />
        <Field label="Context budget" hint="Upper bound on evidence tokens per answer"><NumberField value={d.context_budget_tokens} onChange={num("context_budget_tokens")} min={500} step={500} suffix="tokens" /></Field>
        <Field label="RRF constant (k)" hint="Higher flattens rank differences; 60 is standard"><NumberField value={d.rrf_k} onChange={(v) => s.set({ rrf_k: v })} min={1} /></Field>
        <Field label="Minimum rerank score" hint="Drop passages scoring below this (reranker only)"><NumberField value={d.min_rerank_score} onChange={(v) => s.set({ min_rerank_score: v })} step={0.05} /></Field>
        <Field label="Conversation memory" hint="Previous turns replayed to the model"><NumberField value={d.history_turns} onChange={(v) => s.set({ history_turns: v })} min={0} max={20} suffix="turns" /></Field>
      </div>
      <div className="grid gap-4 border-t pt-5 md:grid-cols-2">
        <Field label="Chunk size" hint="Applies to newly processed documents"><NumberField value={d.chunk_size_tokens} onChange={(v) => s.set({ chunk_size_tokens: v })} min={100} max={4000} suffix="tokens" /></Field>
        <Field label="Chunk overlap"><NumberField value={d.chunk_overlap_tokens} onChange={(v) => s.set({ chunk_overlap_tokens: v })} min={0} max={1000} suffix="tokens" /></Field>
      </div>
      <SwitchRow label="Include the knowledge library in patient conversations" description="When off, patient chats use only the record and that patient's documents." checked={d.include_knowledge_in_patient_chat} onCheckedChange={(v) => s.set({ include_knowledge_in_patient_chat: v })} />
    </SettingsCard>
  );
}

export function VectorSection() {
  const s = useSection("vector_store");
  if (!s.server) return null;
  const d = s.draft;
  return (
    <SettingsCard
      title={<span className="flex items-center gap-2"><Database className="size-4 text-primary" /> Vector store</span>}
      description="Qdrant holds the embedding vectors. Embedded mode needs nothing else to run; server mode scales and supports payload indexes."
      badge={<Badge tone="primary">{s.server.mode === "embedded" ? "Embedded" : "Server"}</Badge>}
      footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} extra={<Button size="sm" variant="secondary" onClick={() => s.test("vector_store")} loading={s.testing}><PlugZap /> Test</Button>} />}
    >
      <Field label="Mode"><Segmented value={d.mode} onChange={(v) => s.set({ mode: v })} options={[{ value: "embedded", label: "Embedded (local folder)" }, { value: "server", label: "Qdrant server" }]} /></Field>
      {d.mode === "server" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="URL"><Input value={d.url} onChange={(e) => s.set({ url: e.target.value })} className="font-mono text-[0.82rem]" placeholder="http://localhost:6333" /></Field>
          <Field label="API key"><SecretField has={d.has_api_key} preview={d.api_key_preview} value={s.secrets.api_key} onChange={(v) => s.setSecret("api_key", v)} /></Field>
        </div>
      )}
      <Field label="Collection prefix" hint="Lets several deployments share one Qdrant server"><Input value={d.collection_prefix} onChange={(e) => s.set({ collection_prefix: e.target.value })} className="max-w-xs font-mono text-[0.82rem]" /></Field>
      <div className="rounded-lg border bg-subtle px-3 py-2 text-xs text-muted-foreground">Switching stores does not copy vectors. After switching, run <b>Re-index library</b> in Embeddings &amp; reranking.</div>
      <TestResult result={s.testResult} />
    </SettingsCard>
  );
}
