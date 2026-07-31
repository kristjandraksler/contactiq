from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase


router = APIRouter(
    tags=["Contacts"],
)


ALLOWED_STATUSES = {
    "NEW",
    "MATCHED",
    "PARTIAL_MATCH",
    "NOT_FOUND",
    "FAILED",
    "PUBLIC_EMAIL",
}

ALLOWED_PERSON_MATCH_TYPES = {
    "person_phone",
    "company_phone",
    "public_person",
    "public_email",
    "none",
}

ALLOWED_SORT_FIELDS = {
    "created_at",
    "updated_at",
    "email",
    "domain",
    "confidence",
    "country_code",
    "phone_country_code",
    "last_scan",
}


def _normalize_code(value: str | None) -> str | None:
    return value.strip().upper() if value else None


def _sanitize_search(value: str) -> str:
    return (
        value.strip()
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


def _apply_common_filters(
    query,
    *,
    search: str | None,
    status: str | None,
    company_country: str | None,
    phone_country: str | None,
    has_phone: bool | None,
    confidence_min: float | None,
    confidence_max: float | None,
    country_mismatch: bool | None,
    person_match_type: str | None,
):
    if status:
        query = query.eq("status", status)

    if company_country:
        query = query.eq("country_code", company_country)

    if phone_country:
        query = query.eq("phone_country_code", phone_country)

    if has_phone is True:
        query = query.not_.is_("phone", "null")
    elif has_phone is False:
        query = query.is_("phone", "null")

    if confidence_min is not None:
        query = query.gte("confidence", confidence_min)

    if confidence_max is not None:
        query = query.lte("confidence", confidence_max)

    if country_mismatch is not None:
        query = query.eq("country_mismatch", country_mismatch)

    if person_match_type:
        query = query.eq("person_match_type", person_match_type)

    if search and search.strip():
        safe_search = _sanitize_search(search)
        query = query.or_(
            f"email.ilike.%{safe_search}%,"
            f"domain.ilike.%{safe_search}%,"
            f"phone.ilike.%{safe_search}%"
        )

    return query


@router.get("/contacts")
def list_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=250),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    country: str | None = Query(
        default=None,
        min_length=2,
        max_length=2,
        description="Backward-compatible alias for company_country.",
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
    has_phone: bool | None = Query(default=None),
    confidence_min: float | None = Query(default=None, ge=0, le=100),
    confidence_max: float | None = Query(default=None, ge=0, le=100),
    country_mismatch: bool | None = Query(default=None),
    person_match_type: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_direction: str = Query(default="desc"),
) -> dict[str, object]:
    try:
        supabase = get_supabase()

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
            raise HTTPException(
                status_code=400,
                detail="Neveljaven status.",
            )

        if (
            normalized_person_match_type
            and normalized_person_match_type
            not in ALLOWED_PERSON_MATCH_TYPES
        ):
            raise HTTPException(
                status_code=400,
                detail="Neveljaven person_match_type.",
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

        if (
            confidence_min is not None
            and confidence_max is not None
            and confidence_min > confidence_max
        ):
            raise HTTPException(
                status_code=400,
                detail="confidence_min ne sme biti večji od confidence_max.",
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
                    "country_flag,country_confidence,country_source,country_evidence,"
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
                "status": normalized_status,
                "company_country": normalized_company_country,
                "phone_country": normalized_phone_country,
                "has_phone": has_phone,
                "confidence_min": confidence_min,
                "confidence_max": confidence_max,
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
            detail=f"Could not load contacts: {exc}",
        ) from exc


@router.get("/contacts/countries")
def list_contact_countries(
    field: str = Query(
        default="company",
        description="company ali phone",
    ),
    has_phone: bool | None = Query(default=None),
) -> dict[str, object]:
    try:
        supabase = get_supabase()

        normalized_field = field.strip().lower()
        if normalized_field not in {"company", "phone"}:
            raise HTTPException(
                status_code=400,
                detail="field mora biti company ali phone.",
            )

        if normalized_field == "company":
            code_field = "country_code"
            name_field = "country_name"
            flag_field = "country_flag"
        else:
            code_field = "phone_country_code"
            name_field = "phone_country_name"
            flag_field = "phone_country_flag"

        query = (
            supabase.table("email_targets")
            .select(
                f"{code_field},{name_field},{flag_field},phone,status"
            )
            .not_.is_(code_field, "null")
        )

        if has_phone is True:
            query = query.not_.is_("phone", "null")
        elif has_phone is False:
            query = query.is_("phone", "null")

        response = query.execute()

        counts: dict[str, dict[str, object]] = {}

        for row in response.data or []:
            code = str(row.get(code_field) or "").upper()
            if not code:
                continue

            item = counts.setdefault(
                code,
                {
                    "code": code,
                    "name": row.get(name_field),
                    "flag": row.get(flag_field),
                    "count": 0,
                },
            )
            item["count"] = int(item["count"]) + 1

        items = sorted(
            counts.values(),
            key=lambda item: (
                -int(item["count"]),
                str(item["name"] or item["code"]),
            ),
        )

        return {
            "items": items,
            "field": normalized_field,
            "has_phone": has_phone,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load countries: {exc}",
        ) from exc
