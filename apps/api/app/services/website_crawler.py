from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

CONTACT_KEYWORDS = (
    "kontakt", "contact", "contacts", "about", "o-nas", "o_nas", "o nas",
    "impressum", "imprint", "team", "podjetje", "company", "support", "podpora",
)
PRIORITY_PATHS = (
    "/kontakt", "/kontakt/", "/contact", "/contact/", "/contacts", "/about",
    "/about-us", "/o-nas", "/o-podjetju", "/impressum", "/imprint",
)
IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".doc",
    ".docx", ".xls", ".xlsx", ".zip", ".rar", ".mp4", ".mp3",
)
IGNORED_PATH_MARKERS = (
    "/wp-admin", "/wp-login", "/cart", "/checkout", "/kosarica", "/blagajna",
    "/feed", "/tag/", "/category/", "/author/",
)
USER_AGENT = "Mozilla/5.0 (compatible; ContactIQ/2.0; +public-business-contact-discovery)"


@dataclass(frozen=True)
class CrawledPage:
    url: str
    html: str


async def host_is_public(hostname: str) -> bool:
    try:
        address_info = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror:
        return False
    if not address_info:
        return False
    for item in address_info:
        try:
            ip = ipaddress.ip_address(item[4][0])
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


def same_host(first_url: str, second_url: str) -> bool:
    first = (urlparse(first_url).hostname or "").lower().removeprefix("www.")
    second = (urlparse(second_url).hostname or "").lower().removeprefix("www.")
    return bool(first) and first == second


def _canonical_url(url: str) -> str:
    clean, _ = urldefrag(url)
    parsed = urlparse(clean)
    path = parsed.path or "/"
    # Query strings frequently create duplicate pages and are not useful for
    # company contact discovery.
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def extract_contact_links(html: str, current_url: str, website_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = _canonical_url(urljoin(current_url, href))
        parsed = urlparse(absolute)
        lowered = absolute.lower()
        if parsed.scheme not in {"http", "https"} or not same_host(website_url, absolute):
            continue
        if lowered.endswith(IGNORED_EXTENSIONS):
            continue
        if any(marker in parsed.path.lower() for marker in IGNORED_PATH_MARKERS):
            continue
        combined = f"{lowered} {anchor.get_text(' ', strip=True).lower()}"
        if any(keyword in combined for keyword in CONTACT_KEYWORDS):
            links.append(absolute)
    return list(dict.fromkeys(links))


async def fetch_html(client: httpx.AsyncClient, url: str) -> CrawledPage | None:
    try:
        response = await client.get(url)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError, httpx.TooManyRedirects):
        return None
    if response.status_code >= 400:
        return None
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return None
    final_url = _canonical_url(str(response.url))
    final_host = urlparse(final_url).hostname
    if not final_host or not await host_is_public(final_host):
        return None
    return CrawledPage(final_url, response.text)


async def resolve_website(client: httpx.AsyncClient, domain: str) -> CrawledPage | None:
    candidates = (
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    )
    for candidate in candidates:
        hostname = urlparse(candidate).hostname
        if hostname and await host_is_public(hostname):
            result = await fetch_html(client, candidate)
            if result:
                return result
    return None


async def crawl_company_website(domain: str, max_pages: int = 10) -> tuple[str | None, list[CrawledPage]]:
    timeout = httpx.Timeout(timeout=12.0, connect=6.0, read=12.0, write=6.0, pool=6.0)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sl,en;q=0.8",
    }
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers=headers,
        follow_redirects=True,
    ) as client:
        homepage = await resolve_website(client, domain)
        if not homepage:
            return None, []

        website = homepage.url
        queue = [website]
        queued = {website}
        visited: set[str] = set()
        cache = {website: homepage}

        for path in PRIORITY_PATHS:
            url = _canonical_url(urljoin(website, path))
            if url not in queued:
                queue.append(url)
                queued.add(url)

        for link in extract_contact_links(homepage.html, website, website):
            if link not in queued:
                queue.append(link)
                queued.add(link)

        pages: list[CrawledPage] = []
        while queue and len(pages) < max_pages:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            page = cache.get(current) or await fetch_html(client, current)
            if not page or not same_host(website, page.url):
                continue
            pages.append(page)
            if len(pages) < max_pages:
                for link in extract_contact_links(page.html, page.url, website):
                    if link not in queued and link not in visited:
                        queue.append(link)
                        queued.add(link)

        return website, pages
