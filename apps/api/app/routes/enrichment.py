from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_supabase
from app.services.company_cache import (
    get_cached_company_result,
    save_company_result,
)
from app.services.phone_finder import find_phone_for_domain
from app.services.providers import clean_domain


router = APIRouter(
    prefix="/enrichment",
    tags=["enrichment"],
)


CONTACT_SELECT_FIELDS = (
    "id,"
    "company_id,"
    "email,"
    "domain,"
    "website,"
    "phone,"
    "confidence,"
    "source_url,"
    "pages_scanned,"
    "scan_attempts,"
    "scan_duration_ms,"
    "last_scan,"
    "status,"
    "created_at,"
    "updated_at"
)


class BulkSelectedRequest(BaseModel):
    contact_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=25,
        description=(
            "Seznam UUID-jev kontaktov. "
            "Naenkrat je dovoljenih največ 25 kontaktov."
        ),
    )

    max_pages: int = Field(
        default=10,
        ge=1,
        le=20,
        description=(
            "Največje število pregledanih strani "
            "za posamezni kontakt."
        ),
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_contact_by_id(
    contact_id: str,
) -> dict[str, Any]:
    supabase = get_supabase()

    response = (
        supabase.table("email_targets")
        .select(CONTACT_SELECT_FIELDS)
        .eq("id", contact_id)
        .limit(1)
        .execute()
    )

    contacts = response.data or []

    if not contacts:
        raise HTTPException(
            status_code=404,
            detail="Kontakt ni bil najden.",
        )

    return contacts[0]


def get_contacts_by_ids(
    contact_ids: list[str],
) -> list[dict[str, Any]]:
    supabase = get_supabase()

    response = (
        supabase.table("email_targets")
        .select(CONTACT_SELECT_FIELDS)
        .in_("id", contact_ids)
        .execute()
    )

    contacts = response.data or []

    contact_map = {
        str(contact["id"]): contact
        for contact in contacts
    }

    return [
        contact_map[contact_id]
        for contact_id in contact_ids
        if contact_id in contact_map
    ]


def update_contact(
    contact_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    supabase = get_supabase()

    response = (
        supabase.table("email_targets")
        .update(payload)
        .eq("id", contact_id)
        .execute()
    )

    updated_rows = response.data or []

    if not updated_rows:
        raise HTTPException(
            status_code=500,
            detail="Rezultata ni bilo mogoče shraniti.",
        )

    return get_contact_by_id(contact_id)


async def enrich_contact_record(
    contact: dict[str, Any],
    max_pages: int,
) -> dict[str, Any]:
    contact_id = str(contact["id"])
    domain = clean_domain(
        str(contact.get("domain") or "")
    )

    current_attempts = int(
        contact.get("scan_attempts") or 0
    )
    next_attempts = current_attempts + 1

    if not domain or "." not in domain:
        updated_contact = update_contact(
            contact_id,
            {
                "phone": None,
                "confidence": None,
                "source_url": None,
                "status": "NOT_FOUND",
                "scan_attempts": next_attempts,
                "last_scan": utc_now_iso(),
            },
        )

        return {
            "success": False,
            "cached": False,
            "contact": updated_contact,
            "result": {
                "status": "NOT_FOUND",
                "error": "Kontakt nima veljavne domene.",
            },
        }

    try:
        cached_result, cached_company_id = (
            get_cached_company_result(domain)
        )

        if cached_result is not None:
            result = cached_result
            company_id = cached_company_id
            from_cache = True
        else:
            result = await find_phone_for_domain(
                raw_domain=domain,
                max_pages=max_pages,
            )
            company_id = save_company_result(
                domain,
                result,
            )
            from_cache = False

        payload: dict[str, Any] = {
            "website": result.website,
            "phone": result.phone,
            "confidence": result.confidence,
            "source_url": result.source_url,
            "pages_scanned": result.pages_scanned,
            "scan_attempts": next_attempts,
            "scan_duration_ms": result.scan_duration_ms,
            "last_scan": utc_now_iso(),
            "status": result.status,
        }

        if company_id:
            payload["company_id"] = company_id

        updated_contact = update_contact(
            contact_id,
            payload,
        )

        return {
            "success": result.status == "MATCHED",
            "cached": from_cache,
            "contact": updated_contact,
            "result": {
                **result.to_dict(),
                "cached": from_cache,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        updated_contact = update_contact(
            contact_id,
            {
                "status": "FAILED",
                "scan_attempts": next_attempts,
                "last_scan": utc_now_iso(),
            },
        )

        return {
            "success": False,
            "cached": False,
            "contact": updated_contact,
            "result": {
                "status": "FAILED",
                "error": str(exc),
                "cached": False,
            },
        }


def create_bulk_summary(
    results: list[dict[str, Any]],
) -> dict[str, int]:
    matched = 0
    not_found = 0
    failed = 0
    cached = 0

    for item_result in results:
        result = item_result.get("result", {})
        result_status = str(
            result.get("status", "FAILED")
        )

        if bool(result.get("cached")):
            cached += 1

        if result_status == "MATCHED":
            matched += 1
        elif result_status == "NOT_FOUND":
            not_found += 1
        else:
            failed += 1

    return {
        "matched": matched,
        "not_found": not_found,
        "failed": failed,
        "cached": cached,
    }


@router.get("/test")
async def test_enrichment(
    domain: str = Query(
        ...,
        min_length=3,
        description=(
            "Domena ali e-mail naslov za testiranje."
        ),
    ),
    max_pages: int = Query(
        default=10,
        ge=1,
        le=20,
        description=(
            "Največje število pregledanih strani."
        ),
    ),
) -> dict[str, Any]:
    normalized_domain = clean_domain(domain)

    cached_result, _ = get_cached_company_result(
        normalized_domain
    )

    if cached_result is not None:
        return {
            **cached_result.to_dict(),
            "cached": True,
        }

    result = await find_phone_for_domain(
        raw_domain=normalized_domain,
        max_pages=max_pages,
    )

    save_company_result(
        normalized_domain,
        result,
    )

    return {
        **result.to_dict(),
        "cached": False,
    }


@router.post("/contacts/{contact_id}")
async def enrich_contact(
    contact_id: str,
    max_pages: int = Query(
        default=10,
        ge=1,
        le=20,
        description=(
            "Največje število pregledanih strani."
        ),
    ),
) -> dict[str, Any]:
    try:
        contact = get_contact_by_id(contact_id)

        return await enrich_contact_record(
            contact=contact,
            max_pages=max_pages,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Kontakta ni bilo mogoče obogatiti: "
                f"{exc}"
            ),
        ) from exc


@router.post("/bulk-selected")
async def bulk_enrich_selected_contacts(
    request: BulkSelectedRequest,
) -> dict[str, Any]:
    try:
        unique_contact_ids = list(
            dict.fromkeys(request.contact_ids)
        )

        contacts = get_contacts_by_ids(
            unique_contact_ids
        )

        found_ids = {
            str(contact["id"])
            for contact in contacts
        }

        missing_ids = [
            contact_id
            for contact_id in unique_contact_ids
            if contact_id not in found_ids
        ]

        results: list[dict[str, Any]] = []

        for contact in contacts:
            results.append(
                await enrich_contact_record(
                    contact=contact,
                    max_pages=request.max_pages,
                )
            )

        summary = create_bulk_summary(results)

        return {
            "status": "completed",
            "requested": len(unique_contact_ids),
            "processed": len(results),
            "missing": len(missing_ids),
            "missing_ids": missing_ids,
            **summary,
            "items": results,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Izbranih kontaktov ni bilo mogoče "
                f"obdelati: {exc}"
            ),
        ) from exc


@router.post("/bulk")
async def bulk_enrich_contacts(
    limit: int = Query(
        default=10,
        ge=1,
        le=250,
        description=(
            "Največje število kontaktov, ki se "
            "obdelajo v enem zahtevku."
        ),
    ),
    max_pages: int = Query(
        default=10,
        ge=1,
        le=20,
        description=(
            "Največje število pregledanih strani "
            "na kontakt."
        ),
    ),
    retry_failed: bool = Query(
        default=False,
        description=(
            "Ali naj množična obdelava ponovno "
            "poskusi tudi kontakte s statusom FAILED."
        ),
    ),
) -> dict[str, Any]:
    try:
        supabase = get_supabase()

        allowed_statuses = [
            "NEW",
            "NOT_FOUND",
        ]

        if retry_failed:
            allowed_statuses.append("FAILED")

        response = (
            supabase.table("email_targets")
            .select(CONTACT_SELECT_FIELDS)
            .in_("status", allowed_statuses)
            .is_("phone", "null")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )

        contacts = response.data or []

        if not contacts:
            return {
                "status": "completed",
                "requested_limit": limit,
                "processed": 0,
                "matched": 0,
                "not_found": 0,
                "failed": 0,
                "cached": 0,
                "items": [],
                "message": (
                    "Ni kontaktov, ki bi ustrezali "
                    "pogojem za množično obdelavo."
                ),
            }

        results: list[dict[str, Any]] = []

        for contact in contacts:
            results.append(
                await enrich_contact_record(
                    contact=contact,
                    max_pages=max_pages,
                )
            )

        summary = create_bulk_summary(results)

        return {
            "status": "completed",
            "requested_limit": limit,
            "processed": len(results),
            **summary,
            "items": results,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Množične obdelave ni bilo mogoče "
                f"dokončati: {exc}"
            ),
        ) from exc