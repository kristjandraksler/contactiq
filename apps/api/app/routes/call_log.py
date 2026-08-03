from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase


router = APIRouter(
    prefix="/call-log",
    tags=["Call Log"],
)


ALLOWED_RESULTS = {
    "CONNECTED",
    "NO_ANSWER",
    "VOICEMAIL",
    "WRONG_NUMBER",
    "NOT_INTERESTED",
    "FOLLOW_UP",
    "MEETING_BOOKED",
    "OFFER_SENT",
    "OTHER",
}

ALLOWED_ACTIONS = {
    "NONE",
    "CALL",
    "EMAIL",
    "MEETING",
    "OFFER",
    "OTHER",
}


def _sanitize_search(value: str) -> str:
    return (
        value.strip()
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


def _utc_day_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _count_query(
    *,
    created_from: str | None = None,
    created_to: str | None = None,
    result: str | None = None,
    next_action: str | None = None,
    next_call_from: str | None = None,
    next_call_to: str | None = None,
) -> int:
    query = (
        get_supabase()
        .table("call_summaries")
        .select("id", count="exact")
        .limit(1)
    )

    if created_from:
        query = query.gte("created_at", created_from)

    if created_to:
        query = query.lt("created_at", created_to)

    if result:
        query = query.eq("call_result", result)

    if next_action:
        query = query.eq("next_action", next_action)

    if next_call_from:
        query = query.gte("next_call_at", next_call_from)

    if next_call_to:
        query = query.lt("next_call_at", next_call_to)

    response = query.execute()
    return int(response.count or 0)


@router.get("")
def list_call_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    call_result: str | None = Query(default=None),
    next_action: str | None = Query(default=None),
    period: str = Query(default="all"),
) -> dict[str, Any]:
    try:
        normalized_result = (
            call_result.strip().upper()
            if call_result
            else None
        )
        normalized_action = (
            next_action.strip().upper()
            if next_action
            else None
        )

        if (
            normalized_result
            and normalized_result not in ALLOWED_RESULTS
        ):
            raise HTTPException(
                status_code=400,
                detail="Neveljaven rezultat klica.",
            )

        if (
            normalized_action
            and normalized_action not in ALLOWED_ACTIONS
        ):
            raise HTTPException(
                status_code=400,
                detail="Neveljavna naslednja aktivnost.",
            )

        now = datetime.now(timezone.utc)
        day_start = _utc_day_start(now)
        created_from: datetime | None = None

        normalized_period = period.strip().lower()

        if normalized_period == "today":
            created_from = day_start
        elif normalized_period == "week":
            created_from = day_start - timedelta(
                days=day_start.weekday()
            )
        elif normalized_period == "month":
            created_from = day_start.replace(day=1)
        elif normalized_period != "all":
            raise HTTPException(
                status_code=400,
                detail="period mora biti all, today, week ali month.",
            )

        offset = (page - 1) * page_size
        range_end = offset + page_size - 1

        query = (
            get_supabase()
            .table("call_summaries")
            .select(
                (
                    "id,contact_id,call_result,summary,next_action,"
                    "next_call_at,duration_seconds,created_by,"
                    "created_at,updated_at,"
                    "email_targets!inner("
                    "id,email,domain,website,phone,country_name,"
                    "country_flag,confidence,person_match_type"
                    ")"
                ),
                count="exact",
            )
        )

        if normalized_result:
            query = query.eq(
                "call_result",
                normalized_result,
            )

        if normalized_action:
            query = query.eq(
                "next_action",
                normalized_action,
            )

        if created_from:
            query = query.gte(
                "created_at",
                created_from.isoformat(),
            )

        if search and search.strip():
            safe_search = _sanitize_search(search)
            query = query.or_(
                (
                    f"summary.ilike.%{safe_search}%,"
                    f"created_by.ilike.%{safe_search}%,"
                    f"email_targets.email.ilike.%{safe_search}%,"
                    f"email_targets.domain.ilike.%{safe_search}%,"
                    f"email_targets.phone.ilike.%{safe_search}%"
                )
            )

        response = (
            query
            .order("created_at", desc=True)
            .range(offset, range_end)
            .execute()
        )

        total = int(response.count or 0)
        total_pages = (
            (total + page_size - 1) // page_size
            if total
            else 0
        )

        today_end = day_start + timedelta(days=1)
        week_start = day_start - timedelta(
            days=day_start.weekday()
        )
        week_end = week_start + timedelta(days=7)

        stats = {
            "today": _count_query(
                created_from=day_start.isoformat(),
                created_to=today_end.isoformat(),
            ),
            "this_week": _count_query(
                created_from=week_start.isoformat(),
                created_to=week_end.isoformat(),
            ),
            "follow_up": _count_query(
                next_action="CALL",
            ),
            "meetings": _count_query(
                result="MEETING_BOOKED",
            ),
            "no_answer": _count_query(
                result="NO_ANSWER",
            ),
            "wrong_number": _count_query(
                result="WRONG_NUMBER",
            ),
        }

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
            "stats": stats,
            "filters": {
                "search": search.strip() if search else None,
                "call_result": normalized_result,
                "next_action": normalized_action,
                "period": normalized_period,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Call Loga ni bilo mogoče naložiti: {exc}",
        ) from exc


@router.get("/follow-ups")
def list_follow_ups(
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        response = (
            get_supabase()
            .table("call_summaries")
            .select(
                (
                    "id,contact_id,call_result,summary,next_action,"
                    "next_call_at,created_by,created_at,"
                    "email_targets!inner("
                    "id,email,domain,phone,country_name,country_flag"
                    ")"
                )
            )
            .not_.is_("next_call_at", "null")
            .gte("next_call_at", now.isoformat())
            .lte("next_call_at", end.isoformat())
            .order("next_call_at")
            .limit(100)
            .execute()
        )

        return {
            "items": response.data or [],
            "days": days,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Follow-upov ni bilo mogoče naložiti: {exc}",
        ) from exc
