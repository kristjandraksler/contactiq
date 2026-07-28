from __future__ import annotations

import re
from dataclasses import dataclass

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.de",
    "yahoo.fr", "yahoo.it", "yahoo.es", "outlook.com", "outlook.de",
    "outlook.fr", "hotmail.com", "hotmail.co.uk", "hotmail.de", "hotmail.fr",
    "live.com", "live.co.uk", "live.de", "msn.com", "icloud.com", "me.com",
    "mac.com", "proton.me", "protonmail.com", "aol.com", "gmx.com",
    "gmx.de", "gmx.at", "gmx.ch", "mail.com", "zoho.com", "yandex.com",
    "yandex.ru", "tutanota.com", "tuta.com", "fastmail.com",
    # Slovenian and regional ISP / public mailbox domains. These are mailbox
    # providers, not the user's company website, and must never be crawled.
    "telemach.net", "siol.net", "t-2.net", "amis.net", "volja.net",
    "email.si", "guest.arnes.si", "arnes.si", "a1.net", "net.hr",
    "vip.hr", "iskon.hr", "t-com.hr", "mts.rs", "eunet.rs", "sbb.rs",
}


def clean_domain(value: str) -> str:
    domain = value.strip().lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[1]
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/", 1)[0].split(":", 1)[0].strip(".")
    return domain.removeprefix("www.")


def is_public_email_domain(value: str) -> bool:
    return clean_domain(value) in PUBLIC_EMAIL_DOMAINS

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

    return EmailPersonHint(
        email=email,
        local_part=local_part,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        search_terms=tuple(dict.fromkeys(terms)),
        reliable_name=reliable_name,
    )

