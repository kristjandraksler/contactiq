# ContactIQ

Interno orodje za obogatitev poslovnih e-poštnih naslovov z javno objavljenimi telefonskimi številkami.

## Arhitektura

- `apps/web` – Next.js uporabniški vmesnik
- `apps/api` – FastAPI
- `apps/worker` – Python worker
- `supabase/migrations` – podatkovni model
- `docs` – arhitektura in naslednji koraki

## Lokalni zagon

### 1. Frontend

```bash
cd apps/web
npm install
npm run dev
```

Odpri `http://localhost:3000`.

### 2. API

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Worker

```bash
cd apps/worker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m worker.main
```

## Supabase

1. Ustvari Supabase projekt.
2. Odpri SQL Editor.
3. Zaženi `supabase/migrations/001_initial_schema.sql`.
4. V `.env` datoteke vnesi Supabase URL in ključe.

## V1 cilj

1. Uvoz obstoječe baze e-mailov.
2. Združevanje po domenah.
3. Pregled javnih strani podjetja.
4. Iskanje telefonskih številk.
5. Povezovanje številke z e-mailom.
6. Ocena ujemanja in shranjevanje vira.
