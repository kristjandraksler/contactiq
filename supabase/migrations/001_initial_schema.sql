create extension if not exists pgcrypto;

create type public.contact_status as enum (
  'NEW', 'QUEUED', 'PROCESSING', 'MATCHED',
  'PARTIAL_MATCH', 'NOT_FOUND', 'FAILED', 'RETRY'
);

create type public.match_type as enum (
  'PERSON_MATCH', 'DIRECT_MATCH', 'DEPARTMENT_MATCH',
  'COMPANY_MATCH', 'DOMAIN_ONLY', 'UNMATCHED'
);

create table public.companies (
  id uuid primary key default gen_random_uuid(),
  name text,
  domain text not null unique,
  website text,
  industry text,
  country text default 'SI',
  city text,
  address text,
  last_crawled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.email_targets (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete set null,
  email text not null unique,
  domain text not null,
  status public.contact_status not null default 'NEW',
  attempts integer not null default 0,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.phone_matches (
  id uuid primary key default gen_random_uuid(),
  email_target_id uuid not null references public.email_targets(id) on delete cascade,
  phone text not null,
  normalized_phone text,
  match_type public.match_type not null default 'UNMATCHED',
  confidence numeric(5,2) check (confidence between 0 and 100),
  contact_name text,
  role text,
  source_url text not null,
  source_title text,
  source_excerpt text,
  verified_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.crawl_jobs (
  id uuid primary key default gen_random_uuid(),
  status public.contact_status not null default 'NEW',
  emails_total integer not null default 0,
  processed integer not null default 0,
  matched integer not null default 0,
  partial integer not null default 0,
  failed integer not null default 0,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create index email_targets_status_idx on public.email_targets(status);
create index email_targets_domain_idx on public.email_targets(domain);
create index phone_matches_email_target_idx on public.phone_matches(email_target_id);
create index phone_matches_normalized_phone_idx on public.phone_matches(normalized_phone);

alter table public.companies enable row level security;
alter table public.email_targets enable row level security;
alter table public.phone_matches enable row level security;
alter table public.crawl_jobs enable row level security;
