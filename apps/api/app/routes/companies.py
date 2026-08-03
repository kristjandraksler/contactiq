from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)

PAGE_SIZE = 1000


def _load_all_contacts() -> list[dict[str, Any]]:
    supabase = get_supabase()
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = (
            supabase.table("email_targets")
            .select(
                (
                    "id,email,domain,website,phone,confidence,source_url,"
                    "status,last_scan,created_at,updated_at,country_code,"
                    "country_name,country_flag,country_confidence,"
                    "country_source,phone_country_code,phone_country_name,"
                    "phone_country_flag,country_mismatch,person_match_type,"
                    "pages_scanned,scan_attempts,scan_duration_ms"
                )
            )
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        batch = response.data or []
        rows.extend(batch)

        if len(batch) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return rows


def _company_name(domain: str) -> str:
    base = domain.lower().removeprefix("www.").split(".")[0]
    return base.replace("-", " ").replace("_", " ").title() or domain


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        domain = str(row.get("domain") or "").strip().lower()
        if not domain:
            continue

        item = grouped.setdefault(
            domain,
            {
                "domain": domain,
                "name": _company_name(domain),
                "website": None,
                "country_code": None,
                "country_name": None,
                "country_flag": None,
                "contacts": 0,
                "phones": 0,
                "person_phones": 0,
                "company_phones": 0,
                "cross_border": 0,
                "matched": 0,
                "not_found": 0,
                "public_email": 0,
                "failed": 0,
                "pending": 0,
                "confidence_total": 0.0,
                "confidence_count": 0,
                "last_scan": None,
            },
        )

        item["contacts"] += 1

        if not item["website"] and row.get("website"):
            item["website"] = row.get("website")

        if not item["country_code"] and row.get("country_code"):
            item["country_code"] = row.get("country_code")
            item["country_name"] = row.get("country_name")
            item["country_flag"] = row.get("country_flag")

        status = str(row.get("status") or "")
        if status == "MATCHED":
            item["matched"] += 1
        elif status == "NOT_FOUND":
            item["not_found"] += 1
        elif status == "PUBLIC_EMAIL":
            item["public_email"] += 1
        elif status == "FAILED":
            item["failed"] += 1
        elif status == "NEW":
            item["pending"] += 1

        if row.get("phone"):
            item["phones"] += 1
            match_type = str(row.get("person_match_type") or "")
            if match_type in {"person_phone", "public_person"}:
                item["person_phones"] += 1
            elif match_type == "company_phone":
                item["company_phones"] += 1

        if row.get("country_mismatch"):
            item["cross_border"] += 1

        confidence = row.get("confidence")
        if confidence is not None:
            try:
                item["confidence_total"] += float(confidence)
                item["confidence_count"] += 1
            except (TypeError, ValueError):
                pass

        scan = row.get("last_scan") or row.get("updated_at")
        if scan and (not item["last_scan"] or str(scan) > str(item["last_scan"])):
            item["last_scan"] = scan

    result: list[dict[str, Any]] = []
    for item in grouped.values():
        contacts = int(item["contacts"])
        phones = int(item["phones"])
        confidence_count = int(item.pop("confidence_count"))
        confidence_total = float(item.pop("confidence_total"))
        item["success_rate"] = round((phones / contacts) * 100, 2) if contacts else 0.0
        item["average_confidence"] = (
            round(confidence_total / confidence_count, 2)
            if confidence_count
            else 0.0
        )
        item["is_public_provider"] = int(item["public_email"]) > 0 and int(item["matched"]) == 0
        result.append(item)

    return result


@router.get("")
def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    has_phone: bool | None = Query(default=None),
    public_provider: bool | None = Query(default=None),
    sort_by: str = Query(default="contacts"),
    sort_direction: str = Query(default="desc"),
) -> dict[str, Any]:
    try:
        items = _aggregate(_load_all_contacts())

        if search and search.strip():
            needle = search.strip().lower()
            items = [
                item
                for item in items
                if needle in str(item["domain"]).lower()
                or needle in str(item["name"]).lower()
                or needle in str(item.get("website") or "").lower()
            ]

        if country:
            normalized_country = country.strip().upper()
            items = [item for item in items if item.get("country_code") == normalized_country]

        if has_phone is True:
            items = [item for item in items if int(item["phones"]) > 0]
        elif has_phone is False:
            items = [item for item in items if int(item["phones"]) == 0]

        if public_provider is not None:
            items = [item for item in items if bool(item["is_public_provider"]) is public_provider]

        allowed_sort = {
            "name", "domain", "contacts", "phones", "success_rate",
            "average_confidence", "last_scan", "country_code",
        }
        if sort_by not in allowed_sort:
            raise HTTPException(status_code=400, detail="Invalid sort_by field.")

        reverse = sort_direction.strip().lower() != "asc"
        items.sort(
            key=lambda item: (
                item.get(sort_by) is not None,
                item.get(sort_by) or "",
            ),
            reverse=reverse,
        )

        total = len(items)
        offset = (page - 1) * page_size
        paginated = items[offset:offset + page_size]
        total_pages = (total + page_size - 1) // page_size if total else 0

        return {
            "items": paginated,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
            "summary": {
                "companies": total,
                "contacts": sum(int(item["contacts"]) for item in items),
                "phones": sum(int(item["phones"]) for item in items),
                "countries": len({item["country_code"] for item in items if item.get("country_code")}),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load companies: {exc}") from exc


@router.get("/{domain:path}")
def company_detail(domain: str) -> dict[str, Any]:
    normalized = unquote(domain).strip().lower().removeprefix("www.")
    try:
        rows = [
            row
            for row in _load_all_contacts()
            if str(row.get("domain") or "").strip().lower().removeprefix("www.") == normalized
        ]

        if not rows:
            raise HTTPException(status_code=404, detail="Company was not found.")

        company = _aggregate(rows)[0]
        contacts = sorted(
            rows,
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )

        sources = []
        seen_sources: set[str] = set()
        for row in contacts:
            source = str(row.get("source_url") or "").strip()
            if source and source not in seen_sources:
                seen_sources.add(source)
                sources.append(source)

        return {
            "company": company,
            "contacts": contacts,
            "sources": sources[:20],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load company: {exc}") from exc
