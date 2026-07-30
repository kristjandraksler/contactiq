-- ContactIQ: PUBLIC_EMAIL classification
-- Run once in Supabase SQL Editor while the worker is paused.

alter type public.contact_status
    add value if not exists 'PUBLIC_EMAIL';

create table if not exists public.public_email_domains (
    domain text primary key,
    created_at timestamptz not null default now()
);

insert into public.public_email_domains (domain)
values
    (' in domain:
        domain = domain.rsplit('),
    (')
    domain = domain.split('),
    (')
    return domain.removeprefix('),
    (').replace('),
    (', 1)[0].split('),
    (', 1)[0].strip('),
    (', 1)[1]
    domain = domain.replace('),
    ('abv.bg'),
    ('amis.net'),
    ('aol.com'),
    ('arnes.si'),
    ('bk.ru'),
    ('centrum.cz'),
    ('centrum.sk'),
    ('email.si'),
    ('eunet.rs'),
    ('fastmail.com'),
    ('freemail.hu'),
    ('gmail.com'),
    ('gmx.at'),
    ('gmx.ch'),
    ('gmx.com'),
    ('gmx.de'),
    ('googlemail.com'),
    ('guest.arnes.si'),
    ('hotmail.co.uk'),
    ('hotmail.com'),
    ('hotmail.de'),
    ('hotmail.fr'),
    ('icloud.com'),
    ('inbox.lv'),
    ('inbox.ru'),
    ('interia.pl'),
    ('iskon.hr'),
    ('laposte.net'),
    ('list.ru'),
    ('live.co.uk'),
    ('live.com'),
    ('live.de'),
    ('mac.com'),
    ('mail.com'),
    ('mail.ee'),
    ('mail.ru'),
    ('me.com'),
    ('msn.com'),
    ('mts.rs'),
    ('net.hr'),
    ('onet.pl'),
    ('orange.fr'),
    ('outlook.com'),
    ('outlook.de'),
    ('outlook.fr'),
    ('poczta.fm'),
    ('private.relay.appleid.com'),
    ('proton.me'),
    ('protonmail.com'),
    ('sbb.rs'),
    ('seznam.cz'),
    ('siol.net'),
    ('t-2.net'),
    ('t-com.hr'),
    ('telemach.net'),
    ('tuta.com'),
    ('tutanota.com'),
    ('vip.hr'),
    ('volja.net'),
    ('web.de'),
    ('wp.pl'),
    ('yahoo.co.uk'),
    ('yahoo.com'),
    ('yahoo.de'),
    ('yahoo.es'),
    ('yahoo.fr'),
    ('yahoo.it'),
    ('yandex.com'),
    ('yandex.ru'),
    ('zoho.com'),
    ('zoznam.sk')
on conflict (domain) do nothing;

create or replace function public.classify_public_email_target()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.domain := lower(trim(new.domain));

    if exists (
        select 1
        from public.public_email_domains p
        where p.domain = new.domain
    ) then
        new.status := 'PUBLIC_EMAIL';
        new.phone := null;
        new.confidence := null;
        new.source_url := null;
        new.website := null;
        new.company_id := null;
        new.person_match_type := 'public_email';
        new.last_error := null;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_classify_public_email_target
on public.email_targets;

create trigger trg_classify_public_email_target
before insert or update of domain
on public.email_targets
for each row
execute function public.classify_public_email_target();

-- Classify existing NEW public-mail contacts.
update public.email_targets et
set
    status = 'PUBLIC_EMAIL',
    phone = null,
    confidence = null,
    source_url = null,
    website = null,
    company_id = null,
    person_match_type = 'public_email',
    last_error = null
where et.status = 'NEW'
  and exists (
      select 1
      from public.public_email_domains p
      where p.domain = lower(trim(et.domain))
  );

-- Remove public-mail domains from the worker queue.
delete from public.domain_jobs dj
where exists (
    select 1
    from public.public_email_domains p
    where p.domain = lower(trim(dj.domain))
);

-- Seeder now creates jobs only for real business domains.
create or replace function public.seed_domain_jobs()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    inserted_count integer := 0;
begin
    insert into public.domain_jobs (
        domain,
        status,
        attempts,
        worker_id,
        started_at,
        finished_at,
        next_retry_at,
        last_error
    )
    select distinct
        lower(trim(et.domain)),
        'PENDING',
        0,
        null::text,
        null::timestamptz,
        null::timestamptz,
        null::timestamptz,
        null::text
    from public.email_targets et
    where et.domain is not null
      and trim(et.domain) <> ''
      and et.status::text = 'NEW'
      and not exists (
          select 1
          from public.public_email_domains p
          where p.domain = lower(trim(et.domain))
      )
    on conflict (domain) do nothing;

    get diagnostics inserted_count = row_count;
    return inserted_count;
end;
$$;

-- Verification result.
select
    status,
    count(*) as contacts
from public.email_targets
group by status
order by contacts desc;
