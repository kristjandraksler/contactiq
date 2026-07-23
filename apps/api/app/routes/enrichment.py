from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_supabase
from app.services.phone_finder import find_phone_for_domain


router = APIRouter(
    prefix="/enrichment",
    tags=["enrichment"],
)


CONTACT_SELECT_FIELDS = (
    "id,"
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
        max_length=250,
        description=(
            "Seznam UUID-jev kontaktov. "
            "Naenkrat je dovoljenih največ 250 kontaktov."
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
    domain = str(
        contact.get("domain") or ""
    ).strip()

    current_attempts = int(
        contact.get("scan_attempts") or 0
    )

    next_attempts = current_attempts + 1

    if not domain:
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
            "skipped": False,
            "contact": updated_contact,
            "result": {
                "status": "FAILED",
                "error": "Kontakt nima veljavne domene.",
            },
        }

    try:
        result = await find_phone_for_domain(
            raw_domain=domain,
            max_pages=max_pages,
        )

        is_skipped = (
            result.status == "SKIPPED_FREE_EMAIL"
        )

        database_status = (
            "NOT_FOUND"
            if is_skipped
            else result.status
        )

        payload: dict[str, Any] = {
            "website": result.website,
            "phone": result.phone,
            "confidence": result.confidence,
            "source_url": result.source_url,
            "pages_scanned": result.pages_scanned,
            "scan_attempts": next_attempts,
            "scan_duration_ms": result.scan_duration_ms,
            "last_scan": utc_now_iso(),
            "status": database_status,
        }

        updated_contact = update_contact(
            contact_id,
            payload,
        )

        is_success = result.status in {
            "MATCHED",
            "PARTIAL_MATCH",
        }

        return {
            "success": is_success,
            "skipped": is_skipped,
            "contact": updated_contact,
            "result": result.to_dict(),
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
            "skipped": False,
            "contact": updated_contact,
            "result": {
                "status": "FAILED",
                "error": str(exc),
            },
        }


def create_bulk_summary(
    results: list[dict[str, Any]],
) -> dict[str, int]:
    matched = 0
    partial_match = 0
    not_found = 0
    skipped = 0
    failed = 0

    for item_result in results:
        result_status = str(
            item_result.get(
                "result",
                {},
            ).get(
                "status",
                "FAILED",
            )
        )

        if result_status == "MATCHED":
            matched += 1

        elif result_status == "PARTIAL_MATCH":
            partial_match += 1

        elif result_status == "NOT_FOUND":
            not_found += 1

        elif result_status == "SKIPPED_FREE_EMAIL":
            skipped += 1

        else:
            failed += 1

    return {
        "matched": matched,
        "partial_match": partial_match,
        "not_found": not_found,
        "skipped": skipped,
        "failed": failed,
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
    result = await find_phone_for_domain(
        raw_domain=domain,
        max_pages=max_pages,
    )

    return result.to_dict()


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
            item_result = await enrich_contact_record(
                contact=contact,
                max_pages=request.max_pages,
            )

            results.append(item_result)

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
                "partial_match": 0,
                "not_found": 0,
                "skipped": 0,
                "failed": 0,
                "items": [],
                "message": (
                    "Ni kontaktov, ki bi ustrezali "
                    "pogojem za množično obdelavo."
                ),
            }

        results: list[dict[str, Any]] = []

        for contact in contacts:
            item_result = await enrich_contact_record(
                contact=contact,
                max_pages=max_pages,
            )

            results.append(item_result)

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