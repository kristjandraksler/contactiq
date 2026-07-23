import csv
import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_supabase


router = APIRouter(
    tags=["Leads"],
)


ALLOWED_STATUSES = {
    "NEW",
    "MATCHED",
    "PARTIAL_MATCH",
    "NOT_FOUND",
    "FAILED",
}


def normalize_status(status: str | None) -> str | None:
    normalized_status = (
        status.strip().upper()
        if status
        else None
    )

    if (
        normalized_status
        and normalized_status not in ALLOWED_STATUSES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Neveljaven status. Dovoljeni statusi so: "
                "NEW, MATCHED, PARTIAL_MATCH, NOT_FOUND, FAILED."
            ),
        )

    return normalized_status


def sanitize_search(search: str) -> str:
    return (
        search.strip()
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


@router.get("/leads")
def list_leads(
    page: int = Query(
        default=1,
        ge=1,
        description="Številka strani.",
    ),
    page_size: int = Query(
        default=25,
        ge=1,
        le=250,
        description="Število zapisov na stran.",
    ),
    search: str | None = Query(
        default=None,
        description="Iskanje po emailu, domeni ali telefonu.",
    ),
    has_phone: bool | None = Query(
        default=None,
        description=(
            "Če je true, vrne samo kontakte "
            "z najdenim telefonom."
        ),
    ),
    confidence_min: float | None = Query(
        default=None,
        ge=0,
        le=100,
        description="Najnižji dovoljeni confidence.",
    ),
    status: str | None = Query(
        default=None,
        description=(
            "Filter po statusu: NEW, MATCHED, PARTIAL_MATCH, "
            "NOT_FOUND ali FAILED."
        ),
    ),
) -> dict[str, object]:
    try:
        supabase = get_supabase()
        normalized_status = normalize_status(status)

        offset = (page - 1) * page_size
        range_end = offset + page_size - 1

        query = (
            supabase.table("email_targets")
            .select(
                (
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
                ),
                count="exact",
            )
        )

        if normalized_status:
            query = query.eq(
                "status",
                normalized_status,
            )

        if has_phone is True:
            query = query.not_.is_(
                "phone",
                "null",
            )

        if has_phone is False:
            query = query.is_(
                "phone",
                "null",
            )

        if confidence_min is not None:
            query = query.gte(
                "confidence",
                confidence_min,
            )

        if search and search.strip():
            safe_search = sanitize_search(search)

            query = query.or_(
                f"email.ilike.%{safe_search}%,"
                f"domain.ilike.%{safe_search}%,"
                f"phone.ilike.%{safe_search}%"
            )

        response = (
            query
            .order(
                "created_at",
                desc=True,
            )
            .range(
                offset,
                range_end,
            )
            .execute()
        )

        total = response.count or 0

        total_pages = (
            (total + page_size - 1) // page_size
            if total > 0
            else 0
        )

        return {
            "items": response.data or [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
            "filters": {
                "search": (
                    search.strip()
                    if search
                    else None
                ),
                "has_phone": has_phone,
                "confidence_min": confidence_min,
                "status": normalized_status,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load leads: {exc}",
        ) from exc


@router.get("/leads/export/csv")
def export_leads_csv(
    search: str | None = Query(
        default=None,
        description="Iskanje po emailu, domeni ali telefonu.",
    ),
    has_phone: bool | None = Query(
        default=None,
        description=(
            "Če je true, izvozi samo kontakte "
            "s telefonom."
        ),
    ),
    confidence_min: float | None = Query(
        default=None,
        ge=0,
        le=100,
        description="Najnižji dovoljeni confidence.",
    ),
    status: str | None = Query(
        default=None,
        description="Filter po statusu.",
    ),
):
    try:
        supabase = get_supabase()
        normalized_status = normalize_status(status)

        query = (
            supabase.table("email_targets")
            .select(
                (
                    "email,"
                    "domain,"
                    "website,"
                    "phone,"
                    "confidence,"
                    "source_url,"
                    "status,"
                    "last_scan,"
                    "created_at"
                )
            )
        )

        if normalized_status:
            query = query.eq(
                "status",
                normalized_status,
            )

        if has_phone is True:
            query = query.not_.is_(
                "phone",
                "null",
            )

        if has_phone is False:
            query = query.is_(
                "phone",
                "null",
            )

        if confidence_min is not None:
            query = query.gte(
                "confidence",
                confidence_min,
            )

        if search and search.strip():
            safe_search = sanitize_search(search)

            query = query.or_(
                f"email.ilike.%{safe_search}%,"
                f"domain.ilike.%{safe_search}%,"
                f"phone.ilike.%{safe_search}%"
            )

        response = (
            query
            .order(
                "created_at",
                desc=True,
            )
            .execute()
        )

        output = io.StringIO()
        output.write("\ufeff")

        writer = csv.writer(
            output,
            delimiter=";",
        )

        writer.writerow(
            [
                "Telefon",
                "E-mail",
                "Domena",
                "Spletna stran",
                "Confidence",
                "Status",
                "Vir",
                "Zadnja obdelava",
            ]
        )

        for lead in response.data or []:
            writer.writerow(
                [
                    lead.get("phone") or "",
                    lead.get("email") or "",
                    lead.get("domain") or "",
                    lead.get("website") or "",
                    (
                        lead.get("confidence")
                        if lead.get("confidence") is not None
                        else ""
                    ),
                    lead.get("status") or "",
                    lead.get("source_url") or "",
                    lead.get("last_scan") or "",
                ]
            )

        csv_content = output.getvalue()
        output.close()

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    'attachment; filename="contactiq-phones.csv"'
                )
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not export leads: {exc}",
        ) from exc