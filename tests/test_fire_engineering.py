"""The fire-engineering public demonstrator (SCN-F01).

Same pipeline, gate, provenance and workflow engine as the automotive
demonstration; only the domain pack and its synthetic data differ. These tests
pin the behaviours the demonstrator exists to show, and that adding a second
domain did not change the first.
"""
from __future__ import annotations

import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from appliance.core.provenance import Classification
from appliance.service import ApplianceService

SCENARIO = "SCN-F01"
PACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "packs", "fire-engineering")
CLASSIFICATION = "SIMULATED — PUBLIC DEMONSTRATOR DATA"


@pytest.fixture(scope="module")
def fire():
    """A dedicated service, so this module never disturbs the shared session."""
    return ApplianceService()


@pytest.fixture(scope="module")
def result(fire):
    return fire.analyse_scenario(SCENARIO)


def _tagged(result, tag):
    return [f for f in result["findings"] if tag in f.tags]


# -- corpus ----------------------------------------------------------------
def test_every_dataset_file_carries_the_public_envelope():
    for folder in ("data", "scenarios"):
        for name in os.listdir(os.path.join(PACK, folder)):
            with open(os.path.join(PACK, folder, name), encoding="utf-8") as fh:
                payload = json.load(fh)
            assert payload["data_classification"] == CLASSIFICATION, name
            assert payload["generated_by"] == "Engineering Knowledge Intelligence demonstrator"
            assert payload["seed"] == 42


def test_corpus_has_the_intended_shape(result):
    types = result["context"].types_present()
    assert types["EngineeringChange"] == 1
    assert types["System"] == 4 and types["Subsystem"] == 4 and types["Component"] == 4
    assert 8 <= types["Requirement"] <= 12
    assert types["FailureMode"] == 6
    assert types["TestCase"] >= 8 and types["TestResult"] >= 8
    assert types["Standard"] >= 6 and types["Document"] == 4 and types["Evidence"] == 6
    assert len(result["context"].relationships) >= 70


def test_corpus_has_no_dangling_references(result):
    assert result["context"].validate() == []


def test_standards_hold_identifiers_only():
    with open(os.path.join(PACK, "data", "standards.json"), encoding="utf-8") as fh:
        for record in json.load(fh)["records"]:
            assert set(record) <= {"id", "identifier", "title", "body", "scope_tag",
                                   "content_policy", "edition", "record_type"}
            assert "no clause text" in record["content_policy"]


def test_unestablished_criteria_carry_no_criterion_text():
    with open(os.path.join(PACK, "data", "tests.json"), encoding="utf-8") as fh:
        tests = json.load(fh)["records"]
    unestablished = [t for t in tests if not t["acceptance_criterion_established"]]
    assert unestablished
    assert all(t["acceptance_criterion"] is None for t in unestablished)


# -- 1-4: scenario, analysis, domains, requirements ---------------------------
def test_scenario_is_listed_and_routed_to_its_own_connector(fire):
    rows = {s["scenario_id"]: s for s in fire.scenarios()}
    assert rows[SCENARIO]["domain"] == "fire-engineering"
    assert rows[SCENARIO]["connector_id"] == "FIRE_SIMULATION"
    assert rows["SCN-001"]["connector_id"] == "SIMULATION"


def test_analysis_completes_on_the_fire_dataset_only(result):
    assert result["status"] == "ok"
    assert result["domain"]["domain"] == "fire-engineering"
    assert list(result["evidence_ledger"]["participation"]) == ["FIRE_SIMULATION"]
    connectors = {e.provenance.connector_id for e in result["context"].entities}
    assert connectors == {"FIRE_SIMULATION"}, "another domain's records leaked in"


def test_fire_specialists_replace_the_automotive_engineer(result):
    names = [a["specialist"] for a in result["activity"]]
    assert "Fire Engineer" in names
    assert "Automotive Engineer" not in names
    assert all(a["status"] == "done" for a in result["activity"])


def test_multiple_fire_safety_domains_are_identified(result):
    systems = _tagged(result, "impacted_system")
    assert len(systems) == 4
    assert sum(1 for f in systems if not f.detail["direct"]) >= 2
    for finding in systems:
        assert finding.rationale, "each domain carries its justifying path"


def test_change_is_classified_from_the_record(result):
    (classification,) = _tagged(result, "change_classification")
    assert classification.detail["baseline_basis"] == "office"
    assert classification.detail["proposed_basis"] == "residential"


