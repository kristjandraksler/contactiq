from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import phonenumbers
from bs4 import BeautifulSoup
from phonenumbers import PhoneNumberFormat


PHONE_PATTERN = re.compile(
    r"""
    (?:
        (?:\+|00)\s?\d{1,3}
        |
        0
    )
    [\s()./-]*
    \d
    (?:[\s()./-]*\d){6,13}
    """,
    re.VERBOSE,
)

CONTACT_KEYWORDS = (
    "kontakt",
    "contact",
    "contacts",
    "about",
    "o-nas",
    "o_nas",
    "o nas",
    "impressum",
    "imprint",
    "team",
    "podjetje",
    "company",
    "support",
    "podpora",
)

PRIORITY_PATHS = (
    "/kontakt",
    "/kontakt/",
    "/contact",
    "/contact/",
    "/contacts",
    "/about",
    "/about-us",
    "/o-nas",
    "/o-podjetju",
    "/impressum",
    "/imprint",
)

IGNORED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
    ".mp4",
    ".mp3",
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; ContactIQ/1.0; "
    "+public-business-contact-discovery)"
)

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "yahoo.de",
    "yahoo.fr",
    "yahoo.it",
    "yahoo.es",
    "outlook.com",
    "outlook.de",
    "outlook.fr",
    "hotmail.com",
    "hotmail.co.uk",
    "hotmail.de",
    "hotmail.fr",
    "live.com",
    "live.co.uk",
    "live.de",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
    "gmx.com",
    "gmx.de",
    "gmx.at",
    "gmx.ch",
    "mail.com",
    "zoho.com",
    "yandex.com",
    "yandex.ru",
    "tutanota.com",
    "tuta.com",
    "fastmail.com",

    # Slovenian and regional internet/mail providers.
    # These may be used by legitimate businesses, but they are not the
    # business website/domain and must never be scanned for a phone number.
    "telemach.net",
    "siol.net",
    "t-2.net",
    "amis.net",
    "volja.net",
    "email.si",
    "guest.arnes.si",
    "arnes.si",
    "net.hr",
    "vip.hr",
    "iskon.hr",
    "t-com.hr",
    "mts.rs",
    "eunet.rs",
    "sbb.rs",
}


def is_public_email_domain(raw_domain: str) -> bool:
    """Return True when the value belongs to a public/ISP mail provider."""
    return clean_domain(raw_domain) in PUBLIC_EMAIL_DOMAINS


@dataclass
class PhoneCandidate:
    phone: str
    score: int
    source_url: str
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


def clean_domain(domain: str) -> str:
    value = domain.strip().lower()

    if "@" in value:
        value = value.rsplit("@", 1)[1]

    value = value.replace("http://", "").replace("https://", "")
    value = value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    value = value.strip(".")

    if value.startswith("www."):
        value = value[4:]

    return value


def get_default_region(domain: str) -> str:
    tld_regions = {
        ".si": "SI",
        ".hr": "HR",
        ".at": "AT",
        ".de": "DE",
        ".it": "IT",
        ".rs": "RS",
        ".ba": "BA",
        ".me": "ME",
        ".mk": "MK",
        ".hu": "HU",
        ".ch": "CH",
        ".cz": "CZ",
        ".sk": "SK",
        ".pl": "PL",
        ".fr": "FR",
        ".es": "ES",
        ".nl": "NL",
        ".be": "BE",
        ".gb": "GB",
        ".uk": "GB",
        ".ie": "IE",
        ".us": "US",
        ".ca": "CA",
        ".au": "AU",
    }

    for suffix, region in tld_regions.items():
        if domain.endswith(suffix):
            return region

    return "SI"


def normalize_phone(raw_phone: str, region: str) -> str | None:
    value = raw_phone.strip()

    if value.lower().startswith("tel:"):
        value = value[4:]

    value = value.split(";", 1)[0]
    value = value.split("?", 1)[0]
    value = value.replace("\u00a0", " ")

    if value.startswith("00"):
        value = f"+{value[2:]}"

    try:
        parsed = phonenumbers.parse(value, region)

        if not phonenumbers.is_possible_number(parsed):
            return None

        if not phonenumbers.is_valid_number(parsed):
            return None

        return phonenumbers.format_number(
            parsed,
            PhoneNumberFormat.E164,
        )

    except phonenumbers.NumberParseException:
        return None


async def host_is_public(hostname: str) -> bool:
    try:
        address_info = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
        )
    except socket.gaierror:
        return False

    if not address_info:
        return False

    for item in address_info:
        raw_ip = item[4][0]

        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False

    return True


