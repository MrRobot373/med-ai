"""Web Research — spec §64-72. Optional, off by default (`ENABLE_RESEARCH`,
privacy-first per spec §64's "web access must NOT be unrestricted by default").
Every outbound query passes through `deidentify.py` first (spec §66, mandatory, no
bypass). `providers/` fetches from trusted sources (PubMed, FDA, ClinicalTrials.gov,
optional self-hosted SearXNG); `ranking.py` scores results by relevance + a modest
authority-tier boost (spec §67); `paper_assistant.py` is the Research Paper Assistant
structured LLM call (spec §70); `services/research.py` owns caching, orchestration,
and persistence via the shared `ClinicalModuleRun` table.
"""
