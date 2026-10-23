"""Trusted external evidence providers (all free public APIs, no keys required):
PubMed (NCBI E-utilities), openFDA drug labels, ClinicalTrials.gov v2."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import WebCache
from app.services.runtime_config import ResearchConfig

logger = get_logger(__name__)

PROVIDERS = {
    "pubmed": {"name": "PubMed", "tier": "Peer-reviewed literature", "url": "https://pubmed.ncbi.nlm.nih.gov"},
    "openfda": {"name": "openFDA", "tier": "Regulatory drug labeling", "url": "https://open.fda.gov"},
    "clinicaltrials": {"name": "ClinicalTrials.gov", "tier": "Trial registry", "url": "https://clinicaltrials.gov"},
}

_STOP = set(
    [
        "what",
        "is",
        "the",
        "are",
        "of",
        "for",
        "and",
        "with",
        "in",
        "on",
        "a",
        "an",
        "to",
        "how",
        "does",
        "do",
        "should",
        "be",
        "patient",
        "patients",
        "treatment",
    ]
)


def keywords(query: str, limit: int = 8) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9\-]+", query.lower()) if w not in _STOP and len(w) > 2]
    return " ".join(list(dict.fromkeys(words))[:limit])


async def _pubmed(client: httpx.AsyncClient, q: str, cfg: ResearchConfig) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    params = {"db": "pubmed", "term": q, "retmode": "json", "retmax": cfg.max_results_per_source, "sort": "relevance"}
    if cfg.pubmed_api_key:
        params["api_key"] = cfg.pubmed_api_key
    ids = (await client.get(f"{base}/esearch.fcgi", params=params)).json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summ = (
        await client.get(f"{base}/esummary.fcgi", params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    ).json()
    abstracts: dict[str, str] = {}
    try:
        xml = (
            await client.get(
                f"{base}/efetch.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"},
            )
        ).text
        for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            pmid = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
            text = " ".join(
                re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", art, re.S)
            )
            if pmid:
                abstracts[pmid.group(1)] = text.strip()
    except httpx.HTTPError:
        pass
    out = []
    for pid in ids:
        item = summ.get("result", {}).get(pid)
        if not item:
            continue
        pubtypes = item.get("pubtype", [])
        out.append(
            {
                "provider": "pubmed",
                "source": "PubMed",
                "id": pid,
                "title": item.get("title", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                "date": item.get("pubdate", ""),
                "journal": item.get("fulljournalname") or item.get("source", ""),
                "evidence_type": next(
                    (
                        t
                        for t in pubtypes
                        if t
                        in (
                            "Meta-Analysis",
                            "Systematic Review",
                            "Randomized Controlled Trial",
                            "Practice Guideline",
                            "Guideline",
                            "Review",
                        )
                    ),
                    pubtypes[0] if pubtypes else "Article",
                ),
                "snippet": (abstracts.get(pid) or "")[:1500],
            }
        )
    return out


async def _openfda(client: httpx.AsyncClient, q: str, cfg: ResearchConfig) -> list[dict]:
    terms = [w for w in q.split() if len(w) > 3][:4]
    if not terms:
        return []
    search = " OR ".join(f'openfda.generic_name:"{t}" OR openfda.brand_name:"{t}"' for t in terms)
    resp = await client.get(
        "https://api.fda.gov/drug/label.json", params={"search": search, "limit": cfg.max_results_per_source}
    )
    if resp.status_code == 404:
        return []
    out = []
    for r in resp.json().get("results", []):
        o = r.get("openfda", {})
        name = ", ".join(o.get("generic_name", [])[:1] or o.get("brand_name", [])[:1]) or "Drug label"
        parts = []
        for key in (
            "indications_and_usage",
            "dosage_and_administration",
            "contraindications",
            "warnings_and_cautions",
            "warnings",
            "adverse_reactions",
            "drug_interactions",
        ):
            if r.get(key):
                parts.append(f"{key.replace('_', ' ').capitalize()}: {r[key][0][:500]}")
        set_id = r.get("set_id", "")
        out.append(
            {
                "provider": "openfda",
                "source": "openFDA",
                "id": set_id,
                "title": f"{name} — FDA label",
                "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={set_id}",
                "date": r.get("effective_time", ""),
                "journal": "FDA Structured Product Labeling",
                "evidence_type": "Drug label",
                "snippet": "\n".join(parts)[:1800],
            }
        )
    return out


async def _clinicaltrials(client: httpx.AsyncClient, q: str, cfg: ResearchConfig) -> list[dict]:
    resp = await client.get(
        "https://clinicaltrials.gov/api/v2/studies",
        params={"query.term": q, "pageSize": cfg.max_results_per_source, "format": "json"},
    )
    out = []
    for s in resp.json().get("studies", []):
        p = s.get("protocolSection", {})
        ident = p.get("identificationModule", {})
        status = p.get("statusModule", {})
        desc = p.get("descriptionModule", {})
        nct = ident.get("nctId", "")
        out.append(
            {
                "provider": "clinicaltrials",
                "source": "ClinicalTrials.gov",
                "id": nct,
                "title": ident.get("briefTitle", ""),
                "url": f"https://clinicaltrials.gov/study/{nct}",
                "date": status.get("startDateStruct", {}).get("date", ""),
                "journal": status.get("overallStatus", ""),
                "evidence_type": "Clinical trial registration",
                "snippet": (desc.get("briefSummary") or "")[:1500],
            }
        )
    return out


_FUNCS = {"pubmed": _pubmed, "openfda": _openfda, "clinicaltrials": _clinicaltrials}


async def search(
    db: Session, cfg: ResearchConfig, query: str, sources: list[str] | None = None
) -> tuple[list[dict], list[dict]]:
    """Returns (results, per-source status). Uses the web cache within its freshness window."""
    q = keywords(query) or query
    chosen = [s for s in (sources or cfg.sources) if s in _FUNCS and s in cfg.sources]
    results: list[dict] = []
    statuses: list[dict] = []
    fresh_after = datetime.now(UTC) - timedelta(hours=cfg.cache_hours)

    async with httpx.AsyncClient(timeout=cfg.timeout_seconds, headers={"User-Agent": "GMS-Clinical-AI/2.0"}) as client:

        async def run(src: str):
            qh = hashlib.sha256(f"{src}|{q}".encode()).hexdigest()
            cached = db.scalars(
                select(WebCache)
                .where(WebCache.provider == src, WebCache.query_hash == qh)
                .order_by(WebCache.fetched_at.desc())
            ).first()
            if (
                cached
                and cfg.cache_hours
                and (cached.fetched_at if cached.fetched_at.tzinfo else cached.fetched_at.replace(tzinfo=UTC))
                > fresh_after
            ):
                return src, cached.results, "cached", None
            try:
                rows = await _FUNCS[src](client, q, cfg)
                db.add(WebCache(provider=src, query_hash=qh, query=q, results=rows))
                return src, rows, "ok", None
            except Exception as exc:  # network / schema errors are reported, not hidden
                logger.warning("Research provider %s failed", src, exc_info=True)
                return src, [], "error", str(exc)[:200]

        for src, rows, status, err in await asyncio.gather(*(run(s) for s in chosen)):
            statuses.append(
                {"provider": src, "name": PROVIDERS[src]["name"], "status": status, "count": len(rows), "error": err}
            )
            results.extend(rows)
    db.commit()
    return results, statuses
