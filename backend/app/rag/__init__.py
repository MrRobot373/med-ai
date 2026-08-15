"""Local RAG core — spec §43/§44. Every module here is a single retrieval stage
(embed, dense, sparse, fuse, rerank, dedup); `pipeline.py` composes them. Chat
orchestration (query classification/rewriting, context construction, citation and
grounding validation) is Phase 08 — it calls into this package, this package doesn't
reach into chat.
"""
