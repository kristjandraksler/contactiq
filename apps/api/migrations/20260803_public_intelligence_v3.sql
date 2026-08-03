-- ContactIQ Public Intelligence v3
-- Requeue only selected public mailbox providers.

update public.email_targets
set
    website = null,
    phone = null,
    confidence = null,
    source_url = null,
    pages_scanned = 0,
    scan_duration_ms = 0,
    last_scan = null,
    status = 'NEW',
    last_error = null,
    phone_country_code = null,
    phone_country_name = null,
    phone_country_flag = null,
    phone_country_confidence = 0,
    country_mismatch = false,
    is_cross_border = false,
    person_match_type = null,
    company_id = null
where lower(trim(domain)) in (
    'gmail.com',
    'googlemail.com',
    'hotmail.com',
    'outlook.com',
    'live.com',
    'yahoo.com',
    'icloud.com',
    'gmx.de',
    'gmx.net',
    'aol.com'
);

insert into public.domain_jobs (
    domain,
    status,
    attempts,
    last_error,
    worker_id,
    started_at,
    finished_at,
    next_retry_at,
    processed_contacts,
    total_contacts,
    created_at,
    updated_at
)
select
    domains.domain,
    'PENDING',
    0,
    null,
    null,
    null,
    null,
    null,
    0,
    domains.total_contacts,
    now(),
    now()
from (
    select
        lower(trim(domain)) as domain,
        count(*)::integer as total_contacts
    from public.email_targets
    where lower(trim(domain)) in (
        'gmail.com',
        'googlemail.com',
        'hotmail.com',
        'outlook.com',
        'live.com',
        'yahoo.com',
        'icloud.com',
        'gmx.de',
        'gmx.net',
        'aol.com'
    )
    group by lower(trim(domain))
) domains
on conflict (domain)
do update set
    status = 'PENDING',
    attempts = 0,
    last_error = null,
    worker_id = null,
    started_at = null,
    finished_at = null,
    next_retry_at = null,
    processed_contacts = 0,
    total_contacts = excluded.total_contacts,
    updated_at = now();
