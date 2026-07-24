from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from .phone_parser import ExtractedPhone, extract_phones
from .providers import clean_domain, is_public_email_domain
from .website_crawler import crawl_company_website


@dataclass
class PhoneCandidate:
    phone: str
    score: int
    source_url: str
    source: str
    occurrences: int
    from_tel_link: bool


@dataclass
class FinderResult:
    status: str
    website: str | None
    phone: str | None
    confidence: int | None
    source_url: str | None
    pages_scanned: int
    scan_duration_ms: int
    candidates: list[dict[str, Any]]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rank_candidates(rows: list[tuple[ExtractedPhone, str]]) -> list[PhoneCandidate]:
    scores: dict[str, int] = defaultdict(int)
    occurrences: dict[str, int] = defaultdict(int)
    tel_links: dict[str, bool] = defaultdict(bool)
    best_source_url: dict[str, str] = {}
    best_source: dict[str, str] = {}
    best_single_score: dict[str, int] = defaultdict(int)

    for extracted, source_url in rows:
        scores[extracted.phone] += extracted.score
        occurrences[extracted.phone] += 1
        tel_links[extracted.phone] = tel_links[extracted.phone] or extracted.from_tel_link
        if extracted.score > best_single_score[extracted.phone]:
            best_single_score[extracted.phone] = extracted.score
            best_source_url[extracted.phone] = source_url
            best_source[extracted.phone] = extracted.source

    ranked: list[PhoneCandidate] = []
    for phone, score in scores.items():
        repeated_bonus = min(max(occurrences[phone] - 1, 0) * 12, 48)
        ranked.append(
            PhoneCandidate(
                phone=phone,
                score=score + repeated_bonus,
                source_url=best_source_url[phone],
                source=best_source[phone],
                occurrences=occurrences[phone],
                from_tel_link=tel_links[phone],
            )
        )

    return sorted(
        ranked,
        key=lambda candidate: (
            candidate.score,
            candidate.source == "schema_org",
            candidate.from_tel_link,
            candidate.occurrences,
        ),
        reverse=True,
    )


def _confidence(candidate: PhoneCandidate) -> int:
    source_base = {
        "schema_org": 96,
        "microdata": 94,
        "tel_link": 92,
        "footer": 86,
        "visible_text": 68,
    }
    confidence = source_base.get(candidate.source, 60)
    if candidate.occurrences >= 2:
        confidence += 2
    if candidate.occurrences >= 3:
        confidence += 1
    return min(confidence, 99)


async def find_phone_for_domain(raw_domain: str, max_pages: int = 10) -> FinderResult:
    started_at = time.perf_counter()
    domain = clean_domain(raw_domain)

    def duration_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

    # Invalid input is not a system failure. It simply cannot be enriched.
    if not domain or "." not in domain:
        return FinderResult(
            status="NOT_FOUND",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error="Domena ni veljavna.",
        )

    # Critical guard: never crawl Gmail, Telemach, SiOL, Outlook, etc. This
    # prevents returning the provider's support number for the mailbox owner.
    if is_public_email_domain(domain):
        return FinderResult(
            status="NOT_FOUND",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error=None,
        )

    try:
        website, pages = await crawl_company_website(domain, max_pages=max_pages)
    except Exception as exc:  # genuine unexpected technical failure only
        return FinderResult(
            status="FAILED",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error=f"Tehnična napaka pri obdelavi: {type(exc).__name__}",
        )

    # A missing or inaccessible website is a completed search with no result,
    # not a technical error for the user.
    if not website or not pages:
        return FinderResult(
            status="NOT_FOUND",
            website=website,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error=None,
        )

    rows: list[tuple[ExtractedPhone, str]] = []
    for page in pages:
        for extracted in extract_phones(page.html, page.url, domain):
            rows.append((extracted, page.url))

    ranked = _rank_candidates(rows)
    if not ranked:
        return FinderResult(
            status="NOT_FOUND",
            website=website,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=len(pages),
            scan_duration_ms=duration_ms(),
            candidates=[],
            error=None,
        )

    best = ranked[0]
    return FinderResult(
        status="MATCHED",
        website=website,
        phone=best.phone,
        confidence=_confidence(best),
        source_url=best.source_url,
        pages_scanned=len(pages),
        scan_duration_ms=duration_ms(),
        candidates=[asdict(candidate) for candidate in ranked[:5]],
        error=None,
    )
