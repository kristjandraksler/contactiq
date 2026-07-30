import csv
import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_supabase
from app.routes.contacts import (
    ALLOWED_PERSON_MATCH_TYPES,
    ALLOWED_SORT_FIELDS,
    ALLOWED_STATUSES,
    _apply_common_filters,
    _normalize_code,
)


router = APIRouter(
    tags=["Leads"],
)


def _normalized_filters(
    *,
    status: str | None,
    country: str | None,
    company_country: str | None,
    phone_country: str | None,
    person_match_type: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    normalized_status = status.strip().upper() if status else None
    normalized_company_country = _normalize_code(
        company_country or country
    )
    normalized_phone_country = _normalize_code(phone_country)
    normalized_person_match_type = (
        person_match_type.strip().lower()
        if person_match_type
        else None
    )

    if normalized_status and normalized_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Neveljaven status.")

    if (
        normalized_person_match_type
        and normalized_person_match_type not in ALLOWED_PERSON_MATCH_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail="Neveljaven person_match_type.",
        )

    return (
        normalized_status,
        normalized_company_country,
        normalized_phone_country,
        normalized_person_match_type,
    )


@router.get("/leads")
def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=250),
    search: str | None = Query(default=None),
    has_phone: bool | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=100),
    confidence_max: float | None = Query(default=None, ge=0, le=100),
    status: str | None = Query(default=None),
    country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
    ),
    company_country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
    ),
    phone_country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
    ),
    country_mismatch: bool | None = Query(default=None),
    person_match_type: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_direction: str = Query(default="desc"),
) -> dict[str, object]:
    try:
        supabase = get_supabase()

        (
            normalized_status,
            normalized_company_country,
            normalized_phone_country,
            normalized_person_match_type,
        ) = _normalized_filters(
            status=status,
            country=country,
            company_country=company_country,
            phone_country=phone_country,
            person_match_type=person_match_type,
        )

        if sort_by not in ALLOWED_SORT_FIELDS:
            raise HTTPException(
                status_code=400,
                detail="Neveljavno polje za sortiranje.",
            )

        normalized_sort_direction = sort_direction.strip().lower()
        if normalized_sort_direction not in {"asc", "desc"}:
            raise HTTPException(
                status_code=400,
                detail="sort_direction mora biti asc ali desc.",
            )

        offset = (page - 1) * page_size
        range_end = offset + page_size - 1

        query = (
            supabase.table("email_targets")
            .select(
                (
                    "id,email,domain,website,phone,confidence,source_url,"
                    "pages_scanned,scan_attempts,scan_duration_ms,last_scan,"
                    "status,created_at,updated_at,country_code,country_name,"
                    "country_flag,country_confidence,country_source,"
                    "phone_country_code,phone_country_name,phone_country_flag,"
                    "phone_country_confidence,country_mismatch,is_cross_border,"
                    "person_match_type"
                ),
                count="exact",
            )
        )

        query = _apply_common_filters(
            query,
            search=search,
            status=normalized_status,
            company_country=normalized_company_country,
            phone_country=normalized_phone_country,
            has_phone=has_phone,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            country_mismatch=country_mismatch,
            person_match_type=normalized_person_match_type,
        )

        response = (
            query
            .order(
                sort_by,
                desc=normalized_sort_direction == "desc",
            )
            .range(offset, range_end)
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
                "search": search.strip() if search else None,
                "has_phone": has_phone,
                "confidence_min": confidence_min,
                "confidence_max": confidence_max,
                "status": normalized_status,
                "company_country": normalized_company_country,
                "phone_country": normalized_phone_country,
                "country_mismatch": country_mismatch,
                "person_match_type": normalized_person_match_type,
                "sort_by": sort_by,
                "sort_direction": normalized_sort_direction,
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
    search: str | None = Query(default=None),
    has_phone: bool | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=100),
    confidence_max: float | None = Query(default=None, ge=0, le=100),
    status: str | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    company_country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
    ),
    phone_country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
    ),
    country_mismatch: bool | None = Query(default=None),
    person_match_type: str | None = Query(default=None),
):
    try:
        supabase = get_supabase()

        (
            normalized_status,
            normalized_company_country,
            normalized_phone_country,
            normalized_person_match_type,
        ) = _normalized_filters(
            status=status,
            country=country,
            company_country=company_country,
            phone_country=phone_country,
            person_match_type=person_match_type,
        )

        query = (
            supabase.table("email_targets")
            .select(
                (
                    "email,domain,website,phone,confidence,source_url,status,"
                    "last_scan,country_code,country_name,country_flag,"
                    "phone_country_code,phone_country_name,phone_country_flag,"
                    "country_mismatch,person_match_type"
                )
            )
        )

        query = _apply_common_filters(
            query,
            search=search,
            status=normalized_status,
            company_country=normalized_company_country,
            phone_country=normalized_phone_country,
            has_phone=has_phone,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            country_mismatch=country_mismatch,
            person_match_type=normalized_person_match_type,
        )

        response = query.order("created_at", desc=True).execute()

        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")

        writer.writerow(
            [
                "Telefon",
                "E-mail",
                "Domena",
                "Spletna stran",
                "Država podjetja",
                "Koda države podjetja",
                "Država telefona",
                "Koda države telefona",
                "Cross-border",
                "Tip zadetka",
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
                    lead.get("country_name") or "",
                    lead.get("country_code") or "",
                    lead.get("phone_country_name") or "",
                    lead.get("phone_country_code") or "",
                    "DA" if lead.get("country_mismatch") else "NE",
                    lead.get("person_match_type") or "",
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
