from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import quote_plus, urlparse

import httpx

PUBLIC_PROVIDERS = {
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com",
    "yahoo.com", "icloud.com", "proton.me", "protonmail.com", "gmx.com",
}
PHONE_RE = re.compile(r"(?<!\d)(?:\+|00)?386[\s./-]?(?:\(0\)[\s./-]?)?\d(?:[\s./-]?\d){7,8}(?!\d)|(?<!\d)0[1-7](?:[\s./-]?\d){7,8}(?!\d)")
RESULT_RE = re.compile(r'<li class="b_algo".*?<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")

@dataclass
class Evidence:
    url: str
    title: str
    snippet: str
    exact_email: bool
    phones: list[str]

@dataclass
class IdentityResolution:
    email: str
    status: str
    person_name: str | None
    company_name: str | None
    company_domain: str | None
    phone: str | None
    phone_type: str | None
    confidence: int
    source_url: str | None
    evidence: list[str]


def _clean(value: str) -> str:
    return html.unescape(TAG_RE.sub(" ", value)).replace("\xa0", " ").strip()


def _normalise_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00386"): digits = digits[2:]
    if digits.startswith("386"): return f"+{digits}"
    if digits.startswith("0"): return f"+386{digits[1:]}"
    return value.strip()


def _name_candidate(email: str) -> str | None:
    local = email.split("@", 1)[0].lower()
    local = re.sub(r"\d+", " ", local)
    parts = [part for part in re.split(r"[._\-+]+", local) if len(part) > 1]
    ignored = {"info", "office", "mail", "contact", "business", "official", "hello"}
    parts = [part for part in parts if part not in ignored]
    if len(parts) < 2: return None
    return " ".join(part.capitalize() for part in parts[:3])


def _company_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host or any(x in host for x in ("bing.com", "google.com", "facebook.com", "linkedin.com")):
        return None
    return host


def _search_queries(email: str, name: str | None) -> Iterable[str]:
    yield f'"{email}"'
    yield f'"{email}" telefon OR phone OR kontakt'
    yield f'"{email}" podjetje OR company'
    if name:
        yield f'"{name}" telefon OR kontakt OR podjetje'
        yield f'"{name}" site:.si'


async def _bing_search(client: httpx.AsyncClient, query: str) -> list[Evidence]:
    response = await client.get(
        f"https://www.bing.com/search?q={quote_plus(query)}&count=10",
        headers={"User-Agent": "Mozilla/5.0 (compatible; ContactIQ/1.0)"},
        timeout=20,
    )
    response.raise_for_status()
    results: list[Evidence] = []
    for url, title, snippet in RESULT_RE.findall(response.text):
        title_clean, snippet_clean = _clean(title), _clean(snippet)
        content = f"{title_clean} {snippet_clean}"
        phones = list(dict.fromkeys(_normalise_phone(p) for p in PHONE_RE.findall(content)))
        results.append(Evidence(url=url, title=title_clean, snippet=snippet_clean, exact_email=False, phones=phones))
    return results


async def resolve_public_email(email: str) -> IdentityResolution:
    email = email.strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain not in PUBLIC_PROVIDERS:
        raise ValueError("This resolver is reserved for public email providers.")

    name = _name_candidate(email)
    evidences: list[Evidence] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for query in _search_queries(email, name):
            try:
                evidences.extend(await _bing_search(client, query))
            except httpx.HTTPError:
                continue

        # Verify the strongest result pages. Exact email on the source page is high-value evidence.
        for evidence in evidences[:8]:
            try:
                page = await client.get(evidence.url, headers={"User-Agent": "Mozilla/5.0 (compatible; ContactIQ/1.0)"}, timeout=12)
                text = _clean(page.text[:1_000_000])
                evidence.exact_email = email in text.lower()
                evidence.phones = list(dict.fromkeys(evidence.phones + [_normalise_phone(p) for p in PHONE_RE.findall(text)]))[:5]
            except httpx.HTTPError:
                pass

    ranked = sorted(evidences, key=lambda e: (e.exact_email, bool(e.phones)), reverse=True)
    best = ranked[0] if ranked else None
    phone_source = next((e for e in ranked if e.phones and e.exact_email), None) or next((e for e in ranked if e.phones), None)
    phone = phone_source.phones[0] if phone_source else None
    company_domain = _company_domain((phone_source or best).url) if (phone_source or best) else None

    confidence = 0
    notes: list[str] = []
    if name: confidence += 15; notes.append(f"Name candidate from email: {name}")
    if best and best.exact_email: confidence += 45; notes.append("Exact email found on a public source page")
    if phone_source and phone_source.exact_email: confidence += 30; notes.append("Phone and exact email appear on the same source")
    elif phone: confidence += 15; notes.append("Phone found in a related public result")
    if company_domain: confidence += 10; notes.append(f"Business domain detected: {company_domain}")
    confidence = min(confidence, 100)

    if phone and confidence >= 70: status = "VERIFIED"
    elif best or phone: status = "NEEDS_REVIEW"
    else: status = "NOT_FOUND"

    return IdentityResolution(
        email=email,
        status=status,
        person_name=name,
        company_name=None,
        company_domain=company_domain,
        phone=phone,
        phone_type="direct_business" if phone_source and phone_source.exact_email else ("company_main" if phone else None),
        confidence=confidence,
        source_url=(phone_source or best).url if (phone_source or best) else None,
        evidence=notes,
    )


def resolution_dict(result: IdentityResolution) -> dict:
    return asdict(result)
