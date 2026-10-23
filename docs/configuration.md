# Configuring AI providers

Everything below is done in the UI as an administrator: **Settings → AI models**,
**Embeddings & reranking**, **Retrieval tuning**, **Vector store**, **Research sources**.
Use **Test** before **Save** — tests run against the unsaved values. Saved changes apply
to the next request; no restart is needed. API keys are encrypted with `APP_SECRET_KEY`
and never returned to the browser.

## Language model (chat, summaries, structured tools)

| Setup | Protocol | Base URL | Example model |
|---|---|---|---|
| Ollama (local) | Ollama | `http://localhost:11434` | `qwen3.5:9b`, `llama3.1:8b`, `gemma3:12b` |
| LM Studio | OpenAI-compatible | `http://localhost:1234/v1` | the loaded model id |
| vLLM | OpenAI-compatible | `http://localhost:8000/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| llama.cpp `llama-server` | OpenAI-compatible | `http://localhost:8080/v1` | any (single model) |
| OpenAI | OpenAI-compatible | `https://api.openai.com/v1` | `gpt-4o-mini` |
| OpenRouter | OpenAI-compatible | `https://openrouter.ai/api/v1` | `anthropic/claude-…`, `meta-llama/…` |
| Groq / Together | OpenAI-compatible | see preset | provider model id |

Notes
- **Fetch models** lists what the endpoint serves.
- **Context window** maps to Ollama `num_ctx`; keep it ≥ the retrieval context budget plus
  ~2k tokens of instructions.
- **Reasoning** off (default) suppresses hidden "thinking" for hybrid-reasoning models;
  `<think>` blocks are filtered from output either way.
- JSON mode is used for structured tools; servers that reject `response_format` are
  retried without it automatically.

## Vision

By default the language model also handles images (needs a multimodal model: qwen3.5,
gemma3, llava, gpt-4o…). Turn that off to point vision at a different endpoint/model.
Vision is used to transcribe scanned PDF pages and photos during ingestion, and for the
Image analysis tool.

## Embeddings

| Setup | Provider | Base URL | Model |
|---|---|---|---|
| Ollama | Ollama | `http://localhost:11434` | `qwen3-embedding:0.6b`, `nomic-embed-text`, `bge-m3` |
| Hugging Face TEI | OpenAI-compatible | `http://localhost:8081/v1` | `BAAI/bge-m3` |
| OpenAI | OpenAI-compatible | `https://api.openai.com/v1` | `text-embedding-3-small` |
| In-process | sentence-transformers | — | `Qwen/Qwen3-Embedding-0.6B` (`pip install -e ".[local-models]"`) |

The vector dimension is detected automatically. **Changing the embedding model requires
a re-index** (Settings shows a banner and a one-click *Re-index library*; keyword search
keeps working meanwhile, new uploads wait until it's done).

## Reranker (optional)

| Preset | Provider | Base URL | Model |
|---|---|---|---|
| Off | — | — | fusion order is used |
| TEI reranker | remote | `http://localhost:8082` | `BAAI/bge-reranker-v2-m3` |
| Jina | remote | `https://api.jina.ai/v1` | `jina-reranker-v2-base-multilingual` |
| Cohere | remote | `https://api.cohere.com/v2` | `rerank-v3.5` |
| vLLM / llama.cpp | remote | `http://localhost:8080/v1` | reranker model id |
| In-process | local | — | `BAAI/bge-reranker-v2-m3` |
| LLM judge | llm | — | uses the language model (one extra call) |

`/rerank` is appended to the base URL; Cohere/Jina/vLLM (`results[].relevance_score`) and
TEI (`[{index, score}]`) response shapes are both understood.

## Retrieval tuning

Profiles: **Fast** (local GPUs), **Balanced**, **Thorough** (needs a large context window),
or **Custom**. Adjustable: dense / BM25 candidate counts and weights, fused candidates,
final passages, RRF constant, minimum rerank score, context budget, conversation memory,
chunk size/overlap (new documents), and whether patient chats also search the library.
Verify changes in **Knowledge library → Retrieval playground**, which runs the exact
pipeline and shows every stage.

## Vector store

- **Embedded** (default): vectors in `DATA_DIR/vectors`, nothing else to run. Single
  process — stop the API before running `python -m app.seed`.
- **Server**: a Qdrant server (`docker compose --profile qdrant up -d`, URL
  `http://localhost:6333` or `http://qdrant:6333` inside compose). After switching, re-index.

## Research sources

Off by default (fully local). When enabled, clinicians can opt in per conversation or use
the Research page. Sources: PubMed (optional NCBI key raises the rate limit), openFDA drug
labels, ClinicalTrials.gov. Queries are de-identified first (patient name/MRN/phone/email,
plus emails, phone numbers, dates, addresses) and every search is audited.
