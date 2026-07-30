from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_supabase
from app.services.country_detector import (
    CountryResult,
    country_mismatch_payload,
    country_payload,
    phone_country_payload,
)
from app.services.phone_finder import FinderResult
from app.services.providers import clean_domain, is_public_email_domain


MATCHED_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(days=7)


COMPANY_CACHE_FIELDS = (
    "id,"
    "domain,"
    "website,"
    "phone,"
    "phone_status,"
    "phone_confidence,"
    "phone_source_url,"
    "phone_checked_at,"
    "phone_scan_duration_ms,"
    "phone_pages_scanned,"
    "phone_candidates,"
    "last_crawled_at,"
    "country_code,"
    "country_name,"
    "country_flag,"
    "country_confidence,"
    "country_source,"
    "language_code,"
    "timezone_name,"
    "phone_country_code,"
    "phone_country_name,"
    "phone_country_flag,"
    "phone_country_confidence,"
    "country_mismatch,"
    "is_cross_border"
)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _cache_ttl(status: str) -> timedelta | None:
    if status == "MATCHED":
        return MATCHED_TTL

    if status == "NOT_FOUND":
        return NOT_FOUND_TTL

    return None


def get_cached_company_result(
    raw_domain: str,
) -> tuple[FinderResult | None, str | None]:
    domain = clean_domain(raw_domain)

    if (
        not domain
        or "." not in domain
        or is_public_email_domain(domain)
    ):
        return None, None

    supabase = get_supabase()

    response = (
        supabase.table("companies")
        .select(COMPANY_CACHE_FIELDS)
        .eq("domain", domain)
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None, None

    company = rows[0]
    company_id = (
        str(company.get("id"))
        if company.get("id")
        else None
    )

    status = str(
        company.get("phone_status") or ""
    ).upper()

    checked_at = _parse_datetime(
        company.get("phone_checked_at")
    )

    ttl = _cache_ttl(status)

    if not checked_at or ttl is None:
        return None, company_id

    if datetime.now(timezone.utc) - checked_at > ttl:
        return None, company_id

    phone = company.get("phone")

    if status == "MATCHED" and not phone:
        return None, company_id

    raw_candidates = company.get("phone_candidates")
    candidates = (
        raw_candidates
        if isinstance(raw_candidates, list)
        else []
    )

    result = FinderResult(
        status=status,
        website=company.get("website"),
        phone=str(phone) if phone else None,
        confidence=company.get("phone_confidence"),
        source_url=company.get("phone_source_url"),
        pages_scanned=int(
            company.get("phone_pages_scanned") or 0
        ),
        scan_duration_ms=int(
            company.get("phone_scan_duration_ms") or 0
        ),
        candidates=candidates,
        error=None,
    )

    return result, company_id


def save_company_result(
    raw_domain: str,
    result: FinderResult,
    country: CountryResult | None = None,
    phone_country: CountryResult | None = None,
) -> str | None:
    domain = clean_domain(raw_domain)

    if (
        not domain
        or "." not in domain
        or is_public_email_domain(domain)
        or result.status not in {"MATCHED", "NOT_FOUND"}
    ):
        return None

    now = datetime.now(timezone.utc).isoformat()

    payload: dict[str, Any] = {
        "domain": domain,
        "website": result.website,
        "phone": (
            result.phone
            if result.status == "MATCHED"
            else None
        ),
        "phone_status": result.status,
        "phone_confidence": (
            result.confidence
            if result.status == "MATCHED"
            else None
        ),
        "phone_source_url": (
            result.source_url
            if result.status == "MATCHED"
            else None
        ),
        "phone_checked_at": now,
        "phone_scan_duration_ms": (
            result.scan_duration_ms
        ),
        "phone_pages_scanned": (
            result.pages_scanned
        ),
        "phone_candidates": (
            result.candidates
            if result.candidates
            else []
        ),
        "last_crawled_at": now,
    }

    if country is not None:
        payload.update(country_payload(country))

    if phone_country is not None:
        payload.update(
            phone_country_payload(phone_country)
        )

    if country is not None and phone_country is not None:
        payload.update(
            country_mismatch_payload(
                country,
                phone_country,
            )
        )

    supabase = get_supabase()

    response = (
        supabase.table("companies")
        .upsert(
            payload,
            on_conflict="domain",
        )
        .execute()
    )

    rows = response.data or []

    if rows and rows[0].get("id"):
        return str(rows[0]["id"])

    lookup = (
        supabase.table("companies")
        .select("id")
        .eq("domain", domain)
        .limit(1)
        .execute()
    )

    lookup_rows = lookup.data or []

    if not lookup_rows:
        return None

    company_id = lookup_rows[0].get("id")

    return str(company_id) if company_id else None