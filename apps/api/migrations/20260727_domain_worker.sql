-- ContactIQ domain worker
-- Run this entire file once in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.domain_jobs (
    id uuid primary key default gen_random_uuid(),
    domain text not null unique,
    status text not null default 'PENDING'
        check (
            status in (
                'PENDING',
                'PROCESSING',
                'MATCHED',
                'NOT_FOUND',
                'FAILED'
            )
        ),
    attempts integer not null default 0,
    last_error text,
    worker_id text,
    started_at timestamptz,
    finished_at timestamptz,
    next_retry_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists domain_jobs_status_retry_idx
    on public.domain_jobs (status, next_retry_at, created_at);

create index if not exists domain_jobs_worker_idx
    on public.domain_jobs (worker_id, status);

create table if not exists public.worker_control (
    worker_name text primary key,
    paused boolean not null default false,
    updated_at timestamptz not null default now()
);

insert into public.worker_control (
    worker_name,
    paused
)
values (
    'domain_enrichment',
    false
)
on conflict (worker_name) do nothing;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists domain_jobs_set_updated_at
on public.domain_jobs;

create trigger domain_jobs_set_updated_at
before update on public.domain_jobs
for each row
execute function public.set_updated_at();

create or replace function public.seed_domain_jobs()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    inserted_count integer;
begin
    insert into public.domain_jobs (
        domain,
        status
    )
    select distinct
        lower(trim(et.domain)),
        'PENDING'
    from public.email_targets et
    where et.domain is not null
      and position('.' in trim(et.domain)) > 0
      and et.phone is null
      and et.status::text in (
          'NEW',
          'NOT_FOUND',
          'FAILED'
      )
    on conflict (domain) do update
    set
        status = case
            when public.domain_jobs.status in (
                'MATCHED',
                'PROCESSING'
            )
            then public.domain_jobs.status
            else 'PENDING'
        end,
        next_retry_at = null,
        last_error = null;

    get diagnostics inserted_count = row_count;
    return inserted_count;
end;
$$;

create or replace function public.claim_domain_jobs(
    p_limit integer,
    p_worker_id text
)
returns setof public.domain_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
    return query
    with claimed as (
        select dj.id
        from public.domain_jobs dj
        where (
            dj.status = 'PENDING'
            or (
                dj.status = 'FAILED'
                and (
                    dj.next_retry_at is null
                    or dj.next_retry_at <= now()
                )
            )
        )
        order by dj.created_at asc
        for update skip locked
        limit greatest(1, least(p_limit, 50))
    )
    update public.domain_jobs dj
    set
        status = 'PROCESSING',
        worker_id = p_worker_id,
        started_at = now(),
        finished_at = null,
        attempts = dj.attempts + 1,
        last_error = null
    from claimed
    where dj.id = claimed.id
    returning dj.*;
end;
$$;

create or replace function public.requeue_stale_domain_jobs(
    p_stale_minutes integer default 30
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    updated_count integer;
begin
    update public.domain_jobs
    set
        status = 'PENDING',
        worker_id = null,
        started_at = null,
        last_error = coalesce(
            last_error,
            'Job was requeued after a stale worker lease.'
        )
    where status = 'PROCESSING'
      and started_at < now() - make_interval(
          mins => greatest(1, p_stale_minutes)
      );

    get diagnostics updated_count = row_count;
    return updated_count;
end;
$$;

create or replace function public.domain_worker_status()
returns table (
    pending bigint,
    processing bigint,
    matched bigint,
    not_found bigint,
    failed bigint,
    total bigint
)
language sql
security definer
set search_path = public
as $$
    select
        count(*) filter (
            where status = 'PENDING'
        ) as pending,
        count(*) filter (
            where status = 'PROCESSING'
        ) as processing,
        count(*) filter (
            where status = 'MATCHED'
        ) as matched,
        count(*) filter (
            where status = 'NOT_FOUND'
        ) as not_found,
        count(*) filter (
            where status = 'FAILED'
        ) as failed,
        count(*) as total
    from public.domain_jobs;
$$;

grant execute on function public.seed_domain_jobs()
to service_role;

grant execute on function public.claim_domain_jobs(integer, text)
to service_role;

grant execute on function public.requeue_stale_domain_jobs(integer)
to service_role;

grant execute on function public.domain_worker_status()
to service_role;
