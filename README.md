# ContactIQ Phone Engine v2

Zip contains replacement files for:

- `apps/api/app/services/phone_parser.py`
- `apps/api/app/services/phone_finder.py`
- `apps/api/app/services/website_crawler.py`
- `apps/api/app/services/providers.py`

## Main improvements

- positive/negative context scoring around phone numbers
- fax, cookie, agency and hosting noise penalties
- DOM cleanup before visible-text parsing
- footer score reduced and footer/body duplicate counting removed
- source-diversity and page-diversity bonuses
- evidence attached to every candidate
- confidence v2 based on independent signals
- URL canonicalization and crawler noise-path filtering

## Install

Copy the four files over the existing files, then run:

```bash
python -m compileall apps/api/app/services
```

Commit and push from the monorepo root:

```bash
git add apps/api/app/services
git commit -m "Upgrade phone matching engine v2"
git push origin main
```

No database migration is required. Existing top-level `FinderResult` fields remain unchanged. Candidate objects now include additional fields: `source_diversity`, `page_diversity`, and `evidence`.
