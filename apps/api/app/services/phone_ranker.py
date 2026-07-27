from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from urllib.parse import urlparse

from .phone_confidence import calculate_confidence
from .phone_explainer import apply_explanation
from .phone_models import PhoneCandidate
from .phone_parser import ExtractedPhone


def page_label(url: str) -> str:
    path = (urlparse(url).path or "/").lower().rstrip("/") or "/"
    if "kontakt" in path or "contact" in path:
        return "contact_page"
    if "impressum" in path or "imprint" in path:
        return "imprint_page"
    if "about" in path or "o-nas" in path or "o-podjetju" in path:
        return "about_page"
    if path == "/":
        return "homepage"
    return "other_page"


def rank_candidates(rows: list[tuple[ExtractedPhone, str]]) -> list[PhoneCandidate]:
    scores: dict[str, int] = defaultdict(int)
    occurrences: dict[str, int] = defaultdict(int)
    tel_links: dict[str, bool] = defaultdict(bool)
    sources: dict[str, set[str]] = defaultdict(set)
    pages: dict[str, set[str]] = defaultdict(set)
    page_labels: dict[str, set[str]] = defaultdict(set)
    context_signals: dict[str, set[str]] = defaultdict(set)
    best_source_url: dict[str, str] = {}
    best_source: dict[str, str] = {}
    best_single_score: dict[str, int] = defaultdict(int)

    for extracted, source_url in rows:
        phone = extracted.phone
        scores[phone] += extracted.score
        occurrences[phone] += 1
        tel_links[phone] = tel_links[phone] or extracted.from_tel_link
        sources[phone].add(extracted.source)
        pages[phone].add(source_url)
        page_labels[phone].add(page_label(source_url))
        context_signals[phone].update(extracted.context_signals)

        if extracted.score > best_single_score[phone]:
            best_single_score[phone] = extracted.score
            best_source_url[phone] = source_url
            best_source[phone] = extracted.source

    ranked: list[PhoneCandidate] = []

    for phone, raw_score in scores.items():
        occurrence_bonus = min(max(occurrences[phone] - 1, 0) * 5, 20)
        diversity_bonus = {1: 0, 2: 20, 3: 38, 4: 52, 5: 62}.get(len(sources[phone]), 70)
        page_bonus = min(max(len(pages[phone]) - 1, 0) * 12, 36)

        labels = page_labels[phone]
        cross_page_bonus = 0
        if "homepage" in labels and "contact_page" in labels:
            cross_page_bonus = 25
        elif "contact_page" in labels and len(pages[phone]) >= 2:
            cross_page_bonus = 15

        candidate = PhoneCandidate(
            phone=phone,
            score=raw_score + occurrence_bonus + diversity_bonus + page_bonus + cross_page_bonus,
            source_url=best_source_url[phone],
            source=best_source[phone],
            occurrences=occurrences[phone],
            from_tel_link=tel_links[phone],
            source_diversity=len(sources[phone]),
            page_diversity=len(pages[phone]),
            evidence=[],
            strengths=[],
            warnings=[],
        )

        provisional_evidence = (
            [f"source:{source}" for source in sorted(sources[phone])]
            + [f"page:{label}" for label in sorted(labels)]
            + sorted(context_signals[phone])
        )
        provisional_candidate = PhoneCandidate(**{**asdict(candidate), "evidence": provisional_evidence})
        confidence = calculate_confidence(provisional_candidate)
        candidate = apply_explanation(
            candidate,
            sources=sources[phone],
            page_labels=labels,
            context_signals=context_signals[phone],
            occurrences=occurrences[phone],
            page_diversity=len(pages[phone]),
            source_diversity=len(sources[phone]),
            from_tel_link=tel_links[phone],
            confidence=confidence,
        )
        ranked.append(candidate)

    return sorted(
        ranked,
        key=lambda candidate: (
            candidate.score,
            candidate.evidence_strength,
            candidate.source_diversity,
            candidate.page_diversity,
            candidate.source == "schema_org",
            candidate.from_tel_link,
            candidate.occurrences,
        ),
        reverse=True,
    )
