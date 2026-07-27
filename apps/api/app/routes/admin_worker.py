from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.database import get_supabase


router = APIRouter(
    prefix="/admin/worker",
    tags=["admin-worker"],
)


def _set_paused(paused: bool) -> dict[str, Any]:
    supabase = get_supabase()

    response = (
        supabase.table("worker_control")
        .upsert(
            {
                "worker_name": "domain_enrichment",
                "paused": paused,
            },
            on_conflict="worker_name",
        )
        .execute()
    )

    rows = response.data or []

    return {
        "worker": "domain_enrichment",
        "paused": paused,
        "saved": bool(rows),
    }


@router.get("/status")
def worker_status() -> dict[str, Any]:
    try:
        supabase = get_supabase()

        status_response = supabase.rpc(
            "domain_worker_status",
        ).execute()

        control_response = (
            supabase.table("worker_control")
            .select("paused,updated_at")
            .eq(
                "worker_name",
                "domain_enrichment",
            )
            .limit(1)
            .execute()
        )

        status_rows = status_response.data or []
        control_rows = control_response.data or []

        counts = (
            status_rows[0]
            if status_rows
            else {
                "pending": 0,
                "processing": 0,
                "matched": 0,
                "not_found": 0,
                "failed": 0,
                "total": 0,
            }
        )

        paused = bool(
            control_rows
            and control_rows[0].get("paused")
        )

        processed = (
            int(counts.get("matched") or 0)
            + int(counts.get("not_found") or 0)
            + int(counts.get("failed") or 0)
        )
        total = int(counts.get("total") or 0)

        return {
            **counts,
            "processed": processed,
            "progress_percent": (
                round(processed / total * 100, 2)
                if total
                else 0
            ),
            "paused": paused,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Statusa workerja ni bilo mogoče "
                f"prebrati: {exc}"
            ),
        ) from exc


@router.post("/seed")
def seed_worker_queue() -> dict[str, Any]:
    try:
        supabase = get_supabase()

        response = supabase.rpc(
            "seed_domain_jobs",
        ).execute()

        return {
            "status": "ok",
            "rows": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Čakalne vrste ni bilo mogoče "
                f"napolniti: {exc}"
            ),
        ) from exc


@router.post("/pause")
def pause_worker() -> dict[str, Any]:
    try:
        return _set_paused(True)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Workerja ni bilo mogoče "
                f"zaustaviti: {exc}"
            ),
        ) from exc


@router.post("/resume")
def resume_worker() -> dict[str, Any]:
    try:
        result = _set_paused(False)

        supabase = get_supabase()
        supabase.rpc(
            "seed_domain_jobs",
        ).execute()

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Workerja ni bilo mogoče "
                f"nadaljevati: {exc}"
            ),
        ) from exc


@router.post("/retry-failed")
def retry_failed_jobs() -> dict[str, Any]:
    try:
        supabase = get_supabase()

        response = (
            supabase.table("domain_jobs")
            .update(
                {
                    "status": "PENDING",
                    "next_retry_at": None,
                    "last_error": None,
                    "worker_id": None,
                    "started_at": None,
                    "finished_at": None,
                }
            )
            .eq("status", "FAILED")
            .execute()
        )

        return {
            "status": "ok",
            "requeued": len(response.data or []),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "FAILED opravil ni bilo mogoče "
                f"ponovno dodati: {exc}"
            ),
        ) from exc
