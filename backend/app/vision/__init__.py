"""Vision AI — spec §58-61. Structured image analysis and previous/current image
comparison, built on `app/llm/generation.py` (the same model chat uses). Analysis
results feed `app/rag/indexing.py`'s `patient_vision` collection so they become real,
retrievable chat evidence (spec §59's "image-to-RAG" stage) — this package has no
knowledge of conversations itself; `app/chat/orchestrator.py` calls into `app.rag`
the same way it already does for `patient_documents`/`medical_knowledge`.
"""
