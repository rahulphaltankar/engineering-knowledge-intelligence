"""The three demonstration workflows, and the acceptance-criterion protection
that matters more than any of them."""
from __future__ import annotations

import pytest

from appliance.core.errors import WorkflowError

WORKFLOWS = ("engineering_impact_assessment", "dvpr", "evidence_gap_analysis")


@pytest.fixture(scope="module")
def outputs(service):
    # generate() works from the CURRENT session, and other modules mutate it.
    # Re-analysing here makes this module independent of test ordering.
    service.analyse_scenario("SCN-001")
    return {wid: service.generate(wid) for wid in WORKFLOWS}


# -- all three are real ----------------------------------------------------
@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_workflow_generates_populated_output(outputs, workflow_id):
    output = outputs[workflow_id]
    assert output.sections
    populated = [s for s in output.sections if not s.is_empty]
    assert populated, f"{workflow_id} produced nothing"


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_workflow_validation_passes_with_no_blocking_failures(outputs, workflow_id):
    validation = outputs[workflow_id].validation
    assert validation["passed"], validation["blocking_failures"]


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_empty_sections_state_a_reason(outputs, workflow_id):
    for section in outputs[workflow_id].sections:
        if section.is_empty:
            assert section.empty_reason, f"{section.key} is empty with no explanation"


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_workflow_carries_provenance(outputs, workflow_id):
    provenance = outputs[workflow_id].provenance
    assert provenance["connectors"] == ["SIMULATION"]
    assert provenance["context_snapshot_id"]
    assert provenance["context_records"] > 0
    assert "SIMULATED" in (provenance["data_classification"] or "")


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_no_fabricated_ids_in_any_output(outputs, workflow_id, context):
    for section in outputs[workflow_id].sections:
        for entity_id in section.evidence_ids:
            assert context.has(entity_id), f"{workflow_id}/{section.key}: {entity_id}"


def test_outputs_share_one_reasoning_context(outputs):
    """An Impact Assessment and a DVP&R generated from one analysis must be
    mutually consistent, which requires the same context snapshot."""
    snapshots = {o.provenance["context_snapshot_id"] for o in outputs.values()}
    assert len(snapshots) == 1


# -- the behaviour that matters most --------------------------------------
def test_dvpr_never_invents_an_acceptance_criterion(outputs):
    table = next(s for s in outputs["dvpr"].sections if s.key == "dvpr")
    unestablished = [r for r in table.rows if not r["criterion_established"]]
    assert unestablished, "the dataset contains tests with no established criterion"
    for row in unestablished:
        assert "REQUIRES PROGRAMME SPECIFICATION" in row["acceptance_criterion"], \
            f"{row['test']}: a threshold was synthesised"


def test_dvpr_validation_rule_blocks_invented_criteria(outputs):
    rule = next(r for r in outputs["dvpr"].validation["rules"]
                if r["rule"] == "no_invented_acceptance_criteria")
    assert rule["passed"]


def test_dvpr_rows_link_to_a_requirement(outputs):
    table = next(s for s in outputs["dvpr"].sections if s.key == "dvpr")
    assert table.rows
    for row in table.rows:
        assert row["requirement"], "a DVP&R row with no requirement linkage is a defect"


def test_dvpr_distinguishes_transferable_from_stale_evidence(outputs):
    table = next(s for s in outputs["dvpr"].sections if s.key == "dvpr")
    actions = {r["action"] for r in table.rows}
    assert any("RE-RUN - existing pass does not cover this case" in a for a in actions), \
        "a passing result on a superseded configuration must not count as coverage"


def test_evidence_gaps_are_categorised_not_merely_counted(outputs):
    gaps = next(s for s in outputs["evidence_gap_analysis"].sections if s.key == "gaps")
    types = {r["gap_type"] for r in gaps.rows}
    assert "criterion_not_established" in types
    assert len(types) >= 3, f"only found {types}"


def test_impact_assessment_reports_cross_domain_reach(outputs):
    systems = next(s for s in outputs["engineering_impact_assessment"].sections
                   if s.key == "impacted_systems")
    assert len(systems.rows) >= 2
    assert any(r["route"] == "cross-domain" for r in systems.rows)
    for row in systems.rows:
        assert row["path"], "every impacted system must carry its justifying path"


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_every_output_declares_unknowns(outputs, workflow_id):
    unknowns = next(s for s in outputs[workflow_id].sections if s.key == "unknowns")
    assert unknowns.items, "unknowns must be surfaced, not buried"


# -- guards ----------------------------------------------------------------
def test_generating_before_analysis_is_refused(service):
    service.reset()
    try:
        with pytest.raises(WorkflowError):
            service.generate("dvpr")
    finally:
        service.analyse_scenario("SCN-001")   # restore shared session state


def test_unknown_workflow_is_refused(service):
    service.analyse_scenario("SCN-001")
    with pytest.raises(WorkflowError):
        service.generate("not_a_workflow")


def test_output_catalogue_reports_availability_with_a_reason(service):
    service.reset()
    try:
        for row in service.output_catalogue():
            if not row["available"]:
                assert row["missing_context"] or not row["implemented"]
    finally:
        service.analyse_scenario("SCN-001")
