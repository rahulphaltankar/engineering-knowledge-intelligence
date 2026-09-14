"""Context construction, traversal, provenance and confidence."""
from __future__ import annotations

import pytest

from appliance.core.context import EngineeringContext
from appliance.core.entities import EngineeringEntity, Relationship
from appliance.core.provenance import (Classification, Confidence, Provenance,
                                       score_confidence, weakest)


def _entity(eid: str, etype: str, **attrs) -> EngineeringEntity:
    return EngineeringEntity(
        id=eid, entity_type=etype, attributes=attrs,
        provenance=Provenance(connector_id="TEST", source_system="test",
                              source_object_id=eid))


# -- provenance is mandatory ----------------------------------------------
def test_entity_cannot_exist_without_provenance():
    with pytest.raises(Exception):
        EngineeringEntity(id="X-001", entity_type="System", attributes={})


def test_every_retrieved_record_carries_provenance(context):
    missing = [e.id for e in context.entities if e.provenance is None]
    assert not missing
    sample = context.entities[0]
    assert sample.provenance.connector_id == "SIMULATION"
    assert sample.provenance.source_object_id == sample.id


def test_simulated_data_classification_is_preserved(context):
    classifications = {e.provenance.data_classification for e in context.entities}
    assert any(c and "SIMULATED" in c for c in classifications), \
        "simulated data must remain labelled so the UI can never imply it is customer data"


# -- classification propagation -------------------------------------------
def test_weakest_classification_caps_derived_findings():
    assert weakest([Classification.FACT, Classification.INFERRED]) is Classification.INFERRED
    assert weakest([Classification.FACT, Classification.DERIVED]) is Classification.DERIVED
    assert weakest([]) is Classification.UNKNOWN


def test_confidence_is_deterministic_and_evidence_driven():
    a = score_confidence(evidence_count=3, independent_sources=2,
                         classification=Classification.DERIVED)
    b = score_confidence(evidence_count=3, independent_sources=2,
                         classification=Classification.DERIVED)
    assert a == b, "same inputs must always produce the same confidence"

    more, _ = score_confidence(evidence_count=5, independent_sources=3,
                               classification=Classification.DERIVED)
    less, _ = score_confidence(evidence_count=1, independent_sources=1,
                               classification=Classification.DERIVED)
    assert more != less


def test_unknown_classification_has_no_confidence():
    band, score = score_confidence(evidence_count=9, independent_sources=3,
                                   classification=Classification.UNKNOWN)
    assert band is Confidence.NONE and score == 0.0


def test_inferred_edge_lowers_confidence():
    _, with_edge = score_confidence(evidence_count=3, independent_sources=1,
                                    classification=Classification.DERIVED,
                                    involves_inferred_edge=True)
    _, without = score_confidence(evidence_count=3, independent_sources=1,
                                  classification=Classification.DERIVED)
    assert with_edge < without, "an inferred edge must reduce confidence"


# -- traversal -------------------------------------------------------------
def test_traversal_returns_a_justifying_path_for_every_record():
    ctx = EngineeringContext()
    for eid, etype in (("ECR-900", "EngineeringChange"), ("COMP-900", "Component"),
                       ("SUB-900", "Subsystem"), ("SYS-900", "System")):
        ctx.add_entity(_entity(eid, etype))
    ctx.add_relationship(Relationship(source_type="EngineeringChange", source_id="ECR-900",
                                      relationship="AFFECTS", target_type="Component",
                                      target_id="COMP-900"))
    ctx.add_relationship(Relationship(source_type="Subsystem", source_id="SUB-900",
                                      relationship="HAS_COMPONENT", target_type="Component",
                                      target_id="COMP-900"))
    paths = ctx.impact_closure("ECR-900", depth=2)
    assert "COMP-900" in paths and "SUB-900" in paths
    assert paths["COMP-900"] and "AFFECTS" in paths["COMP-900"][0]
    assert len(paths["SUB-900"]) == 2, "path length must reflect the number of hops"


def test_structural_completion_resolves_owning_system(analysis):
    """A requirement reached at the depth boundary must still resolve to the
    system it is allocated to, or cross-domain impact is under-reported."""
    ctx, closure = analysis["context"], analysis["closure"]
    systems = [e for e in closure if ctx.get(e) and ctx.get(e).entity_type == "System"]
    assert len(systems) >= 2, "cross-domain reach is the core capability"


def test_traversal_is_deterministic(service):
    a = service.analyse_scenario("SCN-001")
    b = service.analyse_scenario("SCN-001")
    assert a["context_snapshot_id"] == b["context_snapshot_id"]
    assert set(a["closure"]) == set(b["closure"])


def test_context_validation_detects_dangling_reference():
    ctx = EngineeringContext()
    ctx.add_entity(_entity("SYS-901", "System"))
    ctx.add_relationship(Relationship(source_type="System", source_id="SYS-901",
                                      relationship="HAS_SUBSYSTEM",
                                      target_type="Subsystem", target_id="SUB-NOPE"))
    problems = ctx.validate()
    assert any("SUB-NOPE" in p for p in problems)


def test_retrieved_context_has_no_dangling_references(context):
    assert context.validate() == []


# -- stale evidence --------------------------------------------------------
def test_passing_result_on_a_different_configuration_is_flagged(context):
    """Recognising that a green result does not apply is the harder task."""
    stale = [r for r in context.by_type("TestResult")
             if r.result_status == "pass" and context.is_stale(r)]
    assert stale, "the dataset deliberately contains non-transferable passing results"
