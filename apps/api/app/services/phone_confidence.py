from __future__ import annotations

from .phone_models import PhoneCandidate


def calculate_confidence(candidate: PhoneCandidate) -> int:
    source_base = {
        "schema_org": 80,
        "microdata": 78,
        "tel_link": 76,
        "footer": 58,
        "visible_text": 48,
    }

    confidence = source_base.get(candidate.source, 45)
    confidence += min(max(candidate.source_diversity - 1, 0) * 7, 21)
    confidence += min(max(candidate.page_diversity - 1, 0) * 5, 15)

    if candidate.occurrences >= 2:
        confidence += 3
    if candidate.from_tel_link and candidate.source != "tel_link":
        confidence += 3
    if any(item.startswith("positive_context:") for item in candidate.evidence):
        confidence += 4
    if any(item.startswith("negative_context:") for item in candidate.evidence):
        confidence -= 18
    if "page:contact_page" in candidate.evidence:
        confidence += 5

    return max(1, min(confidence, 99))
