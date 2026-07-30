-- ContactIQ Geo v2
-- Run while the worker is paused.

alter table public.email_targets
    add column if not exists phone_country_code text,
    add column if not exists phone_country_name text,
    add column if not exists phone_country_flag text,
    add column if not exists phone_country_confidence integer,
    add column if not exists country_mismatch boolean not null default false,
    add column if not exists is_cross_border boolean not null default false;

alter table public.companies
    add column if not exists phone_country_code text,
    add column if not exists phone_country_name text,
    add column if not exists phone_country_flag text,
    add column if not exists phone_country_confidence integer,
    add column if not exists country_mismatch boolean not null default false,
    add column if not exists is_cross_border boolean not null default false;

-- Existing records whose current country came from the phone:
-- preserve that signal as phone country before recalculating company country.
update public.email_targets
set
    phone_country_code = country_code,
    phone_country_name = country_name,
    phone_country_flag = country_flag,
    phone_country_confidence = country_confidence
where phone is not null
  and country_source in ('phone', 'phone_fallback')
  and phone_country_code is null;

update public.companies
set
    phone_country_code = country_code,
    phone_country_name = country_name,
    phone_country_flag = country_flag,
    phone_country_confidence = country_confidence
where phone is not null
  and country_source in ('phone', 'phone_fallback')
  and phone_country_code is null;

-- Recalculate company country from country-code TLD where possible.
-- This corrects cases such as supernovabih.ba with a foreign +386 number.
with inferred as (
    select
        id,
        case
            when lower(coalesce(website, domain)) ~ '\.si([/:]|$)' then 'SI'
            when lower(coalesce(website, domain)) ~ '\.hr([/:]|$)' then 'HR'
            when lower(coalesce(website, domain)) ~ '\.ba([/:]|$)' then 'BA'
            when lower(coalesce(website, domain)) ~ '\.rs([/:]|$)' then 'RS'
            when lower(coalesce(website, domain)) ~ '\.me([/:]|$)' then 'ME'
            when lower(coalesce(website, domain)) ~ '\.mk([/:]|$)' then 'MK'
            when lower(coalesce(website, domain)) ~ '\.at([/:]|$)' then 'AT'
            when lower(coalesce(website, domain)) ~ '\.de([/:]|$)' then 'DE'
            when lower(coalesce(website, domain)) ~ '\.ch([/:]|$)' then 'CH'
            when lower(coalesce(website, domain)) ~ '\.it([/:]|$)' then 'IT'
            when lower(coalesce(website, domain)) ~ '\.fr([/:]|$)' then 'FR'
            when lower(coalesce(website, domain)) ~ '\.pl([/:]|$)' then 'PL'
            when lower(coalesce(website, domain)) ~ '\.cz([/:]|$)' then 'CZ'
            when lower(coalesce(website, domain)) ~ '\.sk([/:]|$)' then 'SK'
            when lower(coalesce(website, domain)) ~ '\.hu([/:]|$)' then 'HU'
            when lower(coalesce(website, domain)) ~ '\.ro([/:]|$)' then 'RO'
            when lower(coalesce(website, domain)) ~ '\.bg([/:]|$)' then 'BG'
            when lower(coalesce(website, domain)) ~ '\.ee([/:]|$)' then 'EE'
            when lower(coalesce(website, domain)) ~ '\.nl([/:]|$)' then 'NL'
            when lower(coalesce(website, domain)) ~ '\.be([/:]|$)' then 'BE'
            when lower(coalesce(website, domain)) ~ '\.es([/:]|$)' then 'ES'
            when lower(coalesce(website, domain)) ~ '\.pt([/:]|$)' then 'PT'
            when lower(coalesce(website, domain)) ~ '\.uk([/:]|$)' then 'GB'
            else null
        end as code
    from public.email_targets
)
update public.email_targets et
set
    country_code = i.code,
    country_name = case i.code
        when 'SI' then 'Slovenija'
        when 'HR' then 'Hrvaška'
        when 'BA' then 'Bosna in Hercegovina'
        when 'RS' then 'Srbija'
        when 'ME' then 'Črna gora'
        when 'MK' then 'Severna Makedonija'
        when 'AT' then 'Avstrija'
        when 'DE' then 'Nemčija'
        when 'CH' then 'Švica'
        when 'IT' then 'Italija'
        when 'FR' then 'Francija'
        when 'PL' then 'Poljska'
        when 'CZ' then 'Češka'
        when 'SK' then 'Slovaška'
        when 'HU' then 'Madžarska'
        when 'RO' then 'Romunija'
        when 'BG' then 'Bolgarija'
        when 'EE' then 'Estonija'
        when 'NL' then 'Nizozemska'
        when 'BE' then 'Belgija'
        when 'ES' then 'Španija'
        when 'PT' then 'Portugalska'
        when 'GB' then 'Združeno kraljestvo'
    end,
    country_flag = case i.code
        when 'SI' then '🇸🇮'
        when 'HR' then '🇭🇷'
        when 'BA' then '🇧🇦'
        when 'RS' then '🇷🇸'
        when 'ME' then '🇲🇪'
        when 'MK' then '🇲🇰'
        when 'AT' then '🇦🇹'
        when 'DE' then '🇩🇪'
        when 'CH' then '🇨🇭'
        when 'IT' then '🇮🇹'
        when 'FR' then '🇫🇷'
        when 'PL' then '🇵🇱'
        when 'CZ' then '🇨🇿'
        when 'SK' then '🇸🇰'
        when 'HU' then '🇭🇺'
        when 'RO' then '🇷🇴'
        when 'BG' then '🇧🇬'
        when 'EE' then '🇪🇪'
        when 'NL' then '🇳🇱'
        when 'BE' then '🇧🇪'
        when 'ES' then '🇪🇸'
        when 'PT' then '🇵🇹'
        when 'GB' then '🇬🇧'
    end,
    country_confidence = 85,
    country_source = 'tld'
from inferred i
where et.id = i.id
  and i.code is not null
  and (
      et.country_source in ('phone', 'phone_fallback', 'unknown')
      or et.country_code is null
  );

update public.email_targets
set
    country_mismatch = (
        country_code is not null
        and phone_country_code is not null
        and country_code <> phone_country_code
    ),
    is_cross_border = (
        country_code is not null
        and phone_country_code is not null
        and country_code <> phone_country_code
    );

update public.companies
set
    country_mismatch = (
        country_code is not null
        and phone_country_code is not null
        and country_code <> phone_country_code
    ),
    is_cross_border = (
        country_code is not null
        and phone_country_code is not null
        and country_code <> phone_country_code
    );

-- Verify the known example.
select
    email,
    website,
    phone,
    country_code,
    phone_country_code,
    country_mismatch
from public.email_targets
where email = 'zlatko@blic.net';