def same_registered_host(first_url: str, second_url: str) -> bool:
    first_host = (urlparse(first_url).hostname or "").lower()
    second_host = (urlparse(second_url).hostname or "").lower()

    first_host = first_host.removeprefix("www.")
    second_host = second_host.removeprefix("www.")

    return first_host == second_host


def is_contact_url(url: str) -> bool:
    lowered = url.lower()
    return any(keyword in lowered for keyword in CONTACT_KEYWORDS)


def calculate_page_bonus(url: str) -> int:
    lowered = url.lower()

    if "kontakt" in lowered or "contact" in lowered:
        return 35

    if "impressum" in lowered or "imprint" in lowered:
        return 25

    if "about" in lowered or "o-nas" in lowered:
        return 20

    return 5


def extract_contact_links(
    html: str,
    current_url: str,
    website_url: str,
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()

        if not href:
            continue

        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute_url = urljoin(current_url, href)
        parsed = urlparse(absolute_url)

        if parsed.scheme not in {"http", "https"}:
            continue

        if not same_registered_host(website_url, absolute_url):
            continue

        clean_url = absolute_url.split("#", 1)[0]

        if clean_url.lower().endswith(IGNORED_EXTENSIONS):
            continue

        anchor_text = anchor.get_text(" ", strip=True).lower()
        combined = f"{clean_url.lower()} {anchor_text}"

        if any(keyword in combined for keyword in CONTACT_KEYWORDS):
            links.append(clean_url)

    return list(dict.fromkeys(links))


def extract_candidates_from_html(
    html: str,
    page_url: str,
    domain: str,
) -> list[tuple[str, int, bool]]:
    soup = BeautifulSoup(html, "html.parser")
    region = get_default_region(domain)
    page_bonus = calculate_page_bonus(page_url)

    found: list[tuple[str, int, bool]] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()

        if not href.lower().startswith("tel:"):
            continue

        normalized = normalize_phone(href, region)

        if normalized:
            found.append(
                (
                    normalized,
                    100 + page_bonus,
                    True,
                )
            )

    visible_text = soup.get_text(" ", strip=True)

    for match in PHONE_PATTERN.finditer(visible_text):
        raw_phone = match.group(0)
        normalized = normalize_phone(raw_phone, region)

        if normalized:
            found.append(
                (
                    normalized,
                    35 + page_bonus,
                    False,
                )
            )

    return found


async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[str, str] | None:
    try:
        response = await client.get(url)

        if response.status_code >= 400:
            return None

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
        ):
            return None

        final_url = str(response.url)
        final_host = urlparse(final_url).hostname

        if not final_host:
            return None

        if not await host_is_public(final_host):
            return None

        return final_url, response.text

    except (
        httpx.TimeoutException,
        httpx.NetworkError,
        httpx.ProtocolError,
        httpx.TooManyRedirects,
    ):
        return None


async def resolve_website(
    client: httpx.AsyncClient,
    domain: str,
) -> tuple[str, str] | None:
    candidates = (
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    )

    for candidate_url in candidates:
        hostname = urlparse(candidate_url).hostname

        if not hostname:
            continue

        if not await host_is_public(hostname):
            continue

        result = await fetch_html(client, candidate_url)

        if result:
            return result

    return None


def rank_candidates(
    candidate_rows: list[tuple[str, int, bool, str]],
) -> list[PhoneCandidate]:
    scores: dict[str, int] = defaultdict(int)
    occurrences: dict[str, int] = defaultdict(int)
    tel_links: dict[str, bool] = defaultdict(bool)
    best_source: dict[str, str] = {}
    best_single_score: dict[str, int] = defaultdict(int)

    for phone, score, from_tel_link, source_url in candidate_rows:
        scores[phone] += score
        occurrences[phone] += 1

        if from_tel_link:
            tel_links[phone] = True

        if score > best_single_score[phone]:
            best_single_score[phone] = score
            best_source[phone] = source_url

    ranked: list[PhoneCandidate] = []

    for phone, score in scores.items():
        repeated_bonus = min(
            max(occurrences[phone] - 1, 0) * 12,
            48,
        )

        final_score = score + repeated_bonus

        ranked.append(
            PhoneCandidate(
                phone=phone,
                score=final_score,
                source_url=best_source[phone],
                occurrences=occurrences[phone],
                from_tel_link=tel_links[phone],
            )
        )

    return sorted(
        ranked,
        key=lambda candidate: (
            candidate.score,
            candidate.from_tel_link,
            candidate.occurrences,
        ),
        reverse=True,
    )


