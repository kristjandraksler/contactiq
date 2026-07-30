from app.routes.system import router as system_router
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from app.routes.contacts import router as contacts_router
from app.database import get_supabase
from app.import_utils import extract_emails, is_valid_email
from app.routes.enrichment import router as enrichment_router
from app.routes.stats import router as stats_router
from app.routes.leads import router as leads_router
from app.routes.admin_worker import router as admin_worker_router
from app.routes.public_providers import router as public_providers_router

app = FastAPI(
    title="ContactIQ API",
    version="0.6.0",
)

app.include_router(stats_router)
app.include_router(public_providers_router)
app.include_router(enrichment_router)
app.include_router(contacts_router)
app.include_router(leads_router)
app.include_router(system_router)
app.include_router(admin_worker_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://contactiq-eight.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ContactIQ API is running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/database-health")
def database_health() -> dict[str, str | int]:
    try:
        supabase = get_supabase()

        response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        return {
            "status": "ok",
            "database": "connected",
            "email_targets_count": response.count or 0,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase connection failed: {exc}",
        ) from exc





@app.post("/imports/preview")
async def preview_import(
    file: UploadFile = File(...),
) -> dict[str, object]:
    filename = file.filename or "upload"

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Datoteka je prazna.",
            )

        extracted = extract_emails(filename, content)

        valid_emails = [
            email
            for email in extracted
            if is_valid_email(email)
        ]

        invalid_emails = [
            email
            for email in extracted
            if not is_valid_email(email)
        ]

        unique_emails = list(dict.fromkeys(valid_emails))
        duplicates = len(valid_emails) - len(unique_emails)

        return {
            "filename": filename,
            "found": len(extracted),
            "valid": len(valid_emails),
            "invalid": len(invalid_emails),
            "duplicates": duplicates,
            "ready_to_import": len(unique_emails),
            "preview": unique_emails[:20],
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Datoteke ni bilo mogoče obdelati: {exc}",
        ) from exc


@app.post("/imports/commit")
async def commit_import(
    file: UploadFile = File(...),
) -> dict[str, object]:
    filename = file.filename or "upload"

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Datoteka je prazna.",
            )

        extracted = extract_emails(filename, content)

        valid_emails = [
            email
            for email in extracted
            if is_valid_email(email)
        ]

        unique_emails = list(dict.fromkeys(valid_emails))

        invalid_count = len(extracted) - len(valid_emails)
        duplicate_count = len(valid_emails) - len(unique_emails)

        if not unique_emails:
            raise HTTPException(
                status_code=400,
                detail="V datoteki ni veljavnih e-mailov.",
            )

        supabase = get_supabase()

        records = [
            {
                "email": email,
                "domain": email.split("@", 1)[1],
                "status": "NEW",
            }
            for email in unique_emails
        ]

        inserted_count = 0
        batch_size = 500

        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]

            response = (
                supabase.table("email_targets")
                .upsert(
                    batch,
                    on_conflict="email",
                    ignore_duplicates=True,
                )
                .execute()
            )

            inserted_count += len(response.data or [])

        already_exists_count = len(records) - inserted_count

        return {
            "status": "completed",
            "filename": filename,
            "found": len(extracted),
            "valid": len(valid_emails),
            "invalid": invalid_count,
            "duplicates_in_file": duplicate_count,
            "unique_valid": len(unique_emails),
            "inserted": inserted_count,
            "already_existed": already_exists_count,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Uvoz ni uspel: {exc}",
        ) from exc