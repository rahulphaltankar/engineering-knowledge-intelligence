"""The full Engineering Output catalogue - all 25 deliverables.

The product's capability model is 25 engineering deliverables produced by ONE
intelligence layer. All 25 are visible; each carries an honest status resolved
from the actual workflow registry and the actual retrieved context.

Status vocabulary
-----------------
AVAILABLE       a definition exists and the current context supports it
READY           a definition exists; run an analysis to make it available
REQUIRES DATA   a definition exists but the context is missing entity types
NOT APPLICABLE  the entity types this output needs are absent from this
                analysis, so producing it would be meaningless
PLANNED         no workflow definition exists yet

An output is never shown as executable when it is not. That honesty is the
point: a reviewer who clicks a tile and gets a hollow document learns more
about the product than any slide could undo.
"""
from __future__ import annotations

# (id, name, category, description, required_context_types, upstream_skills)
OUTPUT_CATALOGUE: tuple[tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    # -- Engineering understanding -----------------------------------------
    ("engineering_impact_assessment", "Engineering Impact Assessment",
     "Engineering understanding",
     "What the change affects, which systems it reaches and by what path.",
     ("EngineeringChange", "System", "Requirement", "FailureMode"),
     ("automotive-engineer", "dfmea-design")),
    ("requirements_impact_analysis", "Requirements Impact Analysis",
     "Engineering understanding",
     "Which requirements are affected, directly or through allocation.",
     ("Requirement", "EngineeringChange"), ("apqp",)),
    ("engineering_change_impact", "Engineering Change Impact",
     "Engineering understanding",
     "Cross-system consequences, build-level effects and concurrent-change interaction.",
     ("EngineeringChange", "Component", "Configuration"), ("automotive-engineer",)),
    ("failure_mode_analysis", "Failure Mode Analysis",
     "Engineering understanding",
     "Failure modes, causes and effects, including modes absent from the existing FMEA.",
     ("FailureMode", "Component"), ("dfmea-design", "pfmea-process")),
    ("risk_assessment", "Risk Assessment",
     "Engineering understanding",
     "Ranked risk with the basis for the ranking stated.",
     ("Risk", "FailureMode"), ("action-priority-ap", "dfmea-design")),
    ("design_review", "Design Review",
     "Engineering understanding",
     "Gate readiness: requirement baseline, evidence adequacy and open risk.",
     ("Requirement", "System", "Document"), ("apqp",)),

    # -- Quality and problem solving ---------------------------------------
    ("dfmea_review", "DFMEA Review", "Quality and problem solving",
     "Gap audit of the design FMEA against the impacted scope.",
     ("FMEA", "FailureMode"), ("fmea-reviewer", "dfmea-design")),
    ("pfmea_review", "PFMEA Review", "Quality and problem solving",
     "Process FMEA review including control-plan linkage.",
     ("FMEA", "FailureMode", "Subsystem"), ("fmea-reviewer", "pfmea-process")),
    ("root_cause_analysis", "Root Cause Analysis", "Quality and problem solving",
     "Ranked hypotheses with the evidence for and against each.",
     ("QualityIssue", "FailureMode", "TestResult"),
     ("rca-facilitator", "quality-problem-zeroing")),
    ("five_why", "5-Why", "Quality and problem solving",
     "Evidence-backed why-chain that does not stop at operator error.",
     ("QualityIssue", "RootCause"), ("5why-root-cause",)),
    ("fishbone", "Fishbone Analysis", "Quality and problem solving",
     "Causes grouped by category, with unexplored categories shown as unexplored.",
     ("QualityIssue", "FailureMode"), ("fishbone-analysis",)),
    ("eight_d", "8D", "Quality and problem solving",
     "D0-D8 structured problem solving with containment and prevention verified.",
     ("QualityIssue", "RootCause", "CorrectiveAction"),
     ("8d-coach", "8d-problem-solving")),
    ("corrective_action_plan", "Corrective Action Plan", "Quality and problem solving",
     "Containment, corrective and preventive actions with effectiveness verification.",
     ("QualityIssue", "RootCause"), ("car-corrective-action",)),
    ("supplier_quality_assessment", "Supplier Quality Assessment",
     "Quality and problem solving",
     "Supplier risk and escalation justified by history and containment state.",
     ("Supplier", "SupplierIssue", "Component"), ("supplier-scar", "ppap-checker")),

    # -- Verification and validation ---------------------------------------
    ("dvpr", "DVP&R", "Verification and validation",
     "Verification rows traced to failure modes. Never invents an acceptance criterion.",
     ("Requirement", "TestCase", "FailureMode"), ("dvp-test-plan", "apqp")),
    ("verification_plan", "Verification Plan", "Verification and validation",
     "Verification against requirements, reusing coverage that already exists.",
     ("Requirement", "TestCase"), ("dvp-test-plan",)),
    ("validation_plan", "Validation Plan", "Verification and validation",
     "Validation against intended use and worst-case customer usage.",
     ("Requirement", "Vehicle", "Configuration"), ("apqp",)),
    ("test_strategy", "Test Strategy", "Verification and validation",
     "What to test, in what order, and why - prioritised by risk and gap.",
     ("FailureMode", "TestCase"), ("dvp-test-plan", "is-is-not-scoping")),
    ("test_case_recommendations", "Test Case Recommendations",
     "Verification and validation",
     "Candidate test cases with objective, conditions and failure-mode linkage.",
     ("FailureMode", "TestCase"), ("dvp-test-plan",)),

    # -- Evidence and traceability -----------------------------------------
    ("evidence_gap_analysis", "Evidence Gap Analysis", "Evidence and traceability",
     "What evidence exists, what is missing, and precisely why.",
     ("Requirement", "TestCase", "TestResult"), ("dvp-test-plan",)),
    ("traceability_matrix", "Traceability Matrix", "Evidence and traceability",
     "Requirement to failure mode to test to result to evidence. Fully deterministic.",
     ("Requirement", "TestCase", "Evidence"), ()),
    ("regression_impact_analysis", "Regression Impact Analysis",
     "Evidence and traceability",
     "Which completed verification this change invalidates, and why.",
     ("TestCase", "TestResult", "Configuration"), ()),
    ("compliance_standards_impact", "Compliance / Standards Impact",
     "Evidence and traceability",
     "Standards traceability and missing approval evidence. Holds no clause text.",
     ("Standard", "Requirement"),
     ("iatf-16949-audit", "iso-9001-internal-audit", "vda-6-3-audit")),

    # -- Executive ---------------------------------------------------------
    ("engineering_executive_summary", "Engineering Executive Summary", "Executive",
     "The conclusion first, with uncertainty preserved rather than dropped.",
     ("Requirement", "TestResult"), ()),
    ("engineering_decision_brief", "Engineering Decision Brief", "Executive",
     "The decision required, the options, and what evidence is still missing.",
     ("Requirement", "TestResult"), ()),
)

