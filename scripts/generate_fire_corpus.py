"""Generates the synthetic fire-engineering corpus for the public demonstrator.

    python scripts/generate_fire_corpus.py

Writes packs/fire-engineering/data/*.json and packs/fire-engineering/scenarios/.
Every record is SYNTHETIC. Nothing here is taken from any consultancy, client,
building or project. Standards are referenced by public identifier and title
only - no clause text, limit, table or test procedure is reproduced.

The corpus is authored, not sampled: each record exists to exercise a specific
behaviour of the appliance (see the EVIDENCE CONDITIONS block below). The seed
is recorded in every envelope for consistency with the simulation dataset
format; generation is fully deterministic and uses no randomness.

EVIDENCE CONDITIONS deliberately present for SCN-F01
    test_not_run               FTR-006 (flat entrance doorsets), FTR-007 (sprinklers)
    inconclusive + deviation   FTR-002 (Level 3 alarm cause-and-effect)
    criterion_not_established  FTST-003 (detection in flats), FTST-007 (sprinklers)
    evidence_not_transferable  FTR-001 - evacuation assessment on the OFFICE basis
    no_result_recorded         FTST-008 (fire service access survey)
    clean passes               FTR-004, FTR-005, FTR-008
    no verification defined    FREQ-010 (higher-risk building status)
    unverified failure mode    FFM-004 (service penetrations)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "packs", "fire-engineering")

CLASSIFICATION = "SIMULATED — PUBLIC DEMONSTRATOR DATA"
GENERATOR = "Engineering Knowledge Intelligence demonstrator"
SEED = 42

STANDARD_POLICY = ("IDENTIFIER AND TITLE ONLY - no clause text, limit, table or test "
                   "procedure from this document is reproduced")
EDITION_NOTE = "Edition not pinned in the demonstrator; the reviewer confirms the current edition."
RATING_METHOD = ("a qualitative review priority assigned in the SIMULATED dataset; it is "
                 "not a quantified fire risk assessment")

# --------------------------------------------------------------------------
CHANGES = [{
    "id": "FEC-001",
    "title": "Change of use of Level 3 from office to six residential apartments",
    "description": ("Change of use on Level 3 of an existing 8-storey mixed-use building from "
                    "office use to six residential apartments. Single stair. Category L2 fire "
                    "alarm. Existing fire strategy is based on simultaneous evacuation of the "
                    "office population. Sprinklers are not fitted above Level 1."),
    "change_type": "material_change_of_use",
    "change_type_label": "a material change of use",
    "baseline_basis": "office",
    "proposed_basis": "residential",
    "affected_areas": ["Level 3 (whole floor)", "the single common stair serving all levels",
                       "the building-wide fire alarm cause-and-effect"],
    "existing_conditions": [
        "8 storeys, mixed use",
        "One common stair serving all storeys",
        "BS 5839-1 Category L2 fire detection and alarm (office design)",
        "Fire strategy based on simultaneous evacuation of the office population",
        "Sprinklers fitted to Levels 0-1 only",
    ],
    "unrecorded_design_inputs": [
        "height of the topmost storey above ground level in metres",
        "the evacuation strategy intended for the residential floor",
        "whether sprinkler protection is to be extended to Level 3",
        "the smoke control provision for the Level 3 common corridor and stair",
    ],
    "primary_system_id": "FSYS-001",
    "status": "under_review",
    "raised_date": "2026-05-20",
    "project": "Synthetic project - no real building",
}]

SYSTEMS = [
    {"id": "FSYS-001", "name": "Means of escape and evacuation",
     "domain": "Means of warning and escape",
     "description": "Escape routes, the common stair, protected lobbies and the evacuation strategy.",
     "domain_areas": ["Means of Escape", "Evacuation Strategy"]},
    {"id": "FSYS-002", "name": "Fire detection and alarm",
     "domain": "Detection and warning",
     "description": "Automatic detection, manual call points, sounders and cause-and-effect.",
     "domain_areas": ["Fire Detection & Alarm"]},
    {"id": "FSYS-003", "name": "Compartmentation and structural fire protection",
     "domain": "Internal fire spread",
     "description": "Compartment floors and walls, fire-stopping and fire resistance of structure.",
     "domain_areas": ["Passive Fire Protection", "Structural Fire Performance"]},
    {"id": "FSYS-004", "name": "Sprinklers and fire service facilities",
     "domain": "Suppression and firefighting",
     "description": "Automatic suppression, fire mains and access for firefighting.",
     "domain_areas": ["Active Fire Protection", "Firefighting Access"]},
]

SUBSYSTEMS = [
    {"id": "FSUB-001", "system_id": "FSYS-001", "name": "Single common stair and lobbies",
     "description": "The only vertical escape route, with lobby protection at each storey."},
    {"id": "FSUB-002", "system_id": "FSYS-002", "name": "Level 3 alarm zone and cause-and-effect",
     "description": "Detection, sounders and programmed outputs serving Level 3."},
    {"id": "FSUB-003", "system_id": "FSYS-003", "name": "Level 3 compartmentation",
     "description": "Compartment floor, flat separation and fire-stopping on Level 3."},
    {"id": "FSUB-004", "system_id": "FSYS-004", "name": "Sprinkler installation, Levels 0-1",
     "description": "Existing sprinkler protection limited to the lower two storeys."},
]

COMPONENTS = [
    {"id": "FCMP-001", "subsystem_id": "FSUB-001", "system_id": "FSYS-001",
     "name": "Stair lobby fire doorsets (Levels 2-4)"},
    {"id": "FCMP-002", "subsystem_id": "FSUB-002", "system_id": "FSYS-002",
     "name": "Level 3 detectors and sounder circuits"},
    {"id": "FCMP-003", "subsystem_id": "FSUB-003", "system_id": "FSYS-003",
     "name": "Flat entrance doorsets (proposed)"},
    {"id": "FCMP-004", "subsystem_id": "FSUB-004", "system_id": "FSYS-004",
     "name": "Sprinkler valve set and distribution (Levels 0-1)"},
]

STANDARDS = [
    {"id": "FSTD-001", "identifier": "Approved Document B, Volume 1",
     "title": "Fire safety - Volume 1: Dwellings", "body": "HM Government",
     "scope_tag": "statutory_guidance"},
    {"id": "FSTD-002", "identifier": "Approved Document B, Volume 2",
     "title": "Fire safety - Volume 2: Buildings other than dwellings", "body": "HM Government",
     "scope_tag": "statutory_guidance"},
    {"id": "FSTD-003", "identifier": "BS 9991",
     "title": "Fire safety in the design, management and use of residential buildings - Code of practice",
     "body": "BSI", "scope_tag": "code_of_practice"},
    {"id": "FSTD-004", "identifier": "BS 5839-1",
     "title": "Fire detection and fire alarm systems for buildings - Code of practice for "
              "non-domestic premises", "body": "BSI", "scope_tag": "code_of_practice"},
    {"id": "FSTD-005", "identifier": "BS 5839-6",
     "title": "Fire detection and fire alarm systems for buildings - Code of practice for "
              "domestic premises", "body": "BSI", "scope_tag": "code_of_practice"},
    {"id": "FSTD-006", "identifier": "BS 9251",
     "title": "Fire sprinkler systems for domestic and residential occupancies - Code of practice",
     "body": "BSI", "scope_tag": "code_of_practice"},
    {"id": "FSTD-007", "identifier": "Building Safety Act 2022",
     "title": "Building Safety Act 2022", "body": "UK Parliament", "scope_tag": "legislation"},
    {"id": "FSTD-008", "identifier": "The Building Regulations 2010",
     "title": "The Building Regulations 2010 (SI 2010/2214)", "body": "UK Parliament",
     "scope_tag": "legislation"},
]
for _s in STANDARDS:
    _s["content_policy"] = STANDARD_POLICY
    _s["edition"] = EDITION_NOTE


AREAS_BY_SYSTEM = {"FSYS-001": ["Means of Escape", "Evacuation Strategy"],
                   "FSYS-002": ["Fire Detection & Alarm"],
                   "FSYS-003": ["Passive Fire Protection", "Structural Fire Performance"],
                   "FSYS-004": ["Active Fire Protection", "Firefighting Access"]}


def _req(rid, system, title, statement, reference, standards, status, basis,
         applicability="applies", note=None):
    record = {"id": rid, "level": "building", "system_id": system, "title": title,
              "domain_areas": AREAS_BY_SYSTEM[system] + ["Regulatory / Guidance Requirements"],
              "statement": statement, "requirement_type": "life_safety",
              "regulatory_reference": reference, "standard_ids": standards,
              "status": status, "basis": basis, "applicability": applicability,
              "statement_origin": "Plain-language synthetic requirement authored for the "
                                  "demonstrator; not quoted from any standard."}
    if note:
        record["applicability_note"] = note
    return record


B1 = "Building Regulations 2010, Schedule 1, Part B, requirement B1 (means of warning and escape)"
B3 = "Building Regulations 2010, Schedule 1, Part B, requirement B3 (internal fire spread - structure)"
B5 = "Building Regulations 2010, Schedule 1, Part B, requirement B5 (access and facilities for the fire service)"

REQUIREMENTS = [
    _req("FREQ-001", "FSYS-001", "Evacuation strategy for the residential floor",
         "An evacuation strategy appropriate to residential sleeping occupancy is defined for "
         "Level 3 and reconciled with the strategy for the rest of the building.",
         B1, ["FSTD-001", "FSTD-003"], "draft", "residential"),
    _req("FREQ-002", "FSYS-001", "Single stair capacity and protection",
         "The single common stair provides adequate capacity and protection for the evacuating "
         "population under the building's evacuation strategy.",
         B1, ["FSTD-002"], "approved", "office"),
    _req("FREQ-003", "FSYS-001", "Protected escape from flats to the common stair",
         "Escape from each flat is through protected common circulation separated from the stair.",
         B1, ["FSTD-001", "FSTD-003"], "draft", "residential"),
    _req("FREQ-004", "FSYS-002", "Fire detection and alarm within each flat",
         "Each flat has automatic fire detection and alarm to a grade and category selected for "
         "the residential occupancy.",
         B1, ["FSTD-005"], "draft", "residential"),
    _req("FREQ-005", "FSYS-002", "Alarm cause-and-effect compatible with the evacuation strategy",
         "The building fire alarm cause-and-effect is compatible with the evacuation strategy "
         "for the building's occupancies.",
         B1, ["FSTD-004"], "approved", "office"),
    _req("FREQ-006", "FSYS-003", "Compartmentation of each flat",
         "Each flat forms a separate fire compartment from other flats and from the common parts.",
         B3, ["FSTD-001", "FSTD-003"], "draft", "residential"),
    _req("FREQ-007", "FSYS-003", "Fire resistance of the Level 3 compartment floor",
         "The Level 3 compartment floor and its supporting structure achieve the fire resistance "
         "required for the building as altered.",
         B3, ["FSTD-001", "FSTD-002"], "approved", "not_occupancy_dependent"),
    _req("FREQ-008", "FSYS-004", "Sprinkler protection to the residential floor",
         "The need for, and extent of, automatic sprinkler protection to the residential floor "
         "is determined and justified.",
         B3, ["FSTD-001", "FSTD-006"], "draft", "residential", "to_be_confirmed",
         "Whether sprinkler protection must be extended to Level 3 depends on the height of the "
         "topmost storey and on the evacuation strategy adopted; neither is recorded in the "
         "available evidence."),
    _req("FREQ-009", "FSYS-004", "Fire service access and facilities serving Level 3",
         "Fire service access, firefighting facilities and the fire main remain adequate for "
         "firefighting on Level 3.",
         B5, ["FSTD-002"], "approved", "not_occupancy_dependent"),
    _req("FREQ-010", "FSYS-001", "Regulatory route and higher-risk building status",
         "The regulatory route for the works is determined, including whether the building as "
         "altered falls within the higher-risk building definition.",
         "Building Safety Act 2022 (higher-risk building definition); Building Regulations 2010 "
         "(material change of use)", ["FSTD-007", "FSTD-008"], "draft", "residential",
         "to_be_confirmed",
         "Depends on the building's height and storey count measured as the applicable "
         "regulations define, and on the number of residential units after the change; the "
         "height is not recorded in the available evidence."),
]


def _fm(fid, focus, mode, effect, cause, priority, status="open"):
    return {"id": fid, "focus_id": focus, "failure_mode": mode, "failure_effect": effect,
            "failure_cause": cause, "action_priority": priority,
            "action_priority_method": RATING_METHOD, "status": status}


FAILURE_MODES = [
    _fm("FFM-001", "FSYS-001", "Smoke enters the single stair during evacuation",
        "Escape route compromised for occupants above the fire floor, including sleeping residents",
        "Stair protection and evacuation assumptions were made for awake, familiar office occupants",
        "H"),
    _fm("FFM-002", "FSYS-002", "Residents are not warned in time",
        "Delayed evacuation from the flats",
        "Detection and cause-and-effect were designed for office occupancy", "H"),
    _fm("FFM-003", "FCMP-003", "Fire and smoke spread from a flat into common circulation",
        "Common escape route becomes untenable",
        "Flat entrance doorsets not yet specified to a residential performance", "H"),
    _fm("FFM-004", "FSUB-003", "Compartment floor breached by new service penetrations",
        "Fire spread between Level 3 and adjacent storeys",
        "New drainage and ventilation penetrations for the flats not fire-stopped", "M"),
    _fm("FFM-005", "FSUB-003", "Fire in an unsprinklered flat grows beyond the fire size assumed in the strategy",
        "Greater smoke and heat challenge to compartmentation and escape",
        "Sprinklers are not fitted above Level 1", "M"),
    _fm("FFM-006", "FSYS-001", "Firefighting operations and escape conflict in the single stair",
        "Delayed firefighting and obstructed escape",
        "One stair serves both escape and firefighting access", "M"),
]


def _test(tid, title, method, verifies, addresses, standards, criterion, established,
          conditions, domain):
    return {"id": tid, "title": title, "method": method, "level": "building",
            "conditions": conditions,
            "acceptance_criterion": criterion if established else None,
            "acceptance_criterion_established": established,
            "verifies_requirements": verifies, "addresses_failure_modes": addresses,
            "standard_ids": standards, "responsible_domain": domain, "phase": "design_review"}


TESTS = [
    _test("FTST-001", "Stair capacity and evacuation assessment", "calculation_assessment",
          ["FREQ-001", "FREQ-002"], ["FFM-001"], ["FSTD-002"],
          "Stair capacity is not less than the evacuating population determined under the "
          "agreed fire strategy", True,
          "Population and evacuation strategy as defined in the building fire strategy (FDOC-001).",
          "Means of escape"),
    _test("FTST-002", "Fire alarm cause-and-effect functional test", "commissioning_test",
          ["FREQ-005"], ["FFM-002"], ["FSTD-004"],
          "Every initiating device produces the outputs specified in the approved "
          "cause-and-effect matrix", True,
          "All zones, against the matrix in FDOC-002.", "Detection and warning"),
    _test("FTST-003", "Detection and alarm inspection within the flats", "inspection",
          ["FREQ-004"], ["FFM-002"], ["FSTD-005"], None, False,
          "No grade or category of system has been selected for the flats.",
          "Detection and warning"),
    _test("FTST-004", "Stair lobby fire doorset inspection", "inspection",
          ["FREQ-003"], ["FFM-001"], ["FSTD-002"],
          "Doorsets carry third-party certification for their specified fire and smoke "
          "performance, and self-closing devices close and latch the door", True,
          "Stair lobby doorsets, Levels 2-4.", "Means of escape"),
    _test("FTST-005", "Compartment floor fire-resistance evidence review", "document_review",
          ["FREQ-007"], [], ["FSTD-002"],
          "As-built construction matches a tested or assessed specification achieving the "
          "fire resistance period stated in the fire strategy", True,
          "Level 3 / Level 4 compartment floor.", "Internal fire spread"),
    _test("FTST-006", "Flat entrance doorset specification and certification review",
          "document_review", ["FREQ-003", "FREQ-006"], ["FFM-003"], ["FSTD-001"],
          "Doorsets are certified for the fire resistance and smoke control performance the "
          "fire strategy specifies for flat entrance doors", True,
          "Six proposed flat entrance doorsets.", "Internal fire spread"),
    _test("FTST-007", "Sprinkler provision assessment for Level 3", "engineering_assessment",
          ["FREQ-008"], ["FFM-005"], ["FSTD-006", "FSTD-001"], None, False,
          "Scope depends on the evacuation strategy and building height, neither recorded.",
          "Suppression and firefighting"),
    _test("FTST-008", "Fire service access route survey to Level 3", "site_survey",
          ["FREQ-009"], ["FFM-006"], ["FSTD-002"],
          "Access route and firefighting facilities conform to the fire service provisions "
          "recorded in the fire strategy", True,
          "Fire appliance access, entry point and route to Level 3.", "Suppression and firefighting"),
    _test("FTST-009", "Dry rising main pressure test", "commissioning_test",
          ["FREQ-009"], ["FFM-006"], ["FSTD-002"],
          "Rising main holds test pressure for the duration specified by its installation "
          "standard with no loss of pressure", True,
          "Existing dry rising main serving all storeys.", "Suppression and firefighting"),
]


def _result(rid, test, status, basis, date, summary, notes="", deviation=None):
    record = {"id": rid, "test_id": test, "status": status, "basis": basis,
              "executed_date": date, "measured_summary": summary, "notes": notes,
              "origin": "synthetic"}
    if deviation:
        record["deviation"] = deviation
    return record


TEST_RESULTS = [
    _result("FTR-001", "FTST-001", "pass", "office", "2024-03-14",
            "Stair capacity assessed as adequate for simultaneous evacuation of the office "
            "population from every storey.",
            "Assessment inputs were office population and simultaneous evacuation of awake "
            "occupants. Residential sleeping occupancy was not considered."),
    _result("FTR-002", "FTST-002", "inconclusive", "office", "2025-11-06",
            "Cause-and-effect outputs confirmed for Levels 0-2 and 4-7. Level 3 outputs could "
            "not be demonstrated.",
            "Retest not scheduled.",
            deviation="Level 3 was partly stripped out for the proposed works at the time of "
                      "the test; two sounder circuits were isolated, so Level 3 "
                      "cause-and-effect could not be demonstrated."),
    _result("FTR-003", "FTST-003", "pass", "residential", "2026-06-02",
            "Installer's inspection of the show flat reports detectors fitted.",
            "No grade or category has been agreed for the flats, so the result cannot be "
            "judged against a criterion."),
    _result("FTR-004", "FTST-004", "pass", "not_occupancy_dependent", "2026-02-18",
            "All stair lobby doorsets at Levels 2-4 inspected; certification labels present; "
            "self-closing devices close and latch."),
    _result("FTR-005", "FTST-005", "pass", "not_occupancy_dependent", "2026-01-22",
            "As-built floor construction matches the assessed specification referenced in "
            "the fire strategy."),
    _result("FTR-006", "FTST-006", "not_run", "residential", None,
            "Not executed.", "Flat entrance doorsets have not yet been specified or procured."),
    _result("FTR-007", "FTST-007", "not_run", "residential", None,
            "Not executed.", "Assessment not commissioned; the sprinkler decision is outstanding."),
    _result("FTR-008", "FTST-009", "pass", "not_occupancy_dependent", "2025-09-10",
            "Dry rising main pressure test completed with no loss of pressure recorded."),
]

DOCUMENTS = [
    {"id": "FDOC-001", "title": "Existing fire strategy report", "document_type": "fire_strategy",
     "revision": "C", "issued_date": "2023-10-01", "status": "released", "basis": "office",
     "abstract": "Synthetic fire strategy for the building in office use: simultaneous "
                 "evacuation via the single stair, Category L2 detection and alarm, "
                 "sprinklers to Levels 0-1."},
    {"id": "FDOC-002", "title": "Fire alarm cause-and-effect matrix",
     "document_type": "cause_and_effect", "revision": "B", "issued_date": "2023-11-15",
     "status": "released", "basis": "office",
     "abstract": "Programmed alarm outputs for each zone, prepared for office occupancy."},
    {"id": "FDOC-003", "title": "Level 3 change-of-use proposal - six apartments",
     "document_type": "architectural_proposal", "revision": "P2", "issued_date": "2026-05-12",
     "status": "for_comment", "basis": "residential",
     "abstract": "Proposed layout of six flats on Level 3 opening onto a common corridor "
                 "leading to the stair lobby."},
    {"id": "FDOC-004", "title": "Sprinkler installation record, Levels 0-1",
     "document_type": "installation_record", "revision": "A", "issued_date": "2019-04-30",
     "status": "released", "basis": "not_occupancy_dependent",
     "abstract": "Record of the existing sprinkler installation serving the lower two storeys."},
]

EVIDENCE = [
    {"id": "FEV-001", "evidence_type": "assessment_report", "source_record_type": "TestResult",
     "source_record_id": "FTR-001", "title": "Stair capacity and evacuation assessment report",
     "status": "pass", "strength": "moderate", "basis": "office",
     "supports_requirements": ["FREQ-001", "FREQ-002"], "recorded_date": "2024-03-14"},
    {"id": "FEV-002", "evidence_type": "test_certificate", "source_record_type": "TestResult",
     "source_record_id": "FTR-002", "title": "Fire alarm cause-and-effect test certificate (partial)",
     "status": "inconclusive", "strength": "weak", "basis": "office",
     "supports_requirements": ["FREQ-005"], "recorded_date": "2025-11-06"},
    {"id": "FEV-003", "evidence_type": "inspection_record", "source_record_type": "TestResult",
     "source_record_id": "FTR-004", "title": "Stair lobby fire doorset inspection record",
     "status": "pass", "strength": "strong", "basis": "not_occupancy_dependent",
     "supports_requirements": ["FREQ-003"], "recorded_date": "2026-02-18"},
    {"id": "FEV-004", "evidence_type": "document_review", "source_record_type": "TestResult",
     "source_record_id": "FTR-005", "title": "Compartment floor fire-resistance review record",
     "status": "pass", "strength": "strong", "basis": "not_occupancy_dependent",
     "supports_requirements": ["FREQ-007"], "recorded_date": "2026-01-22"},
    {"id": "FEV-005", "evidence_type": "test_certificate", "source_record_type": "TestResult",
     "source_record_id": "FTR-008", "title": "Dry rising main test certificate",
     "status": "pass", "strength": "strong", "basis": "not_occupancy_dependent",
     "supports_requirements": ["FREQ-009"], "recorded_date": "2025-09-10"},
    {"id": "FEV-006", "evidence_type": "fire_strategy", "source_record_type": "Document",
     "source_record_id": "FDOC-001", "title": "Existing fire strategy (office use, simultaneous evacuation)",
     "status": "current_for_previous_use", "strength": "moderate", "basis": "office",
     "supports_requirements": ["FREQ-001", "FREQ-002", "FREQ-005"], "recorded_date": "2023-10-01"},
]

TYPE_OF = {}


def _edge(s, rel, t, note=None):
    return {"source_type": TYPE_OF[s], "source_id": s, "relationship": rel,
            "target_type": TYPE_OF[t], "target_id": t, "note": note}


def relationships() -> list[dict]:
    edges = []
    for sub in SUBSYSTEMS:
        edges.append(_edge(sub["system_id"], "HAS_SUBSYSTEM", sub["id"]))
    for comp in COMPONENTS:
        edges.append(_edge(comp["subsystem_id"], "HAS_COMPONENT", comp["id"]))
    for target in ("FSYS-001", "FSUB-002", "FSUB-003", "FCMP-003"):
        edges.append(_edge("FEC-001", "AFFECTS", target))
    inferred = {"FREQ-007", "FREQ-008", "FREQ-009"}
    for req in REQUIREMENTS:
        edges.append(_edge("FEC-001", "AFFECTS", req["id"],
                           "inferred via allocation" if req["id"] in inferred else None))
        edges.append(_edge(req["id"], "ALLOCATED_TO", req["system_id"]))
        for sid in req["standard_ids"]:
            edges.append(_edge(sid, "APPLIES_TO", req["id"]))
    for test in TESTS:
        for rid in test["verifies_requirements"]:
            edges.append(_edge(rid, "VERIFIED_BY", test["id"]))
        for fid in test["addresses_failure_modes"]:
            edges.append(_edge(fid, "VERIFIED_BY", test["id"]))
        for sid in test["standard_ids"]:
            edges.append(_edge(sid, "APPLIES_TO", test["id"]))
    for res in TEST_RESULTS:
        edges.append(_edge(res["test_id"], "PRODUCES", res["id"]))
    for owner, mode in (("FSYS-001", "FFM-001"), ("FSUB-001", "FFM-001"),
                        ("FSYS-002", "FFM-002"), ("FSUB-002", "FFM-002"),
                        ("FCMP-003", "FFM-003"), ("FSUB-003", "FFM-004"),
                        ("FSUB-003", "FFM-005"), ("FSYS-004", "FFM-005"),
                        ("FSYS-001", "FFM-006"), ("FSYS-004", "FFM-006")):
        edges.append(_edge(owner, "HAS_FAILURE_MODE", mode))
    for ev in EVIDENCE:
        edges.append(_edge(ev["source_record_id"], "SUPPORTS", ev["id"]))
        for rid in ev["supports_requirements"]:
            edges.append(_edge(ev["id"], "SUPPORTS", rid))
    for doc, target in (("FDOC-001", "FEC-001"), ("FDOC-001", "FSYS-001"),
                        ("FDOC-002", "FEC-001"), ("FDOC-002", "FSYS-002"),
                        ("FDOC-003", "FEC-001"), ("FDOC-004", "FEC-001"),
                        ("FDOC-004", "FSYS-004")):
        edges.append(_edge(doc, "DESCRIBES", target))
    return edges


COLLECTIONS = (
    ("engineering_changes.json", "EngineeringChange", "Engineering changes under assessment.", CHANGES),
    ("systems.json", "System", "Fire-safety systems (domains) of the synthetic building.", SYSTEMS),
    ("subsystems.json", "Subsystem", "Subsystems within each fire-safety system.", SUBSYSTEMS),
    ("components.json", "Component", "Components relevant to the change.", COMPONENTS),
    ("requirements.json", "Requirement", "Plain-language synthetic requirements with regulatory references.", REQUIREMENTS),
    ("failure_modes.json", "FailureMode", "Fire hazards expressed as failure modes, with qualitative review priority.", FAILURE_MODES),
    ("tests.json", "TestCase", "Verification activities with acceptance criteria where established.", TESTS),
    ("test_results.json", "TestResult", "Verification results: pass, fail, inconclusive and not_run.", TEST_RESULTS),
    ("standards.json", "Standard", "Standards and legislation. Identifier and title only.", STANDARDS),
    ("documents.json", "Document", "Synthetic project documents.", DOCUMENTS),
    ("evidence.json", "Evidence", "Evidence records derived from results and documents.", EVIDENCE),
)

SCENARIO = {
    "scenario_id": "SCN-F01",
    "category": "Fire engineering - change of use",
    "title": "Level 3 office to residential change of use (single stair)",
    "domain": "fire-engineering",
    "connector": "FIRE_SIMULATION",
    "engineering_question": ("An existing office floor is to become six flats in a single-stair "
                             "building. Which fire-safety domains and requirements does this "
                             "affect, what evidence already exists, does it still apply, and "
                             "what must now be verified?"),
    "one_liner": ("Assess the fire-safety impact of this change and the verification evidence "
                  "it requires."),
    "initial_input": CHANGES[0]["description"],
    "relevant_entities": {"engineering_changes": ["FEC-001"],
                          "systems": [s["id"] for s in SYSTEMS],
                          "requirements": [r["id"] for r in REQUIREMENTS],
                          "tests": [t["id"] for t in TESTS]},
    "expected_impacted_domains": [s["domain"] for s in SYSTEMS],
    "expected_evidence_conditions": {
        "test_not_run": ["FTR-006", "FTR-007"],
        "inconclusive_with_deviation": ["FTR-002"],
        "criterion_not_established": ["FTST-003", "FTST-007"],
        "evidence_not_transferable": ["FTR-001"],
        "no_result_recorded": ["FTST-008"],
        "clean_pass": ["FTR-004", "FTR-005", "FTR-008"],
    },
    "known_unknowns": CHANGES[0]["unrecorded_design_inputs"],
}


def envelope(entity: str, description: str, records: list) -> dict:
    return {"entity": entity, "description": description,
            "data_classification": CLASSIFICATION, "generated_by": GENERATOR,
            "seed": SEED, "records": records}


def write(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main() -> int:
    for _, entity, _, records in COLLECTIONS:
        for record in records:
            record["record_type"] = entity
            TYPE_OF[record["id"]] = entity
    edges = relationships()

    problems = [f"{e['source_id']} -> {e['target_id']}" for e in edges
                if e["source_id"] not in TYPE_OF or e["target_id"] not in TYPE_OF]
    for test in TESTS:
        if not test["acceptance_criterion_established"] and test["acceptance_criterion"]:
            problems.append(f"{test['id']}: criterion present but not established")
    if problems:
        print("integrity problems:", problems)
        return 1

    data = os.path.join(PACK, "data")
    inventory = []
    for filename, entity, description, records in COLLECTIONS:
        write(os.path.join(data, filename), envelope(entity, description, records))
        inventory.append({"file": filename, "entity": entity, "records": len(records)})
    write(os.path.join(data, "relationships.json"),
          envelope("Relationship", "Directed relationship graph for the synthetic corpus.", edges))
    inventory.append({"file": "relationships.json", "entity": "Relationship",
                      "records": len(edges)})
    write(os.path.join(data, "dataset-inventory.json"),
          envelope("Inventory", "Record counts per collection.", inventory))

    scenario = {**SCENARIO, "data_classification": CLASSIFICATION,
                "generated_by": GENERATOR, "seed": SEED}
    write(os.path.join(PACK, "scenarios", "SCN-F01.json"), scenario)
    write(os.path.join(PACK, "scenarios", "index.json"),
          envelope("Scenario", "Scenarios available in the fire-engineering demonstrator.",
                   [{k: SCENARIO[k] for k in ("scenario_id", "category", "title", "one_liner")}]))

    for row in inventory:
        print(f"  {row['file']:28} {row['records']:4} {row['entity']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
