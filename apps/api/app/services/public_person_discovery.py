from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .phone_finder import FinderResult
from .phone_parser import PHONE_PATTERN, default_region, normalize_phone
from .providers import (
    EmailPersonHint,
    extract_person_hint_from_email,
    public_email_is_researchable,
)


logger = logging.getLogger(__name__)

BING_SEARCH_URL = "https://www.bing.com/search"
USER_AGENT = (
    "Mozilla/5.0 (compatible; ContactIQ/3.0; "
    "+public-person-intelligence)"
)

BLOCKED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
}

SEARCH_RESULTS_PER_QUERY = 8
MAX_QUERIES = 6
MAX_FETCHED_PAGES = 6
MAX_HOSTS = 4
PAGE_FETCH_CONCURRENCY = 3

BUSINESS_HINT_WORDS = {
    "company", "business", "director", "manager", "sales", "owner",
    "founder", "ceo", "kontakt", "contact", "team", "staff",
    "podjetje", "direktor", "prodaja", "zaposleni", "about",
}

COMPANY_PATH_HINTS = (
    "/contact", "/kontakt", "/team", "/staff", "/about", "/company",
    "/podjetje", "/impressum", "/imprint",
)


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    query: str
    host: str


def _host(value: str) -> str:
    return (
        urlparse(value).hostname
        or ""
    ).lower().removeprefix("www.")


def _unwrap_bing_url(value: str) -> str:
    parsed = urlparse(value)

    if "bing.com" not in _host(value):
        return value

    query = parse_qs(parsed.query)

    for key in ("u", "url", "r"):
        candidate = query.get(key)

        if candidate:
            return unquote(candidate[0])

    return value


def _is_allowed_result(url: str) -> bool:
    parsed = urlparse(url)
    host = _host(url)

    if parsed.scheme not in {"http", "https"} or not host:
        return False

    return not any(
        host == blocked
        or host.endswith(f".{blocked}")
        for blocked in BLOCKED_HOSTS
    )


def _build_queries(hint: EmailPersonHint) -> list[str]:
    queries: list[str] = [
        f'"{hint.email}"',
        f'"{hint.local_part}"',
    ]

    if hint.full_name:
        name = hint.full_name

        queries.extend(
            [
                f'"{name}" phone OR telefon OR gsm',
                f'"{name}" contact OR kontakt',
                f'"{name}" company OR podjetje',
                f'"{name}" director OR manager OR sales',
            ]
        )
    else:
        spaced = " ".join(
            term
            for term in hint.search_terms
            if "@" not in term and term != hint.local_part
        )

        if spaced:
            queries.extend(
                [
                    f'"{spaced}" phone OR telefon',
                    f'"{spaced}" company OR contact',
                ]
            )

    return list(dict.fromkeys(queries))[:MAX_QUERIES]


async def _search_bing(
    client: httpx.AsyncClient,
    query: str,
) -> list[SearchHit]:
    try:
        response = await client.get(
            BING_SEARCH_URL,
            params={
                "q": query,
                "count": SEARCH_RESULTS_PER_QUERY,
            },
        )
        response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        logger.warning("PUBLIC_SEARCH_QUERY_FAILED query=%s", query)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    hits: list[SearchHit] = []

    for item in soup.select("li.b_algo"):
        anchor = item.select_one("h2 a")

        if anchor is None:
            continue

        raw_url = str(anchor.get("href") or "")
        url = _unwrap_bing_url(raw_url)

        if not _is_allowed_result(url):
            continue

        host = _host(url)

        if not host:
            continue

        snippet_node = item.select_one(".b_caption p")
        snippet = (
            snippet_node.get_text(" ", strip=True)
            if snippet_node is not None
            else ""
        )

        hits.append(
            SearchHit(
                title=anchor.get_text(" ", strip=True),
                url=url,
                snippet=snippet,
                query=query,
                host=host,
            )
        )

        if len(hits) >= SEARCH_RESULTS_PER_QUERY:
            break

    return hits


def _marker_positions(
    text: str,
    hint: EmailPersonHint,
) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    markers: list[tuple[int, int, str]] = []

    for marker in hint.search_terms:
        marker_lower = marker.lower().strip()

        if len(marker_lower) < 4:
            continue

        start = 0

        while True:
            position = lowered.find(marker_lower, start)

            if position == -1:
                break

            markers.append(
                (
                    position,
                    position + len(marker_lower),
                    marker,
                )
            )
            start = position + 1

    return markers


