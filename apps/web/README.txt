ContactIQ Frontend v2

Zamenjaj naslednje datoteke v apps/web:
- app/page.tsx
- app/globals.css
- app/layout.tsx
- components/Sidebar.tsx

Nato iz mape apps/web zaženi:
  npm run build
  git add app/page.tsx app/globals.css app/layout.tsx components/Sidebar.tsx
  git commit -m "Redesign ContactIQ dashboard"
  git push origin main

Frontend uporablja obstoječi NEXT_PUBLIC_API_URL in endpoint /enrichment/test.