def test_applicable_requirements_are_identified(result):
    (applicable,) = _tagged(result, "applicable_requirements")
    rows = applicable.detail["rows"]
    assert len(rows) == 10
    assert all(r["regulatory_reference"] for r in rows)
    undetermined = {r["requirement"] for r in rows if r["applicability"] != "applies"}
    assert undetermined == {"FREQ-008", "FREQ-010"}


# -- 5-8: evidence, transferability, unknowns, confidence ----------------------
def test_evidence_is_retrieved(result):
    (summary,) = _tagged(result, "transferability_summary")
    assert len(summary.detail["rows"]) >= 8


def test_office_basis_evidence_is_not_transferable(result):
    context = result["context"]
    assert context.superseded_basis == {"office"}
    assert context.is_stale(context.get("FTR-001"))
    (finding,) = _tagged(result, "transferability")
    assert finding.detail["result"] == "FTR-001"
    assert "FREQ-002" in finding.detail["requirements"]


def test_all_deliberate_evidence_conditions_are_detected(result):
    items = {}
    for finding in _tagged(result, "evidence_gap"):
        for item in finding.detail["items"]:
            items.setdefault(finding.detail["gap_type"], set()).add(
                item["result"] or item["test"])
    assert {"FTR-006", "FTR-007"} <= items["test_not_run"]
    assert items["inconclusive"] == {"FTR-002"}
    assert {"FTR-003", "FTR-007"} <= items["criterion_not_established"]
    assert items["evidence_not_transferable"] == {"FTR-001"}
    assert items["no_result_recorded"] == {"FTST-008"}


def test_clean_passes_are_recognised(result):
    context = result["context"]
    clean = [r for r in context.by_type("TestResult")
             if r.result_status == "pass" and not context.is_stale(r)
             and context.get(r.get("test_id")).acceptance_criterion_established]
    assert len(clean) >= 3


def test_unknowns_are_reported_not_filled(result):
    unknown = [f for f in result["findings"] if f.classification is Classification.UNKNOWN]
    tags = {t for f in unknown for t in f.tags}
    assert {"criterion_not_established", "applicability_unknown",
            "design_input_unknown"} <= tags
    assert all(f.confidence_score == 0.0 for f in unknown)
    joined = " ".join(result["unknowns"]).lower()
    assert "height" in joined and "acceptance criterion" in joined


def test_confidence_and_provenance_are_present(result):
    for finding in result["findings"]:
        if finding.classification is not Classification.UNKNOWN:
            assert finding.confidence_score > 0
        for ref in finding.evidence:
            assert ref.provenance.connector_id == "FIRE_SIMULATION"
            assert ref.provenance.data_classification == CLASSIFICATION


def test_deterministic_mode_has_no_model_findings_and_no_fabrication(result):
    assert result["execution_mode"] == "deterministic"
    assert not [f for f in result["findings"] if f.classification is Classification.INFERRED]
    assert result["gate_report"]["fabricated_citation_count"] == 0


# -- 9: auditable derivation ---------------------------------------------------
def test_explain_exposes_the_evidence_and_reasoning_trace(fire, result):
    (finding,) = _tagged(result, "transferability")
    payload = fire.explain(finding.id)
    assert payload["classification_meaning"]
    assert "not model self-reported" in payload["confidence_basis"]
    assert payload["derivation"] and payload["rationale"]
    ftr = next(e for e in payload["evidence"] if e["id"] == "FTR-001")
    assert ftr["transferable"] is False and ftr["transferability_reason"]
    assert ftr["provenance"]["source_object_id"] == "FTR-001"


# -- 10, 13: verification & evidence plan --------------------------------------
@pytest.fixture()
def fresh(fire):
    fire.analyse_scenario(SCENARIO)
    return fire


def _plan(output):
    return next(s for s in output.sections if s.key == "plan")


def test_dvpr_is_presented_as_a_verification_and_evidence_plan(fresh):
    output = fresh.generate("dvpr")
    assert output.name == "Verification & Evidence Plan"
    assert output.validation["passed"], output.validation["blocking_failures"]
    assert output.provenance["connectors"] == ["FIRE_SIMULATION"]
    assert output.provenance["data_classification"] == CLASSIFICATION


