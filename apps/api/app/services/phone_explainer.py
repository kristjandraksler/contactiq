from __future__ import annotations

from collections.abc import Iterable

from .evidence_engine import build_evidence_summary
from .phone_models import PhoneCandidate


def apply_explanation(
    candidate: PhoneCandidate,
    *,
    sources: Iterable[str],
    page_labels: Iterable[str],
    context_signals: Iterable[str],
    occurrences: int,
    page_diversity: int,
    source_diversity: int,
    from_tel_link: bool,
    confidence: int,
) -> PhoneCandidate:
    summary = build_evidence_summary(
        sources=sources,
        page_labels=page_labels,
        context_signals=context_signals,
        occurrences=occurrences,
        page_diversity=page_diversity,
        source_diversity=source_diversity,
        from_tel_link=from_tel_link,
        confidence=confidence,
    )

    candidate.evidence = summary.evidence
    candidate.confidence = confidence
    candidate.confidence_label = summary.confidence_label
    candidate.evidence_strength = summary.evidence_strength
    candidate.strengths = summary.strengths
    candidate.warnings = summary.warnings
    return candidate
