from fastapi import APIRouter, HTTPException

from app.database import get_supabase


router = APIRouter(
    tags=["Statistics"],
)


@router.get("/stats")
def stats() -> dict[str, int | float]:
    try:
        supabase = get_supabase()

        def count_by_status(status: str) -> int:
            response = (
                supabase.table("email_targets")
                .select("id", count="exact")
                .eq("status", status)
                .limit(1)
                .execute()
            )

            return response.count or 0

        total_response = (
            supabase.table("email_targets")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        emails_total = total_response.count or 0

        pending = count_by_status("NEW")
        matched = count_by_status("MATCHED")
        partial = count_by_status("PARTIAL_MATCH")
        not_found = count_by_status("NOT_FOUND")
        failed = count_by_status("FAILED")

        completed = matched + partial + not_found + failed

        success_rate = (
            round((matched / completed) * 100, 2)
            if completed > 0
            else 0.0
        )

        return {
            "emails_total": emails_total,
            "pending": pending,
            "matched": matched,
            "partial": partial,
            "not_found": not_found,
            "failed": failed,
            "completed": completed,
            "success_rate": success_rate,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load statistics: {exc}",
        ) from exc