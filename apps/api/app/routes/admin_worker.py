from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase
from app.workers.domain_worker import claim_jobs, process_job, seed_jobs


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

    return {
        "worker": "domain_enrichment",
        "paused": paused,
        "saved": bool(response.data or []),
    }


def _read_status() -> dict[str, Any]:
    supabase = get_supabase()

    status_response = supabase.rpc(
        "domain_worker_status",
    ).execute()

    control_response = (
        supabase.table("worker_control")
        .select("paused,updated_at")
        .eq("worker_name", "domain_enrichment")
        .limit(1)
        .execute()
    )

    status_rows = status_response.data or []
    control_rows = control_response.data or []

    counts = status_rows[0] if status_rows else {
        "pending": 0,
        "processing": 0,
        "matched": 0,
        "not_found": 0,
        "failed": 0,
        "total": 0,
    }

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
        "paused": bool(
            control_rows
            and control_rows[0].get("paused")
        ),
    }


@router.get("/status")
def worker_status() -> dict[str, Any]:
    try:
        return _read_status()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Statusa workerja ni bilo mogoče prebrati: {exc}",
        ) from exc


@router.post("/seed")
def seed_worker_queue() -> dict[str, Any]:
    try:
        rows = seed_jobs()
        return {
            "status": "ok",
            "rows": rows,
            "worker_status": _read_status(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Čakalne vrste ni bilo mogoče napolniti: {exc}",
        ) from exc


@router.post("/run")
async def run_worker_batch(
    limit: int = Query(default=5, ge=1, le=25),
    include_public_emails: bool = Query(
        default=False,
        description=(
            "Research mode: crawl public mailbox providers, but only "
            "accept person-specific phone matches."
        ),
    ),
) -> dict[str, Any]:
    try:
        status_before = await asyncio.to_thread(_read_status)

        if status_before.get("paused"):
            return {
                "status": "paused",
                "claimed": 0,
                "processed_in_batch": 0,
                "worker_status": status_before,
            }

        await asyncio.to_thread(seed_jobs)

        jobs = await asyncio.to_thread(
            claim_jobs,
            limit,
        )

        if not jobs:
            return {
                "status": "completed",
                "claimed": 0,
                "processed_in_batch": 0,
                "worker_status": await asyncio.to_thread(
                    _read_status
                ),
                "message": "Ni več čakajočih domen.",
            }

        await asyncio.gather(
            *(
                process_job(
                    job,
                    include_public_emails=(
                        include_public_emails
                    ),
                )
                for job in jobs
            )
        )

        return {
            "status": "batch_completed",
            "claimed": len(jobs),
            "processed_in_batch": len(jobs),
            "domains": [job.domain for job in jobs],
            "include_public_emails": include_public_emails,
            "worker_status": await asyncio.to_thread(
                _read_status
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Batch obdelave ni bilo mogoče dokončati: {exc}",
        ) from exc


@router.post("/pause")
def pause_worker() -> dict[str, Any]:
    try:
        return _set_paused(True)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Workerja ni bilo mogoče zaustaviti: {exc}",
        ) from exc


@router.post("/resume")
def resume_worker() -> dict[str, Any]:
    try:
        result = _set_paused(False)
        seed_jobs()
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Workerja ni bilo mogoče nadaljevati: {exc}",
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
            detail=f"FAILED opravil ni bilo mogoče ponovno dodati: {exc}",
        ) from exc
