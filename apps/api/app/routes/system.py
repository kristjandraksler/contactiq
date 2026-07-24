from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.database import get_supabase
from app.services.company_cache import MATCHED_TTL, NOT_FOUND_TTL


router = APIRouter(
    prefix="/system",
    tags=["system"],
)


def _count_rows(table_name: str) -> int:
    supabase = get_supabase()

    response = (
        supabase.table(table_name)
        .select("id", count="exact")
        .limit(1)
        .execute()
    )

    return int(response.count or 0)


@router.get("/info")
def get_system_info() -> dict[str, Any]:
    database_status = "connected"
    email_targets_count = 0
    companies_count = 0

    try:
        email_targets_count = _count_rows("email_targets")
        companies_count = _count_rows("companies")
    except Exception:
        database_status = "disconnected"

    return {
        "application": {
            "name": "ContactIQ",
            "version": "0.6.0",
            "environment": "production",
        },
        "services": {
            "api": "online",
            "database": database_status,
            "crawler": "ready",
            "company_cache": "active",
        },
        "database": {
            "provider": "Supabase",
            "email_targets": email_targets_count,
            "companies": companies_count,
        },
        "enrichment": {
            "website_crawler": True,
            "company_cache": True,
            "matched_ttl_days": MATCHED_TTL.days,
            "not_found_ttl_days": NOT_FOUND_TTL.days,
            "statuses": [
                "NEW",
                "MATCHED",
                "NOT_FOUND",
                "FAILED",
            ],
        },
        "stack": {
            "frontend": "Next.js",
            "backend": "FastAPI",
            "database": "Supabase",
            "hosting_frontend": "Vercel",
            "hosting_backend": "Render",
        },
    }