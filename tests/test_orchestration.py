"""Orchestration, specialist selection, synthesis and the evidence gate."""
from __future__ import annotations

from appliance.core.context import EngineeringContext
from appliance.core.entities import EngineeringEntity
from appliance.core.provenance import (Classification, EvidenceRef, Finding,
                                       Provenance)
from appliance.orchestrator.pipeline import INTENT_SPECIALISTS, OrchestrationPipeline
from appliance.orchestrator.synthesis import EvidenceGate, collect_unknowns, synthesise


def _finding(fid: str, statement: str, evidence_ids: list[str],
             classification=Classification.DERIVED, producer="A", tags=None) -> Finding:
    return Finding(id=fid, statement=statement, classification=classification,
                   evidence=[EvidenceRef(entity_id=e, entity_type="System")
                             for e in evidence_ids],
                   produced_by=[producer], tags=tags or [])


def _context_with(*ids: str) -> EngineeringContext:
    ctx = EngineeringContext()
    for eid in ids:
        ctx.add_entity(EngineeringEntity(
            id=eid, entity_type="System", attributes={"name": eid},
            provenance=Provenance(connector_id="TEST", source_system="t",
                                  source_object_id=eid)))
    return ctx


# -- pipeline --------------------------------------------------------------
def test_pipeline_runs_every_stage_in_order(analysis):
    names = [s["name"] for s in analysis["stages"]]
    assert names[0] == "Understanding change"
    assert "Planning required evidence" in names
    assert "Retrieving engineering context" in names
    assert "Synthesising across specialists" in names
    assert names[-1] == "Evidence sufficiency gate"
    assert all(s["status"] in ("done", "degraded") for s in analysis["stages"])


def test_intent_classification_selects_change_impact(analysis):
    assert analysis["intents"][0]["intent"] == "change_impact"


def test_specialist_selection_is_intent_driven(service):
    pipeline = OrchestrationPipeline(service.registry, service.provider, service.skills)
    selected = [k for k, _, _ in pipeline.select_specialists(["change_impact"])]
    assert set(selected) == set(INTENT_SPECIALISTS["change_impact"])
    narrow = [k for k, _, _ in pipeline.select_specialists(["risk_assessment"])]
    assert "evidence" not in narrow, "only relevant specialists should be invoked"


def test_every_specialist_produced_findings(analysis):
    for entry in analysis["activity"]:
        assert entry["status"] == "done", f"{entry['specialist']} failed"
    assert len(analysis["activity"]) >= 4


def test_specialists_carry_upstream_attribution(analysis):
    attributions = [a.get("attribution") for a in analysis["activity"]]
    assert any(a and "MIT" in a for a in attributions), \
        "reused upstream content must be attributed in the run record"


def test_evidence_ledger_records_connector_participation(analysis):
    ledger = analysis["evidence_ledger"]
    assert ledger["participation"], "which connectors answered is part of provenance"
    assert "SIMULATION" in ledger["participation"]


# -- synthesis -------------------------------------------------------------
def test_agreement_between_specialists_raises_confidence():
    one = _finding("F1", "Thermal system is impacted", ["SYS-002"], producer="A")
    two = _finding("F2", "Thermal system is impacted", ["SYS-004"], producer="B")
    merged, _ = synthesise([one, two])
    assert len(merged) == 1
    assert set(merged[0].produced_by) == {"A", "B"}
    assert len(merged[0].evidence) == 2, "evidence from both specialists is retained"


def test_synthesis_caps_classification_at_the_weakest_input():
    strong = _finding("F1", "Same claim", ["SYS-001"], Classification.FACT, "A")
    weak = _finding("F2", "Same claim", ["SYS-002"], Classification.INFERRED, "B")
    merged, _ = synthesise([strong, weak])
    assert merged[0].classification is Classification.INFERRED


# -- evidence gate ---------------------------------------------------------
def test_gate_detects_a_fabricated_citation():
    ctx = _context_with("SYS-001")
    gate = EvidenceGate(ctx)
    gate.apply([_finding("F1", "Claim", ["SYS-001", "SYS-DOESNOTEXIST"])])
    assert "SYS-DOESNOTEXIST" in gate.report()["fabricated_citations"]


def test_gate_strips_unverifiable_evidence_but_keeps_verified():
    ctx = _context_with("SYS-001")
    kept = EvidenceGate(ctx).apply([_finding("F1", "Claim", ["SYS-001", "SYS-FAKE"])])
    assert [e.entity_id for e in kept[0].evidence] == ["SYS-001"]


def test_gate_downgrades_a_claim_with_no_verifiable_evidence():
    ctx = _context_with("SYS-001")
    gate = EvidenceGate(ctx)
    kept = gate.apply([_finding("F1", "Unsupported claim", ["SYS-FAKE"])])
    assert kept[0].classification is Classification.ASSUMED
    assert kept[0].assumptions, "the assumption must be stated, not silently accepted"
    assert gate.report()["downgraded"]


def test_gate_removes_unsupported_model_interpretation():
    ctx = _context_with("SYS-001")
    gate = EvidenceGate(ctx)
    kept = gate.apply([_finding("F1", "Speculation", ["SYS-FAKE"],
                                tags=["model_interpretation"])])
    assert kept == []
    assert gate.report()["removed"]


def test_gate_catches_fabricated_ids_mentioned_only_in_prose():
    ctx = _context_with("SYS-001")
    gate = EvidenceGate(ctx)
    gate.apply([_finding("F1", "This relates to REQ-999 as well", ["SYS-001"])])
    assert "REQ-999" in gate.report()["fabricated_citations"]


def test_real_analysis_produces_no_fabricated_citations(analysis):
    assert analysis["gate_report"]["fabricated_citation_count"] == 0


def test_every_cited_entity_exists_in_context(analysis):
    ctx = analysis["context"]
    for finding in analysis["findings"]:
        for ref in finding.evidence:
            assert ctx.has(ref.entity_id), f"{finding.id} cites missing {ref.entity_id}"


# -- unknown handling ------------------------------------------------------
def test_unknowns_are_collected_and_surfaced():
    unknown = Finding(id="U1", statement="Criterion not established",
                      classification=Classification.UNKNOWN,
                      unknowns=["TEST-004 has no acceptance criterion"])
    assert collect_unknowns([unknown])


def test_analysis_reports_deliberate_unknowns(analysis):
    """The dataset contains tests with no established acceptance criterion.
    An appliance that reports zero unknowns here is not reading them."""
    assert analysis["unknowns"], "deliberate unknowns must survive to the result"
    joined = " ".join(analysis["unknowns"]).lower()
    assert "acceptance criterion" in joined


def test_missing_subject_yields_insufficient_evidence_not_an_error(service):
    result = service.analyse("assess the impact of this change", "ECR-DOES-NOT-EXIST")
    assert result["status"] == "insufficient_evidence"
    assert result["findings"] == []
    assert result["unknowns"], "the reason must be stated"
