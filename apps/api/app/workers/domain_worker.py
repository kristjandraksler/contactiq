from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_supabase
from app.services.company_cache import (
    get_cached_company_result,
    save_company_result,
)
from app.services.phone_finder import FinderResult, find_phone_for_domain
from app.services.providers import clean_domain


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format=(
        "%(asctime)s %(levelname)s "
        "%(name)s %(message)s"
    ),
)

logger = logging.getLogger(__name__)

CONCURRENCY = max(
    1,
    min(
        int(os.getenv("DOMAIN_WORKER_CONCURRENCY", "5")),
        20,
    ),
)

MAX_PAGES = max(
    1,
    min(
        int(os.getenv("DOMAIN_WORKER_MAX_PAGES", "10")),
        20,
    ),
)

IDLE_SLEEP_SECONDS = max(
    2,
    int(os.getenv("DOMAIN_WORKER_IDLE_SLEEP", "15")),
)

PAUSED_SLEEP_SECONDS = max(
    5,
    int(os.getenv("DOMAIN_WORKER_PAUSED_SLEEP", "30")),
)

SEED_INTERVAL_MINUTES = max(
    1,
    int(os.getenv("DOMAIN_WORKER_SEED_INTERVAL_MINUTES", "10")),
)

MAX_RETRIES = max(
    1,
    int(os.getenv("DOMAIN_WORKER_MAX_RETRIES", "3")),
)

STALE_JOB_MINUTES = max(
    5,
    int(os.getenv("DOMAIN_WORKER_STALE_MINUTES", "30")),
)

WORKER_ID = os.getenv(
    "DOMAIN_WORKER_ID",
    (
        f"{socket.gethostname()}-"
        f"{uuid.uuid4().hex[:8]}"
    ),
)


@dataclass(frozen=True)
class DomainJob:
    id: str
    domain: str
    attempts: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def retry_at_iso(attempts: int) -> str:
    delay_minutes = min(
        15 * (2 ** max(attempts - 1, 0)),
        360,
    )
    return (
        datetime.now(timezone.utc)
        + timedelta(minutes=delay_minutes)
    ).isoformat()


