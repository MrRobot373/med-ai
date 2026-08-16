"""Structured clinical modules — spec §63. Each module (summary, SOAP, entity
extraction, differential support, guideline Q&A, report comparison) is its own real
workflow with its own Pydantic schema and prompt — never "send the same prompt to the
chat endpoint with a different system message." Built on `app.llm.generation`/
`app.llm.structured` (the same shared Ollama client chat and vision use) and, where a
module needs evidence, `app.rag.pipeline.retrieve()` — this package has no knowledge
of conversations; `app/services/clinical_modules.py` owns persistence and orchestration.
"""
