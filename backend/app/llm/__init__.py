"""Shared low-level Ollama client — one model, one endpoint, one concurrency budget
(spec §58 "use Qwen3.5 vision capability rather than loading a second large VLM").
`app/chat/` (Phase 08) and `app/vision/` (Phase 09) are peer callers of this package;
this package knows nothing about conversations, citations, or clinical prompts.
"""
