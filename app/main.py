from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_supabase
from app.import_utils import extract_emails, is_valid_email


app = FastAPI(
    title="ContactIQ API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


@app.get("/stats")
def stats() -> dict[str, int]:
    try:
        supabase = get_supabase()

        total_response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        matched_response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .eq("status", "MATCHED")
            .limit(1)
            .execute()
        )

        partial_response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .eq("status", "PARTIAL_MATCH")
            .limit(1)
            .execute()
        )

        not_found_response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .eq("status", "NOT_FOUND")
            .limit(1)
            .execute()
        )

        return {
            "emails_total": total_response.count or 0,
            "matched": matched_response.count or 0,
            "partial": partial_response.count or 0,
            "not_found": not_found_response.count or 0,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load statistics: {exc}",
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