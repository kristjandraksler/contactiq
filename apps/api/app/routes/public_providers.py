from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_supabase
from app.services.providers import (
    clean_domain,
    public_email_cache_info,
    refresh_public_email_domains,
)


router = APIRouter(
    prefix="/admin/public-providers",
    tags=["Public Providers"],
)


class PublicProviderCreate(BaseModel):
    domain: str = Field(min_length=3, max_length=255)


@router.get("")
def list_public_providers(
    search: str | None = Query(default=None),
) -> dict[str, object]:
    try:
        query = (
            get_supabase()
            .table("public_email_domains")
            .select("domain,created_at")
            .order("domain")
        )

        if search and search.strip():
            safe_search = (
                search.strip()
                .replace(",", "")
                .replace("(", "")
                .replace(")", "")
            )
            query = query.ilike("domain", f"%{safe_search}%")

        response = query.execute()

        count_response = (
            get_supabase()
            .table("email_targets")
            .select("id", count="exact")
            .eq("status", "PUBLIC_EMAIL")
            .limit(1)
            .execute()
        )

        return {
            "items": response.data or [],
            "total": len(response.data or []),
            "public_email_contacts": count_response.count or 0,
            "cache": public_email_cache_info(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load public providers: {exc}",
        ) from exc


@router.post("")
def add_public_provider(
    payload: PublicProviderCreate,
) -> dict[str, object]:
    domain = clean_domain(payload.domain)

    if not domain or "." not in domain:
        raise HTTPException(
            status_code=400,
            detail="Neveljavna domena.",
        )

    try:
        response = (
            get_supabase()
            .table("public_email_domains")
            .upsert(
                {"domain": domain},
                on_conflict="domain",
            )
            .execute()
        )

        cache = refresh_public_email_domains(force=True)

        return {
            "saved": True,
            "domain": domain,
            "domains_cached": len(cache),
            "row": (response.data or [None])[0],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not add public provider: {exc}",
        ) from exc


@router.delete("/{domain:path}")
def delete_public_provider(
    domain: str,
) -> dict[str, object]:
    normalized = clean_domain(domain)

    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Neveljavna domena.",
        )

    try:
        (
            get_supabase()
            .table("public_email_domains")
            .delete()
            .eq("domain", normalized)
            .execute()
        )

        cache = refresh_public_email_domains(force=True)

        return {
            "deleted": True,
            "domain": normalized,
            "domains_cached": len(cache),
            "note": (
                "Fallback domains remain protected in code even if deleted "
                "from the database."
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not delete public provider: {exc}",
        ) from exc


@router.post("/reload-cache")
def reload_public_provider_cache() -> dict[str, object]:
    try:
        domains = refresh_public_email_domains(force=True)

        return {
            "reloaded": True,
            "domains_cached": len(domains),
            "cache": public_email_cache_info(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not reload cache: {exc}",
        ) from exc
