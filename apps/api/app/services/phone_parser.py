from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

import phonenumbers
from bs4 import BeautifulSoup
from phonenumbers import PhoneNumberFormat

PHONE_PATTERN = re.compile(
    r"""(?:(?:\+|00)\s?\d{1,3}|0)[\s()./-]*\d(?:[\s()./-]*\d){6,13}""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class ExtractedPhone:
    phone: str
    score: int
    source: str
    from_tel_link: bool = False


def default_region(domain: str) -> str:
    regions = {
        ".si": "SI", ".hr": "HR", ".at": "AT", ".de": "DE",
        ".it": "IT", ".rs": "RS", ".ba": "BA", ".me": "ME",
        ".mk": "MK", ".hu": "HU", ".ch": "CH", ".cz": "CZ",
        ".sk": "SK", ".pl": "PL", ".fr": "FR", ".es": "ES",
        ".nl": "NL", ".be": "BE", ".gb": "GB", ".uk": "GB",
        ".ie": "IE", ".us": "US", ".ca": "CA", ".au": "AU",
    }
    return next((region for suffix, region in regions.items() if domain.endswith(suffix)), "SI")


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
        return 35
    if "impressum" in lowered or "imprint" in lowered:
        return 25
    if "about" in lowered or "o-nas" in lowered:
        return 20
    return 5


def extract_phones(html: str, page_url: str, domain: str) -> list[ExtractedPhone]:
    soup = BeautifulSoup(html, "html.parser")
    region = default_region(domain)
    page_bonus = _page_bonus(page_url)
    found: list[ExtractedPhone] = []

    # 1. Explicit tel: links are the strongest HTML signal.
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href.lower().startswith("tel:"):
            phone = normalize_phone(href, region)
            if phone:
                found.append(ExtractedPhone(phone, 125 + page_bonus, "tel_link", True))

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
            phone = normalize_phone(raw_phone, region)
            if phone:
                found.append(ExtractedPhone(phone, 150 + page_bonus, "schema_org"))

    # 3. Microdata and generic telephone metadata.
    for element in soup.select('[itemprop="telephone"], meta[name="telephone"], meta[property="business:contact_data:phone_number"]'):
        raw_phone = str(element.get("content") or element.get_text(" ", strip=True) or "")
        phone = normalize_phone(raw_phone, region)
        if phone:
            found.append(ExtractedPhone(phone, 135 + page_bonus, "microdata"))

    # 4. Footer text is usually a company-level contact and ranks above body text.
    for footer in soup.find_all("footer"):
        for match in PHONE_PATTERN.finditer(footer.get_text(" ", strip=True)):
            phone = normalize_phone(match.group(0), region)
            if phone:
                found.append(ExtractedPhone(phone, 90 + page_bonus, "footer"))

    # 5. Visible body text fallback.
    for match in PHONE_PATTERN.finditer(soup.get_text(" ", strip=True)):
        phone = normalize_phone(match.group(0), region)
        if phone:
            found.append(ExtractedPhone(phone, 35 + page_bonus, "visible_text"))

    return found
