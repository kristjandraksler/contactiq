from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase
from app.services.phone_finder import find_phone_for_domain


router = APIRouter(
    prefix="/enrichment",
    tags=["enrichment"],
)


@router.get("/test")
async def test_phone_finder(
    domain: str = Query(
        ...,
        min_length=3,
        description="Domena ali e-mail za testiranje.",
    ),
    max_pages: int = Query(
        default=10,
        ge=1,
        le=20,
    ),
) -> dict[str, object]:
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
    ),
) -> dict[str, object]:
    supabase = get_supabase()

    try:
        contact_response = (
            supabase.table("email_targets")
            .select(
                (
                    "id,"
                    "email,"
                    "domain,"
                    "scan_attempts"
                )
            )
            .eq("id", contact_id)
            .limit(1)
            .execute()
        )

        contacts = contact_response.data or []

        if not contacts:
            raise HTTPException(
                status_code=404,
                detail="Kontakt ne obstaja.",
            )

        contact = contacts[0]
        domain = contact.get("domain")

        if not domain:
            email = str(contact.get("email") or "")

            if "@" not in email:
                raise HTTPException(
                    status_code=400,
                    detail="Kontakt nima veljavne domene.",
                )

            domain = email.rsplit("@", 1)[1]

        previous_attempts = int(
            contact.get("scan_attempts") or 0
        )

        result = await find_phone_for_domain(
            raw_domain=str(domain),
            max_pages=max_pages,
        )

        now = datetime.now(timezone.utc).isoformat()

        update_data = {
            "website": result.website,
            "phone": result.phone,
            "confidence": result.confidence,
            "source_url": result.source_url,
            "pages_scanned": result.pages_scanned,
            "scan_attempts": previous_attempts + 1,
            "scan_duration_ms": result.scan_duration_ms,
            "last_scan": now,
            "status": result.status,
        }

        update_response = (
            supabase.table("email_targets")
            .update(update_data)
            .eq("id", contact_id)
            .execute()
        )

        return {
            "status": "completed",
            "contact_id": contact_id,
            "email": contact.get("email"),
            "result": result.to_dict(),
            "saved": bool(update_response.data),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Obogatitev kontakta ni uspela: {exc}",
        ) from exc