from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.services.identity_resolver import (
    resolve_public_email,
    resolution_dict,
)


router = APIRouter(
    prefix="/identity",
    tags=["identity"],
)

SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
)

SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
    "gmx.com",
    "gmx.net",
    "mail.com",
}


class ResolveRequest(BaseModel):
    email: EmailStr


class BatchResolveRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


def _headers(prefer: str | None = None) -> dict[str, str]:
    if not SUPABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL is missing.",
        )

    if not SUPABASE_KEY:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_SERVICE_ROLE_KEY is missing.",
        )

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    return headers


def _domain_from_email(email: str) -> str:
    return email.strip().lower().split("@")[-1]


def _is_public_email(email: str) -> bool:
    return _domain_from_email(email) in PUBLIC_EMAIL_DOMAINS


async def _save_identity_result(
    client: httpx.AsyncClient,
    result: Any,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    result_data = resolution_dict(result)

    record = {
        "id": str(uuid.uuid4()),
        **result_data,
        "created_at": now,
        "updated_at": now,
    }

    response = await client.post(
        (
            f"{SUPABASE_URL}/rest/v1/email_identity_results"
            "?on_conflict=email"
        ),
        headers=_headers(
            "resolution=merge-duplicates,return=representation"
        ),
        json=record,
        timeout=30,
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not save identity result: "
                f"{response.status_code} {response.text}"
            ),
        )

    rows = response.json()

    if isinstance(rows, list) and rows:
        return rows[0]

    return record


async def _mark_email_target(
    client: httpx.AsyncClient,
    email: str,
    status: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    response = await client.patch(
        (
            f"{SUPABASE_URL}/rest/v1/email_targets"
            f"?email=eq.{email}"
        ),
        headers=_headers("return=minimal"),
        json={
            "identity_status": status,
            "identity_checked_at": now,
        },
        timeout=20,
    )

    # Ne ustavimo resolverja, če stolpca še ne obstajata.
    if response.status_code >= 400:
        print(
            "Could not update identity status for "
            f"{email}: {response.text}"
        )


@router.get("/health")
async def identity_health() -> dict[str, Any]:
    return {
        "ok": True,
        "module": "identity",
        "supabase_url_configured": bool(SUPABASE_URL),
        "service_role_configured": bool(SUPABASE_KEY),
    }


@router.post("/resolve")
async def resolve_identity(
    payload: ResolveRequest,
) -> dict[str, Any]:
    email = str(payload.email).strip().lower()

    if not _is_public_email(email):
        raise HTTPException(
            status_code=400,
            detail=(
                "This Identity resolver currently processes only "
                "public email providers such as Gmail, Outlook, "
                "Yahoo, iCloud and Proton."
            ),
        )

    try:
        result = await resolve_public_email(email)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Identity search failed: {exc}",
        ) from exc

    async with httpx.AsyncClient() as client:
        saved_result = await _save_identity_result(
            client,
            result,
        )

        status = str(
            saved_result.get("status", "resolved")
        ).lower()

        await _mark_email_target(
            client,
            email,
            status,
        )

    return saved_result


@router.get("/results")
async def identity_results(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            (
                f"{SUPABASE_URL}/rest/v1/email_identity_results"
                f"?select=*"
                f"&order=updated_at.desc"
                f"&limit={limit}"
            ),
            headers=_headers(),
            timeout=30,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not load identity results: "
                f"{response.status_code} {response.text}"
            ),
        )

    items = response.json()

    return {
        "items": items,
        "count": len(items),
    }


@router.post("/resolve-batch")
async def resolve_identity_batch(
    payload: BatchResolveRequest,
) -> dict[str, Any]:
    limit = payload.limit

    domain_filters = ",".join(
        f"domain.eq.{domain}"
        for domain in sorted(PUBLIC_EMAIL_DOMAINS)
    )

    query_url = (
        f"{SUPABASE_URL}/rest/v1/email_targets"
        "?select=id,email,domain,phone,identity_status"
        "&phone=is.null"
        "&or=(identity_status.is.null,identity_status.eq.pending,"
        "identity_status.eq.failed)"
        f"&or=({domain_filters})"
        "&order=created_at.asc"
        f"&limit={limit}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            query_url,
            headers=_headers(),
            timeout=30,
        )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Could not load Identity contacts: "
                    f"{response.status_code} {response.text}"
                ),
            )

        contacts = response.json()
        results: list[dict[str, Any]] = []

        for contact in contacts:
            email = str(
                contact.get("email") or ""
            ).strip().lower()

            if not email:
                continue

            await _mark_email_target(
                client,
                email,
                "processing",
            )

            try:
                identity_result = await resolve_public_email(
                    email
                )

                saved_result = await _save_identity_result(
                    client,
                    identity_result,
                )

                result_status = str(
                    saved_result.get(
                        "status",
                        "resolved",
                    )
                ).lower()

                await _mark_email_target(
                    client,
                    email,
                    result_status,
                )

                results.append(
                    {
                        "email": email,
                        "success": True,
                        "status": result_status,
                        "result": saved_result,
                    }
                )

            except Exception as exc:
                await _mark_email_target(
                    client,
                    email,
                    "failed",
                )

                results.append(
                    {
                        "email": email,
                        "success": False,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

    successful = sum(
        1 for item in results if item["success"]
    )

    failed = len(results) - successful

    return {
        "requested_limit": limit,
        "processed": len(results),
        "successful": successful,
        "failed": failed,
        "results": results,
    }