def is_paused() -> bool:
    supabase = get_supabase()

    response = (
        supabase.table("worker_control")
        .select("paused")
        .eq("worker_name", "domain_enrichment")
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return bool(rows and rows[0].get("paused"))


def seed_jobs() -> int:
    supabase = get_supabase()
    response = supabase.rpc(
        "seed_domain_jobs",
    ).execute()

    value = response.data

    if isinstance(value, int):
        return value

    if isinstance(value, list) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return 0

    return 0


def requeue_stale_jobs() -> int:
    supabase = get_supabase()
    response = supabase.rpc(
        "requeue_stale_domain_jobs",
        {
            "p_stale_minutes": STALE_JOB_MINUTES,
        },
    ).execute()

    value = response.data

    if isinstance(value, int):
        return value

    return 0


def claim_jobs(limit: int) -> list[DomainJob]:
    supabase = get_supabase()

    response = supabase.rpc(
        "claim_domain_jobs",
        {
            "p_limit": limit,
            "p_worker_id": WORKER_ID,
        },
    ).execute()

    rows = response.data or []

    return [
        DomainJob(
            id=str(row["id"]),
            domain=str(row["domain"]),
            attempts=int(row.get("attempts") or 0),
        )
        for row in rows
    ]


def update_job(
    job_id: str,
    payload: dict[str, Any],
) -> None:
    supabase = get_supabase()

    (
        supabase.table("domain_jobs")
        .update(payload)
        .eq("id", job_id)
        .execute()
    )


def update_email_targets_for_domain(
    domain: str,
    result: FinderResult,
    company_id: str | None,
) -> int:
    supabase = get_supabase()

    payload: dict[str, Any] = {
        "website": result.website,
        "phone": result.phone,
        "confidence": result.confidence,
        "source_url": result.source_url,
        "pages_scanned": result.pages_scanned,
        "scan_duration_ms": result.scan_duration_ms,
        "last_scan": utc_now_iso(),
        "status": result.status,
        "last_error": result.error,
    }

    if company_id:
        payload["company_id"] = company_id

    response = (
        supabase.table("email_targets")
        .update(payload)
        .eq("domain", domain)
        .execute()
    )

    return len(response.data or [])


async def resolve_domain(
    domain: str,
) -> tuple[FinderResult, str | None, bool]:
    cached_result, cached_company_id = (
        await asyncio.to_thread(
            get_cached_company_result,
            domain,
        )
    )

    if cached_result is not None:
        return (
            cached_result,
            cached_company_id,
            True,
        )

    result = await find_phone_for_domain(
        raw_domain=domain,
        max_pages=MAX_PAGES,
    )

    company_id = await asyncio.to_thread(
        save_company_result,
        domain,
        result,
    )

    return result, company_id, False


async def process_job(job: DomainJob) -> None:
    domain = clean_domain(job.domain)

    if not domain or "." not in domain:
        update_job(
            job.id,
            {
                "status": "NOT_FOUND",
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "last_error": "Invalid domain.",
            },
        )
        return

    try:
        result, company_id, from_cache = (
            await resolve_domain(domain)
        )

        updated_contacts = await asyncio.to_thread(
            update_email_targets_for_domain,
            domain,
            result,
            company_id,
        )

        if result.status in {
            "MATCHED",
            "NOT_FOUND",
        }:
            job_status = result.status
            next_retry_at = None
        else:
            job_status = "FAILED"
            next_retry_at = retry_at_iso(job.attempts)

        update_job(
            job.id,
            {
                "status": job_status,
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "last_error": result.error,
                "next_retry_at": next_retry_at,
            },
        )

        logger.info(
            (
                "domain=%s status=%s cached=%s "
                "contacts=%s phone=%s"
            ),
            domain,
            result.status,
            from_cache,
            updated_contacts,
            result.phone,
        )

    except Exception as exc:
        terminal_failure = job.attempts >= MAX_RETRIES

        update_job(
            job.id,
            {
                "status": "FAILED",
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "last_error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "next_retry_at": (
                    None
                    if terminal_failure
                    else retry_at_iso(job.attempts)
                ),
            },
        )

        logger.exception(
            "Domain job failed: %s",
            domain,
        )


async def worker_loop() -> None:
    logger.info(
        (
            "Starting ContactIQ domain worker "
            "worker_id=%s concurrency=%s max_pages=%s"
        ),
        WORKER_ID,
        CONCURRENCY,
        MAX_PAGES,
    )

    requeued = await asyncio.to_thread(
        requeue_stale_jobs,
    )

    if requeued:
        logger.warning(
            "Requeued %s stale domain jobs.",
            requeued,
        )

    last_seed_at: datetime | None = None

    while True:
        try:
            paused = await asyncio.to_thread(
                is_paused,
            )

            if paused:
                logger.info(
                    "Worker is paused."
                )
                await asyncio.sleep(
                    PAUSED_SLEEP_SECONDS
                )
                continue

            now = datetime.now(timezone.utc)

            if (
                last_seed_at is None
                or now - last_seed_at
                >= timedelta(
                    minutes=SEED_INTERVAL_MINUTES
                )
            ):
                seeded = await asyncio.to_thread(
                    seed_jobs,
                )
                last_seed_at = now

                logger.info(
                    "Domain queue synchronized. rows=%s",
                    seeded,
                )

            jobs = await asyncio.to_thread(
                claim_jobs,
                CONCURRENCY,
            )

            if not jobs:
                await asyncio.sleep(
                    IDLE_SLEEP_SECONDS
                )
                continue

            await asyncio.gather(
                *(
                    process_job(job)
                    for job in jobs
                )
            )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Unexpected worker loop error."
            )
            await asyncio.sleep(
                IDLE_SLEEP_SECONDS
            )


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
