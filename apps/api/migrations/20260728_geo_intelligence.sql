-- ContactIQ Geo Intelligence
-- Run once in Supabase SQL Editor before deploying the Python/frontend code.

alter table public.companies
    add column if not exists country_code text,
    add column if not exists country_name text,
    add column if not exists country_flag text,
    add column if not exists country_confidence integer,
    add column if not exists country_source text,
    add column if not exists language_code text,
    add column if not exists timezone_name text;

alter table public.email_targets
    add column if not exists country_code text,
    add column if not exists country_name text,
    add column if not exists country_flag text,
    add column if not exists country_confidence integer,
    add column if not exists country_source text,
    add column if not exists language_code text,
    add column if not exists timezone_name text,
    add column if not exists person_match_type text;

create index if not exists companies_country_code_idx
    on public.companies(country_code);

create index if not exists email_targets_country_code_idx
    on public.email_targets(country_code);

create index if not exists email_targets_person_match_type_idx
    on public.email_targets(person_match_type);
