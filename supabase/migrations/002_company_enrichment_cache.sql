-- ContactIQ: company-level enrichment cache
-- MATCHED results are considered fresh for 30 days.
-- NOT_FOUND results are considered fresh for 7 days.
-- FAILED results are intentionally not cached.

alter table public.companies
  add column if not exists phone text,
  add column if not exists confidence integer,
  add column if not exists source_url text,
  add column if not exists pages_scanned integer not null default 0,
  add column if not exists scan_duration_ms integer,
  add column if not exists enrichment_status text,
  add column if not exists verified_at timestamptz;

alter table public.companies
  drop constraint if exists companies_confidence_check;

alter table public.companies
  add constraint companies_confidence_check
  check (
    confidence is null
    or confidence between 0 and 100
  );

alter table public.companies
  drop constraint if exists companies_enrichment_status_check;

alter table public.companies
  add constraint companies_enrichment_status_check
  check (
    enrichment_status is null
    or enrichment_status in ('MATCHED', 'NOT_FOUND')
  );

create index if not exists companies_verified_at_idx
  on public.companies(verified_at);

create index if not exists companies_enrichment_status_idx
  on public.companies(enrichment_status);

-- Keep updated_at current when cached enrichment data changes.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists companies_set_updated_at
  on public.companies;

create trigger companies_set_updated_at
before update on public.companies
for each row
execute function public.set_updated_at();