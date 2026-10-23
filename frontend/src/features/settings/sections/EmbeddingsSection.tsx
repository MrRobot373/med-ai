import { AlertTriangle, Binary, ListOrdered, PlugZap, RefreshCw } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";
import { Badge, Button, Field, Input, Segmented } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useSection, useSettingsView } from "../useSection";
import { ModelInput, NumberField, PresetPicker, SaveBar, SecretField, SettingsCard, TestResult } from "../parts";

const EMB_PRESETS = [
  { id: "ollama-qwen", name: "Ollama · Qwen3 Embedding", provider: "ollama", base_url: "http://localhost:11434", model: "qwen3-embedding:0.6b" },
  { id: "ollama-nomic", name: "Ollama · nomic-embed-text", provider: "ollama", base_url: "http://localhost:11434", model: "nomic-embed-text" },
  { id: "tei", name: "Text Embeddings Inference", provider: "openai", base_url: "http://localhost:8081/v1", model: "BAAI/bge-m3" },
  { id: "openai", name: "OpenAI", provider: "openai", base_url: "https://api.openai.com/v1", model: "text-embedding-3-small" },
  { id: "local", name: "In-process (sentence-transformers)", provider: "local", base_url: "", model: "Qwen/Qwen3-Embedding-0.6B" },
];
const RR_PRESETS = [
  { id: "none", name: "Off", provider: "none", base_url: "", model: "" },
  { id: "tei", name: "TEI reranker", provider: "remote", base_url: "http://localhost:8082", model: "BAAI/bge-reranker-v2-m3" },
  { id: "jina", name: "Jina", provider: "remote", base_url: "https://api.jina.ai/v1", model: "jina-reranker-v2-base-multilingual" },
  { id: "cohere", name: "Cohere", provider: "remote", base_url: "https://api.cohere.com/v2", model: "rerank-v3.5" },
  { id: "llamacpp", name: "llama.cpp / vLLM", provider: "remote", base_url: "http://localhost:8080/v1", model: "bge-reranker-v2-m3" },
  { id: "local", name: "In-process cross-encoder", provider: "local", base_url: "", model: "BAAI/bge-reranker-v2-m3" },
  { id: "llm", name: "LLM as judge", provider: "llm", base_url: "", model: "" },
];

function ReindexCard() {
  const { data } = useSettingsView();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["reindex"], queryFn: () => api<any>("/api/settings/reindex"), refetchInterval: (q) => (q.state.data?.running ? 1500 : false) });
  const st = data?.index_status;
  const start = async () => {
    try { await api("/api/settings/reindex", { method: "POST" }); toast.success("Re-index started"); status.refetch(); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed"); }
  };
  const finished = !!status.data && !status.data.running && !!status.data.result;
  useEffect(() => { if (finished) qc.invalidateQueries({ queryKey: ["settings"] }); }, [finished, qc]);
  return (
    <SettingsCard title="Vector index" description="Vectors are tied to the embedding model that produced them." badge={st?.dimension ? <Badge>{st.dimension}-d</Badge> : undefined}
      footer={<Button size="sm" variant={st?.reindex_required ? "primary" : "secondary"} onClick={start} loading={status.data?.running}><RefreshCw /> Re-index library</Button>}>
      {st?.reindex_required ? (
        <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning-soft p-3 text-sm text-warning-foreground"><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><b>Re-index required.</b> The embedding model changed since the library was indexed. Uploads are paused until you re-index; keyword (BM25) search keeps working.</div></div>
      ) : <p className="text-sm text-muted-foreground">Index is in sync with the current embedding model.</p>}
      {status.data?.running && <p className="text-sm">Re-indexing… {status.data.done}/{status.data.total || "?"} documents</p>}
      {status.data?.error && <p className="text-sm text-danger">{status.data.error}</p>}
      {status.data?.result && !status.data.running && <p className="text-sm text-success-foreground">Re-indexed {status.data.result.documents} documents ({status.data.result.chunks} chunks, {status.data.result.dimension}-d).</p>}
    </SettingsCard>
  );
}

