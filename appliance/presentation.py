"""Presentation view-models.

Information compression is a product capability, not a cosmetic layer: 956
records and 2,018 relationships have to become an engineering conclusion a
person can absorb in ten seconds.

Everything here is DERIVED from the pipeline result. Nothing is authored,
nothing is estimated, and no sentence is produced that the findings do not
support. Where the analysis establishes nothing, the summary says so.
"""
from __future__ import annotations

from .core.provenance import Classification, Finding


def _tagged(findings: list[Finding], *tags: str) -> list[Finding]:
    wanted = set(tags)
    return [f for f in findings if wanted & set(f.tags)]


GAP_LABELS = {
    "test_not_run": "Verification not executed",
    "inconclusive": "Result cannot be judged",
    "criterion_not_established": "Acceptance criterion not established",
    "evidence_not_transferable": "Existing evidence does not cover this configuration or basis",
    "no_result_recorded": "Test defined, no result recorded",
}

GAP_DETAIL = {
    "test_not_run": "No evidence exists because the test has not been run.",
    "inconclusive": "A result exists but cannot be judged against its criterion.",
    "criterion_not_established": "Requires a programme- or project-specific "
                                 "criterion. No threshold has been assumed.",
    "evidence_not_transferable": "A passing result exists but was obtained on a "
                                 "configuration or design basis that does not represent "
                                 "this change.",
    "no_result_recorded": "A test is defined but no result is present in the context.",
}

GAP_ACTION = {
    "test_not_run": "Execute",
    "inconclusive": "Re-run under representative conditions",
    "criterion_not_established": "Establish criterion",
    "evidence_not_transferable": "Re-run on the changed configuration or basis",
    "no_result_recorded": "Record or execute",
}

# Ordered by how much they should worry an engineer.
GAP_SEVERITY = ("criterion_not_established", "test_not_run",
                "evidence_not_transferable", "inconclusive", "no_result_recorded")


def executive(result: dict) -> dict:
    """Level 1 - what a decision-maker needs in ten seconds."""
    if result.get("status") != "ok":
        return {
            "answerable": False,
            "headline": "The available context does not support an answer.",
            "unknowns": result.get("unknowns", []),
        }

    context = result["context"]
    findings = result["findings"]
    subject = context.get(result["subject_id"])

    impacted = sorted(_tagged(findings, "impacted_system"),
                      key=lambda f: (f.detail.get("hops", 0),
                                     f.detail.get("system_id", "")))
    domains = []
    for finding in impacted:
        domains.append({
            "system_id": finding.detail.get("system_id"),
            "name": (context.get(finding.detail["system_id"]).title
                     if context.get(finding.detail.get("system_id")) else ""),
            "domain": finding.detail.get("domain") or "",
            "direct": bool(finding.detail.get("direct")),
            "hops": finding.detail.get("hops", 0),
            "finding_id": finding.id,
            "confidence": finding.confidence.value,
        })

    # -- gaps, grouped by class ------------------------------------------
    gap_groups: dict[str, list[dict]] = {}
    for finding in _tagged(findings, "evidence_gap"):
        gap_type = finding.detail.get("gap_type", "")
        gap_groups.setdefault(gap_type, []).extend(
            finding.detail.get("items", []) or [])
    attention = []
    for gap_type in GAP_SEVERITY:
        items = gap_groups.get(gap_type)
        if not items:
            continue
        attention.append({
            "gap_type": gap_type,
            "label": GAP_LABELS.get(gap_type, gap_type),
            "detail": GAP_DETAIL.get(gap_type, ""),
            "action": GAP_ACTION.get(gap_type, "Review"),
            "count": len(items),
            "requirements": sorted({i.get("requirement") for i in items
                                    if i.get("requirement")})[:6],
        })

    # -- evidence posture -------------------------------------------------
    evidence_summary = next(
        (f.detail for f in _tagged(findings, "evidence_summary")), {}) or {}
    supported = [f for f in findings
                 if f.evidence and f.classification is not Classification.UNKNOWN]

    # -- risk -------------------------------------------------------------
    risks = _tagged(findings, "risk")
    top_risks = []
    for finding in risks:
        fm_id = finding.detail.get("failure_mode_id")
        if not fm_id:
            continue
        mode = context.get(fm_id)
        if mode is None:
            continue
        top_risks.append({
            "id": fm_id, "mode": mode.get("failure_mode"),
            "effect": mode.get("failure_effect"),
            "severity": mode.get("severity"),
            "action_priority": mode.get("action_priority"),
            "finding_id": finding.id,
        })
    top_risks.sort(key=lambda r: -(int(r["severity"] or 0)))

    concurrent = _tagged(findings, "concurrent_change")
    safety = [f for f in _tagged(findings, "functional_safety")]

    # -- significance, from measurable properties only --------------------
    cross_domain = [d for d in domains if not d["direct"]]
    total_gaps = sum(g["count"] for g in attention)
    if cross_domain and total_gaps:
        significance = "Broad"
        significance_note = (
            f"Reaches {len(domains)} systems including {len(cross_domain)} beyond the "
            f"system named in the change, with {total_gaps} verification gaps.")
    elif domains:
        significance = "Contained"
        significance_note = f"Reaches {len(domains)} system(s) with limited gap exposure."
    else:
        significance = "Not established"
        significance_note = "No impacted system was reachable from the subject."

    # -- next action, assembled only from what was actually found ---------
    actions = []
    if attention:
        first = attention[0]
        actions.append(f"{first['action']}: {first['label'].lower()} on "
                       f"{first['count']} requirement/test pair(s).")
    if cross_domain:
        actions.append(
            f"Review the {len(cross_domain)} cross-domain system(s) reached only "
            f"through relationship paths - these are the impacts most often missed.")
    if concurrent:
        actions.append(concurrent[0].statement)
    if safety:
        actions.append(safety[0].statement)

    transfer = next((f for f in _tagged(findings, "transferability_summary")), None)
    if transfer is not None and not any("transfer" in a.lower() for a in actions):
        blocked = [r for r in transfer.detail.get("rows", []) if not r["transferable"]]
        if blocked:
            actions.append(
                f"Review whether to re-establish the {len(blocked)} evidence item(s) obtained "
                f"on a superseded basis: {', '.join(r['id'] for r in blocked)}.")

    return {
        "answerable": True,
        "domain": result.get("domain") or {},
        "knowledge": knowledge(result),
        "subject_id": result["subject_id"],
        "subject_title": subject.title if subject else result["subject_id"],
        "subject_description": (subject.get("description") if subject else "") or "",
        "subject_status": (subject.get("status") if subject else "") or "",
        "domains": domains,
        "cross_domain_count": len(cross_domain),
        "significance": significance,
        "significance_note": significance_note,
        "attention": attention,
        "total_gaps": total_gaps,
        "risks": top_risks[:5],
        "risk_count": len(top_risks),
        "supported_findings": len(supported),
        "total_findings": len(findings),
        "evidence_rows": evidence_summary.get("rows", 0),
        "unknowns": result.get("unknowns", []),
        "actions": actions,
        "execution_mode": result.get("execution_mode"),
        "duration_ms": result.get("duration_ms"),
        "context_records": len(context),
        "closure_size": len(result.get("closure", {})),
        "snapshot": result.get("context_snapshot_id"),
        "fabricated_citations": result["gate_report"]["fabricated_citation_count"],
    }


