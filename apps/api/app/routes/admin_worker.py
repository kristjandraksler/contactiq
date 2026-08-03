from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase
from app.workers.domain_worker import (
    claim_jobs,
    process_job,
    requeue_stale_jobs,
    seed_jobs,
)


logger = logging.getLogger(__name__)

DOMAIN_REQUEST_TIMEOUT_SECONDS = 240


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


async def _process_logged_job(
    job: Any,
    *,
    include_public_emails: bool,
) -> None:
    started_at = time.perf_counter()

    logger.info(
        "WORKER_DOMAIN_START domain=%s job_id=%s attempts=%s "
        "include_public_emails=%s",
        job.domain,
        job.id,
        job.attempts,
        include_public_emails,
    )

    try:
        await asyncio.wait_for(
            process_job(
                job,
                include_public_emails=include_public_emails,
            ),
            timeout=DOMAIN_REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "WORKER_DOMAIN_TIMEOUT domain=%s job_id=%s elapsed_seconds=%.2f",
            job.domain,
            job.id,
            time.perf_counter() - started_at,
        )
    except asyncio.CancelledError:
        logger.warning(
            "WORKER_DOMAIN_CANCELLED domain=%s job_id=%s elapsed_seconds=%.2f",
            job.domain,
            job.id,
            time.perf_counter() - started_at,
        )
        raise
    except Exception:
        logger.exception(
            "WORKER_DOMAIN_FAILED domain=%s job_id=%s elapsed_seconds=%.2f",
            job.domain,
            job.id,
            time.perf_counter() - started_at,
        )
        raise
    else:
        logger.info(
            "WORKER_DOMAIN_END domain=%s job_id=%s elapsed_seconds=%.2f",
            job.domain,
            job.id,
            time.perf_counter() - started_at,
        )


def _list_worker_jobs(
    *,
    status: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    supabase = get_supabase()

    query = (
        supabase.table("domain_jobs")
        .select(
            (
                "id,domain,status,attempts,worker_id,started_at,finished_at,"
                "next_retry_at,last_error,processed_contacts,total_contacts,"
                "created_at,updated_at"
            )
        )
    )

    if status:
        query = query.eq("status", status)

    response = (
        query
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data or []


def _worker_center_payload() -> dict[str, Any]:
    status = _read_status()

    active_jobs = _list_worker_jobs(
        status="PROCESSING",
        limit=25,
    )
    pending_jobs = _list_worker_jobs(
        status="PENDING",
        limit=25,
    )
    failed_jobs = _list_worker_jobs(
        status="FAILED",
        limit=25,
    )

    recent_response = (
        get_supabase()
        .table("domain_jobs")
        .select(
            (
                "id,domain,status,attempts,worker_id,started_at,finished_at,"
                "next_retry_at,last_error,processed_contacts,total_contacts,"
                "created_at,updated_at"
            )
        )
        .in_(
            "status",
            ["MATCHED", "NOT_FOUND", "FAILED"],
        )
        .order("updated_at", desc=True)
        .limit(20)
        .execute()
    )

    active_contacts = sum(
        int(job.get("total_contacts") or 0)
        for job in active_jobs
    )
    active_processed = sum(
        int(job.get("processed_contacts") or 0)
        for job in active_jobs
    )

    return {
        "worker": {
            **status,
            "state": (
                "paused"
                if status.get("paused")
                else "running"
                if int(status.get("processing") or 0) > 0
                else "queued"
                if int(status.get("pending") or 0) > 0
                else "completed"
                if (
                    int(status.get("total") or 0) > 0
                    and float(status.get("progress_percent") or 0) >= 100
                )
                else "idle"
            ),
        },
        "summary": {
            "active_contacts": active_contacts,
            "active_processed": active_processed,
            "queue_health_percent": (
                round(
                    (
                        int(status.get("processed") or 0)
                        / int(status.get("total") or 1)
                    )
                    * 100,
                    2,
                )
                if int(status.get("total") or 0) > 0
                else 100.0
            ),
        },
        "active_jobs": active_jobs,
        "pending_jobs": pending_jobs,
        "failed_jobs": failed_jobs,
        "recent_jobs": recent_response.data or [],
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

        logger.info(
            "WORKER_BATCH_START claimed=%s domains=%s include_public_emails=%s",
            len(jobs),
            ",".join(job.domain for job in jobs),
            include_public_emails,
        )

        await asyncio.gather(
            *(
                _process_logged_job(
                    job,
                    include_public_emails=include_public_emails,
                )
                for job in jobs
            )
        )

        logger.info(
            "WORKER_BATCH_END claimed=%s domains=%s",
            len(jobs),
            ",".join(job.domain for job in jobs),
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


@router.post("/requeue-stale")
def requeue_stale_worker_jobs(
    stale_minutes: int = Query(default=10, ge=5, le=1440),
) -> dict[str, Any]:
    try:
        requeued = requeue_stale_jobs(stale_minutes)

        logger.warning(
            "WORKER_REQUEUE_STALE stale_minutes=%s requeued=%s",
            stale_minutes,
            requeued,
        )

        return {
            "status": "ok",
            "stale_minutes": stale_minutes,
            "requeued": requeued,
            "worker_status": _read_status(),
        }

    except Exception as exc:
        logger.exception(
            "WORKER_REQUEUE_STALE_FAILED stale_minutes=%s",
            stale_minutes,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Stale opravil ni bilo mogoče ponovno dodati: "
                f"{exc}"
            ),
        ) from exc


@router.get("/center")
def worker_center() -> dict[str, Any]:
    try:
        return _worker_center_payload()
    except Exception as exc:
        logger.exception("WORKER_CENTER_LOAD_FAILED")
        raise HTTPException(
            status_code=500,
            detail=f"Worker Centra ni bilo mogoče naložiti: {exc}",
        ) from exc


@router.post("/jobs/{job_id}/retry")
def retry_worker_job(
    job_id: str,
) -> dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("domain_jobs")
            .update(
                {
                    "status": "PENDING",
                    "attempts": 0,
                    "worker_id": None,
                    "started_at": None,
                    "finished_at": None,
                    "next_retry_at": None,
                    "last_error": None,
                }
            )
            .eq("id", job_id)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Worker opravilo ni bilo najdeno.",
            )

        return {
            "status": "ok",
            "job": rows[0],
            "worker_center": _worker_center_payload(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "WORKER_JOB_RETRY_FAILED job_id=%s",
            job_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Opravila ni bilo mogoče ponoviti: {exc}",
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
