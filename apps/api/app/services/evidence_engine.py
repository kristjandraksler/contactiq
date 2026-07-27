from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SOURCE_STRENGTH = {
    "schema_org": 5,
    "microdata": 5,
    "tel_link": 5,
    "footer": 3,
    "visible_text": 2,
}

PAGE_STRENGTH = {
    "contact_page": 5,
    "imprint_page": 4,
    "about_page": 3,
    "homepage": 3,
    "other_page": 1,
}


@dataclass(frozen=True)
class EvidenceSummary:
    evidence: list[str]
    strengths: list[str]
    warnings: list[str]
    evidence_strength: int
    confidence_label: str


def confidence_label(confidence: int | None) -> str:
    if confidence is None:
        return "UNKNOWN"
    if confidence >= 90:
        return "VERY_HIGH"
    if confidence >= 75:
        return "HIGH"
    if confidence >= 50:
        return "MEDIUM"
    return "LOW"


def build_evidence_summary(
    *,
    sources: Iterable[str],
    page_labels: Iterable[str],
    context_signals: Iterable[str],
    occurrences: int,
    page_diversity: int,
    source_diversity: int,
    from_tel_link: bool,
    confidence: int | None = None,
) -> EvidenceSummary:
    source_set = set(sources)
    page_set = set(page_labels)
    signal_set = set(context_signals)

    evidence: list[str] = []
    strengths: list[str] = []
    warnings: list[str] = []

    for source in sorted(source_set):
        evidence.append(f"source:{source}")

    for page_label in sorted(page_set):
        evidence.append(f"page:{page_label}")

    evidence.extend(sorted(signal_set))

    if page_diversity >= 2:
        evidence.append(f"repeated_on_{page_diversity}_pages")
        strengths.append("Repeated on multiple pages")

    if source_diversity >= 2:
        evidence.append(f"source_diversity:{source_diversity}")
        strengths.append("Confirmed by multiple source types")

    if "schema_org" in source_set:
        strengths.append("Published in schema.org structured data")

    if "microdata" in source_set:
        strengths.append("Published in telephone metadata")

    if "tel_link" in source_set or from_tel_link:
        strengths.append("Published as a clickable telephone link")

    if "contact_page" in page_set:
        strengths.append("Found on a contact page")

    if "imprint_page" in page_set:
        strengths.append("Found on an imprint page")

    if any(
        signal.startswith("positive_context:")
        for signal in signal_set
    ):
        strengths.append("Found near a telephone or contact keyword")

    negative_signals = sorted(
        signal
        for signal in signal_set
        if signal.startswith("negative_context:")
    )
    for signal in negative_signals:
        warnings.append(
            f"Negative context detected: {signal.split(':', 1)[1]}"
        )

    if source_set == {"visible_text"}:
        warnings.append("Found only in visible page text")

    if page_diversity == 1:
        warnings.append("Found on only one page")

    if occurrences == 1:
        warnings.append("Found only once")

    evidence_strength = 0
    evidence_strength += max(
        (SOURCE_STRENGTH.get(source, 1) for source in source_set),
        default=0,
    )
    evidence_strength += max(
        (PAGE_STRENGTH.get(label, 0) for label in page_set),
        default=0,
    )
    evidence_strength += min(source_diversity - 1, 3) * 2
    evidence_strength += min(page_diversity - 1, 3) * 2

    if any(
        signal.startswith("positive_context:")
        for signal in signal_set
    ):
        evidence_strength += 2

    if negative_signals:
        evidence_strength -= 3

    evidence_strength = max(0, min(evidence_strength, 20))

    return EvidenceSummary(
        evidence=evidence,
        strengths=list(dict.fromkeys(strengths)),
        warnings=list(dict.fromkeys(warnings)),
        evidence_strength=evidence_strength,
        confidence_label=confidence_label(confidence),
    )
