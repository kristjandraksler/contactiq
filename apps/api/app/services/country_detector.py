from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

import phonenumbers


@dataclass(frozen=True)
class CountryResult:
    code: str | None
    name: str | None
    flag: str | None
    confidence: int
    source: str
    language_code: str | None
    timezone_name: str | None
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COUNTRIES: dict[str, dict[str, str]] = {
    "SI": {"name": "Slovenija", "flag": "🇸🇮", "language": "sl", "timezone": "Europe/Ljubljana"},
    "HR": {"name": "Hrvaška", "flag": "🇭🇷", "language": "hr", "timezone": "Europe/Zagreb"},
    "AT": {"name": "Avstrija", "flag": "🇦🇹", "language": "de", "timezone": "Europe/Vienna"},
    "DE": {"name": "Nemčija", "flag": "🇩🇪", "language": "de", "timezone": "Europe/Berlin"},
    "CZ": {"name": "Češka", "flag": "🇨🇿", "language": "cs", "timezone": "Europe/Prague"},
    "SK": {"name": "Slovaška", "flag": "🇸🇰", "language": "sk", "timezone": "Europe/Bratislava"},
    "IT": {"name": "Italija", "flag": "🇮🇹", "language": "it", "timezone": "Europe/Rome"},
    "HU": {"name": "Madžarska", "flag": "🇭🇺", "language": "hu", "timezone": "Europe/Budapest"},
    "RS": {"name": "Srbija", "flag": "🇷🇸", "language": "sr", "timezone": "Europe/Belgrade"},
    "BA": {"name": "Bosna in Hercegovina", "flag": "🇧🇦", "language": "bs", "timezone": "Europe/Sarajevo"},
    "ME": {"name": "Črna gora", "flag": "🇲🇪", "language": "sr", "timezone": "Europe/Podgorica"},
    "MK": {"name": "Severna Makedonija", "flag": "🇲🇰", "language": "mk", "timezone": "Europe/Skopje"},
    "CH": {"name": "Švica", "flag": "🇨🇭", "language": "de", "timezone": "Europe/Zurich"},
    "FR": {"name": "Francija", "flag": "🇫🇷", "language": "fr", "timezone": "Europe/Paris"},
    "GB": {"name": "Združeno kraljestvo", "flag": "🇬🇧", "language": "en", "timezone": "Europe/London"},
    "NL": {"name": "Nizozemska", "flag": "🇳🇱", "language": "nl", "timezone": "Europe/Amsterdam"},
    "BE": {"name": "Belgija", "flag": "🇧🇪", "language": "nl", "timezone": "Europe/Brussels"},
    "EE": {"name": "Estonija", "flag": "🇪🇪", "language": "et", "timezone": "Europe/Tallinn"},
    "PL": {"name": "Poljska", "flag": "🇵🇱", "language": "pl", "timezone": "Europe/Warsaw"},
    "RO": {"name": "Romunija", "flag": "🇷🇴", "language": "ro", "timezone": "Europe/Bucharest"},
    "BG": {"name": "Bolgarija", "flag": "🇧🇬", "language": "bg", "timezone": "Europe/Sofia"},
    "ES": {"name": "Španija", "flag": "🇪🇸", "language": "es", "timezone": "Europe/Madrid"},
    "PT": {"name": "Portugalska", "flag": "🇵🇹", "language": "pt", "timezone": "Europe/Lisbon"},
    "US": {"name": "Združene države", "flag": "🇺🇸", "language": "en", "timezone": "America/New_York"},
    "CA": {"name": "Kanada", "flag": "🇨🇦", "language": "en", "timezone": "America/Toronto"},
}

TLD_TO_COUNTRY = {
    "si": "SI", "hr": "HR", "at": "AT", "de": "DE", "cz": "CZ", "sk": "SK",
    "it": "IT", "hu": "HU", "rs": "RS", "ba": "BA", "me": "ME", "mk": "MK",
    "ch": "CH", "fr": "FR", "uk": "GB", "nl": "NL", "be": "BE", "ee": "EE",
    "pl": "PL", "ro": "RO", "bg": "BG", "es": "ES", "pt": "PT",
    "ca": "CA", "us": "US",
}

