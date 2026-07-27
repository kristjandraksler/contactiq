from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

import phonenumbers
from bs4 import BeautifulSoup, Tag
from phonenumbers import PhoneNumberType

from .phone_parser import extract_phones

GENERIC_LOCAL_PARTS = {
    "info", "office", "kontakt", "contact", "hello", "sales", "prodaja",
    "support", "podpora", "admin", "marketing", "booking", "service",
    "servis", "jobs", "careers", "hr", "reception", "recepcija",
}
TOKEN_SPLIT_RE = re.compile(r"[._+\-\s]+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

@dataclass(frozen=True)
class PersonIdentity:
    email: str
    local_part: str
    first_name: str | None
    last_name: str | None
    tokens: tuple[str, ...]
    is_generic: bool

@dataclass(frozen=True)
class PersonPhoneMatch:
    matched: bool
    phone: str | None
    confidence: int | None
    source_url: str | None
    person_name: str | None
    score: int
    evidence: tuple[str, ...]
    block_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _ascii(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c))

def _normalize(value: str) -> str:
    return NON_ALNUM_RE.sub(" ", _ascii(value).lower()).strip()

def extract_person_identity(email: str) -> PersonIdentity:
    raw = email.strip().lower()
    local = raw.split("@", 1)[0].split("+", 1)[0]
    tokens = tuple(t for t in TOKEN_SPLIT_RE.split(_normalize(local)) if t and not t.isdigit())
    generic = local in GENERIC_LOCAL_PARTS or any(t in GENERIC_LOCAL_PARTS for t in tokens) or not tokens
    first = tokens[0] if tokens and not generic else None
    last = tokens[-1] if len(tokens) >= 2 and not generic else None
    return PersonIdentity(raw, local, first, last, tokens, generic)

def _identity_score(text: str, identity: PersonIdentity) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []
    compact = text.replace(" ", "")
    email_compact = _normalize(identity.email).replace(" ", "")
    local_compact = _normalize(identity.local_part).replace(" ", "")
    if email_compact and email_compact in compact:
        score += 150; evidence.append("exact_email")
    if local_compact and local_compact in compact:
        score += 100; evidence.append("email_local_part")
    first, last = identity.first_name or "", identity.last_name or ""
    if first and last:
        if f"{first} {last}" in text or f"{last} {first}" in text:
            score += 95; evidence.append("full_name")
        else:
            if first in text: score += 30; evidence.append("first_name")
            if last in text: score += 45; evidence.append("last_name")
    elif first and first in text:
        score += 35; evidence.append("single_name_token")
    return score, evidence

def _blocks(soup: BeautifulSoup, identity: PersonIdentity) -> list[Tag]:
    needles = {_normalize(identity.email), _normalize(identity.local_part), *identity.tokens}
    found: list[Tag] = []
    seen: set[int] = set()
    for node in soup.find_all(string=True):
        parent = node.parent
        if not isinstance(parent, Tag):
            continue
        text = _normalize(str(node))
        if not any(n and n in text for n in needles):
            continue
        current: Tag | None = parent
        for _ in range(5):
            if current is None: break
            block_text = current.get_text(" ", strip=True)
            if 20 <= len(block_text) <= 1800 and id(current) not in seen:
                found.append(current); seen.add(id(current))
            current = current.parent if isinstance(current.parent, Tag) else None
    return found

def _mobile_bonus(phone: str) -> tuple[int, str]:
    try:
        parsed = phonenumbers.parse(phone, None)
        t = phonenumbers.number_type(parsed)
    except phonenumbers.NumberParseException:
        return 0, "unknown"
    if t == PhoneNumberType.MOBILE: return 18, "mobile"
    if t == PhoneNumberType.FIXED_LINE_OR_MOBILE: return 12, "fixed_or_mobile"
    if t == PhoneNumberType.FIXED_LINE: return 0, "fixed_line"
    return 0, "other"

def find_person_phone_in_pages(email: str, pages: list[Any], domain: str) -> PersonPhoneMatch:
    identity = extract_person_identity(email)
    if identity.is_generic:
        return PersonPhoneMatch(False, None, None, None, None, 0, ("generic_email",))
    matches: list[PersonPhoneMatch] = []
    for page in pages:
        soup = BeautifulSoup(page.html, "html.parser")
        for block in _blocks(soup, identity):
            block_text = block.get_text(" ", strip=True)
            normalized = _normalize(block_text)
            identity_score, evidence = _identity_score(normalized, identity)
            if identity_score < 45:
                continue
            phones = extract_phones(str(block), page.url, domain)
            for item in phones:
                bonus, ptype = _mobile_bonus(item.phone)
                score = identity_score + min(item.score, 80) + bonus
                ev = [*evidence, f"phone_source:{item.source}", f"phone_type:{ptype}"]
                if item.from_tel_link:
                    score += 10; ev.append("tel_link")
                confidence = max(1, min(int(45 + score * 0.28), 99))
                name = " ".join(x.capitalize() for x in (identity.first_name, identity.last_name) if x) or None
                matches.append(PersonPhoneMatch(True, item.phone, confidence, page.url, name, score, tuple(dict.fromkeys(ev)), block_text[:500]))
    if not matches:
        return PersonPhoneMatch(False, None, None, None, None, 0, ("no_person_match",))
    matches.sort(key=lambda x: (x.score, x.confidence or 0), reverse=True)
    best = matches[0]
    strong = {"exact_email", "email_local_part", "full_name"}
    if not strong.intersection(best.evidence):
        return PersonPhoneMatch(False, None, None, None, best.person_name, best.score, (*best.evidence, "rejected_weak_identity_match"))
    return best
