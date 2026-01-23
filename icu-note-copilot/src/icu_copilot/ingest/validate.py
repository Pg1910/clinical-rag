"""Data validation utilities"""
from __future__ import annotations

from typing import Iterable, Set

from .schemas import EvidenceRecord


def ensure_unique_ids(records: Iterable[EvidenceRecord]) -> None:
    seen: Set[str] = set()
    for r in records:
        if r.evidence_id in seen:
            raise ValueError(f"Duplicate evidence_id found: {r.evidence_id}")
        seen.add(r.evidence_id)
