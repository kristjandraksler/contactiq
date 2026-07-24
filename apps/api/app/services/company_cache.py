from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_supabase
from app.services.phone_finder import FinderResult
from app.services.providers import clean_domain, is_public_email_domain


MATCHED_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(days=7)

COMPANY_CACHE_FIELDS = (
    "id,"
    "domain,"
    "website,"
    "phone,"
    "confidence,"
    "source_url,"
    "pages_scanned,"
    "scan_duration_ms,"
    "enrichment_status,"
    "verified_at"
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
    status = str(
        company.get("enrichment_status") or ""
    ).upper()

    verified_at = _parse_datetime(
        company.get("verified_at")
    )
    ttl = _cache_ttl(status)

    if not verified_at or ttl is None:
        return None, str(company.get("id"))

    if datetime.now(timezone.utc) - verified_at > ttl:
        return None, str(company.get("id"))

    phone = company.get("phone")

    if status == "MATCHED" and not phone:
        return None, str(company.get("id"))

    result = FinderResult(
        status=status,
        website=company.get("website"),
        phone=str(phone) if phone else None,
        confidence=company.get("confidence"),
        source_url=company.get("source_url"),
        pages_scanned=int(
            company.get("pages_scanned") or 0
        ),
        scan_duration_ms=0,
        candidates=[],
        error=None,
    )

    return result, str(company.get("id"))


def save_company_result(
    raw_domain: str,
    result: FinderResult,
) -> str | None:
    domain = clean_domain(raw_domain)

    if (
        not domain
        or "." not in domain
        or is_public_email_domain(domain)
        or result.status not in {"MATCHED", "NOT_FOUND"}
    ):
        return None

    payload: dict[str, Any] = {
        "domain": domain,
        "website": result.website,
        "phone": (
            result.phone
            if result.status == "MATCHED"
            else None
        ),
        "confidence": (
            result.confidence
            if result.status == "MATCHED"
            else None
        ),
        "source_url": (
            result.source_url
            if result.status == "MATCHED"
            else None
        ),
        "pages_scanned": result.pages_scanned,
        "scan_duration_ms": result.scan_duration_ms,
        "enrichment_status": result.status,
        "verified_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "last_crawled_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

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

    if rows:
        return str(rows[0].get("id"))

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

    return str(lookup_rows[0].get("id"))


