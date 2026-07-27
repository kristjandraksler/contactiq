from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

import phonenumbers
from bs4 import BeautifulSoup, Comment, Tag
from phonenumbers import PhoneNumberFormat

PHONE_PATTERN = re.compile(
    r"""(?:(?:\+|00)\s?\d{1,3}|0)[\s()./-]*\d(?:[\s()./-]*\d){6,13}""",
    re.VERBOSE,
)

POSITIVE_CONTEXT: dict[str, int] = {
    "telefon": 24,
    "telephone": 24,
    "phone": 24,
    "tel.": 18,
    "kontakt": 22,
    "contact": 22,
    "pokličite": 22,
    "poklicite": 22,
    "call us": 22,
    "centrala": 18,
    "reception": 16,
    "recepcija": 16,
    "office": 12,
    "pisarna": 12,
    "prodaja": 12,
    "sales": 12,
}

NEGATIVE_CONTEXT: dict[str, int] = {
    "fax": -20,
    "faks": -20,
    "telefaks": -20,
    "powered by": -20,
    "website by": -20,
    "web design": -20,
    "izdelava spletne": -20,
    "izdelava strani": -20,
    "digital agency": -18,
    "marketing agency": -15,
    "hosting": -15,
    "cookie": -12,
    "consent": -12,
    "gdpr": -12,
    "analytics": -10,
    "privacy policy": -8,
    "politika zasebnosti": -8,
}

NOISE_TAGS = ("script", "style", "noscript", "svg", "template", "iframe", "canvas")
NOISE_ATTRIBUTE_KEYWORDS = (
    "cookie",
    "consent",
    "gdpr",
        "cookiebot",
    "onetrust",
)


@dataclass(frozen=True)
class ExtractedPhone:
    phone: str
    score: int
    source: str
    from_tel_link: bool = False
    context_signals: tuple[str, ...] = ()


def default_region(domain: str) -> str:
    regions = {
        ".si": "SI", ".hr": "HR", ".at": "AT", ".de": "DE",
        ".it": "IT", ".rs": "RS", ".ba": "BA", ".me": "ME",
        ".mk": "MK", ".hu": "HU", ".ch": "CH", ".cz": "CZ",
        ".sk": "SK", ".pl": "PL", ".fr": "FR", ".es": "ES",
        ".nl": "NL", ".be": "BE", ".gb": "GB", ".uk": "GB",
        ".ie": "IE", ".us": "US", ".ca": "CA", ".au": "AU",
    }
    lowered = domain.lower().rstrip(".")
    return next((region for suffix, region in regions.items() if lowered.endswith(suffix)), "SI")


def normalize_phone(value: str, region: str) -> str | None:
    raw = value.strip()
    if raw.lower().startswith("tel:"):
        raw = raw[4:]
    raw = raw.split(";", 1)[0].split("?", 1)[0].replace("\u00a0", " ")
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def _walk_json(value: Any) -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"telephone", "phone", "contactpoint"}:
                if isinstance(item, str):
                    yield key, item
                elif isinstance(item, dict):
                    telephone = item.get("telephone")
                    if isinstance(telephone, str):
                        yield "telephone", telephone
                elif isinstance(item, list):
                    for nested in item:
                        yield from _walk_json(nested)
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _page_bonus(page_url: str) -> int:
    lowered = page_url.lower()
    if "kontakt" in lowered or "contact" in lowered:
        return 40
    if "impressum" in lowered or "imprint" in lowered:
        return 28
    if "about" in lowered or "o-nas" in lowered or "o-podjetju" in lowered:
        return 20
    return 5


def _context_score(text: str) -> tuple[int, tuple[str, ...]]:
    lowered = " ".join(text.lower().split())
    score = 0
    signals: list[str] = []

    # Apply only the strongest positive and strongest negative hit. This avoids
    # runaway scores when several synonyms occur in the same short block.
    positive_hits = [(weight, phrase) for phrase, weight in POSITIVE_CONTEXT.items() if phrase in lowered]
    negative_hits = [(weight, phrase) for phrase, weight in NEGATIVE_CONTEXT.items() if phrase in lowered]

    if positive_hits:
        weight, phrase = max(positive_hits)
        score += weight
        signals.append(f"positive_context:{phrase}")
    if negative_hits:
        weight, phrase = min(negative_hits)
        score += weight
        signals.append(f"negative_context:{phrase}")

    return score, tuple(signals)