def test_plan_rows_trace_requirement_to_finding(fresh):
    plan = _plan(fresh.generate("dvpr"))
    row = next(r for r in plan.rows if r["result"] == "FTR-001")
    assert row["requirement"] and row["test"] == "FTST-001"
    assert row["evidence_records"] == ["FEV-001"]
    assert row["findings"], "the row must name the findings that justify its action"


def test_plan_never_invents_an_acceptance_criterion(fresh):
    plan = _plan(fresh.generate("dvpr"))
    unestablished = [r for r in plan.rows if not r["criterion_established"]]
    assert {r["test"] for r in unestablished} == {"FTST-003", "FTST-007"}
    for row in unestablished:
        assert row["acceptance_criterion"].startswith("NOT ESTABLISHED")
        assert not re.search(r"\d", row["acceptance_criterion"]), "no figure may appear"


# -- 11, 12: human review ------------------------------------------------------
def test_reject_requires_a_note(fresh):
    finding = fresh.session.result["findings"][0]
    from appliance.core.errors import ReviewError
    with pytest.raises(ReviewError):
        fresh.review(finding.id, "reject", "Reviewer", "")
    with pytest.raises(ReviewError):
        fresh.review(finding.id, "accept", "", "")
    with pytest.raises(ReviewError):
        fresh.review(finding.id, "approve", "Reviewer", "")


def test_review_is_stored_beside_the_finding_not_in_it(fresh):
    finding = next(f for f in fresh.session.result["findings"] if "transferability" in f.tags)
    before = finding.model_dump()
    record = fresh.review(finding.id, "accept", "Demo Reviewer", "Agreed.")
    assert finding.model_dump() == before
    assert record["finding_snapshot"] == {
        "statement": finding.statement, "classification": "DERIVED",
        "confidence_score": finding.confidence_score, "evidence_ids": finding.evidence_ids}
    assert record["timestamp"] and record["reviewer"] == "Demo Reviewer"


def test_rejecting_a_finding_changes_the_plan(fresh):
    before = _plan(fresh.generate("dvpr"))
    finding = next(f for f in fresh.session.result["findings"] if "transferability" in f.tags)
    fresh.review(finding.id, "reject", "Demo Reviewer",
                 "Assessment scope to be re-checked against the residential population.")
    output = fresh.generate("dvpr")
    after = _plan(output)

    row_before = next(r for r in before.rows if r["result"] == "FTR-001")
    row_after = next(r for r in after.rows if r["result"] == "FTR-001")
    assert row_before["action"] != row_after["action"]
    assert row_after["action"].startswith("HELD")
    assert row_after["review"].startswith("REJECTED")

    listed = {r["id"] for s in output.sections if s.kind == "finding_list" for r in s.rows}
    assert finding.id not in listed
    record = next(s for s in output.sections if s.key == "review_record")
    assert record.rows[0]["decision"] == "REJECTED"
    assert output.review_summary["rejected"] == 1
    assert output.validation["passed"]


def test_a_new_analysis_starts_with_no_reviews(fresh):
    finding = fresh.session.result["findings"][0]
    fresh.review(finding.id, "accept", "Reviewer")
    fresh.analyse_scenario(SCENARIO)
    assert fresh.session.reviews == {} and fresh.session.review_log == []


# -- through the HTTP surface --------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from appliance.api.app import app
    return TestClient(app)


# -- the fire-engineering product surface -------------------------------------
FIRE_PAGES = ("/", "/analyse-change", "/requirements", "/evidence", "/reasoning",
              "/verification-plan", "/verification-plan?output=change-impact-assessment",
              "/verification-plan?output=evidence-assessment", "/review", "/architecture")

# Automotive product-lifecycle and quality vocabulary that must not appear anywhere
# in the fire-engineering surface.
AUTOMOTIVE_TERMS = ("DVP", "dvpr", "Automotive", "automotive", "FMEA", "PLM", "PDM",
                    "BOM", "Supplier", "OEM", "ENTERPRISE ENGINEERING INTELLIGENCE",
                    "connector categor", "Vehicle", "vehicle", "PPAP", "APQP", "ASIL",
                    "action priority", "failure mode", "programme", "Programme")


def _visible(html: str) -> str:
    return re.sub(r'<script src="[^"]+"></script>', "", html)


def _transfer_finding(client) -> str:
    html = client.get("/evidence").text
    return re.search(r"Passing evidence FTR-001.*?/explain/(TRF-\d+)", html, re.S).group(1)