TEXT_SIGNALS: dict[str, tuple[str, ...]] = {
    "SI": ("slovenija", "slovenia", "ljubljana", "maribor", "celje", "kranj", "koper", "nova gorica", "novo mesto", "ptuj"),
    "HR": ("hrvatska", "croatia", "zagreb", "split", "rijeka", "osijek", "varaždin", "varazdin", "zadar"),
    "AT": ("österreich", "austria", "wien", "vienna", "graz", "salzburg", "linz"),
    "DE": ("deutschland", "germany", "berlin", "münchen", "munich", "hamburg"),
    "CZ": ("česká republika", "czech republic", "czechia", "praha", "prague", "brno"),
    "SK": ("slovensko", "slovakia", "bratislava", "košice", "kosice"),
    "IT": ("italia", "italy", "milano", "milan", "roma", "rome", "trieste"),
    "HU": ("magyarország", "hungary", "budapest"),
    "RS": ("srbija", "serbia", "beograd", "belgrade", "novi sad"),
    "BA": ("bosna i hercegovina", "bosnia and herzegovina", "sarajevo", "banja luka"),
    "CH": ("schweiz", "switzerland", "suisse", "zürich", "zurich", "geneva"),
    "FR": ("france", "paris", "lyon", "marseille"),
    "GB": ("united kingdom", "england", "london", "manchester"),
    "NL": ("nederland", "netherlands", "amsterdam", "rotterdam"),
    "EE": ("eesti", "estonia", "tallinn"),
    "PL": ("polska", "poland", "warszawa", "warsaw", "kraków", "krakow"),
}


def _build_result(code: str | None, confidence: int, source: str) -> CountryResult:
    if not code or code not in COUNTRIES:
        return CountryResult(None, None, None, 0, "unknown", None, None)

    country = COUNTRIES[code]
    return CountryResult(
        code=code,
        name=country["name"],
        flag=country["flag"],
        confidence=max(0, min(confidence, 100)),
        source=source,
        language_code=country["language"],
        timezone_name=country["timezone"],
    )


def _country_from_phone(phone: str | None) -> str | None:
    if not phone:
        return None

    try:
        parsed = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException:
        return None

    region = phonenumbers.region_code_for_number(parsed)
    return region if region in COUNTRIES else None


def _country_from_tld(website_or_domain: str | None) -> str | None:
    if not website_or_domain:
        return None

    value = website_or_domain.strip().lower()
    host = (urlparse(value).hostname or "") if "://" in value else value.split("/", 1)[0].split(":", 1)[0]
    host = host.removeprefix("www.")
    suffix = host.rsplit(".", 1)[-1] if "." in host else ""
    return TLD_TO_COUNTRY.get(suffix)


def _page_text(pages: list[Any] | None) -> str:
    if not pages:
        return ""

    chunks: list[str] = []
    for page in pages:
        html = str(getattr(page, "html", "") or "")
        if not html:
            continue
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).lower()
        chunks.append(text[:20000])

    return " ".join(chunks)


def _country_from_text(text: str) -> tuple[str | None, int]:
    if not text:
        return None, 0

    scores: dict[str, int] = {}
    for code, markers in TEXT_SIGNALS.items():
        score = 0
        for marker in markers:
            occurrences = text.count(marker)
            if occurrences:
                score += min(occurrences, 3) * 8
        if score:
            scores[code] = score

    if not scores:
        return None, 0

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_code, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score < 8 or best_score - second_score < 4:
        return None, 0

    return best_code, min(90, 70 + best_score)



def detect_phone_country(
    phone: str | None,
) -> CountryResult:
    """
    Detect only the numbering-plan country of the selected phone.
    This does not represent the company's country.
    """
    return _build_result(
        _country_from_phone(phone),
        100 if _country_from_phone(phone) else 0,
        "phone" if _country_from_phone(phone) else "unknown",
    )


def phone_country_payload(
    result: CountryResult,
) -> dict[str, Any]:
    return {
        "phone_country_code": result.code,
        "phone_country_name": result.name,
        "phone_country_flag": result.flag,
        "phone_country_confidence": result.confidence,
    }


def country_mismatch_payload(
    company_country: CountryResult,
    phone_country: CountryResult,
) -> dict[str, Any]:
    mismatch = bool(
        company_country.code
        and phone_country.code
        and company_country.code != phone_country.code
    )

    return {
        "country_mismatch": mismatch,
        "is_cross_border": mismatch,
    }

def detect_country(
    *,
    phone: str | None = None,
    website_or_domain: str | None = None,
    pages: list[Any] | None = None,
    allow_tld: bool = True,
    entity: str = "company",
) -> CountryResult:
    """
    Backward-compatible entry point.

    entity="company" uses page text/TLD first.
    entity="person" uses the selected phone first.
    """
    if entity == "person":
        phone_result = detect_phone_country(phone)
        if phone_result.code:
            return phone_result

    return detect_company_country(
        phone=phone,
        website_or_domain=website_or_domain,
        pages=pages,
        allow_tld=allow_tld,
    )


LANG_TO_COUNTRY = {
    "sl": "SI", "hr": "HR", "bs": "BA", "sr": "RS", "mk": "MK",
    "de-at": "AT", "de-ch": "CH", "de-de": "DE",
    "sk": "SK", "cs": "CZ", "pl": "PL", "hu": "HU",
    "ro": "RO", "bg": "BG", "it": "IT", "fr": "FR",
    "nl": "NL", "et": "EE", "es": "ES", "pt": "PT",
}

