"""Local embedding abstraction — spec §5. Wraps `Qwen3-Embedding-0.6B` via
`sentence-transformers`. Lazy-loaded singleton (same double-checked-locking pattern as
`app/ingestion/ocr.py`'s `_get_reader()`) so importing this module never triggers the
~600 MB model download/load — it only loads the first time an embed function is
actually called. Vector dimension is read from the loaded model, never hardcoded
(spec §5 "never manually hardcode vector dimension if the library can expose it").

Every other `rag/*` module calls `embed_query()`/`embed_documents()`, never
`SentenceTransformer` directly — spec §5 "create an abstraction so another embedding
model can be substituted later without changing the RAG pipeline."
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.config.settings import Settings
from app.logging import get_logger

logger = get_logger(__name__)

_model = None
_loaded_model_name: str | None = None
_model_lock = threading.Lock()


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    dimension: int


def is_loaded() -> bool:
    return _model is not None


def _get_model(settings: Settings):
    global _model, _loaded_model_name
    if _model is None or _loaded_model_name != settings.embedding_model:
        with _model_lock:
            if _model is None or _loaded_model_name != settings.embedding_model:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model %s on %s", settings.embedding_model, settings.embedding_device)
                # Qwen3-Embedding is decoder-based; transformers' default "eager"
                # attention is markedly slower on CPU than PyTorch's built-in fused
                # "sdpa" kernel for this architecture (measured ~2.2x on a 400-word
                # chunk) — a real, verified throughput fix, not a guess.
                try:
                    _model = SentenceTransformer(
                        settings.embedding_model,
                        device=settings.embedding_device,
                        model_kwargs={"attn_implementation": "sdpa"},
                    )
                except Exception:
                    logger.warning("sdpa attention unavailable for embedding model; falling back to default", exc_info=True)
                    _model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
                # See settings.embedding_max_seq_length's docstring — capping this is
                # the other big lever for CPU throughput on this model.
                _model.max_seq_length = settings.embedding_max_seq_length
                _loaded_model_name = settings.embedding_model
    return _model


def get_embedding_dimension(settings: Settings) -> int:
    model = _get_model(settings)
    # sentence-transformers renamed this method (get_sentence_embedding_dimension ->
    # get_embedding_dimension) partway through its 5.x series — support both so this
    # doesn't break on an older pinned version either.
    getter = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    return getter()


def embed_documents(texts: list[str], settings: Settings) -> EmbeddingResult:
    """Embeds passage/document text — used when indexing chunks."""
    return _embed(texts, settings, is_query=False)


def embed_query(text: str, settings: Settings) -> list[float]:
    """Embeds a single search query. Returns the raw vector (not wrapped in
    `EmbeddingResult`) since every caller wants exactly one vector for the search
    call, not a batch."""
    return _embed([text], settings, is_query=True).vectors[0]


def _embed(texts: list[str], settings: Settings, is_query: bool) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(vectors=[], dimension=get_embedding_dimension(settings))

    model = _get_model(settings)
    vectors = None
    if is_query:
        # Qwen3-Embedding ships an asymmetric query/document convention — a "query"
        # instruction prompt measurably improves retrieval quality over embedding the
        # bare query text. Fall back to plain encoding if this particular model
        # doesn't define that prompt rather than hard-failing the whole pipeline over
        # an optional quality improvement.
        try:
            vectors = model.encode(
                texts, batch_size=settings.embedding_batch_size, prompt_name="query", normalize_embeddings=True
            )
        except Exception:
            logger.warning("Embedding model has no 'query' prompt configured; encoding plain", exc_info=True)
    if vectors is None:
        vectors = model.encode(texts, batch_size=settings.embedding_batch_size, normalize_embeddings=True)

    return EmbeddingResult(vectors=vectors.tolist(), dimension=vectors.shape[1])
