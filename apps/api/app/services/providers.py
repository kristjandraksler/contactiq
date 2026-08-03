from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass

from app.database import get_supabase


logger = logging.getLogger(__name__)

# Safe bootstrap fallback. Database values are merged into this cache.
# This keeps the API operational even if Supabase is briefly unavailable.
FALLBACK_PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.de",
    "yahoo.fr", "yahoo.it", "yahoo.es", "outlook.com", "outlook.de",
    "outlook.fr", "hotmail.com", "hotmail.co.uk", "hotmail.de", "hotmail.fr",
    "live.com", "live.co.uk", "live.de", "msn.com", "icloud.com", "me.com",
    "mac.com", "proton.me", "protonmail.com", "aol.com", "gmx.com",
    "gmx.de", "gmx.at", "gmx.ch", "mail.com", "zoho.com", "yandex.com",
    "yandex.ru", "tutanota.com", "tuta.com", "fastmail.com",
    "telemach.net", "siol.net", "t-2.net", "amis.net", "volja.net",
    "email.si", "guest.arnes.si", "arnes.si", "a1.net", "net.hr",
    "vip.hr", "iskon.hr", "t-com.hr", "mts.rs", "eunet.rs", "sbb.rs",
    "mailbox.org", "mail.ch", "posteo.net", "sapo.pt",
    "teol.net", "tel.net.ba", "bih.net.ba", "blic.net",
}

PUBLIC_EMAIL_CACHE_TTL_SECONDS = 300

_cache_lock = threading.Lock()
_cached_public_domains: set[str] = set(FALLBACK_PUBLIC_EMAIL_DOMAINS)
_cache_loaded_at = 0.0


def clean_domain(value: str) -> str:
    domain = value.strip().lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[1]
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/", 1)[0].split(":", 1)[0].strip(".")
    return domain.removeprefix("www.")


def refresh_public_email_domains(
    *,
    force: bool = False,
) -> set[str]:
    """
    Load public mailbox domains from Supabase and merge them with the safe
    fallback set. The cache is process-local and refreshes every five minutes.
    """
    global _cached_public_domains, _cache_loaded_at

    now = time.monotonic()

    if (
        not force
        and _cache_loaded_at
        and now - _cache_loaded_at < PUBLIC_EMAIL_CACHE_TTL_SECONDS
    ):
        return set(_cached_public_domains)

    with _cache_lock:
        now = time.monotonic()

        if (
            not force
            and _cache_loaded_at
            and now - _cache_loaded_at < PUBLIC_EMAIL_CACHE_TTL_SECONDS
        ):
            return set(_cached_public_domains)

        domains = set(FALLBACK_PUBLIC_EMAIL_DOMAINS)

        try:
            response = (
                get_supabase()
                .table("public_email_domains")
                .select("domain")
                .execute()
            )

            for row in response.data or []:
                raw_domain = str(row.get("domain") or "")
                domain = clean_domain(raw_domain)

                if domain and "." in domain:
                    domains.add(domain)

        except Exception:
            logger.exception(
                "Could not refresh public email domain cache; using fallback/cache."
            )

            if _cached_public_domains:
                return set(_cached_public_domains)

        _cached_public_domains = domains
        _cache_loaded_at = time.monotonic()

        return set(_cached_public_domains)


def get_public_email_domains() -> set[str]:
    return refresh_public_email_domains(force=False)


def public_email_cache_info() -> dict[str, int | float]:
    age_seconds = (
        max(0.0, time.monotonic() - _cache_loaded_at)
        if _cache_loaded_at
        else -1.0
    )

    return {
        "domains_cached": len(_cached_public_domains),
        "cache_age_seconds": round(age_seconds, 2),
        "cache_ttl_seconds": PUBLIC_EMAIL_CACHE_TTL_SECONDS,
    }


def is_public_email_domain(value: str) -> bool:
    domain = clean_domain(value)

    if not domain:
        return False

    return domain in get_public_email_domains()


GENERIC_LOCAL_PARTS = {
    "info",
    "office",
    "kontakt",
    "contact",
    "hello",
    "sales",
    "prodaja",
    "support",
    "podpora",
    "admin",
    "marketing",
    "booking",
    "service",
    "servis",
    "jobs",
    "careers",
    "hr",
    "reception",
    "recepcija",
}