def score_to_confidence(candidate: PhoneCandidate) -> int:
    confidence = 40

    if candidate.from_tel_link:
        confidence += 30

    if candidate.score >= 100:
        confidence += 8

    if candidate.score >= 180:
        confidence += 8

    if candidate.score >= 250:
        confidence += 6

    if candidate.occurrences >= 2:
        confidence += 5

    if candidate.occurrences >= 3:
        confidence += 5

    if candidate.occurrences >= 4:
        confidence += 4

    return min(confidence, 99)


async def find_phone_for_domain(
    raw_domain: str,
    max_pages: int = 10,
) -> FinderResult:
    started_at = time.perf_counter()
    domain = clean_domain(raw_domain)

    if not domain or "." not in domain:
        duration = int(
            (time.perf_counter() - started_at) * 1000
        )

        return FinderResult(
            status="FAILED",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration,
            candidates=[],
            error="Domena ni veljavna.",
        )

    if domain in PUBLIC_EMAIL_DOMAINS:
        duration = int(
            (time.perf_counter() - started_at) * 1000
        )

        return FinderResult(
            status="EMAIL_FOUND",
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=0,
            scan_duration_ms=duration,
            candidates=[],
            error=(
                "E-poštni naslov je veljaven, vendar domena pripada "
                "javnemu ponudniku e-pošte, zato telefona ne iščemo."
            ),
        )

    timeout = httpx.Timeout(
        timeout=12.0,
        connect=6.0,
        read=12.0,
        write=6.0,
        pool=6.0,
    )

    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "sl,en;q=0.8",
    }

    candidate_rows: list[tuple[str, int, bool, str]] = []
    pages_scanned = 0
    website: str | None = None

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers=headers,
        follow_redirects=True,
    ) as client:
        resolved = await resolve_website(
            client,
            domain,
        )

        if not resolved:
            duration = int(
                (time.perf_counter() - started_at) * 1000
            )

            return FinderResult(
                status="FAILED",
                website=None,
                phone=None,
                confidence=None,
                source_url=None,
                pages_scanned=0,
                scan_duration_ms=duration,
                candidates=[],
                error=(
                    "Spletne strani domene ni bilo "
                    "mogoče odpreti."
                ),
            )

        website, homepage_html = resolved

        queue: list[str] = [website]
        queued: set[str] = {website}
        visited: set[str] = set()

        cached_pages: dict[str, str] = {
            website: homepage_html,
        }

        for path in PRIORITY_PATHS:
            priority_url = urljoin(
                website,
                path,
            )

            if priority_url not in queued:
                queue.append(priority_url)
                queued.add(priority_url)

        homepage_links = extract_contact_links(
            homepage_html,
            website,
            website,
        )

        for link in homepage_links:
            if link not in queued:
                queue.append(link)
                queued.add(link)

        while queue and pages_scanned < max_pages:
            current_url = queue.pop(0)

            if current_url in visited:
                continue

            visited.add(current_url)

            html = cached_pages.get(current_url)
            final_url = current_url

            if html is None:
                fetched = await fetch_html(
                    client,
                    current_url,
                )

                if not fetched:
                    continue

                final_url, html = fetched

            if not same_registered_host(
                website,
                final_url,
            ):
                continue

            pages_scanned += 1

            extracted = extract_candidates_from_html(
                html=html,
                page_url=final_url,
                domain=domain,
            )

            for phone, score, from_tel_link in extracted:
                candidate_rows.append(
                    (
                        phone,
                        score,
                        from_tel_link,
                        final_url,
                    )
                )

            if pages_scanned < max_pages:
                discovered_links = extract_contact_links(
                    html,
                    final_url,
                    website,
                )

                for link in discovered_links:
                    if (
                        link not in queued
                        and link not in visited
                    ):
                        queue.append(link)
                        queued.add(link)

    duration = int(
        (time.perf_counter() - started_at) * 1000
    )

    ranked = rank_candidates(candidate_rows)

    if not ranked:
        return FinderResult(
            status="NOT_FOUND",
            website=website,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=pages_scanned,
            scan_duration_ms=duration,
            candidates=[],
            error=None,
        )

    best = ranked[0]
    confidence = score_to_confidence(best)

    status = (
        "MATCHED"
        if confidence >= 75
        else "PARTIAL_MATCH"
    )

    return FinderResult(
        status=status,
        website=website,
        phone=best.phone,
        confidence=confidence,
        source_url=best.source_url,
        pages_scanned=pages_scanned,
        scan_duration_ms=duration,
        candidates=[
            asdict(candidate)
            for candidate in ranked[:5]
        ],
        error=None,
    )