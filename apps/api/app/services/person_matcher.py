from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from .phone_parser import (
    PHONE_PATTERN,
    default_region,
    normalize_phone,
)


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

TOKEN_SPLIT_RE = re.compile(r"[._+\-\s]+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
WHITESPACE_RE = re.compile(r"\s+")


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
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def _normalize(value: str) -> str:
    return NON_ALNUM_RE.sub(
        " ",
        _ascii(value).lower(),
    ).strip()


def extract_person_identity(
    email: str,
) -> PersonIdentity:
    raw_email = email.strip().lower()
    local_part = raw_email.split("@", 1)[0]
    local_part = local_part.split("+", 1)[0]

    tokens = tuple(
        token
        for token in TOKEN_SPLIT_RE.split(
            _normalize(local_part)
        )
        if token and not token.isdigit()
    )

    is_generic = (
        local_part in GENERIC_LOCAL_PARTS
        or any(
            token in GENERIC_LOCAL_PARTS
            for token in tokens
        )
        or not tokens
    )

    first_name = (
        tokens[0]
        if tokens and not is_generic
        else None
    )
    last_name = (
        tokens[-1]
        if len(tokens) >= 2 and not is_generic
        else None
    )

    return PersonIdentity(
        email=raw_email,
        local_part=local_part,
        first_name=first_name,
        last_name=last_name,
        tokens=tokens,
        is_generic=is_generic,
    )


def _person_name(
    identity: PersonIdentity,
) -> str | None:
    parts = [
        value.capitalize()
        for value in (
            identity.first_name,
            identity.last_name,
        )
        if value
    ]
    return " ".join(parts) or None


def _normalize_phone_matches(
    text: str,
    domain: str,
) -> list[tuple[int, int, str]]:
    region = default_region(domain)
    matches: list[tuple[int, int, str]] = []

    for match in PHONE_PATTERN.finditer(text):
        normalized = normalize_phone(
            match.group(0),
            region,
        )

        if normalized:
            matches.append(
                (
                    match.start(),
                    match.end(),
                    normalized,
                )
            )

    return matches


def _best_phone_near_marker(
    text: str,
    marker_start: int,
    marker_end: int,
    domain: str,
    before_limit: int = 260,
    after_limit: int = 220,
) -> tuple[str, int, str] | None:
    phones = _normalize_phone_matches(
        text,
        domain,
    )

    candidates: list[
        tuple[int, str, str]
    ] = []

    for phone_start, phone_end, phone in phones:
        if phone_end <= marker_start:
            distance = marker_start - phone_end

            if distance <= before_limit:
                candidates.append(
                    (
                        distance,
                        phone,
                        "before_marker",
                    )
                )

        elif phone_start >= marker_end:
            distance = phone_start - marker_end

            if distance <= after_limit:
                candidates.append(
                    (
                        distance,
                        phone,
                        "after_marker",
                    )
                )

    if not candidates:
        return None

    distance, phone, direction = min(
        candidates,
        key=lambda item: item[0],
    )

    return phone, distance, direction


def _email_anchor_matches(
    anchor: Tag,
    identity: PersonIdentity,
) -> bool:
    href = str(
        anchor.get("href") or ""
    ).strip().lower()

    visible = anchor.get_text(
        " ",
        strip=True,
    ).lower()

    target = href.removeprefix("mailto:")
    target = target.split("?", 1)[0]

    return (
        target == identity.email
        or identity.email in visible
        or target.startswith(
            f"{identity.local_part}@"
        )
    )


def _context_texts_for_anchor(
    anchor: Tag,
) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()

    def add_text(element: Tag | None) -> None:
        if element is None:
            return

        text = WHITESPACE_RE.sub(
            " ",
            element.get_text(
                " ",
                strip=True,
            ),
        ).strip()

        if text and text not in seen:
            seen.add(text)
            texts.append(text)

    parent = (
        anchor.parent
        if isinstance(anchor.parent, Tag)
        else None
    )

    add_text(parent)

    if parent is not None:
        previous = parent.find_previous_sibling()
        following = parent.find_next_sibling()

        if isinstance(previous, Tag):
            add_text(previous)

        if isinstance(following, Tag):
            add_text(following)

        if isinstance(parent.parent, Tag):
            add_text(parent.parent)

    current = parent

    for _ in range(3):
        if (
            current is None
            or not isinstance(current.parent, Tag)
        ):
            break

        current = current.parent
        add_text(current)

    return texts


def _match_exact_email(
    soup: BeautifulSoup,
    identity: PersonIdentity,
    page_url: str,
    domain: str,
) -> list[PersonPhoneMatch]:
    matches: list[PersonPhoneMatch] = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        if not _email_anchor_matches(
            anchor,
            identity,
        ):
            continue

        for text in _context_texts_for_anchor(
            anchor
        ):
            lowered = text.lower()

            marker_candidates = [
                identity.email,
                identity.local_part,
                anchor.get_text(
                    " ",
                    strip=True,
                ).lower(),
            ]

            marker_start = -1
            marker_end = -1

            for marker in marker_candidates:
                marker = str(marker or "").lower()

                if not marker:
                    continue

                position = lowered.find(marker)

                if position != -1:
                    marker_start = position
                    marker_end = (
                        position + len(marker)
                    )
                    break

            if marker_start == -1:
                continue

            nearby = _best_phone_near_marker(
                text,
                marker_start,
                marker_end,
                domain,
            )

            if nearby is None:
                continue

            phone, distance, direction = nearby

            score = 220 - min(distance, 160)
            confidence = max(
                85,
                min(
                    99,
                    90
                    + int(
                        max(0, 80 - distance)
                        / 20
                    ),
                ),
            )

            matches.append(
                PersonPhoneMatch(
                    matched=True,
                    phone=phone,
                    confidence=confidence,
                    source_url=page_url,
                    person_name=_person_name(
                        identity
                    ),
                    score=score,
                    evidence=(
                        "exact_email",
                        "phone_near_email",
                        f"direction:{direction}",
                        f"distance:{distance}",
                    ),
                    block_text=text[:500],
                )
            )

    return matches


def _name_markers(
    identity: PersonIdentity,
) -> tuple[str, ...]:
    first = identity.first_name or ""
    last = identity.last_name or ""

    if first and last:
        return (
            f"{first} {last}",
            f"{last} {first}",
        )

    if first:
        return (first,)

    return ()


def _match_name_proximity(
    soup: BeautifulSoup,
    identity: PersonIdentity,
    page_url: str,
    domain: str,
) -> list[PersonPhoneMatch]:
    markers = _name_markers(identity)

    if not markers:
        return []

    matches: list[PersonPhoneMatch] = []

    for element in soup.find_all(
        ["p", "li", "div", "section", "td"],
    ):
        text = WHITESPACE_RE.sub(
            " ",
            element.get_text(
                " ",
                strip=True,
            ),
        ).strip()

        if not text or len(text) > 900:
            continue

        normalized = _normalize(text)

        marker = next(
            (
                candidate
                for candidate in markers
                if candidate in normalized
            ),
            None,
        )

        if marker is None:
            continue

        marker_start = normalized.find(marker)
        marker_end = marker_start + len(marker)

        nearby = _best_phone_near_marker(
            normalized,
            marker_start,
            marker_end,
            domain,
        )

        if nearby is None:
            continue

        phone, distance, direction = nearby

        score = 150 - min(distance, 110)
        confidence = max(
            65,
            min(
                88,
                74
                + int(
                    max(0, 60 - distance)
                    / 10
                ),
            ),
        )

        matches.append(
            PersonPhoneMatch(
                matched=True,
                phone=phone,
                confidence=confidence,
                source_url=page_url,
                person_name=_person_name(
                    identity
                ),
                score=score,
                evidence=(
                    "full_name",
                    "phone_near_name",
                    f"direction:{direction}",
                    f"distance:{distance}",
                ),
                block_text=text[:500],
            )
        )

    return matches


def find_person_phone_in_pages(
    email: str,
    pages: list[Any],
    domain: str,
) -> PersonPhoneMatch:
    identity = extract_person_identity(
        email
    )

    if identity.is_generic:
        return PersonPhoneMatch(
            matched=False,
            phone=None,
            confidence=None,
            source_url=None,
            person_name=None,
            score=0,
            evidence=("generic_email",),
        )

    exact_matches: list[
        PersonPhoneMatch
    ] = []

    name_matches: list[
        PersonPhoneMatch
    ] = []

    for page in pages:
        soup = BeautifulSoup(
            page.html,
            "html.parser",
        )

        exact_matches.extend(
            _match_exact_email(
                soup,
                identity,
                page.url,
                domain,
            )
        )

        if not exact_matches:
            name_matches.extend(
                _match_name_proximity(
                    soup,
                    identity,
                    page.url,
                    domain,
                )
            )

    candidates = (
        exact_matches
        if exact_matches
        else name_matches
    )

    if not candidates:
        return PersonPhoneMatch(
            matched=False,
            phone=None,
            confidence=None,
            source_url=None,
            person_name=_person_name(
                identity
            ),
            score=0,
            evidence=("no_person_match",),
        )

    candidates.sort(
        key=lambda item: (
            item.score,
            item.confidence or 0,
        ),
        reverse=True,
    )

    return candidates[0]
