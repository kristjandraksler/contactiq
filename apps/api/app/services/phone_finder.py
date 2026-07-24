from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

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
    source_diversity: int
    page_diversity: int
    evidence: list[str]


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


def _page_label(url: str) -> str:
    path = (urlparse(url).path or "/").lower().rstrip("/") or "/"
    if "kontakt" in path or "contact" in path:
        return "contact_page"
    if "impressum" in path or "imprint" in path:
        return "imprint_page"
    if "about" in path or "o-nas" in path or "o-podjetju" in path:
        return "about_page"
    if path == "/":
        return "homepage"
    return "other_page"


def _rank_candidates(rows: list[tuple[ExtractedPhone, str]]) -> list[PhoneCandidate]:
    scores: dict[str, int] = defaultdict(int)
    occurrences: dict[str, int] = defaultdict(int)
    tel_links: dict[str, bool] = defaultdict(bool)
    sources: dict[str, set[str]] = defaultdict(set)
    pages: dict[str, set[str]] = defaultdict(set)
    page_labels: dict[str, set[str]] = defaultdict(set)
    context_signals: dict[str, set[str]] = defaultdict(set)
    best_source_url: dict[str, str] = {}
    best_source: dict[str, str] = {}
    best_single_score: dict[str, int] = defaultdict(int)

    for extracted, source_url in rows:
        scores[extracted.phone] += extracted.score
        occurrences[extracted.phone] += 1
        tel_links[extracted.phone] = tel_links[extracted.phone] or extracted.from_tel_link
        sources[extracted.phone].add(extracted.source)
        pages[extracted.phone].add(source_url)
        page_labels[extracted.phone].add(_page_label(source_url))
        context_signals[extracted.phone].update(extracted.context_signals)

        if extracted.score > best_single_score[extracted.phone]:
            best_single_score[extracted.phone] = extracted.score
            best_source_url[extracted.phone] = source_url
            best_source[extracted.phone] = extracted.source

    ranked: list[PhoneCandidate] = []
    for phone, raw_score in scores.items():
        occurrence_bonus = min(max(occurrences[phone] - 1, 0) * 5, 20)
        diversity_bonus = {1: 0, 2: 20, 3: 38, 4: 52, 5: 62}.get(
            len(sources[phone]), 70
        )
        page_bonus = min(max(len(pages[phone]) - 1, 0) * 12, 36)

        labels = page_labels[phone]
        cross_page_bonus = 0
        if "homepage" in labels and "contact_page" in labels:
            cross_page_bonus = 25
        elif "contact_page" in labels and len(pages[phone]) >= 2:
            cross_page_bonus = 15

        final_score = raw_score + occurrence_bonus + diversity_bonus + page_bonus + cross_page_bonus

        evidence = [f"source:{source}" for source in sorted(sources[phone])]
        evidence.extend(f"page:{label}" for label in sorted(labels))
        evidence.extend(sorted(context_signals[phone]))
        if len(pages[phone]) >= 2:
            evidence.append(f"repeated_on_{len(pages[phone])}_pages")
        if len(sources[phone]) >= 2:
            evidence.append(f"source_diversity:{len(sources[phone])}")

        ranked.append(
            PhoneCandidate(
                phone=phone,
                score=final_score,
                source_url=best_source_url[phone],
                source=best_source[phone],
                occurrences=occurrences[phone],
                from_tel_link=tel_links[phone],
                source_diversity=len(sources[phone]),
                page_diversity=len(pages[phone]),
                evidence=evidence,
            )
        )

    return sorted(
        ranked,
        key=lambda candidate: (
            candidate.score,
            candidate.source_diversity,
            candidate.page_diversity,
            candidate.source == "schema_org",
            candidate.from_tel_link,
            candidate.occurrences,
        ),
        reverse=True,
    )


def _confidence(candidate: PhoneCandidate) -> int:
    source_base = {
        "schema_org": 80,
        "microdata": 78,
        "tel_link": 76,
        "footer": 58,
        "visible_text": 48,
    }
    confidence = source_base.get(candidate.source, 45)

    confidence += min(max(candidate.source_diversity - 1, 0) * 7, 21)
    confidence += min(max(candidate.page_diversity - 1, 0) * 5, 15)
    if candidate.occurrences >= 2:
        confidence += 3
    if candidate.from_tel_link and candidate.source != "tel_link":
        confidence += 3
    if any(item.startswith("positive_context:") for item in candidate.evidence):
        confidence += 4
    if any(item.startswith("negative_context:") for item in candidate.evidence):
        confidence -= 18
    if "page:contact_page" in candidate.evidence:
        confidence += 5

    return max(1, min(confidence, 99))


async def find_phone_for_domain(raw_domain: str, max_pages: int = 10) -> FinderResult:
    started_at = time.perf_counter()
    domain = clean_domain(raw_domain)

    def duration_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

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
    except Exception as exc:
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