CATEGORY_ORDER = ("Engineering understanding", "Quality and problem solving",
                  "Verification and validation", "Evidence and traceability",
                  "Executive")

# Internal entity types are a property of the data model, not of engineering.
# A reader seeing "this analysis contains no RootCause" is being shown a
# Python class name; what they need to be told is that no root-cause record was
# reached. The semantics are identical - only the vocabulary changes.
PLAIN_TYPE_NAMES: dict[str, str] = {
    "EngineeringChange": "engineering change",
    "System": "system",
    "Subsystem": "subsystem",
    "Component": "component",
    "Configuration": "build configuration",
    "Requirement": "requirement",
    "FailureMode": "failure mode",
    "FMEA": "FMEA",
    "Risk": "assessed risk",
    "Document": "engineering document",
    "QualityIssue": "quality issue",
    "RootCause": "root-cause record",
    "CorrectiveAction": "corrective action",
    "Supplier": "supplier",
    "SupplierIssue": "supplier-quality issue",
    "TestCase": "test case",
    "TestResult": "test result",
    "Evidence": "evidence record",
    "Standard": "standard",
    "Vehicle": "vehicle programme",
}


def plain(entity_type: str) -> str:
    """Reader-facing name for an internal entity type."""
    return PLAIN_TYPE_NAMES.get(entity_type, entity_type)


def plain_list(types: list[str] | tuple[str, ...], conjunction: str = "or") -> str:
    """'a test case', 'a test case or a test result', 'a, b or c'."""
    names = [plain(t) for t in types]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {conjunction} " + names[-1]


def resolve_status(implemented: bool, has_analysis: bool,
                   present_types: set[str],
                   required: tuple[str, ...]) -> tuple[str, str]:
    """(status, reason) resolved from real registry and real context state."""
    missing = [t for t in required if t not in present_types]

    if not has_analysis:
        if implemented:
            return "READY", "Run an analysis to make this output available."
        return "PLANNED", "Workflow definition not yet authored."

    if missing:
        if implemented:
            return "REQUIRES DATA", ("No " + plain_list(missing)
                                     + " is present in the current analysis "
                                       "scope.")
        return "NOT APPLICABLE", ("No " + plain_list(missing)
                                  + " is present in the current analysis scope, "
                                    "so this output would have nothing to "
                                    "report.")

    if implemented:
        return "AVAILABLE", "Generated from the current analysis context."
    return "PLANNED", ("The context supports this output; the workflow "
                       "definition is not yet authored.")


def build_catalogue(registry, present_types: set[str],
                    has_analysis: bool, profile=None) -> list[dict]:
    """`profile` (a DomainProfile) renames outputs for its domain and marks which
    outputs the domain considers relevant. The 25 ids and their status rules do
    not change per domain."""
    names = getattr(profile, "catalogue_names", None) or {}
    relevant = set(getattr(profile, "outputs", None) or [])
    rows = []
    for (oid, name, category, description, required, skills) in OUTPUT_CATALOGUE:
        definition = registry.get(oid)
        implemented = definition is not None and bool(definition.sections)
        status, reason = resolve_status(implemented, has_analysis,
                                        present_types, required)
        variant = profile.workflow_variant(oid) if profile is not None else {}
        rows.append({
            "id": oid, "name": names.get(oid) or variant.get("name") or name,
            "category": category,
            "description": " ".join(str(variant.get("description") or description).split()),
            "domain_relevant": not relevant or oid in relevant,
            "required_context_types": list(required),
            "upstream_skills": list(variant.get("upstream_skills") or skills),
            "implemented": implemented,
            "maturity": definition.maturity if definition else "planned",
            "status": status, "reason": reason,
            "executable": status == "AVAILABLE",
        })
    rows.sort(key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["name"]))
    return rows


def catalogue_summary(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"total": len(rows), "by_status": counts,
            "implemented": sum(1 for r in rows if r["implemented"]),
            "executable": sum(1 for r in rows if r["executable"])}
