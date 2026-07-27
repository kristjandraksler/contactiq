from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PhoneCandidate:
    phone: str
    score: int
    source_url: str
    source: str
    occurrences: int
    from_tel_link: bool
    source_diversity: int
    page_diversity: int
    evidence: list[str]
    confidence: int | None = None
    confidence_label: str = "UNKNOWN"
    evidence_strength: int = 0
    strengths: list[str] | None = None
    warnings: list[str] | None = None


@dataclass
class FinderResult:
    status: str
    website: str | None
    phone: str | None
    confidence: int | None
    source_url: str | None
    pages_scanned: int
    scan_duration_ms: int
    candidates: list[dict[str, Any]]
    error: str | None = None
    confidence_label: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