CURRENCY_SIGNALS = {
    "BAM": "BA", "RSD": "RS", "PLN": "PL", "HUF": "HU",
    "CZK": "CZ", "RON": "RO", "BGN": "BG", "CHF": "CH",
}


def _result_v5(
    code: str | None,
    confidence: int,
    source: str,
    evidence: list[str],
) -> CountryResult:
    if not code or code not in COUNTRIES:
        return CountryResult(None, None, None, 0, "unknown", None, None, ())

    data = COUNTRIES[code]
    return CountryResult(
        code=code,
        name=data["name"],
        flag=data["flag"],
        confidence=max(0, min(confidence, 100)),
        source=source,
        language_code=data["language"],
        timezone_name=data["timezone"],
        evidence=tuple(dict.fromkeys(evidence)),
    )


def _locale_country(value: str | None) -> str | None:
    normalized = (value or "").strip().lower().replace("_", "-")
    if not normalized:
        return None
    if normalized in LANG_TO_COUNTRY:
        return LANG_TO_COUNTRY[normalized]
    if "-" in normalized:
        region = normalized.rsplit("-", 1)[-1].upper()
        if region in COUNTRIES:
            return region
    return LANG_TO_COUNTRY.get(normalized.split("-", 1)[0])


def _json_ld_countries(pages: list[Any] | None) -> list[str]:
    import json

    found: list[str] = []

    def walk(value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for page in pages or []:
        for raw in getattr(page, "json_ld", ()) or ():
            try:
                parsed = json.loads(raw)
            except Exception:
                continue

            for node in walk(parsed):
                for key, value in node.items():
                    normalized_key = str(key).replace("_", "").lower()
                    if normalized_key not in {
                        "addresscountry", "country", "countrycode"
                    }:
                        continue

                    text = str(value).strip()
                    upper = text.upper()
                    if upper in COUNTRIES:
                        found.append(upper)
                        continue

                    lowered = text.lower()
                    for code, data in COUNTRIES.items():
                        if lowered == data["name"].lower():
                            found.append(code)

    return found


def detect_company_country(
    *,
    phone: str | None = None,
    website_or_domain: str | None = None,
    pages: list[Any] | None = None,
    allow_tld: bool = True,
) -> CountryResult:
    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}

    def add(code: str | None, points: int, label: str) -> None:
        if not code or code not in COUNTRIES:
            return
        scores[code] = scores.get(code, 0) + points
        evidence.setdefault(code, []).append(label)

    for code in _json_ld_countries(pages):
        add(code, 45, f"schema_address:{code}")

    for page in pages or []:
        og_locale = getattr(page, "og_locale", None)
        html_lang = getattr(page, "html_lang", None)

        add(_locale_country(og_locale), 30, f"og_locale:{og_locale}")
        add(_locale_country(html_lang), 20, f"html_lang:{html_lang}")

        for hreflang in getattr(page, "hreflangs", ()) or ():
            add(_locale_country(hreflang), 10, f"hreflang:{hreflang}")

    text = _page_text(pages)

    for code, markers in TEXT_SIGNALS.items():
        occurrences = sum(min(text.count(marker), 3) for marker in markers)
        if occurrences:
            add(code, min(36, occurrences * 6), f"page_text:{code}")

    for currency, code in CURRENCY_SIGNALS.items():
        if re.search(rf"\b{re.escape(currency.lower())}\b", text):
            add(code, 20, f"currency:{currency}")

    if allow_tld:
        tld_code = _country_from_tld(website_or_domain)
        add(tld_code, 25, f"tld:{tld_code}")

    phone_code = _country_from_phone(phone)
    add(phone_code, 8, f"phone_fallback:{phone_code}")

    if not scores:
        return _result_v5(None, 0, "unknown", [])

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_code, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    margin = best_score - second_score

    confidence = min(
        99,
        max(55, 55 + best_score // 2 + min(margin, 20)),
    )

    best_evidence = evidence.get(best_code, [])
    source = (
        "combined"
        if len(best_evidence) > 1
        else best_evidence[0].split(":", 1)[0]
        if best_evidence
        else "unknown"
    )

    return _result_v5(best_code, confidence, source, best_evidence)


def country_payload(result: CountryResult) -> dict[str, Any]:
    return {
        "country_code": result.code,
        "country_name": result.name,
        "country_flag": result.flag,
        "country_confidence": result.confidence,
        "country_source": result.source,
        "country_evidence": list(result.evidence),
        "language_code": result.language_code,
        "timezone_name": result.timezone_name,
    }

