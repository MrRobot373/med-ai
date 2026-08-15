"""Clinical chat — spec §39/§43/§48. Query classification, context assembly, real
token-streaming generation, citation extraction/validation, and grounding validation.
Named `chat/` rather than the spec's suggested flat `rag/` layout specifically to avoid
colliding with Phase 07's already-shipped `app/rag/pipeline.py` retrieval module — this
package calls into `app.rag`, `app.rag` has no knowledge of this one.
"""
