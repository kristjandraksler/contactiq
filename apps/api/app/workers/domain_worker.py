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
from app.services.providers import clean_domain, is_public_email_domain
from app.services.website_crawler import crawl_company_website


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

CONCURRENCY = max(
    1,
    min(int(os.getenv("DOMAIN_WORKER_CONCURRENCY", "5")), 20),
)
MAX_PAGES = max(
    1,
    min(int(os.getenv("DOMAIN_WORKER_MAX_PAGES", "10")), 20),
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

PUBLIC_EMAIL_CHUNK_SIZE = max(
    1,
    min(int(os.getenv("PUBLIC_EMAIL_CHUNK_SIZE", "10")), 50),
)
PUBLIC_EMAIL_SEARCH_TIMEOUT_SECONDS = max(
    5,
    min(int(os.getenv("PUBLIC_EMAIL_SEARCH_TIMEOUT_SECONDS", "20")), 90),
)
PUBLIC_EMAIL_CONTACT_CONCURRENCY = max(
    1,
    min(int(os.getenv("PUBLIC_EMAIL_CONTACT_CONCURRENCY", "20")), 20),
)

# The admin endpoint has a 240-second timeout. Keep each claimed public-email
# job below that limit, then return it to PENDING if contacts remain.
PUBLIC_EMAIL_JOB_BUDGET_SECONDS = max(
    30,
    min(int(os.getenv("PUBLIC_EMAIL_JOB_BUDGET_SECONDS", "200")), 220),
)

WORKER_ID = os.getenv(
    "DOMAIN_WORKER_ID",
    f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
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
    response = (
        get_supabase()
        .table("worker_control")
        .select("paused")
        .eq("worker_name", "domain_enrichment")
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return bool(rows and rows[0].get("paused"))


def seed_jobs() -> int:
    response = get_supabase().rpc("seed_domain_jobs").execute()
    value = response.data

    if isinstance(value, int):
        return value

    if isinstance(value, list) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return 0

    return 0


def requeue_stale_jobs(
    stale_minutes: int | None = None,
) -> int:
    response = get_supabase().rpc(
        "requeue_stale_domain_jobs",
        {
            "p_stale_minutes": (
                stale_minutes
                if stale_minutes is not None
                else STALE_JOB_MINUTES
            ),
        },
    ).execute()

    value = response.data

    if isinstance(value, int):
        return value

    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return int(
                first.get("requeued")
                or first.get("count")
                or 0
            )
        try:
            return int(first or 0)
        except (TypeError, ValueError):
            return 0

    return 0


def claim_jobs(limit: int) -> list[DomainJob]:
    response = get_supabase().rpc(
        "claim_domain_jobs",
        {
            "p_limit": limit,
            "p_worker_id": WORKER_ID,
        },
    ).execute()

    return [
        DomainJob(
            id=str(row["id"]),
            domain=str(row["domain"]),
            attempts=int(row.get("attempts") or 0),
        )
        for row in (response.data or [])
    ]


def update_job(
    job_id: str,
    payload: dict[str, Any],
) -> None:
    (
        get_supabase()
        .table("domain_jobs")
        .update(payload)
        .eq("id", job_id)
        .execute()
    )


def get_contacts_for_domain(
    domain: str,
) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("email_targets")
        .select("id,email,domain,scan_attempts,status")
        .eq("domain", domain)
        .execute()
    )
    return response.data or []


def get_new_contacts_chunk(
    domain: str,
    limit: int,
) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("email_targets")
        .select("id,email,domain,scan_attempts,status")
        .eq("domain", domain)
        .eq("status", "NEW")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return response.data or []


def count_contacts(
    domain: str,
    *,
    status: str | None = None,
) -> int:
    query = (
        get_supabase()
        .table("email_targets")
        .select("id", count="exact")
        .eq("domain", domain)
        .limit(1)
    )

    if status:
        query = query.eq("status", status)

    response = query.execute()
    return int(response.count or 0)


def count_domain_matches(domain: str) -> int:
    response = (
        get_supabase()
        .table("email_targets")
        .select("id", count="exact")
        .eq("domain", domain)
        .eq("status", "MATCHED")
        .limit(1)
        .execute()
    )
    return int(response.count or 0)


def update_contact(
    contact_id: str,
    payload: dict[str, Any],
) -> None:
    (
        get_supabase()
        .table("email_targets")
        .update(payload)
        .eq("id", contact_id)
        .execute()
    )


def classify_public_domain_without_research(
    domain: str,
) -> None:
    (
        get_supabase()
        .table("email_targets")
        .update(
            {
                "website": None,
                "phone": None,
                "confidence": None,
                "source_url": None,
                "pages_scanned": 0,
                "scan_duration_ms": 0,
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
            }
        )
        .eq("domain", domain)
        .execute()
    )


def _identity_status(result: FinderResult) -> str:
    if result.error:
        return "FAILED"

    if result.status == "MATCHED" and result.phone:
        return (
            "VERIFIED"
            if int(result.confidence or 0) >= 75
            else "NEEDS_REVIEW"
        )

    return "NOT_FOUND"


def _identity_person_name(result: FinderResult) -> str | None:
    for candidate in result.candidates or []:
        person_name = candidate.get("person_name")
        if person_name:
            return str(person_name)

    return None


def _identity_evidence(result: FinderResult) -> list[str]:
    evidence: list[str] = []

    for candidate in result.candidates or []:
        for key in ("strengths", "evidence", "warnings"):
            values = candidate.get(key) or []

            if isinstance(values, str):
                values = [values]

            for value in values:
                cleaned = str(value).strip()

                if cleaned and cleaned not in evidence:
                    evidence.append(cleaned)

                if len(evidence) >= 20:
                    return evidence

    if result.error:
        evidence.append(f"Error: {result.error}")

    return evidence[:20]


def _split_identity_name(
    full_name: str | None,
) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None

    parts = [
        part
        for part in full_name.strip().split()
        if part
    ]

    if not parts:
        return None, None

    if len(parts) == 1:
        return parts[0], None

    return parts[0], " ".join(parts[1:])


def save_identity_result(
    email: str,
    result: FinderResult,
    phone_country: Any,
) -> None:
    now = utc_now_iso()
    status = _identity_status(result)
    full_name = _identity_person_name(result)
    first_name, last_name = _split_identity_name(full_name)

    record = {
        "id": str(uuid.uuid4()),
        "email": email.strip().lower(),
        "name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "company": None,
        "website": result.website,
        "phone": result.phone,
        "phone_type": (
            "direct_business"
            if result.phone
            and status in {"VERIFIED", "NEEDS_REVIEW"}
            else None
        ),
        "country_code": getattr(
            phone_country,
            "country_code",
            None,
        ),
        "country_name": getattr(
            phone_country,
            "country_name",
            None,
        ),
        "confidence": int(result.confidence or 0),
        "status": status,
        "source_url": result.source_url,
        "source_provider": "public_person_discovery",
        "evidence": _identity_evidence(result),
        "created_at": now,
        "updated_at": now,
    }

    (
        get_supabase()
        .table("email_identity_results")
        .upsert(
            record,
            on_conflict="email",
        )
        .execute()
    )


def _payload(
    result: FinderResult,
    company_id: str | None,
    attempts: int,
    country: Any,
    phone_country: Any,
    person_match_type: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "website": result.website,
        "phone": result.phone,
        "confidence": result.confidence,
        "source_url": result.source_url,
        "pages_scanned": result.pages_scanned,
        "scan_attempts": attempts,
        "scan_duration_ms": result.scan_duration_ms,
        "last_scan": utc_now_iso(),
        "status": result.status,
        "last_error": result.error,
    }
    payload.update(country_payload(country))
    payload.update(phone_country_payload(phone_country))
    payload.update(
        country_mismatch_payload(
            country,
            phone_country,
        )
    )
    payload["person_match_type"] = person_match_type

    if company_id:
        payload["company_id"] = company_id
    else:
        payload["company_id"] = None

    return payload


def _not_found_public_result(
    duration_ms: int,
    error: str | None = None,
) -> FinderResult:
    return FinderResult(
        status="NOT_FOUND",
        website=None,
        phone=None,
        confidence=None,
        source_url=None,
        pages_scanned=0,
        scan_duration_ms=duration_ms,
        candidates=[],
        error=error,
        confidence_label="UNKNOWN",
    )


async def _process_public_contact(
    contact: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> bool:
    email = str(contact.get("email") or "")
    started_at = time.perf_counter()

    async with semaphore:
        try:
            result = await asyncio.wait_for(
                search_public_mailbox_person(email),
                timeout=PUBLIC_EMAIL_SEARCH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            result = _not_found_public_result(
                int(
                    (
                        time.perf_counter()
                        - started_at
                    )
                    * 1000
                ),
                (
                    "Public person search timed out after "
                    f"{PUBLIC_EMAIL_SEARCH_TIMEOUT_SECONDS}s."
                ),
            )
            logger.warning(
                "PUBLIC_EMAIL_TIMEOUT email=%s timeout_seconds=%s",
                email,
                PUBLIC_EMAIL_SEARCH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            result = _not_found_public_result(
                int(
                    (
                        time.perf_counter()
                        - started_at
                    )
                    * 1000
                ),
                f"{type(exc).__name__}: {exc}",
            )
            logger.exception(
                "PUBLIC_EMAIL_SEARCH_FAILED email=%s",
                email,
            )

    matched = bool(
        result.status == "MATCHED"
        and result.phone
    )

    if not matched:
        result = FinderResult(
            status=result.status,
            website=None,
            phone=None,
            confidence=None,
            source_url=None,
            pages_scanned=result.pages_scanned,
            scan_duration_ms=result.scan_duration_ms,
            candidates=result.candidates,
            error=result.error,
            confidence_label=result.confidence_label,
        )

        if result.error:
            logger.info(
                "PUBLIC_EMAIL_SKIPPED email=%s reason=%s",
                email,
                result.error,
            )

    phone_country = detect_phone_country(result.phone)
    country = phone_country if matched else detect_phone_country(None)

    await asyncio.to_thread(
            save_identity_result,
            email,
            result,
            phone_country,
        )

    contact_payload = _payload(
        result,
        None,
        int(contact.get("scan_attempts") or 0) + 1,
        country,
        phone_country,
        "public_person" if matched else "public_email",
    )
    contact_payload.update(
        {
            "identity_status": _identity_status(result).lower(),
            "identity_checked_at": utc_now_iso(),
        }
    )

    await asyncio.to_thread(
        update_contact,
        str(contact["id"]),
        contact_payload,
    )

    logger.info(
        "PUBLIC_EMAIL_CONTACT_DONE email=%s matched=%s elapsed_seconds=%.2f",
        email,
        matched,
        time.perf_counter() - started_at,
    )

    return matched


async def _process_public_email_chunk(
    job: DomainJob,
    domain: str,
) -> None:
    started_at = time.perf_counter()

    total_contacts = await asyncio.to_thread(
        count_contacts,
        domain,
    )

    semaphore = asyncio.Semaphore(
        PUBLIC_EMAIL_CONTACT_CONCURRENCY
    )

    processed_this_claim = 0

    logger.info(
        "PUBLIC_EMAIL_JOB_START domain=%s total=%s chunk_size=%s budget_seconds=%s",
        domain,
        total_contacts,
        PUBLIC_EMAIL_CHUNK_SIZE,
        PUBLIC_EMAIL_JOB_BUDGET_SECONDS,
    )

    while True:
        elapsed = time.perf_counter() - started_at

        if elapsed >= PUBLIC_EMAIL_JOB_BUDGET_SECONDS:
            logger.info(
                "PUBLIC_EMAIL_JOB_BUDGET_REACHED domain=%s elapsed_seconds=%.2f processed_this_claim=%s",
                domain,
                elapsed,
                processed_this_claim,
            )
            break

        chunk = await asyncio.to_thread(
            get_new_contacts_chunk,
            domain,
            PUBLIC_EMAIL_CHUNK_SIZE,
        )

        if not chunk:
            break

        logger.info(
            "PUBLIC_EMAIL_CHUNK_START domain=%s chunk=%s total=%s processed_this_claim=%s",
            domain,
            len(chunk),
            total_contacts,
            processed_this_claim,
        )

        await asyncio.gather(
            *(
                _process_public_contact(
                    contact,
                    semaphore,
                )
                for contact in chunk
            )
        )

        processed_this_claim += len(chunk)

        logger.info(
            "PUBLIC_EMAIL_CHUNK_END domain=%s chunk=%s processed_this_claim=%s elapsed_seconds=%.2f",
            domain,
            len(chunk),
            processed_this_claim,
            time.perf_counter() - started_at,
        )

    remaining = await asyncio.to_thread(
        count_contacts,
        domain,
        status="NEW",
    )
    processed = max(total_contacts - remaining, 0)
    matched = await asyncio.to_thread(
        count_domain_matches,
        domain,
    )

    if remaining > 0:
        update_job(
            job.id,
            {
                "status": "PENDING",
                "processed_contacts": processed,
                "total_contacts": total_contacts,
                "worker_id": None,
                "started_at": None,
                "finished_at": None,
                "last_error": None,
                "next_retry_at": None,
            },
        )
    else:
        update_job(
            job.id,
            {
                "status": (
                    "MATCHED"
                    if matched > 0
                    else "NOT_FOUND"
                ),
                "processed_contacts": total_contacts,
                "total_contacts": total_contacts,
                "worker_id": None,
                "started_at": None,
                "finished_at": utc_now_iso(),
                "last_error": None,
                "next_retry_at": None,
            },
        )

    logger.info(
        "PUBLIC_EMAIL_JOB_END domain=%s processed=%s total=%s remaining=%s matched=%s processed_this_claim=%s elapsed_seconds=%.2f",
        domain,
        processed,
        total_contacts,
        remaining,
        matched,
        processed_this_claim,
        time.perf_counter() - started_at,
    )


async def process_job(
    job: DomainJob,
    include_public_emails: bool = False,
) -> None:
    domain = clean_domain(job.domain)

    if not domain or "." not in domain:
        update_job(
            job.id,
            {
                "status": "NOT_FOUND",
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "started_at": None,
                "last_error": "Invalid domain.",
                "next_retry_at": None,
            },
        )
        return

    started_at = time.perf_counter()

    try:
        public_email_domain = is_public_email_domain(domain)

        if public_email_domain:
            gmail_domain = domain in {
                "gmail.com",
                "googlemail.com",
            }

            if include_public_emails and gmail_domain:
                await _process_public_email_chunk(
                    job,
                    domain,
                )
            else:
                await asyncio.to_thread(
                    classify_public_domain_without_research,
                    domain,
                )
                total_contacts = await asyncio.to_thread(
                    count_contacts,
                    domain,
                )
                update_job(
                    job.id,
                    {
                        "status": "NOT_FOUND",
                        "processed_contacts": total_contacts,
                        "total_contacts": total_contacts,
                        "finished_at": utc_now_iso(),
                        "worker_id": None,
                        "started_at": None,
                        "last_error": (
                            "Public mailbox provider excluded; "
                            "this worker researches Gmail only."
                        ),
                        "next_retry_at": None,
                    },
                )

            return

        logger.info(
            "DOMAIN_STAGE domain=%s stage=load_contacts_start",
            domain,
        )
        contacts = await asyncio.to_thread(
            get_contacts_for_domain,
            domain,
        )
        logger.info(
            "DOMAIN_STAGE domain=%s stage=load_contacts_end contacts=%s",
            domain,
            len(contacts),
        )

        logger.info(
            "DOMAIN_STAGE domain=%s stage=crawl_start max_pages=%s",
            domain,
            MAX_PAGES,
        )
        website, pages = await crawl_company_website(
            domain,
            max_pages=MAX_PAGES,
        )
        logger.info(
            "DOMAIN_STAGE domain=%s stage=crawl_end website=%s pages=%s elapsed_seconds=%.2f",
            domain,
            website,
            len(pages),
            time.perf_counter() - started_at,
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
                            "source_url": person.source_url,
                            "evidence": list(person.evidence),
                            "person_name": person.person_name,
                        }
                    ],
                    error=None,
                    confidence_label=(
                        "VERY_HIGH"
                        if (person.confidence or 0) >= 90
                        else "HIGH"
                        if (person.confidence or 0) >= 75
                        else "MEDIUM"
                        if (person.confidence or 0) >= 50
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
                    int(contact.get("scan_attempts") or 0) + 1,
                    company_country,
                    detect_phone_country(chosen.phone),
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
                "processed_contacts": len(contacts),
                "total_contacts": len(contacts),
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "started_at": None,
                "last_error": company_result.error,
                "next_retry_at": (
                    None
                    if job_status != "FAILED"
                    else retry_at_iso(job.attempts)
                ),
            },
        )

        logger.info(
            "domain=%s company_status=%s contacts=%s person_matches=%s",
            domain,
            company_result.status,
            len(contacts),
            person_matches,
        )

    except asyncio.CancelledError:
        update_job(
            job.id,
            {
                "status": "PENDING",
                "worker_id": None,
                "started_at": None,
                "finished_at": None,
                "last_error": (
                    "Job cancelled before completion; "
                    "automatically returned to queue."
                ),
                "next_retry_at": None,
            },
        )
        logger.warning(
            "Domain job cancelled and requeued: %s",
            domain,
        )
        raise

    except Exception as exc:
        terminal_failure = job.attempts >= MAX_RETRIES

        update_job(
            job.id,
            {
                "status": "FAILED",
                "finished_at": utc_now_iso(),
                "worker_id": None,
                "started_at": None,
                "last_error": f"{type(exc).__name__}: {exc}",
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
        "Starting ContactIQ domain worker worker_id=%s concurrency=%s max_pages=%s",
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
            if await asyncio.to_thread(is_paused):
                await asyncio.sleep(PAUSED_SLEEP_SECONDS)
                continue

            now = datetime.now(timezone.utc)

            if (
                last_seed_at is None
                or now - last_seed_at
                >= timedelta(minutes=SEED_INTERVAL_MINUTES)
            ):
                seeded = await asyncio.to_thread(seed_jobs)
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
                await asyncio.sleep(IDLE_SLEEP_SECONDS)
                continue

            await asyncio.gather(
                *(
                    process_job(
                        job,
                        include_public_emails=True,
                    )
                    for job in jobs
                )
            )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Unexpected worker loop error."
            )
            await asyncio.sleep(IDLE_SLEEP_SECONDS)


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()