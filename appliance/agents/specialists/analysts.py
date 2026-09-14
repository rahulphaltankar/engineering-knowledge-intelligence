"""The four specialists used by the change-impact pipeline.

Each derives findings deterministically from the engineering graph, then
optionally adds model interpretation. None of them contains engineering
methodology in Python - the methodology lives in the vendored upstream skills,
and the deterministic parts here are graph and set operations, not domain rules.
"""
from __future__ import annotations

from ...core.context import EngineeringContext
from ...core.provenance import Classification, EvidenceRef, Finding
from .base import Specialist


def _refs(context: EngineeringContext, ids: list[str],
          closure: dict[str, list[str]] | None = None) -> list[EvidenceRef]:
    out = []
    # One reference per record: a result cited once per requirement it bears on
    # is still one item of evidence, and must not inflate confidence.
    for eid in dict.fromkeys(ids):
        ref = context.evidence_ref(eid, (closure or {}).get(eid))
        if ref is not None:
            out.append(ref)
    return out


class DomainSpecialist(Specialist):
    """The DOMAIN role: cross-system reach of a change, in any domain.

    Which systems a change reaches, and by what path, is graph traversal and is
    identical for a vehicle and a building. Subclasses add only the reasoning
    their domain's data makes possible.
    """

    key = "domain"

    def impacted_system_findings(self, context, subject_id, closure) -> list[Finding]:
        findings: list[Finding] = []
        change = context.get(subject_id)
        if change is None:
            return findings

        # Which systems does the change actually reach, and by what path?
        systems = [context.get(eid) for eid in closure
                   if context.get(eid) and context.get(eid).entity_type == "System"]
        primary = change.get("primary_system_id")
        for system in sorted(systems, key=lambda s: s.id):
            path = closure.get(system.id, [])
            hops = len(path)
            direct = system.id == primary
            refs = _refs(context, [change.id, system.id], closure)
            findings.append(self.make_finding(
                f"{system.title} is impacted by {change.id}"
                + ("" if direct else f" through a {hops}-hop relationship path"),
                refs, self.display_name,
                rationale=(" then ".join(path) if path
                           else "Named directly as the primary system of the change."),
                tags=["impacted_system", "direct" if direct else "cross_domain"],
                detail={"system_id": system.id, "hops": hops,
                        "domain": system.get("domain"), "direct": direct},
                prefix="IMP"))
        return findings


class AutomotiveSpecialist(DomainSpecialist):
    """Vehicle-level cross-system reasoning, backed by the upstream
    automotive-engineer operating model."""

    display_name = "Automotive Engineer"
    domain = "vehicle systems"

    def derive(self, context, subject_id, closure) -> list[Finding]:
        change = context.get(subject_id)
        if change is None:
            return []
        findings = self.impacted_system_findings(context, subject_id, closure)

        # Concurrent changes competing for the same budget. Assessing each change
        # in isolation is the classic way a mass budget quietly breaks.
        others = [context.get(eid) for eid in closure
                  if context.get(eid)
                  and context.get(eid).entity_type == "EngineeringChange"
                  and eid != subject_id]
        mass_related = [c for c in others
                        if any(k in ((c.get("description") or "") + c.title).lower()
                               for k in ("mass", "wheel", "tyre", "battery",
                                         "capacity", "relocat"))]
        if mass_related:
            ids = [change.id] + [c.id for c in mass_related]
            findings.append(self.make_finding(
                f"{len(mass_related)} concurrent engineering change(s) in scope also "
                f"affect vehicle mass or its distribution: "
                f"{', '.join(c.id for c in mass_related)}. Mass budget must be "
                f"assessed across all of them together, not per change.",
                _refs(context, ids, closure), self.display_name,
                rationale="Concurrent changes reached through the programme graph "
                          "that independently affect the same vehicle budget.",
                tags=["concurrent_change", "mass_budget"],
                detail={"changes": [c.id for c in mass_related]},
                prefix="IMP"))
        return findings