def test_a_new_client_lands_on_the_fire_engineering_surface():
    from appliance.api.app import app
    html = TestClient(app).get("/").text
    for text in ("Fire Engineering Knowledge Intelligence",
                 "Evidence-grounded technical decision support for fire engineering",
                 "BB7 × University of Leeds KTP Demonstrator",
                 "Synthetic public demonstration data — not BB7 internal data",
                 "not commissioned, supplied or endorsed by BB7",
                 "Analysis mode: Deterministic"):
        assert text in html, text
    for item in ("Overview", "Analyse Change", "Requirements", "Evidence", "Reasoning",
                 "Verification Plan", "Review", "Architecture"):
        assert f">{item}</a>" in html, item
    assert "Change of use on Level 3 of an existing 8-storey mixed-use building" in html


def test_overview_coverage_is_computed_not_asserted():
    from appliance.api.app import app
    html = TestClient(app).get("/").text
    assert "Conceptual categories for this demonstrator" in html
    assert "Conceptual - not represented in this demonstrator" in html   # e.g. drawings
    assert "Represented in the synthetic corpus" in html
    assert "Not modelled" in html                                          # smoke control
    for domain in ("Means of Escape", "Evacuation Strategy", "Fire Detection &amp; Alarm",
                   "Active Fire Protection", "Passive Fire Protection", "Smoke Control",
                   "Structural Fire Performance", "Firefighting Access"):
        assert domain in html, domain


def test_no_automotive_vocabulary_anywhere_in_the_fire_surface():
    from appliance.api.app import app
    client = TestClient(app)
    pages = {"before analysis " + p: client.get(p).text for p in FIRE_PAGES}
    pages["analysis"] = client.post("/analyse", data={"scenario_id": SCENARIO}).text
    for fid in set(re.findall(r"/explain/([A-Z]+-\d+)", pages["analysis"])):
        pages["explain " + fid] = client.get(f"/explain/{fid}").text
    fid = _transfer_finding(client)
    client.get("/verification-plan")
    pages["review"] = client.post(f"/review/{fid}", data={
        "decision": "reject", "reviewer": "R", "note": "n",
        "targets": "review-summary,output,pill"}).text
    for page in FIRE_PAGES:
        pages[page] = client.get(page).text
    for workflow in ("verification-evidence-plan", "change-impact-assessment",
                     "evidence-assessment"):
        pages["output " + workflow] = client.post(f"/output/{workflow}").text
    for name, html in pages.items():
        leaked = [term for term in AUTOMOTIVE_TERMS if term in _visible(html)]
        assert not leaked, f"{name}: {leaked}"


def test_fire_architecture_is_the_knowledge_architecture_not_the_connector_catalogue():
    from appliance.api.app import app
    client = TestClient(app)
    html = client.get("/architecture").text
    assert "Fire Engineering Knowledge Intelligence Architecture" in html
    for layer in ("Knowledge sources", "Knowledge structure", "Relationships &amp; context",
                  "Evidence retrieval", "Reasoning", "Provenance &amp; confidence",
                  "Human review", "Technical decision output"):
        assert layer in html, layer
    assert "Running now:" in html and "FIRE_SIMULATION" in html
    assert "NO ADAPTER" not in html and "CONTAINER" not in html
    assert client.get("/sources").url.path == "/architecture"
    assert client.get("/outputs").url.path == "/verification-plan"


