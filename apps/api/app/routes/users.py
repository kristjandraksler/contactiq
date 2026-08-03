from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.database import get_supabase


router = APIRouter(
    prefix="/admin/users",
    tags=["Users"],
)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    role: Literal["admin", "user"] = "user"


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: Literal["admin", "user"] | None = None
    active: bool | None = None


def _token_from_header(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Prijava je zahtevana.")

    return authorization.removeprefix("Bearer ").strip()


def _require_admin(token: str) -> dict[str, object]:
    supabase = get_supabase()

    auth_response = supabase.auth.get_user(token)
    user = auth_response.user

    if not user:
        raise HTTPException(status_code=401, detail="Neveljavna seja.")

    profile_response = (
        supabase.table("profiles")
        .select("id,email,role,active")
        .eq("id", str(user.id))
        .limit(1)
        .execute()
    )

    profiles = profile_response.data or []

    if not profiles:
        raise HTTPException(status_code=403, detail="Profil ni bil najden.")

    profile = profiles[0]

    if not bool(profile.get("active")):
        raise HTTPException(status_code=403, detail="Uporabnik je deaktiviran.")

    if profile.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administratorska vloga je zahtevana.",
        )

    return profile


@router.get("")
def list_users(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    token = _token_from_header(authorization)
    _require_admin(token)

    supabase = get_supabase()
    auth_response = supabase.auth.admin.list_users(
        page=1,
        per_page=1000,
    )

    profiles_response = (
        supabase.table("profiles")
        .select("id,email,full_name,role,active,created_at")
        .order("created_at", desc=True)
        .execute()
    )

    profiles = {
        str(item["id"]): item
        for item in (profiles_response.data or [])
    }

    items: list[dict[str, object]] = []

    for user in auth_response:
        profile = profiles.get(str(user.id), {})

        items.append(
            {
                "id": str(user.id),
                "email": user.email or profile.get("email"),
                "full_name": profile.get("full_name"),
                "role": profile.get("role", "user"),
                "active": bool(profile.get("active", True)),
                "created_at": (
                    user.created_at.isoformat()
                    if getattr(user, "created_at", None)
                    else profile.get("created_at")
                ),
                "last_sign_in_at": (
                    user.last_sign_in_at.isoformat()
                    if getattr(user, "last_sign_in_at", None)
                    else None
                ),
            }
        )

    return {"items": items, "total": len(items)}


@router.post("")
def create_user(
    payload: UserCreate,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    token = _token_from_header(authorization)
    _require_admin(token)

    supabase = get_supabase()

    response = supabase.auth.admin.create_user(
        {
            "email": str(payload.email).lower(),
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": payload.full_name,
                "role": payload.role,
            },
        }
    )

    user = response.user

    if not user:
        raise HTTPException(
            status_code=500,
            detail="Uporabnika ni bilo mogoče ustvariti.",
        )

    (
        supabase.table("profiles")
        .upsert(
            {
                "id": str(user.id),
                "email": str(payload.email).lower(),
                "full_name": payload.full_name,
                "role": payload.role,
                "active": True,
            },
            on_conflict="id",
        )
        .execute()
    )

    return {
        "created": True,
        "id": str(user.id),
        "email": user.email,
    }


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdate,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    token = _token_from_header(authorization)
    admin_profile = _require_admin(token)

    if (
        user_id == str(admin_profile["id"])
        and payload.active is False
    ):
        raise HTTPException(
            status_code=400,
            detail="Svojega administratorskega računa ne moreš deaktivirati.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Ni sprememb za shranjevanje.",
        )

    response = (
        get_supabase()
        .table("profiles")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Uporabnik ni bil najden.",
        )

    return {"updated": True, "item": rows[0]}