class RequirementsSpecialist(Specialist):
    """Requirement impact and baseline status."""

    key = "requirements"
    display_name = "Requirements Analyst"
    domain = "requirements"

    def derive(self, context, subject_id, closure) -> list[Finding]:
        findings: list[Finding] = []
        change = context.get(subject_id)
        if change is None:
            return findings

        affected = [context.get(eid) for eid in closure
                    if context.get(eid) and context.get(eid).entity_type == "Requirement"]
        if not affected:
            return findings

        inferred_targets = {r.target_id for r in context.relationships
                            if r.source_id == subject_id and r.inferred}
        direct = [r for r in affected if r.id not in inferred_targets]
        via_allocation = [r for r in affected if r.id in inferred_targets]

        findings.append(self.make_finding(
            f"{len(affected)} requirement(s) are in the impact scope of {change.id}: "
            f"{len(direct)} stated directly, {len(via_allocation)} inferred through "
            f"allocation.",
            _refs(context, [change.id] + [r.id for r in affected[:8]], closure),
            self.display_name,
            rationale="Requirements reached from the change through the "
                      "allocation and derivation graph.",
            tags=["requirements_impact"],
            inferred_edge=bool(via_allocation),
            detail={"total": len(affected), "direct": [r.id for r in direct],
                    "inferred": [r.id for r in via_allocation]},
            prefix="REQ"))

        # An unbaselined requirement is a different risk from an approved one.
        unbaselined = [r for r in affected if not r.is_approved]
        if unbaselined:
            findings.append(self.make_finding(
                f"{len(unbaselined)} affected requirement(s) are not yet baselined "
                f"(status not approved): "
                f"{', '.join(sorted(r.id for r in unbaselined)[:6])}"
                + (" ..." if len(unbaselined) > 6 else "")
                + ". A change assessed against an unbaselined requirement carries "
                  "different risk from one assessed against an approved requirement.",
                _refs(context, [r.id for r in unbaselined[:8]], closure),
                self.display_name,
                rationale="Requirement status read directly from the retrieved records.",
                tags=["requirements_impact", "baseline_risk"],
                detail={"requirements": sorted(r.id for r in unbaselined)},
                prefix="REQ"))

        # Safety-integrity requirements deserve separate visibility.
        safety = [r for r in affected
                  if str(r.get("asil") or "").upper().startswith("ASIL")]
        if safety:
            findings.append(self.make_finding(
                f"{len(safety)} affected requirement(s) carry a safety integrity "
                f"allocation: "
                + ", ".join(f"{r.id} ({r.get('asil')})" for r in sorted(safety, key=lambda x: x.id)[:6]),
                _refs(context, [r.id for r in safety[:8]], closure), self.display_name,
                rationale="ASIL allocation read directly from the requirement records.",
                tags=["requirements_impact", "functional_safety"],
                detail={"requirements": sorted(r.id for r in safety)},
                prefix="REQ"))
        return findings


class QualityRiskSpecialist(Specialist):
    """Failure modes and risk, backed by the upstream FMEA skills."""

    key = "quality"
    display_name = "Quality / FMEA Analyst"
    domain = "quality and risk"

    def derive(self, context, subject_id, closure) -> list[Finding]:
        findings: list[Finding] = []
        modes = [context.get(eid) for eid in closure
                 if context.get(eid) and context.get(eid).entity_type == "FailureMode"]
        if not modes:
            return findings

        high = [m for m in modes if str(m.get("action_priority")).upper() == "H"]
        medium = [m for m in modes if str(m.get("action_priority")).upper() == "M"]
        mode_word = self.term("failure_mode", "failure mode")
        priority = self.term("action_priority", "action priority")
        findings.append(self.make_finding(
            f"{len(modes)} {mode_word}(s) are associated with the impacted scope: "
            f"{len(high)} at high {priority}, {len(medium)} at medium.",
            _refs(context, [m.id for m in (high + medium)[:8]], closure),
            self.display_name,
            rationale=f"{mode_word[0].upper() + mode_word[1:]}s reached from impacted "
                      f"components, subsystems and systems through the "
                      f"{self.term('risk_graph', 'FMEA graph')}.",
            tags=["failure_modes"],
            detail={"total": len(modes), "high": [m.id for m in high],
                    "medium": [m.id for m in medium]},
            prefix="FM"))

        # Surface the highest action priority present. If nothing is at H, the
        # top medium items by severity are still the risks an engineer must see -
        # reporting an empty risk table when severity-10 modes are in scope would
        # be misleading.
        ranked = high if high else medium
        band = "High" if high else "Medium"
        for mode in sorted(ranked, key=lambda m: (-int(m.get("severity") or 0), m.id))[:6]:
            # Ratings are quoted only when the source record carries them. A
            # dataset without S/O/D ratings must not acquire them in the prose.
            rated = all(mode.get(k) is not None
                        for k in ("severity", "occurrence", "detection"))
            rating = (f"(S{mode.get('severity')}/O{mode.get('occurrence')}"
                      f"/D{mode.get('detection')}) " if rated else "")
            method = mode.get("action_priority_method") or (
                "the source dataset's documented local heuristic; the AIAG-VDA "
                "action priority tables are not reproduced")
            findings.append(self.make_finding(
                f"{band} {priority}: {mode.get('failure_mode')} "
                f"{rating}- {mode.get('failure_effect')}",
                _refs(context, [mode.id], closure), self.display_name,
                rationale=f"Highest {priority} band present in scope is "
                          f"{band.upper()[0]}. {priority[0].upper() + priority[1:]} "
                          f"{mode.get('action_priority')} assigned by {method}.",
                tags=["risk", "high_action_priority"],
                detail={"failure_mode_id": mode.id,
                        "severity": mode.get("severity"),
                        "cause": mode.get("failure_cause"),
                        "control": mode.get("prevention_control")},
                prefix="RSK"))

        # Failure modes with no verifying test are the gap worth surfacing.
        verified = {r.source_id for r in context.relationships
                    if r.relationship == "VERIFIED_BY" and r.source_type == "FailureMode"}
        unverified = [m for m in high + medium if m.id not in verified]
        if unverified:
            findings.append(self.make_finding(
                f"{len(unverified)} {mode_word}(s) at medium or high {priority} "
                f"have no {self.term('verifying_test', 'verifying test')} in the "
                f"retrieved context: {', '.join(sorted(m.id for m in unverified)[:6])}",
                _refs(context, [m.id for m in unverified[:8]], closure),
                self.display_name,
                rationale=f"No VERIFIED_BY edge from these {mode_word}s to any "
                          f"{self.term('test_case', 'test case')} present in the context.",
                tags=["risk", "verification_gap"],
                detail={"failure_modes": sorted(m.id for m in unverified)},
                prefix="RSK"))
        return findings