export function EmbeddingsSection() {
  const e = useSection("embeddings");
  const r = useSection("reranker");
  if (!e.server || !r.server) return null;
  const ed = e.draft;
  const rd = r.draft;
  const embActive = EMB_PRESETS.find((p) => p.provider === ed.provider && p.base_url === ed.base_url && p.model === ed.model)?.id;
  const rrActive = RR_PRESETS.find((p) => p.provider === rd.provider && (p.provider !== "remote" || p.base_url === rd.base_url))?.id;

  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard
        title={<span className="flex items-center gap-2"><Binary className="size-4 text-primary" /> Embedding model</span>}
        description="Turns text into vectors for semantic search. Changing it requires re-indexing the library."
        badge={<Badge tone="primary">{e.server.model}</Badge>}
        footer={<SaveBar dirty={e.dirty} saving={e.saving} onSave={e.save} onReset={e.reset} extra={<Button size="sm" variant="secondary" onClick={() => e.test("embeddings")} loading={e.testing}><PlugZap /> Test</Button>} />}
      >
        <Field label="Preset"><PresetPicker presets={EMB_PRESETS} active={embActive} onPick={(p) => e.set({ provider: p.provider, base_url: p.base_url, model: p.model })} /></Field>
        <div className="grid gap-4 md:grid-cols-[260px_1fr]">
          <Field label="Provider"><Segmented value={ed.provider} onChange={(x) => e.set({ provider: x })} options={[{ value: "ollama", label: "Ollama" }, { value: "openai", label: "OpenAI-compat." }, { value: "local", label: "In-process" }]} /></Field>
          {ed.provider !== "local" ? <Field label="Base URL"><Input value={ed.base_url} onChange={(x) => e.set({ base_url: x.target.value })} className="font-mono text-[0.82rem]" /></Field>
            : <Field label="Device" hint="cpu, cuda or mps"><Input value={ed.device} onChange={(x) => e.set({ device: x.target.value })} /></Field>}
        </div>
        {ed.provider !== "local" && <Field label="API key"><SecretField has={ed.has_api_key} preview={ed.api_key_preview} value={e.secrets.api_key} onChange={(x) => e.setSecret("api_key", x)} /></Field>}
        <Field label="Model">
          {ed.provider === "local" ? <Input value={ed.model} onChange={(x) => e.set({ model: x.target.value })} className="font-mono text-[0.82rem]" /> : <ModelInput value={ed.model} onChange={(x) => e.set({ model: x })} fetchBody={{ section: "embeddings", provider: ed.provider, base_url: ed.base_url, api_key: e.secrets.api_key || undefined }} />}
        </Field>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Batch size"><NumberField value={ed.batch_size} onChange={(x) => e.set({ batch_size: x })} min={1} max={512} /></Field>
          <Field label="Query instruction" hint="Prefix for queries with instruction-tuned embedders (optional)."><Input value={ed.query_instruction} onChange={(x) => e.set({ query_instruction: x.target.value })} placeholder="e.g. Instruct: Retrieve clinical passages\nQuery: " /></Field>
        </div>
        <TestResult result={e.testResult} />
      </SettingsCard>

      <ReindexCard />

      <SettingsCard
        title={<span className="flex items-center gap-2"><ListOrdered className="size-4 text-primary" /> Reranker</span>}
        description="Re-scores fused candidates with a cross-encoder for higher precision. Optional."
        badge={<Badge tone={rd.provider === "none" ? "neutral" : "primary"}>{r.server.provider === "none" ? "Off" : r.server.provider === "llm" ? "LLM judge" : r.server.model}</Badge>}
        footer={<SaveBar dirty={r.dirty} saving={r.saving} onSave={r.save} onReset={r.reset} extra={<Button size="sm" variant="secondary" onClick={() => r.test("reranker")} loading={r.testing}><PlugZap /> Test</Button>} />}
      >
        <Field label="Preset"><PresetPicker presets={RR_PRESETS} active={rrActive} onPick={(p) => r.set({ provider: p.provider, base_url: p.base_url, model: p.model })} /></Field>
        {rd.provider === "remote" && (
          <>
            <Field label="Base URL" hint="The /rerank path is appended. Cohere, Jina, TEI, vLLM and llama.cpp response shapes are supported."><Input value={rd.base_url} onChange={(x) => r.set({ base_url: x.target.value })} className="font-mono text-[0.82rem]" /></Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Model"><Input value={rd.model} onChange={(x) => r.set({ model: x.target.value })} className="font-mono text-[0.82rem]" /></Field>
              <Field label="API key"><SecretField has={rd.has_api_key} preview={rd.api_key_preview} value={r.secrets.api_key} onChange={(x) => r.setSecret("api_key", x)} /></Field>
            </div>
          </>
        )}
        {rd.provider === "local" && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Cross-encoder model"><Input value={rd.model} onChange={(x) => r.set({ model: x.target.value })} className="font-mono text-[0.82rem]" /></Field>
            <Field label="Device"><Input value={rd.device} onChange={(x) => r.set({ device: x.target.value })} /></Field>
          </div>
        )}
        {rd.provider === "llm" && <p className="text-sm text-muted-foreground">The language model scores candidates in a single extra call. No extra service needed, but adds latency.</p>}
        {rd.provider === "none" && <p className="text-sm text-muted-foreground">Passages are ranked by reciprocal-rank fusion of dense and BM25 results.</p>}
        <TestResult result={r.testResult} />
      </SettingsCard>
    </div>
  );
}
