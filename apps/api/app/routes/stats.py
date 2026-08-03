from fastapi import APIRouter, HTTPException

from app.database import get_supabase


router = APIRouter(
    tags=["Statistics"],
)


@router.get("/stats")
def stats() -> dict[str, object]:
    try:
        supabase = get_supabase()

        rows: list[dict[str, object]] = []

        page_size = 1000
        offset = 0

        while True:
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
                        "phone_country_code,"
                        "phone_country_name,"
                        "phone_country_flag,"
                        "person_match_type"
                    )
                )
                .range(
                    offset,
                    offset + page_size - 1,
                )
                .execute()
            )

            batch = response.data or []
            rows.extend(batch)

            if len(batch) < page_size:
                break

            offset += page_size

        counts = {
            "NEW": 0,
            "MATCHED": 0,
            "PARTIAL_MATCH": 0,
            "NOT_FOUND": 0,
            "FAILED": 0,
            "PUBLIC_EMAIL": 0,
        }

        business_country_counts: dict[
            str,
            dict[str, object],
        ] = {}

        phone_country_counts: dict[
            str,
            dict[str, object],
        ] = {}

        confidence_values: list[float] = []

        person_phones = 0
        company_phones = 0
        phones_found = 0

        for row in rows:
            status = str(
                row.get("status") or ""
            )

            if status in counts:
                counts[status] += 1

            phone = row.get("phone")
            confidence = row.get("confidence")
            match_type = str(
                row.get("person_match_type") or ""
            )

            if phone:
                phones_found += 1

                if confidence is not None:
                    try:
                        confidence_values.append(
                            float(confidence)
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

                if match_type in {
                    "person_phone",
                    "public_person",
                }:
                    person_phones += 1
                elif match_type == "company_phone":
                    company_phones += 1

                phone_code = str(
                    row.get("phone_country_code")
                    or row.get("country_code")
                    or ""
                ).upper()

                if phone_code:
                    phone_item = (
                        phone_country_counts.setdefault(
                            phone_code,
                            {
                                "code": phone_code,
                                "name": (
                                    row.get(
                                        "phone_country_name"
                                    )
                                    or row.get(
                                        "country_name"
                                    )
                                ),
                                "flag": (
                                    row.get(
                                        "phone_country_flag"
                                    )
                                    or row.get(
                                        "country_flag"
                                    )
                                ),
                                "count": 0,
                            },
                        )
                    )

                    phone_item["count"] = (
                        int(phone_item["count"]) + 1
                    )

            if status != "PUBLIC_EMAIL":
                company_code = str(
                    row.get("country_code") or ""
                ).upper()

                if company_code:
                    company_item = (
                        business_country_counts.setdefault(
                            company_code,
                            {
                                "code": company_code,
                                "name": row.get(
                                    "country_name"
                                ),
                                "flag": row.get(
                                    "country_flag"
                                ),
                                "count": 0,
                            },
                        )
                    )

                    company_item["count"] = (
                        int(company_item["count"]) + 1
                    )

        emails_total = len(rows)

        public_email = counts["PUBLIC_EMAIL"]

        business_contacts = max(
            0,
            emails_total - public_email,
        )

        matched = counts["MATCHED"]
        partial = counts["PARTIAL_MATCH"]
        not_found = counts["NOT_FOUND"]
        failed = counts["FAILED"]
        pending = counts["NEW"]

        business_completed = (
            matched
            + partial
            + not_found
            + failed
        )

        processed_total = (
            emails_total - pending
        )

        success_rate = (
            round(
                (
                    phones_found
                    / business_contacts
                )
                * 100,
                2,
            )
            if business_contacts > 0
            else 0.0
        )

        completed_success_rate = (
            round(
                (
                    phones_found
                    / business_completed
                )
                * 100,
                2,
            )
            if business_completed > 0
            else 0.0
        )

        average_confidence = (
            round(
                sum(confidence_values)
                / len(confidence_values),
                2,
            )
            if confidence_values
            else 0.0
        )

        countries = sorted(
            business_country_counts.values(),
            key=lambda item: -int(
                item["count"]
            ),
        )

        phone_countries = sorted(
            phone_country_counts.values(),
            key=lambda item: -int(
                item["count"]
            ),
        )

        return {
            "emails_total": emails_total,
            "business_contacts": (
                business_contacts
            ),
            "public_email": public_email,
            "pending": pending,
            "matched": matched,
            "partial": partial,
            "not_found": not_found,
            "failed": failed,
            "completed": business_completed,
            "processed_total": processed_total,
            "phones_found": phones_found,
            "success_rate": success_rate,
            "business_success_rate": (
                success_rate
            ),
            "completed_success_rate": (
                completed_success_rate
            ),
            "average_confidence": (
                average_confidence
            ),
            "person_phones": person_phones,
            "company_phones": company_phones,
            "countries": countries,
            "countries_total": len(
                countries
            ),
            "phone_countries": (
                phone_countries
            ),
            "phone_countries_total": len(
                phone_countries
            ),
            "unknown_country": max(
                0,
                business_contacts
                - sum(
                    int(item["count"])
                    for item in countries
                ),
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load statistics: "
                f"{exc}"
            ),
        ) from exc