def _business_context_score(text: str) -> int:
    lowered = text.lower()
    return min(
        30,
        sum(
            5
            for word in BUSINESS_HINT_WORDS
            if word in lowered
        ),
    )


def _phone_candidates_near_markers(
    text: str,
    hint: EmailPersonHint,
    region: str,
    source_url: str,
    source: str,
) -> list[dict[str, Any]]:
    markers = _marker_positions(text, hint)

    if not markers:
        return []

    phones: list[tuple[int, int, str]] = []

    for match in PHONE_PATTERN.finditer(text):
        normalized = normalize_phone(match.group(0), region)

        if normalized:
            phones.append(
                (
                    match.start(),
                    match.end(),
                    normalized,
                )
            )

    context_score = _business_context_score(text)
    candidates: list[dict[str, Any]] = []

    for marker_start, marker_end, marker in markers:
        for phone_start, phone_end, phone in phones:
            if phone_end <= marker_start:
                distance = marker_start - phone_end
            elif phone_start >= marker_end:
                distance = phone_start - marker_end
            else:
                distance = 0

            if distance > 450:
                continue

            exact_email = marker.lower() == hint.email.lower()
            full_name = (
                hint.full_name is not None
                and marker.lower() == hint.full_name.lower()
            )

            score = 75 - min(distance // 5, 65)
            evidence = [
                f"source:{source}",
                f"distance:{distance}",
            ]

            if exact_email:
                score += 75
                evidence.append("exact_email")
            elif full_name:
                score += 45
                evidence.append("full_name")
            else:
                score += 20
                evidence.append("identity_hint")

            if context_score:
                score += context_score
                evidence.append(f"business_context:{context_score}")

            confidence = max(
                35,
                min(
                    96,
                    42 + score // 2,
                ),
            )

            candidates.append(
                {
                    "phone": phone,
                    "score": score,
                    "source_url": source_url,
                    "source": source,
                    "occurrences": 1,
                    "from_tel_link": False,
                    "source_diversity": 1,
                    "page_diversity": 1,
                    "evidence": evidence,
                    "confidence": confidence,
                    "confidence_label": (
                        "VERY_HIGH"
                        if confidence >= 90
                        else "HIGH"
                        if confidence >= 75
                        else "MEDIUM"
                        if confidence >= 50
                        else "LOW"
                    ),
                    "evidence_strength": (
                        10
                        if exact_email
                        else 8
                        if full_name
                        else 5
                    ),
                    "strengths": [
                        (
                            "Exact public e-mail appears near the phone"
                            if exact_email
                            else "Identity hint appears near the phone"
                        )
                    ],
                    "warnings": [
                        "Public-web result; review the source before use"
                    ],
                    "person_name": hint.full_name,
                }
            )

    return candidates


async def _fetch_page_text(
    client: httpx.AsyncClient,
    url: str,
) -> str:
    try:
        response = await client.get(url, follow_redirects=True)
    except (httpx.HTTPError, httpx.TimeoutException):
        return ""

    if response.status_code >= 400:
        return ""

    content_type = response.headers.get("content-type", "").lower()

    if (
        "text/html" not in content_type
        and "application/xhtml+xml" not in content_type
    ):
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(
        ["script", "style", "noscript", "svg", "iframe"]
    ):
        tag.decompose()

    return soup.get_text(" ", strip=True)


def _rank_hits(
    hits: list[SearchHit],
    hint: EmailPersonHint,
) -> list[SearchHit]:
    def score(hit: SearchHit) -> tuple[int, int]:
        combined = f"{hit.title} {hit.snippet} {hit.url}".lower()
        value = 0

        if hint.email.lower() in combined:
            value += 100

        if hint.full_name and hint.full_name.lower() in combined:
            value += 60

        if hint.local_part.lower() in combined:
            value += 25

        value += _business_context_score(combined)

        if any(path in hit.url.lower() for path in COMPANY_PATH_HINTS):
            value += 15

        return value, -len(hit.url)

    return sorted(hits, key=score, reverse=True)


async def discover_public_person(
    email: str,
) -> FinderResult:
    started_at = time.perf_counter()
    hint = extract_person_hint_from_email(email)

    def duration_ms() -> int:
        return int((time.perf_counter() - started_at) * 1000)

    if not public_email_is_researchable(email):
        return FinderResult(
            status="NOT_FOUND",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error="Skipped low-quality public mailbox identity.",
            confidence_label="UNKNOWN",
        )

    if not hint.search_terms:
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
            confidence_label="UNKNOWN",
        )

    timeout = httpx.Timeout(
        timeout=15.0,
        connect=7.0,
        read=15.0,
        write=7.0,
        pool=7.0,
    )

    limits = httpx.Limits(
        max_connections=8,
        max_keepalive_connections=4,
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "sl,en,de,hr;q=0.7",
    }

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers=headers,
        follow_redirects=True,
    ) as client:
        query_results = await asyncio.gather(
            *(
                _search_bing(client, query)
                for query in _build_queries(hint)
            )
        )

        all_hits = [
            hit
            for query_hits in query_results
            for hit in query_hits
        ]

        deduplicated: list[SearchHit] = []
        seen_urls: set[str] = set()
        seen_hosts: dict[str, int] = {}

        for hit in _rank_hits(all_hits, hint):
            if hit.url in seen_urls:
                continue

            if seen_hosts.get(hit.host, 0) >= 2:
                continue

            seen_urls.add(hit.url)
            seen_hosts[hit.host] = seen_hosts.get(hit.host, 0) + 1
            deduplicated.append(hit)

        candidates: list[dict[str, Any]] = []

        for hit in deduplicated:
            snippet_text = html_lib.unescape(
                f"{hit.title} {hit.snippet}"
            )

            candidates.extend(
                _phone_candidates_near_markers(
                    snippet_text,
                    hint,
                    default_region(hit.host),
                    hit.url,
                    "search_snippet",
                )
            )

        selected: list[SearchHit] = []
        selected_hosts: set[str] = set()

        for hit in deduplicated:
            if len(selected) >= MAX_FETCHED_PAGES:
                break

            if hit.host not in selected_hosts:
                selected_hosts.add(hit.host)
                selected.append(hit)
                continue

            if len(selected_hosts) < MAX_HOSTS:
                selected.append(hit)

        semaphore = asyncio.Semaphore(PAGE_FETCH_CONCURRENCY)

        async def fetch(hit: SearchHit) -> tuple[SearchHit, str]:
            async with semaphore:
                return hit, await _fetch_page_text(client, hit.url)

        fetched_results = await asyncio.gather(
            *(fetch(hit) for hit in selected)
        )

        fetched_pages = 0

        for hit, page_text in fetched_results:
            if not page_text:
                continue

            fetched_pages += 1

            candidates.extend(
                _phone_candidates_near_markers(
                    page_text,
                    hint,
                    default_region(hit.host),
                    hit.url,
                    "public_web_page",
                )
            )

    if not candidates:
        return FinderResult(
            status="NOT_FOUND",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=fetched_pages,
            scan_duration_ms=duration_ms(),
            candidates=[],
            error=None,
            confidence_label="UNKNOWN",
        )

    merged: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        phone = str(candidate["phone"])
        current = merged.get(phone)

        if (
            current is None
            or int(candidate["score"]) > int(current["score"])
        ):
            merged[phone] = candidate

    ranked = sorted(
        merged.values(),
        key=lambda candidate: (
            int(candidate["score"]),
            int(candidate.get("evidence_strength", 0)),
        ),
        reverse=True,
    )

    best = ranked[0]
    confidence = int(best.get("confidence") or 1)

    return FinderResult(
        status="MATCHED",
        website=_host(str(best["source_url"])) or None,
        phone=str(best["phone"]),
        confidence=confidence,
        source_url=str(best["source_url"]),
        pages_scanned=fetched_pages,
        scan_duration_ms=duration_ms(),
        candidates=ranked[:8],
        error=None,
        confidence_label=(
            "VERY_HIGH"
            if confidence >= 90
            else "HIGH"
            if confidence >= 75
            else "MEDIUM"
            if confidence >= 50
            else "LOW"
        ),
    )


async def search_public_mailbox_person(
    email: str,
) -> FinderResult:
    return await discover_public_person(email)
