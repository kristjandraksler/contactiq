from __future__ import annotations

import html as html_lib
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .phone_finder import FinderResult
from .phone_parser import (
    PHONE_PATTERN,
    default_region,
    normalize_phone,
)
from .providers import (
    EmailPersonHint,
    extract_person_hint_from_email,
)


BING_SEARCH_URL = "https://www.bing.com/search"
USER_AGENT = (
    "Mozilla/5.0 (compatible; ContactIQ/2.0; "
    "+public-business-contact-discovery)"
)

BLOCKED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "tiktok.com",
}

MAX_SEARCH_RESULTS = 6
MAX_FETCHED_PAGES = 4


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    query: str


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

    if parsed.scheme not in {"http", "https"}:
        return False

    if not host:
        return False

    return not any(
        host == blocked
        or host.endswith(f".{blocked}")
        for blocked in BLOCKED_HOSTS
    )


def _build_queries(
    hint: EmailPersonHint,
) -> list[str]:
    queries = [
        f'"{hint.email}" telefon OR phone OR gsm',
        f'"{hint.local_part}" telefon OR phone OR gsm',
    ]

    if hint.full_name:
        queries.extend(
            [
                f'"{hint.full_name}" telefon',
                f'"{hint.full_name}" phone OR gsm',
            ]
        )

    return list(dict.fromkeys(queries))


async def _search_bing(
    client: httpx.AsyncClient,
    query: str,
) -> list[SearchHit]:
    try:
        response = await client.get(
            BING_SEARCH_URL,
            params={
                "q": query,
                "count": MAX_SEARCH_RESULTS,
            },
        )
        response.raise_for_status()
    except (
        httpx.HTTPError,
        httpx.TimeoutException,
    ):
        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    hits: list[SearchHit] = []

    for item in soup.select("li.b_algo"):
        anchor = item.select_one("h2 a")

        if anchor is None:
            continue

        raw_url = str(
            anchor.get("href") or ""
        )
        url = _unwrap_bing_url(raw_url)

        if not _is_allowed_result(url):
            continue

        snippet_node = item.select_one(
            ".b_caption p"
        )

        snippet = (
            snippet_node.get_text(
                " ",
                strip=True,
            )
            if snippet_node is not None
            else ""
        )

        hits.append(
            SearchHit(
                title=anchor.get_text(
                    " ",
                    strip=True,
                ),
                url=url,
                snippet=snippet,
                query=query,
            )
        )

        if len(hits) >= MAX_SEARCH_RESULTS:
            break

    return hits


def _marker_positions(
    text: str,
    hint: EmailPersonHint,
) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    markers: list[tuple[int, int, str]] = []

    for marker in hint.search_terms:
        marker_lower = marker.lower()
        start = 0

        while True:
            position = lowered.find(
                marker_lower,
                start,
            )

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


