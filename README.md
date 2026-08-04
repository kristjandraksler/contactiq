# ContactIQ Auth + Users

Paket doda:

- Supabase email/password login;
- zaščito vseh frontend strani prek `proxy.ts`;
- login brez sidebarja;
- ohranitev seje v piškotkih;
- logout;
- tabelo `profiles`;
- vlogi `admin` in `user`;
- admin stran `/users`;
- ustvarjanje uporabnikov na frontendu;
- spremembo vloge;
- aktivacijo/deaktivacijo;
- prikaz prijavljenega uporabnika v sidebarju.

## 1. Razpakiranje

Razpakiraj ZIP v koren projekta in prepiši obstoječe datoteke.

## 2. Namesti pakete

```powershell
cd .\apps\web
npm install
cd ..\..
```

## 3. Dodaj auth CSS v globals.css

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\install-auth.ps1
```

## 4. Supabase SQL

V Supabase SQL Editorju zaženi:

```text
apps/api/migrations/20260803_auth_profiles.sql
```

Nato ustvari prvega uporabnika v:

```text
Authentication → Users → Add user
```

Po ustvarjanju ga promoviraj v admina:

```sql
update public.profiles
set role = 'admin'
where email = 'TVOJ-EMAIL';
```

## 5. Environment variables

### Vercel

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
NEXT_PUBLIC_API_URL
```

Če imaš star `anon` ključ, lahko namesto publishable uporabiš:

```text
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### Render

Backend že uporablja:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Service role ključ nikoli ne dodajaj v Vercel frontend environment.

## 6. Commit

```powershell
git add .\apps\web\package.json
git add .\apps\web\package-lock.json
git add .\apps\web\proxy.ts
git add .\apps\web\lib\supabase
git add .\apps\web\components\auth
git add .\apps\web\components\Sidebar.tsx
git add .\apps\web\app\layout.tsx
git add .\apps\web\app\globals.css
git add .\apps\web\app\login
git add .\apps\web\app\users
git add .\apps\api\app\routes\users.py
git add .\apps\api\app\main.py
git add .\apps\api\migrations\20260803_auth_profiles.sql
git add .\.env.example

git commit -m "Add Supabase auth and user management"
git push origin main
```

## Pomembno

Frontend strani so zaščitene z loginom. Admin endpoint `/admin/users` preverja Supabase access token in admin vlogo.

Obstoječi poslovni API endpointi (`/contacts`, `/companies`, `/leads` ...) v tem paketu še niso vsi preklopljeni na preverjanje access tokena, ker bi bilo treba hkrati posodobiti vse obstoječe `fetch` klice. Zato login prepreči dostop skozi aplikacijo, neposredna zaščita celotnega API-ja pa je ločena naslednja varnostna faza.