def _element_context(element: Tag, limit: int = 90) -> str:
    parent = element.parent if isinstance(element.parent, Tag) else element
    text = parent.get_text(" ", strip=True)
    return text[:limit]


def _remove_noise(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()

    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    for element in list(soup.find_all(True)):
        if not isinstance(element, Tag) or element.parent is None:
            continue
        element_id = str(element.get("id") or "")
        classes = element.get("class") or []
        class_text = " ".join(str(value) for value in classes)
        marker = f"{element_id} {class_text}".lower()
        if any(keyword in marker for keyword in NOISE_ATTRIBUTE_KEYWORDS):
            element.decompose()


def _append_candidate(
    found: list[ExtractedPhone],
    raw_phone: str,
    region: str,
    base_score: int,
    page_bonus: int,
    source: str,
    context: str = "",
    from_tel_link: bool = False,
) -> None:
    phone = normalize_phone(raw_phone, region)
    if not phone:
        return
    context_delta, signals = _context_score(context)
    if source in {'schema_org','tel_link'}:
        context_delta=max(context_delta,0)
        signals=tuple(s for s in signals if not s.startswith('negative_context:'))
    found.append(
        ExtractedPhone(
            phone=phone,
            score=max(base_score + page_bonus + max(min(context_delta,10),-20), 1),
            source=source,
            from_tel_link=from_tel_link,
            context_signals=signals,
        )
    )


def extract_phones(html: str, page_url: str, domain: str) -> list[ExtractedPhone]:
    soup = BeautifulSoup(html, "html.parser")
    region = default_region(domain)
    page_bonus = _page_bonus(page_url)
    found: list[ExtractedPhone] = []

    # 1. Explicit tel: links are a strong, deliberate signal.
    tel_anchors: list[Tag] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href.lower().startswith("tel:"):
            _append_candidate(
                found,
                href,
                region,
                base_score=125,
                page_bonus=page_bonus,
                source="tel_link",
                context=_element_context(anchor),
                from_tel_link=True,
            )
            tel_anchors.append(anchor)

    # 2. Schema.org / JSON-LD Organization and LocalBusiness data.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_json = script.string or script.get_text(" ", strip=True)
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        for _, raw_phone in _walk_json(payload):
            _append_candidate(
                found,
                raw_phone,
                region,
                base_score=150,
                page_bonus=page_bonus,
                source="schema_org",
                context="schema.org telephone contact",
            )

    # 3. Microdata and generic telephone metadata.
    selector = (
        '[itemprop="telephone"], meta[name="telephone"], '
        'meta[property="business:contact_data:phone_number"]'
    )
    for element in soup.select(selector):
        raw_phone = str(element.get("content") or element.get_text(" ", strip=True) or "")
        _append_candidate(
            found,
            raw_phone,
            region,
            base_score=135,
            page_bonus=page_bonus,
            source="microdata",
            context=_element_context(element),
        )

    # Remove noisy DOM areas only after structured data and tel links are read.
    _remove_noise(soup)

    # Avoid counting tel-link text again as generic visible text.
    for anchor in tel_anchors:
        if anchor.parent is not None:
            anchor.decompose()

    # 4. Footer is useful but less trustworthy than explicit structured data.
    for footer in list(soup.find_all("footer")):
        footer_text = footer.get_text(" ", strip=True)
        for match in PHONE_PATTERN.finditer(footer_text):
            start, end = match.span()
            context = footer_text[max(0, start - 120):min(len(footer_text), end + 120)]
            _append_candidate(
                found,
                match.group(0),
                region,
                base_score=55,
                page_bonus=page_bonus,
                source="footer",
                context=context,
            )
        # Prevent footer numbers being counted a second time as body text.
        footer.decompose()

    # 5. Visible body text fallback.
    body_text = soup.get_text(" ", strip=True)
    for match in PHONE_PATTERN.finditer(body_text):
        start, end = match.span()
        context = body_text[max(0, start - 120):min(len(body_text), end + 120)]
        _append_candidate(
            found,
            match.group(0),
            region,
            base_score=35,
            page_bonus=page_bonus,
            source="visible_text",
            context=context,
        )

    return found