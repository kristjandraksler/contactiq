from __future__ import annotations

import logging
import time
from dataclasses import asdict

from .evidence_engine import confidence_label
from .phone_confidence import calculate_confidence
from .phone_models import FinderResult
from .phone_parser import ExtractedPhone, extract_phones
from .phone_ranker import rank_candidates
from .providers import clean_domain, is_public_email_domain
from .website_crawler import crawl_company_website


logger = logging.getLogger(__name__)
DEBUG_DOMAINS: set[str] = {"letko.net"}


def _debug_enabled(domain: str) -> bool:
    return domain.lower() in DEBUG_DOMAINS


def _debug(domain: str, *values: object) -> None:
    if not _debug_enabled(domain):
        return
    logger.warning("[PHONE FINDER DEBUG] %s", " ".join(str(v) for v in values))


async def find_phone_for_domain(raw_domain: str, max_pages: int = 10) -> FinderResult:
    started_at = time.perf_counter()
    domain = clean_domain(raw_domain)

    def duration_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

    _debug(domain, "=" * 70)
    _debug(domain, "RAW INPUT:", raw_domain)
    _debug(domain, "CLEAN DOMAIN:", domain)

    if not domain or "." not in domain:
        return FinderResult(
            status="NOT_FOUND", website=None, phone=None, confidence=None,
            source_url=None, pages_scanned=0, scan_duration_ms=duration_ms(),
            candidates=[], error="Domena ni veljavna.", confidence_label="UNKNOWN",
        )

    if is_public_email_domain(domain):
        return FinderResult(
            status="NOT_FOUND", website=None, phone=None, confidence=None,
            source_url=None, pages_scanned=0, scan_duration_ms=duration_ms(),
            candidates=[], error=None, confidence_label="UNKNOWN",
        )

    try:
        website, pages = await crawl_company_website(domain, max_pages=max_pages)
    except Exception as exc:
        _debug(domain, "CRAWLER EXCEPTION:", type(exc).__name__, str(exc))
        return FinderResult(
            status="FAILED", website=None, phone=None, confidence=None,
            source_url=None, pages_scanned=0, scan_duration_ms=duration_ms(),
            candidates=[], error=f"Tehnična napaka pri obdelavi: {type(exc).__name__}",
            confidence_label="UNKNOWN",
        )

    if not website or not pages:
        return FinderResult(
            status="NOT_FOUND", website=website, phone=None, confidence=None,
            source_url=None, pages_scanned=0, scan_duration_ms=duration_ms(),
            candidates=[], error=None, confidence_label="UNKNOWN",
        )

    rows: list[tuple[ExtractedPhone, str]] = []

    for page in pages:
        try:
            extracted_phones = extract_phones(page.html, page.url, domain)
            _debug(domain, "=" * 60)
            _debug(domain, "PAGE:", page.url, "| PHONES FOUND:", len(extracted_phones))
            for extracted_phone in extracted_phones:
                _debug(
                    domain,
                    "PHONE:", extracted_phone.phone,
                    "| SOURCE:", extracted_phone.source,
                    "| SCORE:", extracted_phone.score,
                    "| KEYWORD DISTANCE:", extracted_phone.keyword_distance,
                    "| POSITION:", extracted_phone.position_ratio,
                    "| HTML TAG:", extracted_phone.html_tag,
                    "| SECTION:", extracted_phone.section,
                )
            _debug(domain, "=" * 60)
        except Exception as exc:
            _debug(domain, "PARSER ERROR:", page.url, type(exc).__name__, str(exc))
            continue

        for extracted in extracted_phones:
            rows.append((extracted, page.url))

    ranked = rank_candidates(rows)

    if not ranked:
        return FinderResult(
            status="NOT_FOUND", website=website, phone=None, confidence=None,
            source_url=None, pages_scanned=len(pages), scan_duration_ms=duration_ms(),
            candidates=[], error=None, confidence_label="UNKNOWN",
        )

    best = ranked[0]
    best_confidence = best.confidence if best.confidence is not None else calculate_confidence(best)

    return FinderResult(
        status="MATCHED",
        website=website,
        phone=best.phone,
        confidence=best_confidence,
        source_url=best.source_url,
        pages_scanned=len(pages),
        scan_duration_ms=duration_ms(),
        candidates=[asdict(candidate) for candidate in ranked[:5]],
        error=None,
        confidence_label=confidence_label(best_confidence),
    )
