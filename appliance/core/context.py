"""The common engineering context and its traversal primitives.

This is where the product's differentiating capability actually lives. Everything
here is deterministic: the same context and the same query always return the same
records, by the same paths. That is what makes evaluation, regression testing and
audit possible, and it is why a large part of the appliance's reasoning needs no
model at all.

The traversal algorithms are ported from the simulation repository's
`connector_sim.py`, which already returns the path to every reached record.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Iterable

from .entities import EngineeringEntity, Relationship
from .provenance import Classification, EvidenceRef


class ContextConflict:
    """Two sources disagreeing about one logical entity.

    Reported, never silently resolved: only the customer knows which system is
    authoritative for which field.
    """

    def __init__(self, entity_id: str, field: str, a: object, b: object,
                 source_a: str, source_b: str):
        self.entity_id, self.field = entity_id, field
        self.value_a, self.value_b = a, b
        self.source_a, self.source_b = source_a, source_b

    def as_dict(self) -> dict:
        return {"entity_id": self.entity_id, "field": self.field,
                "value_a": self.value_a, "value_b": self.value_b,
                "source_a": self.source_a, "source_b": self.source_b}


class EngineeringContext:
    """Everything retrieved for one request, indexed for traversal."""

    def __init__(self) -> None:
        self._entities: dict[str, EngineeringEntity] = {}
        self._by_type: dict[str, list[EngineeringEntity]] = defaultdict(list)
        self._out: dict[str, list[Relationship]] = defaultdict(list)
        self._in: dict[str, list[Relationship]] = defaultdict(list)
        self._edges: set[tuple] = set()
        self.conflicts: list[ContextConflict] = []
        self.retrieval_reason: dict[str, str] = {}
        self.truncated: list[str] = []
        # The design basis the analysis is conducted on, and the bases it
        # supersedes. Set from the subject record when that record declares
        # them; unset, transferability falls back to explicit flags and notes.
        self.current_basis: str | None = None
        self.superseded_basis: set[str] = set()

    # -- population --------------------------------------------------------
    def add_entity(self, entity: EngineeringEntity, reason: str = "retrieved") -> None:
        existing = self._entities.get(entity.id)
        if existing is not None:
            if existing.provenance.connector_id != entity.provenance.connector_id:
                for field, value in entity.attributes.items():
                    other = existing.attributes.get(field)
                    if other is not None and other != value:
                        self.conflicts.append(ContextConflict(
                            entity.id, field, other, value,
                            existing.provenance.connector_id,
                            entity.provenance.connector_id))
            return
        self._entities[entity.id] = entity
        self._by_type[entity.entity_type].append(entity)
        self.retrieval_reason.setdefault(entity.id, reason)

    def add_relationship(self, rel: Relationship) -> None:
        key = rel.key()
        if key in self._edges:
            return
        self._edges.add(key)
        self._out[rel.source_id].append(rel)
        self._in[rel.target_id].append(rel)

    # -- access ------------------------------------------------------------
    def get(self, entity_id: str) -> EngineeringEntity | None:
        return self._entities.get(entity_id)

    def has(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def by_type(self, entity_type: str) -> list[EngineeringEntity]:
        return list(self._by_type.get(entity_type, []))

    def types_present(self) -> dict[str, int]:
        return {k: len(v) for k, v in sorted(self._by_type.items()) if v}

    @property
    def entities(self) -> list[EngineeringEntity]:
        return list(self._entities.values())

    @property
    def relationships(self) -> list[Relationship]:
        seen, out = set(), []
        for rels in self._out.values():
            for r in rels:
                if r.key() not in seen:
                    seen.add(r.key())
                    out.append(r)
        return out

    def __len__(self) -> int:
        return len(self._entities)

    # -- identity ----------------------------------------------------------
    def snapshot_id(self) -> str:
        """Stable hash of content. Identical retrieval yields an identical id."""
        digest = hashlib.sha256()
        for eid in sorted(self._entities):
            digest.update(eid.encode())
            digest.update(self._entities[eid].provenance.source_object_id.encode())
        for key in sorted(str(k) for k in self._edges):
            digest.update(key.encode())
        return digest.hexdigest()[:16]

    # -- traversal ---------------------------------------------------------
    def neighbours(self, entity_id: str) -> list[tuple[Relationship, str, str]]:
        """(relationship, neighbour_id, direction) for one record."""
        out = [(r, r.target_id, "out") for r in self._out.get(entity_id, [])]
        out += [(r, r.source_id, "in") for r in self._in.get(entity_id, [])]
        return out

    def impact_closure(self, origin_id: str, depth: int = 2,
                       follow: Iterable[str] | None = None,
                       max_records: int = 2000) -> dict[str, list[str]]:
        """Breadth-first traversal returning {entity_id: justifying path}.

        The primitive underneath change impact, traceability and regression
        analysis. Every reached record carries the path by which it was reached,
        so any downstream claim can be justified.
        """
        follow_set = set(follow) if follow else None
        paths: dict[str, list[str]] = {origin_id: []}
        queue = deque([(origin_id, 0)])
        while queue:
            current, level = queue.popleft()
            if level >= depth:
                continue
            for rel, nxt, direction in self.neighbours(current):
                if follow_set and rel.relationship not in follow_set:
                    continue
                if nxt in paths:
                    continue
                if len(paths) >= max_records:
                    self.truncated.append(
                        f"traversal from {origin_id} truncated at {max_records} records")
                    return paths
                arrow = "->" if direction == "out" else "<-"
                paths[nxt] = paths[current] + [f"{current} {arrow}{rel.relationship}{arrow} {nxt}"]
                queue.append((nxt, level + 1))
        return paths

    # Structural ownership edges. Resolving the system a reached requirement
    # belongs to is not an extra hop of reasoning - it is an attribute of the
    # requirement. Without this, entities discovered at the depth boundary have
    # no structural home and cross-domain impact is under-reported.
    # A test's result is an attribute of the test, not a further hop of
    # reasoning - the evidence specialist reads it either way, so excluding it
    # from the closure made the scope under-report what the analysis touched.
    _STRUCTURAL_OUT = {"ALLOCATED_TO", "PRODUCES"}
    _STRUCTURAL_IN = {"HAS_SUBSYSTEM", "HAS_COMPONENT", "CONTAINS", "COVERS"}
    _STRUCTURAL_TARGETS = {"System", "Subsystem", "FMEA", "TestResult"}

    def structural_completion(self, paths: dict[str, list[str]]) -> dict[str, list[str]]:
        """Add the structural owners of everything already reached.

        Applied after impact_closure so that a requirement reached at the depth
        boundary still resolves to the system it is allocated to.
        """
        added: dict[str, list[str]] = {}
        for entity_id in list(paths):
            for rel, neighbour, direction in self.neighbours(entity_id):
                if neighbour in paths or neighbour in added:
                    continue
                if direction == "out" and rel.relationship in self._STRUCTURAL_OUT:
                    ok = rel.target_type in self._STRUCTURAL_TARGETS
                elif direction == "in" and rel.relationship in self._STRUCTURAL_IN:
                    ok = rel.source_type in self._STRUCTURAL_TARGETS
                else:
                    ok = False
                if not ok or not self.has(neighbour):
                    continue
                arrow = "->" if direction == "out" else "<-"
                added[neighbour] = paths[entity_id] + [
                    f"{entity_id} {arrow}{rel.relationship}{arrow} {neighbour}"]
        paths.update(added)
        return paths

    def trace_path(self, source_id: str, target_id: str,
                   max_depth: int = 5) -> list[str] | None:
        """Shortest justifying path between two records, or None."""
        paths = self.impact_closure(source_id, depth=max_depth)
        return paths.get(target_id)

    # -- evidence ----------------------------------------------------------
    def tests_for_requirement(self, requirement_id: str) -> list[EngineeringEntity]:
        return [t for t in self.by_type("TestCase")
                if requirement_id in (t.get("verifies_requirements") or [])]

    def results_for_test(self, test_id: str) -> list[EngineeringEntity]:
        return [r for r in self.by_type("TestResult") if r.get("test_id") == test_id]

    def evidence_for_requirement(self, requirement_id: str) -> dict:
        """Every test, result and gap bearing on one requirement.

        Gaps are enumerated explicitly rather than left as an absence, because an
        absence is indistinguishable from "nothing to report" downstream.
        """
        rows, gaps = [], []
        for test in self.tests_for_requirement(requirement_id):
            results = self.results_for_test(test.id)
            if not results:
                gaps.append({"requirement_id": requirement_id, "test_id": test.id,
                             "test_title": test.title, "result_id": None,
                             "gap_type": "no_result_recorded",
                             "reason": "Test defined but no result is present in context."})
                continue
            for res in results:
                stale = self.is_stale(res)
                row = {"requirement_id": requirement_id, "test_id": test.id,
                       "test_title": test.title, "result_id": res.id,
                       "status": res.result_status,
                       "configuration_id": res.get("configuration_id"),
                       "basis": res.get("basis"),
                       "acceptance_criterion": test.acceptance_criterion,
                       "criterion_established": test.acceptance_criterion_established,
                       "notes": res.get("notes") or "",
                       "deviation": res.get("deviation"),
                       "non_transferable": stale}
                rows.append(row)
                # An unestablished acceptance criterion is a gap in its own right,
                # independent of the result status. Nesting it under an elif chain
                # hides the single most important gap class the appliance detects.
                if not test.acceptance_criterion_established:
                    gaps.append({**row, "gap_type": "criterion_not_established",
                                 "reason": "Acceptance criterion is not established for "
                                           "this test; the result cannot be judged and no "
                                           "threshold may be assumed."})
                if res.result_status == "not_run":
                    gaps.append({**row, "gap_type": "test_not_run",
                                 "reason": "No evidence exists - the test has not been executed."})
                elif res.result_status == "inconclusive":
                    gaps.append({**row, "gap_type": "inconclusive",
                                 "reason": row["deviation"] or "Result cannot be judged."})
                elif stale and res.result_status == "pass":
                    gaps.append({**row, "gap_type": "evidence_not_transferable",
                                 "reason": self.transferability_reason(res) or
                                           row["notes"] or
                                           "Passing result was obtained on a configuration "
                                           "that does not represent the case under analysis."})
        return {"requirement_id": requirement_id, "rows": rows, "gaps": gaps}

    # -- transferability -----------------------------------------------------
    def set_evidence_basis(self, current: str | None,
                           superseded: list[str] | set[str] | None) -> None:
        """Declare the basis under analysis and the bases it replaces.

        Domain-neutral: a basis may be a build configuration, an occupancy, an
        operating envelope. Evidence obtained on a superseded basis does not
        cover the case under analysis however green it is.
        """
        self.current_basis = current
        self.superseded_basis = {b for b in (superseded or []) if b and b != current}

    def transferability_reason(self, record: EngineeringEntity) -> str | None:
        basis = record.get("basis")
        if basis and basis in self.superseded_basis:
            return (f"Obtained on the '{basis}' basis; the change under analysis "
                    f"establishes the '{self.current_basis}' basis, so this evidence "
                    f"does not transfer.")
        return None

    def is_stale(self, result: EngineeringEntity) -> bool:
        """Does a passing result actually cover the case under analysis?

        Recognising that a green result does not apply is a harder and more
        valuable reasoning task than noticing a red one. The simulation dataset
        deliberately contains six such cases.

        Checked in order: a declared basis the analysis supersedes, an explicit
        transferable flag on the record, then the free-text markers the
        automotive simulation dataset uses.
        """
        if self.transferability_reason(result):
            return True
        if result.get("transferable") is False:
            return True
        note = (result.get("notes") or "").lower()
        if not note:
            return False
        markers = ("not representative", "not transferable", "superseded",
                   "does not clear", "not the failing", "incumbent",
                   "measured on the current", "not yet repeated",
                   "not the reduced loading", "before the proposed")
        return any(m in note for m in markers)

    # -- evidence refs -----------------------------------------------------
    def evidence_ref(self, entity_id: str, path: list[str] | None = None) -> EvidenceRef | None:
        entity = self.get(entity_id)
        if entity is None:
            return None
        return EvidenceRef(entity_id=entity.id, entity_type=entity.entity_type,
                           summary=entity.summary, path=path or [],
                           provenance=entity.provenance)

    # -- validation --------------------------------------------------------
    def validate(self) -> list[str]:
        """Reference integrity. A dangling reference reaching an agent becomes an
        invented fact, so it is far cheaper to catch here."""
        problems = []
        for rel in self.relationships:
            if rel.source_id not in self._entities:
                problems.append(f"relationship source missing: {rel.source_id}")
            if rel.target_id not in self._entities:
                problems.append(f"relationship target missing: {rel.target_id}")
        for entity in self._entities.values():
            if entity.provenance is None:  # pragma: no cover - model enforces
                problems.append(f"entity without provenance: {entity.id}")
        return problems
