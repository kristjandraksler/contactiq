# ContactIQ Worker v2

Paket vsebuje:

- `apps/api/app/routes/admin_worker.py`
- `apps/api/app/workers/domain_worker.py`
- `run_all_domains.ps1`

## Kaj doda

- endpoint `POST /admin/worker/requeue-stale`;
- samodejni requeue zataknjenih `PROCESSING` jobov;
- retry pri 502, 503, timeoutih in resetih povezave;
- eksponentno čakanje po napakah;
- hitrost, ETA in podrobnejši napredek;
- log datoteko v `logs/`;
- nastavljiv batch size.

## Namestitev

Zamenjaj tri datoteke in nato iz korena projekta:

```powershell
git add .\apps\api\app\routes\admin_worker.py
git add .\apps\api\app\workers\domain_worker.py
git add .\run_all_domains.ps1
git commit -m "Add resilient worker v2"
git push origin main
```

Po Render deployu preveri endpoint:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://contactiq-5w9n.onrender.com/admin/worker/requeue-stale?stale_minutes=10"
```

Zagon z varnimi privzetimi vrednostmi:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_all_domains.ps1
```

Zagon z večjim batchom:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\run_all_domains.ps1 `
  -BatchSize 10 `
  -SleepSeconds 3 `
  -StallMinutes 10
```

Za Render, ki je že vračal 502, začni z `BatchSize 5`. Povečaj na 10 šele po stabilnem testu.