def engineering_detail(result: dict) -> dict:
    """Level 2 - what an engineer should inspect."""
    if result.get("status") != "ok":
        return {"answerable": False}
    findings = result["findings"]
    context = result["context"]

    groups = [
        ("Classification", _tagged(findings, "change_classification")),
        ("Impact", _tagged(findings, "impacted_system", "cross_domain",
                           "concurrent_change", "mass_budget")),
        ("Requirements", _tagged(findings, "requirements_impact",
                                 "applicable_requirements", "applicability_unknown")),
        ("Risk and failure modes", _tagged(findings, "risk", "failure_modes")),
        ("Evidence", _tagged(findings, "evidence_summary", "evidence_gap",
                             "transferability", "transferability_summary",
                             "verification_gap")),
        ("Not established", _tagged(findings, "design_input_unknown")),
    ]
    rendered = []
    shown: set[str] = set()
    for title, items in groups:
        # A finding appears once, under the first concern that claims it.
        items = [f for f in items if f.id not in shown]
        shown.update(f.id for f in items)
        if not items:
            continue
        rendered.append({
            "title": title,
            "findings": [{
                "id": f.id, "statement": f.statement,
                "classification": f.classification.value,
                "confidence": f.confidence.value,
                "confidence_score": f.confidence_score,
                "evidence_count": len(f.evidence),
                "produced_by": ", ".join(f.produced_by),
                "rationale": f.rationale,
            } for f in items],
        })
    return {
        "answerable": True,
        "groups": rendered,
        "context_types": context.types_present(),
        "stages": result["stages"],
        "activity": result["activity"],
        "gate": result["gate_report"],
        "ledger": result["evidence_ledger"],
        "snapshot": result["context_snapshot_id"],
    }


