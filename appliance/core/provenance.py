"""Provenance, classification and confidence.

This module is the credibility mechanism of the appliance. Every material finding
carries where it came from, how it was arrived at, and how much weight it
deserves.

Classification vocabulary
-------------------------
FACT      directly retrieved from a source system
DERIVED   computed deterministically from facts (graph traversal, set logic)
INFERRED  reasoned by a model from evidence
ASSUMED   the model supplied a premise not present in the context
UNKNOWN   the context does not contain the answer

The propagation rule matters more than the vocabulary: a finding can never be
classified more strongly than its weakest input. A conclusion built on an
INFERRED premise is not a FACT no matter how confident it sounds.
"""
from __future__ import annotations

import datetime as _dt
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel, Field


class Classification(str, Enum):
    FACT = "FACT"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    UNKNOWN = "UNKNOWN"


# Ordered weakest-last. Used for capping during propagation.
_STRENGTH = {
    Classification.FACT: 0,
    Classification.DERIVED: 1,
    Classification.INFERRED: 2,
    Classification.ASSUMED: 3,
    Classification.UNKNOWN: 4,
}


def weakest(classifications: Sequence[Classification]) -> Classification:
    """The weakest classification in a set - the cap for anything derived from it."""
    if not classifications:
        return Classification.UNKNOWN
    return max(classifications, key=lambda c: _STRENGTH[c])


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class Provenance(BaseModel):
    """Where a record came from. Mandatory on every entity and finding."""

    connector_id: str
    source_system: str
    source_object_id: str
    retrieved_at: str = Field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat())
    source_url: str | None = None
    source_version: str | None = None
    transformation: str | None = None
    data_classification: str | None = None
    licence: str | None = None

    def short(self) -> str:
        return f"{self.connector_id}:{self.source_object_id}"


class EvidenceRef(BaseModel):
    """A citation. `entity_id` must exist in the context or the gate removes it."""

    entity_id: str
    entity_type: str
    summary: str = ""
    path: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class Finding(BaseModel):
    """One material statement produced by the appliance.

    A Finding with no evidence and classification UNKNOWN is a legitimate and
    often valuable result - it records that something could not be established.
    """

    id: str
    statement: str
    classification: Classification = Classification.INFERRED
    confidence: Confidence = Confidence.LOW
    confidence_score: float = 0.0
    evidence: list[EvidenceRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    produced_by: list[str] = Field(default_factory=list)
    rationale: str = ""
    tags: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def evidence_ids(self) -> list[str]:
        return [e.entity_id for e in self.evidence]


def score_confidence(
    *,
    evidence_count: int,
    independent_sources: int,
    classification: Classification,
    agreeing_specialists: int = 1,
    involves_inferred_edge: bool = False,
    derivation_depth: int = 1,
) -> tuple[Confidence, float]:
    """Deterministic confidence from evidence properties.

    Deliberately NOT model self-reported confidence, which is poorly calibrated.
    The same inputs always produce the same score, which is what makes
    reproducibility and calibration measurement possible.
    """
    if classification is Classification.UNKNOWN:
        return Confidence.NONE, 0.0

    score = 0.0
    score += min(evidence_count, 5) * 0.10            # up to 0.50
    score += min(independent_sources, 3) * 0.08        # up to 0.24
    score += min(max(agreeing_specialists - 1, 0), 3) * 0.07  # up to 0.21

    if classification is Classification.FACT:
        score += 0.25
    elif classification is Classification.DERIVED:
        score += 0.18
    elif classification is Classification.ASSUMED:
        score -= 0.20

    if involves_inferred_edge:
        score -= 0.10
    score -= max(derivation_depth - 1, 0) * 0.05

    score = round(max(0.0, min(1.0, score)), 3)
    if score >= 0.70:
        band = Confidence.HIGH
    elif score >= 0.40:
        band = Confidence.MEDIUM
    elif score > 0.0:
        band = Confidence.LOW
    else:
        band = Confidence.NONE
    return band, score