class EvidenceSpecialist(Specialist):
    """Evidence coverage and gaps across the impacted requirements."""

    key = "evidence"
    display_name = "Evidence Analyst"
    domain = "verification evidence"

    def derive(self, context, subject_id, closure) -> list[Finding]:
        findings: list[Finding] = []
        requirements = [context.get(eid) for eid in closure
                        if context.get(eid)
                        and context.get(eid).entity_type == "Requirement"]
        if not requirements:
            return findings

        all_rows, all_gaps = [], []
        for requirement in requirements:
            assessment = context.evidence_for_requirement(requirement.id)
            all_rows.extend(assessment["rows"])
            all_gaps.extend(assessment["gaps"])

        by_type: dict[str, list[dict]] = {}
        for gap in all_gaps:
            by_type.setdefault(gap["gap_type"], []).append(gap)

        # A pass that cannot be judged against an established criterion is not
        # passing evidence, however it was recorded.
        passing = [r for r in all_rows if r["status"] == "pass" and not r["non_transferable"]
                   and r["criterion_established"]]
        findings.append(self.make_finding(
            f"{len(all_rows)} test result(s) bear on the impacted requirements; "
            f"{len(passing)} provide transferable passing evidence and "
            f"{len(all_gaps)} evidence gap(s) were identified.",
            _refs(context, [r["result_id"] for r in all_rows[:8] if r["result_id"]], closure),
            self.display_name,
            rationale="Evidence assembled by walking requirement to test to result "
                      "for every requirement in the impact scope.",
            tags=["evidence_summary"],
            detail={"rows": len(all_rows), "gaps": len(all_gaps),
                    "by_gap_type": {k: len(v) for k, v in by_type.items()}},
            prefix="EV"))

        labels = {
            "test_not_run": "no evidence exists - the test has not been executed",
            "inconclusive": "the result cannot be judged",
            "criterion_not_established": "no acceptance criterion is established",
            "evidence_not_transferable": "the passing result does not cover this case",
            "no_result_recorded": "a test is defined but no result is present",
        }
        for gap_type, gaps in sorted(by_type.items()):
            ids = [g["result_id"] or g["test_id"] for g in gaps][:8]
            unknowns = ([f"{g['test_id']}: {g['reason']}" for g in gaps[:4]]
                        if gap_type == "criterion_not_established" else [])
            findings.append(self.make_finding(
                f"{len(gaps)} requirement/test pair(s) where "
                f"{labels.get(gap_type, gap_type)}.",
                _refs(context, ids, closure), self.display_name,
                classification=(Classification.UNKNOWN
                                if gap_type == "criterion_not_established"
                                else Classification.DERIVED),
                rationale="Derived from the retrieved test results and their "
                          "acceptance criteria; no criterion has been assumed.",
                tags=["evidence_gap", gap_type],
                detail={"gap_type": gap_type,
                        "items": [{"requirement": g["requirement_id"],
                                   "test": g["test_id"], "result": g["result_id"],
                                   "reason": g["reason"]} for g in gaps]},
                unknowns=unknowns,
                prefix="GAP"))
        return findings


ALL_SPECIALISTS = (AutomotiveSpecialist, RequirementsSpecialist,
                   QualityRiskSpecialist, EvidenceSpecialist)
