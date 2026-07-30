from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_supabase
from app.services.company_cache import save_company_result
from app.services.country_detector import (
    country_mismatch_payload,
    country_payload,
    detect_company_country,
    detect_phone_country,
    phone_country_payload,
)
from app.services.person_matcher import find_person_phone_in_pages
from app.services.person_search import search_public_mailbox_person
from app.services.phone_finder import FinderResult, find_phone_from_pages
from app.services.website_crawler import crawl_company_website
from app.services.providers import clean_domain, is_public_email_domain


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


def get_contacts_for_domain(domain: str) -> list[dict[str, Any]]:
    supabase = get_supabase()
    response = (
        supabase.table("email_targets")
        .select("id,email,domain,scan_attempts")
        .eq("domain", domain)
        .execute()
    )
    return response.data or []

def update_contact(contact_id: str, payload: dict[str, Any]) -> None:
    supabase = get_supabase()
    supabase.table("email_targets").update(payload).eq("id", contact_id).execute()

def _payload(
    result: FinderResult,
    company_id: str | None,
    attempts: int,
    country: Any,
    phone_country: Any,
    person_match_type: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "website": result.website, "phone": result.phone,
        "confidence": result.confidence, "source_url": result.source_url,
        "pages_scanned": result.pages_scanned, "scan_attempts": attempts,
        "scan_duration_ms": result.scan_duration_ms, "last_scan": utc_now_iso(),
        "status": result.status, "last_error": result.error,
    }
    payload.update(country_payload(country))
    payload.update(
        phone_country_payload(phone_country)
    )
    payload.update(
        country_mismatch_payload(
            country,
            phone_country,
        )
    )
    payload["person_match_type"] = person_match_type
    if company_id:
        payload["company_id"] = company_id
    return payload

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
                "next_retry_at": None,
            },
        )
        return

    started_at = time.perf_counter()

    try:
        contacts = await asyncio.to_thread(
            get_contacts_for_domain,
            domain,
        )

        # Public mailbox / ISP domains are not company websites.
        # They are classified immediately and never crawled or searched.
        if is_public_email_domain(domain):
            for contact in contacts:
                attempts = (
                    int(contact.get("scan_attempts") or 0)
                    + 1
                )

                await asyncio.to_thread(
                    update_contact,
                    str(contact["id"]),
                    {
                        "website": None,
                        "phone": None,
                        "confidence": None,
                        "source_url": None,
                        "pages_scanned": 0,
                        "scan_attempts": attempts,
                        "scan_duration_ms": int(
                            (
                                time.perf_counter()
                                - started_at
                            )
                            * 1000
                        ),
                        "last_scan": utc_now_iso(),
                        "status": "PUBLIC_EMAIL",
                        "last_error": None,
                        "country_code": None,
                        "country_name": None,
                        "country_flag": None,
                        "country_confidence": 0,
                        "country_source": "unknown",
                        "country_evidence": [],
                        "language_code": None,
                        "timezone_name": None,
                        "phone_country_code": None,
                        "phone_country_name": None,
                        "phone_country_flag": None,
                        "phone_country_confidence": 0,
                        "country_mismatch": False,
                        "is_cross_border": False,
                        "person_match_type": "public_email",
                        "company_id": None,
                    },
                )

            update_job(
                job.id,
                {
                    "status": "NOT_FOUND",
                    "finished_at": utc_now_iso(),
                    "worker_id": None,
                    "last_error": (
                        "Public mailbox provider; "
                        "excluded from company enrichment."
                    ),
                    "next_retry_at": None,
                },
            )

            logger.info(
                "domain=%s public_mailbox=true contacts=%s classified=PUBLIC_EMAIL",
                domain,
                len(contacts),
            )
            return

        website, pages = await crawl_company_website(
            domain,
            max_pages=MAX_PAGES,
        )

        company_result = find_phone_from_pages(
            domain=domain,
            website=website,
            pages=pages,
            started_at=started_at,
        )

        company_country = detect_company_country(
            phone=company_result.phone,
            website_or_domain=website or domain,
            pages=pages,
            allow_tld=True,
        )

        company_phone_country = detect_phone_country(
            company_result.phone
        )

        company_id = await asyncio.to_thread(
            save_company_result,
            domain,
            company_result,
            company_country,
            company_phone_country,
        )

        person_matches = 0

        for contact in contacts:
            email = str(contact.get("email") or "")
            person = find_person_phone_in_pages(
                email,
                pages,
                domain,
            )

            logger.info(
                (
                    "PERSON MATCH email=%s "
                    "matched=%s phone=%s "
                    "score=%s evidence=%s"
                ),
                email,
                person.matched,
                person.phone,
                person.score,
                person.evidence,
            )

            if person.matched and person.phone:
                person_matches += 1
                chosen = FinderResult(
                    status="MATCHED",
                    website=website,
                    phone=person.phone,
                    confidence=person.confidence,
                    source_url=person.source_url,
                    pages_scanned=len(pages),
                    scan_duration_ms=int(
                        (
                            time.perf_counter()
                            - started_at
                        )
                        * 1000
                    ),
                    candidates=[
                        {
                            "phone": person.phone,
                            "score": person.score,
                            "source": "person_block",
                            "source_url": (
                                person.source_url
                            ),
                            "evidence": list(
                                person.evidence
                            ),
                            "person_name": (
                                person.person_name
                            ),
                        }
                    ],
                    error=None,
                    confidence_label=(
                        "VERY_HIGH"
                        if (
                            person.confidence or 0
                        ) >= 90
                        else "HIGH"
                        if (
                            person.confidence or 0
                        ) >= 75
                        else "MEDIUM"
                        if (
                            person.confidence or 0
                        ) >= 50
                        else "LOW"
                    ),
                )
            else:
                chosen = company_result

            await asyncio.to_thread(
                update_contact,
                str(contact["id"]),
                _payload(
                    chosen,
                    company_id,
                    int(
                        contact.get(
                            "scan_attempts"
                        )
                        or 0
                    )
                    + 1,
                    company_country,
                    detect_phone_country(
                        chosen.phone
                    ),
                    (
                        "person_phone"
                        if person.matched and person.phone
                        else "company_phone"
                        if chosen.status == "MATCHED"
                        else "none"
                    ),
                ),
            )

        job_status = (
            company_result.status
            if company_result.status
            in {"MATCHED", "NOT_FOUND"}
            else "FAILED"
        )

        update_job(
            job.id,
            {
                "status": job_status,
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "last_error": company_result.error,
                "next_retry_at": (
                    None
                    if job_status != "FAILED"
                    else retry_at_iso(
                        job.attempts
                    )
                ),
            },
        )

        logger.info(
            (
                "domain=%s company_status=%s "
                "contacts=%s person_matches=%s"
            ),
            domain,
            company_result.status,
            len(contacts),
            person_matches,
        )

    except Exception as exc:
        terminal_failure = (
            job.attempts >= MAX_RETRIES
        )

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
                    else retry_at_iso(
                        job.attempts
                    )
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