def test_ui_flow_end_to_end(client):
    page = client.post("/analyse", data={"scenario_id": SCENARIO})
    assert page.status_code == 200
    html = page.text
    for text in ("Change", "Impacted fire-safety domains", "Applicable requirements",
                 "Knowledge / relationship paths", "Evidence", "Transferability",
                 "Unknown / evidence gaps", "Confidence", "Human review",
                 "Verification &amp; Evidence Plan", "Not transferable",
                 "Session scoped · unauthenticated · demonstrator only"):
        assert text in html, text

    finding = _transfer_finding(client)
    why = client.get(f"/explain/{finding}")
    for text in ("Auditable derivation", "Classification reason", "Confidence basis",
                 "Evidence gate outcome", "Relationship path", "Provenance",
                 "Transferability reasoning", "Assumptions", "Supporting evidence",
                 "Engineering Review"):
        assert text in why.text, text
    assert "chain of thought" not in why.text.lower()

    plan = client.get("/verification-plan")
    assert "Verification &amp; Evidence Plan" in plan.text and "HELD" not in plan.text
    assert "NOT ESTABLISHED" in plan.text

    refused = client.post(f"/review/{finding}", data={
        "decision": "reject", "reviewer": "UI Reviewer", "note": "", "targets": "output"})
    assert refused.status_code == 400 and "requires a note" in refused.text

    rejected = client.post(f"/review/{finding}", data={
        "decision": "reject", "reviewer": "UI Reviewer", "note": "Not agreed.",
        "targets": "review-summary,output,pill"})
    assert rejected.status_code == 200 and "Rejected" in rejected.text
    # The plan on screen is regenerated out of band with the decision applied.
    assert 'id="output" hx-swap-oob' in rejected.text and "HELD" in rejected.text

    plan = client.get("/verification-plan")
    assert "Held" in plan.text and "Not agreed." in plan.text


def test_review_updates_only_regions_the_page_has(client):
    client.post("/analyse", data={"scenario_id": SCENARIO})
    finding = _transfer_finding(client)
    bare = client.post(f"/review/{finding}", data={
        "decision": "accept", "reviewer": "R", "note": "", "targets": ""})
    assert "hx-swap-oob" not in bare.text, "no out-of-band target the page lacks"


def test_domain_is_selected_per_client_not_globally(client):
    from appliance.api.app import app
    automotive = TestClient(app)
    automotive.get("/domain/automotive")
    automotive.post("/analyse", data={"scenario_id": "SCN-001"})
    dvpr = automotive.post("/output/dvpr").text
    assert "<h2>DVP&amp;R</h2>" in dvpr and "REQUIRES PROGRAMME SPECIFICATION" in dvpr
    assert "Automotive engineering reference demonstration" in automotive.get("/").text

    fire = TestClient(app)
    assert "Fire Engineering Knowledge Intelligence" in fire.get("/").text
    fire.post("/analyse", data={"scenario_id": SCENARIO})
    assert "DVP" not in _visible(fire.post("/output/verification-evidence-plan").text)

    # Analysing a scenario selects its domain's surface.
    switched = TestClient(app)
    switched.post("/analyse", data={"scenario_id": "SCN-001"})
    assert "Automotive engineering reference demonstration" in switched.get("/").text
    switched.get("/domain/fire-engineering")
    assert "Fire Engineering Knowledge Intelligence" in switched.get("/").text


def test_fire_pages_without_analysis_offer_to_run_it():
    from appliance.api.app import app
    client = TestClient(app)
    for page in ("/requirements", "/evidence", "/reasoning", "/verification-plan", "/review"):
        html = client.get(page).text
        assert f'action="/run/{SCENARIO}"' in html, page
    landed = client.post(f"/run/{SCENARIO}", data={"next": "/requirements"})
    assert landed.url.path == "/requirements" and "FREQ-010" in landed.text


def test_api_review_round_trip_and_session_isolation(client):
    from appliance.api.app import app
    other = TestClient(app)
    client.post("/api/analyse/SCN-F01")
    other.post("/api/analyse/SCN-F01")
    finding = client.get("/api/reviews")  # establishes nothing yet
    assert finding.json()["current"] == {}

    data = client.post("/api/analyse/SCN-F01").json()
    fid = next(f["id"] for f in data["findings"] if "change_classification" in f["tags"])
    ok = client.post(f"/api/review/{fid}",
                     json={"decision": "accept", "reviewer": "API Reviewer", "note": ""})
    assert ok.status_code == 200 and ok.json()["decision"] == "accepted"
    assert fid in client.get("/api/reviews").json()["current"]
    assert other.get("/api/reviews").json()["current"] == {}, "reviews leaked across sessions"


# -- 15: the automotive demonstration is unchanged ----------------------------
def test_automotive_scenario_still_uses_its_own_specialists_and_names(fire):
    result = fire.analyse_scenario("SCN-001")
    names = [a["specialist"] for a in result["activity"]]
    assert "Automotive Engineer" in names and "Fire Engineer" not in names
    assert list(result["evidence_ledger"]["participation"]) == ["SIMULATION"]
    output = fire.generate("dvpr")
    assert output.name == "DVP&R"
    assert any(s.key == "dvpr" for s in output.sections)
