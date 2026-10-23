import { Cpu, Eye, PlugZap } from "lucide-react";
import { Badge, Button, Field, Input, Segmented, Slider, SwitchRow } from "@/components/ui";
import { useSection } from "../useSection";
import { ModelInput, NumberField, PresetPicker, SaveBar, SecretField, SettingsCard, TestResult } from "../parts";

export const LLM_PRESETS = [
  { id: "ollama", name: "Ollama (local)", provider: "ollama", base_url: "http://localhost:11434", hint: "Native Ollama API", needsKey: false },
  { id: "lmstudio", name: "LM Studio", provider: "openai", base_url: "http://localhost:1234/v1", needsKey: false },
  { id: "vllm", name: "vLLM", provider: "openai", base_url: "http://localhost:8000/v1", needsKey: false },
  { id: "llamacpp", name: "llama.cpp server", provider: "openai", base_url: "http://localhost:8080/v1", needsKey: false },
  { id: "openai", name: "OpenAI", provider: "openai", base_url: "https://api.openai.com/v1", needsKey: true },
  { id: "openrouter", name: "OpenRouter", provider: "openai", base_url: "https://openrouter.ai/api/v1", needsKey: true },
  { id: "groq", name: "Groq", provider: "openai", base_url: "https://api.groq.com/openai/v1", needsKey: true },
  { id: "together", name: "Together AI", provider: "openai", base_url: "https://api.together.xyz/v1", needsKey: true },
];

const matchPreset = (provider: string, url: string) => LLM_PRESETS.find((p) => p.provider === provider && p.base_url === url?.replace(/\/$/, ""))?.id ?? "custom";
const isCloud = (url: string) => !!url && !/localhost|127\.0\.0\.1|0\.0\.0\.0|\.local\b|^http:\/\/(10|192\.168|172\.(1[6-9]|2\d|3[01]))\./.test(url);

function EndpointFields({ s, section }: { s: ReturnType<typeof useSection>; section: string }) {
  const d = s.draft;
  return (
    <>
      <Field label="Provider preset" hint="Fills in the endpoint — you can still edit everything below.">
        <PresetPicker presets={[...LLM_PRESETS, { id: "custom", name: "Custom…" } as any]} active={matchPreset(d.provider, d.base_url)} onPick={(p: any) => p.id !== "custom" && s.set({ provider: p.provider, base_url: p.base_url })} />
      </Field>
      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <Field label="API protocol">
          <Segmented value={d.provider} onChange={(v) => s.set({ provider: v })} options={[{ value: "ollama", label: "Ollama" }, { value: "openai", label: "OpenAI-compatible" }]} />
        </Field>
        <Field label="Base URL" hint={d.provider === "openai" ? "Include the version path, e.g. …/v1" : "e.g. http://localhost:11434"}>
          <Input value={d.base_url ?? ""} onChange={(e) => s.set({ base_url: e.target.value })} className="font-mono text-[0.82rem]" />
        </Field>
      </div>
      {isCloud(d.base_url) && <div className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning-foreground"><b>External endpoint.</b> Prompts sent here include patient context. Use only with a provider covered by your data-processing agreement.</div>}
      <Field label="API key" hint="Optional for local servers. Stored encrypted; never shown again.">
        <SecretField has={d.has_api_key} preview={d.api_key_preview} value={s.secrets.api_key} onChange={(v) => s.setSecret("api_key", v)} />
      </Field>
      <Field label="Model">
        <ModelInput value={d.model ?? ""} onChange={(v) => s.set({ model: v })} fetchBody={{ section, provider: d.provider, base_url: d.base_url, api_key: s.secrets.api_key || undefined }} placeholder="e.g. qwen3.5:9b" />
      </Field>
    </>
  );
}

export function ModelsSection() {
  const s = useSection("llm");
  const v = useSection("vision");
  if (!s.server || !v.server) return null;
  const d = s.draft;
  return (
    <div className="space-y-[var(--gap)]">
      <SettingsCard
        title={<span className="flex items-center gap-2"><Cpu className="size-4 text-primary" /> Language model</span>}
        description="Generates answers, summaries, notes and structured outputs. Switch providers any time — the next request uses the new model."
        badge={<Badge tone="primary">{s.server.model}</Badge>}
        footer={<SaveBar dirty={s.dirty} saving={s.saving} onSave={s.save} onReset={s.reset} extra={<Button size="sm" variant="secondary" onClick={() => s.test("llm")} loading={s.testing}><PlugZap /> Test connection</Button>} />}
      >
        <EndpointFields s={s} section="llm" />
        <TestResult result={s.testResult} />
        <div className="grid gap-5 border-t pt-5 md:grid-cols-2">
          <Field label={`Temperature · ${Number(d.temperature).toFixed(2)}`} hint="Low values keep clinical output consistent (0.1–0.2 recommended).">
            <Slider value={[d.temperature]} min={0} max={1} step={0.05} onValueChange={([x]) => s.set({ temperature: x })} />
          </Field>
          <Field label="Max output tokens"><NumberField value={d.max_output_tokens} onChange={(x) => s.set({ max_output_tokens: x })} min={64} /></Field>
          <Field label="Context window" hint="Tokens the server should allocate (Ollama num_ctx)."><NumberField value={d.context_window} onChange={(x) => s.set({ context_window: x })} min={1024} step={1024} suffix="tokens" /></Field>
          <Field label="Request timeout"><NumberField value={d.timeout_seconds} onChange={(x) => s.set({ timeout_seconds: x })} min={5} suffix="sec" /></Field>
          <Field label="Concurrent generations" hint="Keep at 1 for a single local GPU."><NumberField value={d.max_concurrency} onChange={(x) => s.set({ max_concurrency: x })} min={1} max={32} /></Field>
          <div className="pt-6"><SwitchRow label="Allow reasoning / thinking" description="Lets hybrid-reasoning models think before answering. Slower; reasoning text is never shown." checked={!!d.reasoning} onCheckedChange={(x) => s.set({ reasoning: x })} /></div>
        </div>
      </SettingsCard>

      <SettingsCard
        title={<span className="flex items-center gap-2"><Eye className="size-4 text-primary" /> Vision model</span>}
        description="Reads scanned pages and images during ingestion and powers image analysis."
        footer={<SaveBar dirty={v.dirty} saving={v.saving} onSave={v.save} onReset={v.reset} extra={<Button size="sm" variant="secondary" onClick={() => v.test("vision")} loading={v.testing}><PlugZap /> Test</Button>} />}
      >
        <SwitchRow label="Use the language model for vision" description="Works when the main model is multimodal (e.g. qwen3.5, gemma3, llava, gpt-4o)." checked={!!v.draft.use_main_llm} onCheckedChange={(x) => v.set({ use_main_llm: x })} />
        {!v.draft.use_main_llm && <EndpointFields s={v} section="vision" />}
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Max image dimension" hint="Images are downscaled before sending."><NumberField value={v.draft.max_image_dimension} onChange={(x) => v.set({ max_image_dimension: x })} min={256} max={4096} suffix="px" /></Field>
          <Field label={`Temperature · ${Number(v.draft.temperature).toFixed(2)}`}><Slider value={[v.draft.temperature]} min={0} max={1} step={0.05} onValueChange={([x]) => v.set({ temperature: x })} /></Field>
        </div>
        <TestResult result={v.testResult} />
      </SettingsCard>
    </div>
  );
}
