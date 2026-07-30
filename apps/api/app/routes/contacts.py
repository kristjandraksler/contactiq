from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase


router = APIRouter(
    tags=["Contacts"],
)


@router.get("/contacts")
def list_contacts(
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
        description="Iskanje po emailu ali domeni.",
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
        description="ISO2 koda države.",
    ),
) -> dict[str, object]:
    try:
        supabase = get_supabase()

        allowed_statuses = {
            "NEW",
            "MATCHED",
            "PARTIAL_MATCH",
            "NOT_FOUND",
            "FAILED",
            "PUBLIC_EMAIL",
        }

        normalized_status = status.strip().upper() if status else None
        normalized_country = (
            country.strip().upper()
            if country
            else None
        )

        if normalized_status and normalized_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Neveljaven status. Dovoljeni statusi so: "
                    "NEW, MATCHED, PARTIAL_MATCH, NOT_FOUND, FAILED, PUBLIC_EMAIL."
                ),
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
            query = query.eq("status", normalized_status)

        if normalized_country:
            query = query.eq("country_code", normalized_country)

        if search and search.strip():
            safe_search = (
                search.strip()
                .replace(",", "")
                .replace("(", "")
                .replace(")", "")
            )

            query = query.or_(
                f"email.ilike.%{safe_search}%,"
                f"domain.ilike.%{safe_search}%"
            )

        response = (
            query
            .order("created_at", desc=True)
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
                "country": normalized_country,
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
    has_phone: bool | None = Query(
        default=None,
        description="Če je true, šteje samo kontakte s telefonom.",
    ),
) -> dict[str, object]:
    try:
        supabase = get_supabase()

        query = (
            supabase.table("email_targets")
            .select(
                "country_code,country_name,country_flag,phone"
            )
            .not_.is_("country_code", "null")
        )

        if has_phone is True:
            query = query.not_.is_("phone", "null")
        elif has_phone is False:
            query = query.is_("phone", "null")

        response = query.execute()

        counts: dict[str, dict[str, object]] = {}

        for row in response.data or []:
            code = str(row.get("country_code") or "").upper()
            if not code:
                continue

            item = counts.setdefault(
                code,
                {
                    "code": code,
                    "name": row.get("country_name"),
                    "flag": row.get("country_flag"),
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
            "has_phone": has_phone,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load countries: {exc}",
        ) from exc
