create extension if not exists pgcrypto;

create table if not exists public.call_summaries (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.email_targets(id) on delete cascade,
  call_result text not null,
  summary text not null,
  next_action text not null default 'NONE',
  next_call_at timestamptz,
  duration_seconds integer,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint call_summary_duration check (duration_seconds is null or duration_seconds between 0 and 86400),
  constraint call_summary_result check (call_result in ('CONNECTED','NO_ANSWER','VOICEMAIL','WRONG_NUMBER','NOT_INTERESTED','FOLLOW_UP','MEETING_BOOKED','OFFER_SENT','OTHER')),
  constraint call_summary_action check (next_action in ('NONE','CALL','EMAIL','MEETING','OFFER','OTHER'))
);

create index if not exists idx_call_summaries_contact_created
on public.call_summaries(contact_id, created_at desc);

create index if not exists idx_call_summaries_next_call
on public.call_summaries(next_call_at) where next_call_at is not null;