NAME_SEPARATOR_RE = re.compile(r"[._+\-\s]+")
NON_LETTER_RE = re.compile(r"[^a-zA-ZÀ-ž]+")


NOISY_LOCAL_PART_TOKENS = {
    "admin", "mail", "email", "test", "user", "unknown", "guest",
    "support", "contact", "office", "info", "sales", "service",
    "hello", "jobs", "career", "booking", "team",
    "gamer", "gaming", "dragon", "killer", "queen", "king",
}

NOISY_LOCAL_PART_RE = re.compile(
    r"^(?:\d+|[a-z]{1,2}\d{3,}|\d{3,}[a-z]{1,2}|.*(?:xx|xxx|lol|test).*)$",
    re.IGNORECASE,
)


def public_email_is_researchable(value: str) -> bool:
    """
    Conservative quality gate for public-mailbox research.

    Returns False for generic aliases, mostly numeric local parts and obvious
    nicknames that are unlikely to represent a real person.
    """
    email = value.strip().lower()
    local_part = email.split("@", 1)[0].split("+", 1)[0]

    if not local_part or len(local_part) < 4:
        return False

    normalized = NON_LETTER_RE.sub("", local_part)

    if len(normalized) < 4:
        return False

    if local_part in GENERIC_LOCAL_PARTS:
        return False

    if NOISY_LOCAL_PART_RE.match(local_part):
        return False

    raw_tokens = [
        token
        for token in NAME_SEPARATOR_RE.split(local_part)
        if token
    ]

    cleaned_tokens = [
        NON_LETTER_RE.sub("", token)
        for token in raw_tokens
    ]

    cleaned_tokens = [
        token
        for token in cleaned_tokens
        if token
    ]

    if any(token in NOISY_LOCAL_PART_TOKENS for token in cleaned_tokens):
        return False

    letters = sum(char.isalpha() for char in local_part)
    digits = sum(char.isdigit() for char in local_part)

    if digits > letters:
        return False

    return True


@dataclass(frozen=True)
class EmailPersonHint:
    email: str
    local_part: str
    first_name: str | None
    last_name: str | None
    full_name: str | None
    search_terms: tuple[str, ...]
    reliable_name: bool


def extract_person_hint_from_email(
    value: str,
) -> EmailPersonHint:
    """
    Extract a conservative person hint from an e-mail address.

    Delimited local parts such as `alexandra.reichel` are treated as a
    reliable full name. Concatenated local parts such as `alexandrareichel`
    are not split by guessing; they are still preserved as exact search terms.
    """
    email = value.strip().lower()
    local_part = email.split("@", 1)[0]
    local_part = local_part.split("+", 1)[0]

    raw_tokens = [
        token
        for token in NAME_SEPARATOR_RE.split(local_part)
        if token
    ]

    tokens = [
        NON_LETTER_RE.sub("", token)
        for token in raw_tokens
    ]
    tokens = [
        token
        for token in tokens
        if token
    ]

    is_generic = (
        local_part in GENERIC_LOCAL_PARTS
        or any(
            token in GENERIC_LOCAL_PARTS
            for token in tokens
        )
    )

    first_name: str | None = None
    last_name: str | None = None
    reliable_name = False

    if (
        not is_generic
        and len(tokens) >= 2
        and len(tokens[0]) >= 2
        and len(tokens[-1]) >= 2
    ):
        first_name = tokens[0].capitalize()
        last_name = tokens[-1].capitalize()
        reliable_name = True

    full_name = (
        f"{first_name} {last_name}"
        if first_name and last_name
        else None
    )

    terms: list[str] = []

    if email and "@" in email:
        terms.append(email)

    if local_part and not is_generic:
        terms.append(local_part)

    if full_name:
        terms.append(full_name)

        if first_name and last_name:
            terms.append(f"{last_name} {first_name}")

    spaced_local = " ".join(tokens)

    if (
        spaced_local
        and spaced_local != local_part
        and not is_generic
    ):
        terms.append(spaced_local)

    return EmailPersonHint(
        email=email,
        local_part=local_part,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        search_terms=tuple(dict.fromkeys(terms)),
        reliable_name=reliable_name,
    )
