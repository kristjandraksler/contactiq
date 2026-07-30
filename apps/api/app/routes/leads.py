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
    "PUBLIC_EMAIL",
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
                "NEW, MATCHED, PARTIAL_MATCH, NOT_FOUND, FAILED, PUBLIC_EMAIL."
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
            "NOT_FOUND, FAILED ali PUBLIC_EMAIL."
        ),
    ),
    country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
        description="ISO2 koda države, npr. SI, HR ali DE.",
    ),
) -> dict[str, object]:
    try:
        supabase = get_supabase()
        normalized_status = normalize_status(status)
        normalized_country = (
            country.strip().upper()
            if country
            else None
        )

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
                    "country_code,"
                    "country_name,"
                    "country_flag,"
                    "source_url,"
                    "pages_scanned,"
                    "scan_attempts,"
                    "scan_duration_ms,"
                    "last_scan,"
                    "status,"
                    "created_at,"
                    "updated_at,"
                    "country_code,"
                    "country_name,"
                    "country_flag,"
                    "country_confidence,"
                    "country_source,"
                    "person_match_type"
                ),
                count="exact",
            )
        )

        if normalized_status:
            query = query.eq(
                "status",
                normalized_status,
            )

        if normalized_country:
            query = query.eq(
                "country_code",
                normalized_country,
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
                "country": normalized_country,
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
    country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
        description="ISO2 koda države.",
    ),
):
    try:
        supabase = get_supabase()
        normalized_status = normalize_status(status)
        normalized_country = (
            country.strip().upper()
            if country
            else None
        )

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

        if normalized_country:
            query = query.eq(
                "country_code",
                normalized_country,
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
                "Država",
                "Koda države",
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
                    lead.get("country_name") or "",
                    lead.get("country_code") or "",
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