def knowledge(result: dict) -> dict:
    """Knowledge-presentation view-model: classification, applicable requirements,
    evidence cards with provenance and the derivation pipeline. Built only from
    findings and records; empty when a domain's specialists produce none of it."""
    context = result["context"]
    findings = result["findings"]

    classification = next((f for f in _tagged(findings, "change_classification")), None)
    applicable = next((f for f in _tagged(findings, "applicable_requirements")), None)
    transfer = next((f for f in _tagged(findings, "transferability_summary")), None)
    per_item = {f.detail.get("result"): f.id for f in _tagged(findings, "transferability")}

    cards = []
    for row in (transfer.detail.get("rows", []) if transfer else []):
        entity = context.get(row["id"])
        if entity is None:
            continue
        p = entity.provenance
        cards.append({**row,
                      "classification": entity.classification.value,
                      "finding_id": per_item.get(row["id"]) or transfer.id,
                      "provenance": {"connector_id": p.connector_id,
                                     "source_object_id": p.source_object_id,
                                     "source_version": p.source_version,
                                     "source_url": p.source_url,
                                     "retrieved_at": p.retrieved_at,
                                     "data_classification": p.data_classification}})
    cards.sort(key=lambda c: (c["transferable"], c["id"]))

    requirements = []
    for row in (applicable.detail.get("rows", []) if applicable else []):
        requirements.append({**row, "standards": [
            {"id": sid, "identifier": context.get(sid).get("identifier")}
            for sid in row["standards"] if context.get(sid)]})

    unknown_findings = [{"id": f.id, "statement": f.statement}
                        for f in findings if f.classification is Classification.UNKNOWN]
    return {
        "classification": ({"id": classification.id, **classification.detail,
                            "statement": classification.statement}
                           if classification else None),
        "requirements": requirements,
        "applicable_finding": applicable.id if applicable else None,
        "evidence_cards": cards,
        "transferable_count": sum(1 for c in cards if c["transferable"]),
        "unknown_findings": unknown_findings,
    }


def derivation_pipeline(result: dict, reviews: dict | None = None) -> list[dict]:
    """The eleven-step knowledge flow, each step populated from what actually ran.

    INPUT -> CLASSIFICATION -> APPLICABLE REQUIREMENTS -> KNOWLEDGE / RELATIONSHIPS
    -> EVIDENCE RETRIEVAL -> IMPACT / RISK -> TRANSFERABILITY -> UNKNOWN / GAPS
    -> CONFIDENCE + PROVENANCE -> HUMAN REVIEW -> VERIFICATION OUTPUT
    """
    if result.get("status") != "ok":
        return []
    context, findings, closure = result["context"], result["findings"], result["closure"]
    k = knowledge(result)
    stages = {s["name"]: s for s in result.get("stages", [])}
    reviews = reviews or {}
    decisions = [r["decision"] for r in reviews.values()]

    def count(entity_type):
        return sum(1 for eid in closure
                   if context.get(eid) and context.get(eid).entity_type == entity_type)

    systems = _tagged(findings, "impacted_system")
    hazards = [f for f in findings if context.get(f.detail.get("failure_mode_id") or "")]
    gaps = sum(len(f.detail.get("items", []) or []) for f in _tagged(findings, "evidence_gap"))
    in_scope_edges = sum(1 for r in context.relationships
                         if r.source_id in closure and r.target_id in closure)
    gate = result["gate_report"]
    cls = k["classification"]
    reqs = k["requirements"]
    return [
        {"stage": "Input", "detail": f"{result['subject_id']} - "
                                     f"{context.get(result['subject_id']).title}"},
        {"stage": "Classification",
         "detail": (f"{cls['label']} ({cls['baseline_basis']} -> {cls['proposed_basis']})"
                    if cls else stages.get("Understanding change", {}).get("detail", ""))},
        {"stage": "Applicable requirements",
         "detail": (f"{len(reqs)} requirements, "
                    f"{sum(1 for r in reqs if r['applicability'] != 'applies')} awaiting "
                    f"confirmation" if reqs else f"{count('Requirement')} requirements")},
        {"stage": "Knowledge / relationships",
         "detail": f"{len(closure)} records and {in_scope_edges} relationships reached; "
                   f"{len(systems)} domains"},
        {"stage": "Evidence retrieval",
         "detail": f"{count('TestResult')} results, {count('Evidence')} evidence records, "
                   f"{count('Document')} documents"},
        {"stage": "Impact / risk reasoning",
         "detail": f"{sum(1 for s in systems if not s.detail.get('direct'))} cross-domain "
                   f"impacts; {len(hazards)} prioritised hazards"},
        {"stage": "Evidence transferability",
         "detail": (f"{k['transferable_count']} transfer, "
                    f"{len(k['evidence_cards']) - k['transferable_count']} do not"
                    if k["evidence_cards"] else "No basis declared")},
        {"stage": "Unknown / gap detection",
         "detail": f"{gaps} evidence gaps; {len(k['unknown_findings'])} UNKNOWN findings"},
        {"stage": "Confidence + provenance",
         "detail": f"{len(findings)} findings passed the gate; "
                   f"{gate['fabricated_citation_count']} fabricated citations"},
        {"stage": "Human review",
         "detail": f"{decisions.count('accepted')} accepted, "
                   f"{decisions.count('rejected')} rejected, "
                   f"{max(len(findings) - len(decisions), 0)} pending"},
        {"stage": "Verification / action output",
         "detail": "Verification outputs available from this same context, with review "
                   "decisions applied when generated"},
    ]
