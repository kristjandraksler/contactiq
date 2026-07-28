# ContactIQ domain worker – public mailbox fix

Zamenjaj:

`apps/api/app/workers/domain_worker.py`

Nova logika:

- `a1.net`, `gmail.com`, `siol.net`, `telemach.net` in druge javne mailbox domene se ne crawla kot podjetja.
- Za vsak e-mail se uporabi `search_public_mailbox_person()`.
- Če ni zanesljivega osebnega zadetka, se shrani `NOT_FOUND`.
- Telefonska številka ponudnika e-pošte se ne pripiše kontaktu.

## Git

```powershell
git add .\apps\api\app\workers\domain_worker.py
git commit -m "Fix public mailbox handling in domain worker"
git push origin main
```

Pred ponovnim zagonom batcha ponastavi napačno obdelane javne domene.
