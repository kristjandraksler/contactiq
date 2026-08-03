create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    full_name text null,
    role text not null default 'user',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint profiles_role_check check (role in ('admin', 'user'))
);

alter table public.profiles enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
on public.profiles
for select
to authenticated
using (auth.uid() = id);

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (
        id,
        email,
        full_name,
        role,
        active
    )
    values (
        new.id,
        coalesce(new.email, ''),
        nullif(new.raw_user_meta_data ->> 'full_name', ''),
        case
            when new.raw_user_meta_data ->> 'role' = 'admin'
                then 'admin'
            else 'user'
        end,
        true
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = coalesce(
            excluded.full_name,
            public.profiles.full_name
        ),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_auth_user();

-- Create missing profiles for users that already exist.
insert into public.profiles (
    id,
    email,
    full_name,
    role,
    active
)
select
    id,
    coalesce(email, ''),
    nullif(raw_user_meta_data ->> 'full_name', ''),
    case
        when raw_user_meta_data ->> 'role' = 'admin'
            then 'admin'
        else 'user'
    end,
    true
from auth.users
on conflict (id) do nothing;

-- After running this migration, promote your first admin:
-- update public.profiles
-- set role = 'admin'
-- where email = 'YOUR_EMAIL';
