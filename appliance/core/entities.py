"""Canonical engineering entities and relationships.

v0.1 design note
----------------
The canonical model is a single `EngineeringEntity` carrying `entity_type`,
`id`, `attributes` and mandatory `provenance`, plus typed accessors for the
fields the workflows actually consume.

Twenty-five separate Pydantic classes would be the fuller expression of the canonical model,
but it would also be brittle against a connector that supplies partial records -
which every real connector does. The attribute bag preserves everything the
source gave us, and the accessors give the workflows the typed reads they need.
This is a deliberate v0.1 simplification, recorded rather than hidden.

The entity-type vocabulary and the relationship vocabulary are adopted verbatim
from the simulation repository's schemas, which are already validated against 956
records and 2,018 edges.
"""
from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, Field

from .provenance import Classification, Provenance

ENTITY_TYPES = (
    "Programme", "Vehicle", "Configuration", "System", "Subsystem", "Component",
    "Supplier", "Requirement", "EngineeringChange", "FMEA", "FailureMode", "Risk",
    "TestCase", "TestResult", "VVActivity", "QualityIssue", "NCR", "RootCause",
    "CorrectiveAction", "SupplierIssue", "Evidence", "Document", "Standard",
    "Signal", "Measurement",
)

# Adopted from the simulation relationship schema (29 types).
RELATIONSHIP_TYPES = (
    "HAS_VEHICLE", "HAS_CONFIGURATION", "APPLIES_TO", "HAS_SUBSYSTEM",
    "HAS_COMPONENT", "PROVIDES", "ALLOCATED_TO", "DERIVED_FROM", "AFFECTS",
    "RAISED_AGAINST", "COVERS", "CONTAINS", "HAS_FAILURE_MODE", "CREATES",
    "VERIFIED_BY", "PRODUCES", "EXECUTED_ON", "RELATES_TO", "INCLUDES",
    "ASSOCIATED_WITH", "RAISED_FOR", "CAUSED_BY", "ADDRESSED_BY", "HAS_ISSUE",
    "DESCRIBES", "MEASURES", "EVIDENCES", "SUPPORTS", "EXPOSES",
)


class EngineeringEntity(BaseModel):
    """One canonical engineering record. Provenance is mandatory at construction."""

    id: str
    entity_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    classification: Classification = Classification.FACT

    # -- typed reads -------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    @property
    def title(self) -> str:
        for key in ("title", "name", "statement", "failure_mode", "identifier", "path"):
            value = self.attributes.get(key)
            if value:
                return str(value)
        return self.id

    @property
    def summary(self) -> str:
        text = self.title
        return text if len(text) <= 160 else text[:157] + "..."

    # Requirement
    @property
    def is_approved(self) -> bool:
        return self.attributes.get("status") == "approved"

    # TestCase
    @property
    def acceptance_criterion(self) -> str | None:
        return self.attributes.get("acceptance_criterion")

    @property
    def acceptance_criterion_established(self) -> bool:
        # Absent flag defaults to False: unknown-by-default is the safe direction.
        return bool(self.attributes.get("acceptance_criterion_established", False))

    # TestResult
    @property
    def result_status(self) -> str | None:
        return self.attributes.get("status")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.entity_type} {self.id}>"


class Relationship(BaseModel):
    """A directed, typed edge. Inferred edges are marked so confidence can discount them."""

    source_type: str
    source_id: str
    relationship: str
    target_type: str
    target_id: str
    note: str | None = None

    @property
    def inferred(self) -> bool:
        return bool(self.note and "inferred" in self.note.lower())

    def key(self) -> tuple:
        return (self.source_type, self.source_id, self.relationship,
                self.target_type, self.target_id)


def entity_types_present(entities: Iterable[EngineeringEntity]) -> set[str]:
    return {e.entity_type for e in entities}