def _phone_candidates_near_markers(
    text: str,
    hint: EmailPersonHint,
    region: str,
    source_url: str,
    source: str,
) -> list[dict[str, Any]]:
    markers = _marker_positions(
        text,
        hint,
    )

    if not markers:
        return []

    phones: list[
        tuple[int, int, str]
    ] = []

    for match in PHONE_PATTERN.finditer(text):
        normalized = normalize_phone(
            match.group(0),
            region,
        )

        if normalized:
            phones.append(
                (
                    match.start(),
                    match.end(),
                    normalized,
                )
            )

    candidates: list[dict[str, Any]] = []

    for marker_start, marker_end, marker in markers:
        for phone_start, phone_end, phone in phones:
            if phone_end <= marker_start:
                distance = marker_start - phone_end
            elif phone_start >= marker_end:
                distance = phone_start - marker_end
            else:
                distance = 0

            if distance > 320:
                continue

            exact_email = (
                marker.lower()
                == hint.email.lower()
            )
            full_name = (
                hint.full_name is not None
                and marker.lower()
                == hint.full_name.lower()
            )

            score = 80 - min(
                distance // 4,
                70,
            )

            evidence = [
                f"source:{source}",
                f"distance:{distance}",
            ]

            if exact_email:
                score += 70
                evidence.append("exact_email")

            elif full_name:
                score += 40
                evidence.append("full_name")

            else:
                score += 20
                evidence.append(
                    "email_local_part"
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
                    "confidence": max(
                        35,
                        min(
                            88,
                            45 + score // 3,
                        ),
                    ),
                    "confidence_label": (
                        "HIGH"
                        if score >= 105
                        else "MEDIUM"
                        if score >= 70
                        else "LOW"
                    ),
                    "evidence_strength": (
                        9
                        if exact_email
                        else 6
                        if full_name
                        else 4
                    ),
                    "strengths": [
                        (
                            "Točen e-mail je javno "
                            "objavljen ob telefonu"
                            if exact_email
                            else "Ime oziroma e-mail "
                            "oznaka je objavljena ob "
                            "telefonu"
                        )
                    ],
                    "warnings": [
                        (
                            "Rezultat prihaja iz javnega "
                            "spletnega iskanja in ni "
                            "potrjen z domeno podjetja"
                        )
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
        response = await client.get(
            url,
            follow_redirects=True,
        )
    except (
        httpx.HTTPError,
        httpx.TimeoutException,
    ):
        return ""

    if response.status_code >= 400:
        return ""

    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if (
        "text/html" not in content_type
        and "application/xhtml+xml"
        not in content_type
    ):
        return ""

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
        ]
    ):
        tag.decompose()

    return soup.get_text(
        " ",
        strip=True,
    )


async def search_public_mailbox_person(
    email: str,
) -> FinderResult:
    started_at = time.perf_counter()
    hint = extract_person_hint_from_email(
        email
    )

    def duration_ms() -> int:
        return int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
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
        timeout=12.0,
        connect=6.0,
        read=12.0,
        write=6.0,
        pool=6.0,
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "sl,en;q=0.8",
    }

    all_hits: list[SearchHit] = []

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    ) as client:
        for query in _build_queries(hint):
            all_hits.extend(
                await _search_bing(
                    client,
                    query,
                )
            )

        deduplicated: list[SearchHit] = []
        seen_urls: set[str] = set()

        for hit in all_hits:
            if hit.url in seen_urls:
                continue

            seen_urls.add(hit.url)
            deduplicated.append(hit)

        candidates: list[
            dict[str, Any]
        ] = []

        # Search snippets first.
        for hit in deduplicated:
            snippet_text = html_lib.unescape(
                f"{hit.title} {hit.snippet}"
            )

            candidates.extend(
                _phone_candidates_near_markers(
                    snippet_text,
                    hint,
                    default_region(
                        _host(hit.url)
                    ),
                    hit.url,
                    "search_snippet",
                )
            )

        # Fetch only a few top public pages.
        fetched_pages = 0

        for hit in deduplicated[
            :MAX_FETCHED_PAGES
        ]:
            page_text = await _fetch_page_text(
                client,
                hit.url,
            )

            if not page_text:
                continue

            fetched_pages += 1

            candidates.extend(
                _phone_candidates_near_markers(
                    page_text,
                    hint,
                    default_region(
                        _host(hit.url)
                    ),
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

    # Merge duplicate phone candidates and keep strongest proof.
    merged: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        phone = str(candidate["phone"])
        current = merged.get(phone)

        if (
            current is None
            or int(candidate["score"])
            > int(current["score"])
        ):
            merged[phone] = candidate

    ranked = sorted(
        merged.values(),
        key=lambda candidate: (
            int(candidate["score"]),
            int(
                candidate.get(
                    "evidence_strength",
                    0,
                )
            ),
        ),
        reverse=True,
    )

    best = ranked[0]
    confidence = int(
        best.get("confidence") or 1
    )

    return FinderResult(
        status="MATCHED",
        website=None,
        phone=str(best["phone"]),
        confidence=confidence,
        source_url=str(
            best["source_url"]
        ),
        pages_scanned=fetched_pages,
        scan_duration_ms=duration_ms(),
        candidates=ranked[:5],
        error=None,
        confidence_label=(
            "HIGH"
            if confidence >= 75
            else "MEDIUM"
            if confidence >= 50
            else "LOW"
        ),
    )
