"""The two experiences: architecture (what the product IS) and intelligence
(what the product DOES), plus the 25-output capability model.

The theme running through these tests is honesty. The interface is allowed to
communicate the intended architecture; it is not allowed to imply that anything
unbuilt is working, or to offer an output it cannot actually produce.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from appliance import architecture as arch_model
from appliance.workflows.catalogue import OUTPUT_CATALOGUE, resolve_status


@pytest.fixture(scope="module")
def client():
    from appliance.api.app import app
    return TestClient(app)


# ==========================================================================
# Architecture model
# ==========================================================================
def test_architecture_status_is_verified_against_modules_on_disk():
    """A component cannot silently claim IMPLEMENTED after its code is removed."""
    assert arch_model.verify() == []


def test_every_implemented_component_names_its_module():
    for _, layer, components in arch_model.LAYERS:
        for name, status, module, _note in components:
            if status == arch_model.IMPLEMENTED:
                assert module, f"{layer}/{name} claims IMPLEMENTED with no module"


def test_architecture_covers_all_six_layers(service):
    layers = service.architecture()["layers"]
    assert len(layers) == 6
    names = " ".join(l["name"] for l in layers)
    for expected in ("Connector Framework", "Data and Context",
                     "Intelligence and Agent Orchestration",
                     "Analytics and Inference", "Security and Governance", "Chat"):
        assert expected in names


def test_architecture_declares_unbuilt_components_as_planned(service):
    summary = service.architecture()["summary"]
    assert summary["PLANNED"] > 0, \
        "an architecture with nothing planned is either finished or dishonest"
    assert summary["IMPLEMENTED"] > summary["PLANNED"]


def test_chat_is_declared_planned_not_implemented(service):
    chat = next(l for l in service.architecture()["layers"] if "Chat" in l["name"])
    assert all(c["status"] == "PLANNED" for c in chat["components"])


# ==========================================================================
# Output capability model
# ==========================================================================
def test_catalogue_contains_exactly_twenty_five_outputs():
    assert len(OUTPUT_CATALOGUE) == 25
    assert len({o[0] for o in OUTPUT_CATALOGUE}) == 25


def test_catalogue_ids_match_the_workflow_registry(service):
    """A built workflow must appear in the catalogue under the same id, or the
    UI would show it as planned while it is actually executable."""
    built = {d.id for d in service.workflows.all() if d.sections}
    catalogued = {o[0] for o in OUTPUT_CATALOGUE}
    assert built <= catalogued, f"workflows missing from the catalogue: {built - catalogued}"


def test_only_genuinely_built_outputs_are_executable(service):
    service.analyse_scenario("SCN-001")
    rows = service.full_output_catalogue()
    for row in rows:
        if row["executable"]:
            assert row["implemented"], f"{row['id']} offered but not implemented"
            assert service.workflows.get(row["id"]) is not None


def test_three_outputs_are_executable_today(service):
    service.analyse_scenario("SCN-001")
    executable = [r["id"] for r in service.full_output_catalogue() if r["executable"]]
    assert sorted(executable) == ["dvpr", "engineering_impact_assessment",
                                  "evidence_gap_analysis"]


def test_unavailable_outputs_always_state_a_reason(service):
    service.analyse_scenario("SCN-001")
    for row in service.full_output_catalogue():
        if not row["executable"]:
            assert row["reason"], f"{row['id']} unavailable with no explanation"


def test_status_is_scoped_to_the_analysis_not_the_whole_dataset(service):
    """Using the full connector dataset would mark every output applicable and
    destroy the meaning of the status."""
    service.analyse_scenario("SCN-001")
    statuses = {r["status"] for r in service.full_output_catalogue()}
    assert "NOT APPLICABLE" in statuses, \
        "a change-impact analysis has no root cause or supplier issue in scope"


def test_status_resolution_rules():
    assert resolve_status(True, False, set(), ("Requirement",))[0] == "READY"
    assert resolve_status(False, False, set(), ("Requirement",))[0] == "PLANNED"
    assert resolve_status(True, True, {"Requirement"}, ("Requirement",))[0] == "AVAILABLE"
    assert resolve_status(True, True, set(), ("Requirement",))[0] == "REQUIRES DATA"
    assert resolve_status(False, True, set(), ("Requirement",))[0] == "NOT APPLICABLE"


# ==========================================================================
# Executive presentation
# ==========================================================================
def test_executive_answers_the_seven_decision_questions(service):
    service.analyse_scenario("SCN-001")
    e = service.executive()
    assert e["answerable"]
    assert e["subject_title"]                      # what changed
    assert e["domains"]                            # what is affected
    assert e["significance"] in ("Broad", "Contained", "Not established")
    assert e["attention"]                          # what needs attention
    assert e["supported_findings"] > 0             # what evidence supports this
    assert e["unknowns"]                           # what is missing
    assert e["actions"]                            # what to do next


def test_executive_significance_is_derived_not_asserted(service):
    service.analyse_scenario("SCN-001")
    e = service.executive()
    assert str(len(e["domains"])) in e["significance_note"]
    assert str(e["total_gaps"]) in e["significance_note"]


def test_executive_actions_are_bound_to_real_findings(service):
    """Every recommended action must trace to something the analysis found."""
    service.analyse_scenario("SCN-001")
    e = service.executive()
    findings = " ".join(f.statement for f in service.session.result["findings"])
    gap_labels = " ".join(a["label"].lower() for a in e["attention"])
    for action in e["actions"]:
        assert (action in findings or any(w in action.lower() for w in
                ("establish", "execute", "re-run", "review", "record"))
                or action.lower() in gap_labels)


def test_executive_reports_unanswerable_rather_than_guessing(service):
    service.analyse("assess this change", "ECR-NOT-REAL")
    e = service.executive()
    assert e["answerable"] is False
    assert e["unknowns"]


def test_gap_classes_carry_a_human_label_and_an_action(service):
    service.analyse_scenario("SCN-001")
    for gap in service.executive()["attention"]:
        assert gap["label"] and gap["detail"] and gap["action"]
        assert gap["count"] > 0


def test_criterion_gap_is_surfaced_as_the_most_important_class(service):
    service.analyse_scenario("SCN-001")
    types = [g["gap_type"] for g in service.executive()["attention"]]
    assert "criterion_not_established" in types
    assert types[0] == "criterion_not_established", \
        "an unestablished acceptance criterion should lead the attention list"


# ==========================================================================
# Routes
# ==========================================================================
@pytest.mark.parametrize("path", ["/", "/architecture", "/sources", "/outputs",
                                  "/evidence", "/health", "/api/architecture",
                                  "/api/connectors", "/api/outputs"])
def test_route_responds(client, path):
    assert client.get(path).status_code == 200


def test_architecture_page_shows_all_three_columns(client):
    client.get("/domain/automotive")
    html = client.get("/architecture").text
    for column in ("Input connectors", "ENTERPRISE ENGINEERING INTELLIGENCE CONTAINER",
                   "Engineering outputs"):
        assert column in html
    assert "End-to-end data flow" in html
    assert "Operating principles" in html


def test_architecture_page_shows_planned_components_honestly(client):
    client.get("/domain/automotive")
    html = client.get("/architecture").text
    assert "PLAN" in html and "IMPL" in html


def test_sources_page_distinguishes_no_adapter_from_disabled(client):
    client.get("/domain/automotive")
    html = client.get("/sources").text
    assert "NO ADAPTER" in html
    assert "No enterprise system is connected" in html


def test_outputs_page_lists_all_twenty_five(client):
    import html as html_lib
    client.get("/domain/automotive")
    rendered = html_lib.unescape(client.get("/outputs").text)
    for _, name, *_ in OUTPUT_CATALOGUE:
        assert name in rendered, f"{name} missing from the outputs page"


def test_intelligence_flow_end_to_end(client):
    analysis = client.post("/analyse", data={"scenario_id": "SCN-001"})
    assert analysis.status_code == 200
    for heading in ("What changed", "What is affected", "What needs attention",
                    "What engineering should do next",
                    "What the appliance could not establish"):
        assert heading in analysis.text
    assert "Explain" in analysis.text   # the auditable-derivation control

    import re
    finding = re.search(r"/explain/([A-Z]+-\d+)", analysis.text)
    assert finding
    why = client.get(f"/explain/{finding.group(1)}")
    assert why.status_code == 200
    assert "Supporting evidence" in why.text
    assert "Relationship path" in why.text or "No verifiable evidence" in why.text

    for workflow in ("engineering_impact_assessment", "dvpr", "evidence_gap_analysis"):
        generated = client.post(f"/output/{workflow}")
        assert generated.status_code == 200
        assert "Validation" in generated.text

    assert client.post("/reset").status_code == 200


def test_deterministic_mode_is_stated_not_disguised(client):
    html = client.get("/").text
    assert "Analysis mode: Deterministic" in html
    assert "AI is thinking" not in html


def test_no_chain_of_thought_is_exposed(client):
    client.post("/analyse", data={"scenario_id": "SCN-001"})
    import re
    analysis = client.post("/analyse", data={"scenario_id": "SCN-001"}).text
    finding = re.search(r"/explain/([A-Z]+-\d+)", analysis)
    why = client.get(f"/explain/{finding.group(1)}").text
    for leak in ("chain of thought", "thinking:", "<thinking"):
        assert leak not in why.lower()
