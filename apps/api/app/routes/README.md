# ContactIQ brezplačna batch obdelava

1. Zamenjaj `apps/api/app/routes/admin_worker.py`.
2. Pushaj spremembo.
3. Za en batch pokliči:

```powershell
Invoke-RestMethod -Method Post -Uri "https://contactiq-5w9n.onrender.com/admin/worker/run?limit=5"
```

4. Za celotno bazo zaženi:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_all_domains.ps1
```

Računalnik mora med obdelavo ostati prižgan.
