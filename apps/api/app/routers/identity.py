from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from app.services.identity_resolver import resolve_public_email, resolution_dict

router = APIRouter(prefix="/identity", tags=["identity"])
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

class ResolveRequest(BaseModel):
    email: EmailStr


def _headers(prefer: str | None = None) -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase server environment variables are missing.")
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    if prefer: headers["Prefer"] = prefer
    return headers

@router.post("/resolve")
async def resolve_identity(payload: ResolveRequest):
    try:
        result = await resolve_public_email(str(payload.email))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Identity search failed: {exc}") from exc

    now = datetime.now(timezone.utc).isoformat()
    record = {"id": str(uuid.uuid4()), **resolution_dict(result), "created_at": now, "updated_at": now}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/email_identity_results?on_conflict=email",
            headers=_headers("resolution=merge-duplicates,return=representation"),
            json=record,
            timeout=20,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Could not save identity result: {response.text}")
    rows = response.json()
    return rows[0] if rows else record

@router.get("/results")
async def identity_results(limit: int = Query(100, ge=1, le=500)):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/email_identity_results?select=*&order=updated_at.desc&limit={limit}",
            headers=_headers(), timeout=20,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Could not load identity results: {response.text}")
    return {"items": response.json()}
