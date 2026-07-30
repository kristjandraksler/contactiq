from fastapi import APIRouter, HTTPException

from app.database import get_supabase


router = APIRouter(
    tags=["Statistics"],
)


@router.get("/stats")
def stats() -> dict[str, object]:
    try:
        supabase = get_supabase()

        response = (
            supabase.table("email_targets")
            .select(
                (
                    "status,"
                    "phone,"
                    "confidence,"
                    "country_code,"
                    "country_name,"
                    "country_flag,"
                    "person_match_type"
                )
            )
            .execute()
        )

        rows = response.data or []

        counts = {
            "NEW": 0,
            "MATCHED": 0,
            "PARTIAL_MATCH": 0,
            "NOT_FOUND": 0,
            "FAILED": 0,
            "PUBLIC_EMAIL": 0,
        }

        country_counts: dict[str, dict[str, object]] = {}
        confidence_values: list[float] = []
        person_phones = 0
        company_phones = 0

        for row in rows:
            status = str(row.get("status") or "")
            if status in counts:
                counts[status] += 1

            phone = row.get("phone")
            confidence = row.get("confidence")

            if phone and confidence is not None:
                try:
                    confidence_values.append(float(confidence))
                except (TypeError, ValueError):
                    pass

            match_type = row.get("person_match_type")
            if phone and match_type in {"person_phone", "public_person"}:
                person_phones += 1
            elif phone and match_type == "company_phone":
                company_phones += 1

            if phone:
                code = str(row.get("country_code") or "").upper()
                if code:
                    item = country_counts.setdefault(
                        code,
                        {
                            "code": code,
                            "name": row.get("country_name"),
                            "flag": row.get("country_flag"),
                            "count": 0,
                        },
                    )
                    item["count"] = int(item["count"]) + 1

        emails_total = len(rows)
        public_email = counts["PUBLIC_EMAIL"]
        business_contacts = max(0, emails_total - public_email)

        matched = counts["MATCHED"]
        partial = counts["PARTIAL_MATCH"]
        not_found = counts["NOT_FOUND"]
        failed = counts["FAILED"]
        pending = counts["NEW"]

        business_completed = matched + partial + not_found + failed

        business_success_rate = (
            round((matched / business_completed) * 100, 2)
            if business_completed > 0
            else 0.0
        )

        average_confidence = (
            round(sum(confidence_values) / len(confidence_values), 2)
            if confidence_values
            else 0.0
        )

        countries = sorted(
            country_counts.values(),
            key=lambda item: -int(item["count"]),
        )

        return {
            "emails_total": emails_total,
            "business_contacts": business_contacts,
            "public_email": public_email,
            "pending": pending,
            "matched": matched,
            "partial": partial,
            "not_found": not_found,
            "failed": failed,
            "completed": business_completed,
            "success_rate": business_success_rate,
            "business_success_rate": business_success_rate,
            "average_confidence": average_confidence,
            "person_phones": person_phones,
            "company_phones": company_phones,
            "countries": countries,
            "countries_total": len(countries),
            "unknown_country": max(
                0,
                matched - sum(int(item["count"]) for item in countries),
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load statistics: {exc}",
        ) from exc
