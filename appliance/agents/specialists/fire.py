"""Fire-engineering domain specialist.

Fills the DOMAIN role for the fire-engineering pack. Like every specialist,
`derive()` is deterministic graph and set reasoning over the retrieved context -
it holds no fire-engineering rules. What makes a finding fire-specific is the
DATA: the change record declares the basis it moves from and to and the design
inputs it does not record; requirements declare their regulatory reference and
whether their applicability is established; evidence declares the basis it was
obtained on. The engineering judgement those attributes encode belongs to the
pack (`packs/fire-engineering`) and to the human reviewer, not to Python.

Model interpretation, when a provider is configured, is inherited unchanged
from `Specialist.interpret`: the pack's fire-engineer profile becomes system
context, the engineering context is passed as untrusted data, and anything the
evidence gate cannot verify is removed.
"""
from __future__ import annotations

from ...core.provenance import Classification, Finding
from .analysts import DomainSpecialist, _refs

# Entity types that can carry a design basis and therefore be superseded by it.
_BASIS_BEARING = ("Requirement", "Document", "Evidence", "TestResult")


def _in_closure(context, closure, entity_type):
    return sorted((e for e in (context.get(eid) for eid in closure)
                   if e is not None and e.entity_type == entity_type),
                  key=lambda e: e.id)


def _listing(ids: list[str], limit: int = 6) -> str:
    return ", ".join(ids[:limit]) + (" ..." if len(ids) > limit else "")


class FireEngineeringSpecialist(DomainSpecialist):
    display_name = "Fire Engineer"
    domain = "fire safety"

    def derive(self, context, subject_id, closure) -> list[Finding]:
        change = context.get(subject_id)
        if change is None:
            return []
        findings = self.impacted_system_findings(context, subject_id, closure)
        findings += self._classification(context, change, closure, findings)
        findings += self._applicable_requirements(context, change, closure)
        findings += self._superseded_basis(context, change, closure)
        findings += self._transferability(context, change, closure)
        findings += self._unverified_requirements(context, change, closure)
        findings += self._unrecorded_inputs(context, change, closure)
        return findings

    # -- classification ----------------------------------------------------
    def _classification(self, context, change, closure, impacted) -> list[Finding]:
        systems = [f.detail for f in impacted if f.detail.get("system_id")]
        domains = [s.get("domain") or s["system_id"] for s in systems]
        baseline, proposed = change.get("baseline_basis"), change.get("proposed_basis")
        label = change.get("change_type_label") or change.get("change_type") or "change"
        areas = change.get("affected_areas") or []
        statement = (f"{change.id} is classified as {label}"
                     + (f" from '{baseline}' to '{proposed}' use" if baseline and proposed else "")
                     + (f", affecting {'; '.join(areas)}" if areas else "")
                     + f". It reaches {len(systems)} fire-safety domain(s): "
                     + "; ".join(domains) + ".")
        return [self.make_finding(
            statement,
            _refs(context, [change.id] + [s["system_id"] for s in systems], closure),
            self.display_name,
            rationale=("Classification read from the change record's declared change type "
                       "and basis; domains are the systems reached from the change by "
                       "graph traversal. No classification is inferred from free text."),
            tags=["change_classification"],
            detail={"change_type": change.get("change_type"), "label": label,
                    "baseline_basis": baseline, "proposed_basis": proposed,
                    "affected_areas": areas,
                    "existing_conditions": change.get("existing_conditions") or [],
                    "domains": domains},
            prefix="CLS")]

    # -- applicable requirements -------------------------------------------
    def _applicable_requirements(self, context, change, closure) -> list[Finding]:
        requirements = _in_closure(context, closure, "Requirement")
        if not requirements:
            return []
        rows, standards = [], {}
        for req in requirements:
            std_ids = [s for s in (req.get("standard_ids") or []) if context.has(s)]
            for sid in std_ids:
                standards.setdefault(sid, []).append(req.id)
            rows.append({"requirement": req.id, "title": req.title,
                         "regulatory_reference": req.get("regulatory_reference") or "",
                         "standards": std_ids,
                         "applicability": req.get("applicability") or "not stated",
                         "status": req.get("status") or "",
                         "basis": req.get("basis") or ""})
        confirmed = [r for r in rows if r["applicability"] == "applies"]
        undetermined = [r for r in rows if r["applicability"] != "applies"]
        references = "; ".join(
            f"{sid} ({context.get(sid).get('identifier') or context.get(sid).title}) "
            f"-> {', '.join(req_ids)}" for sid, req_ids in sorted(standards.items()))
        findings = [self.make_finding(
            f"{len(rows)} requirement(s) apply to the scope of {change.id}: "
            f"{len(confirmed)} with applicability recorded as established and "
            f"{len(undetermined)} awaiting confirmation. They trace to "
            f"{len(standards)} regulatory or standards reference(s): {references}.",
            _refs(context, [r["requirement"] for r in rows] + sorted(standards), closure),
            self.display_name,
            rationale=("Requirements reached from the change, grouped by the standard "
                       "records they cite. Standards are held as identifiers only; no "
                       "clause text is reproduced or relied upon."),
            tags=["applicable_requirements"],
            detail={"rows": rows, "standards": {k: v for k, v in sorted(standards.items())}},
            prefix="APP")]

        for row in undetermined:
            req = context.get(row["requirement"])
            reason = req.get("applicability_note") or "Applicability is not recorded."
            findings.append(self.make_finding(
                f"Applicability of {req.id} ({req.title}) cannot be established from "
                f"the available evidence. {reason}",
                _refs(context, [req.id, change.id], closure), self.display_name,
                classification=Classification.UNKNOWN,
                rationale="The requirement record declares its applicability as not yet "
                          "established. The appliance reports this rather than deciding it.",
                tags=["applicability_unknown"],
                detail={"requirement": req.id},
                unknowns=[f"{req.id}: {reason}"],
                prefix="UNK"))
        return findings

    # -- superseded basis ----------------------------------------------------
    def _superseded_basis(self, context, change, closure) -> list[Finding]:
        superseded = context.superseded_basis
        if not superseded:
            return []
        dependent = [e for t in _BASIS_BEARING for e in _in_closure(context, closure, t)
                     if e.get("basis") in superseded]
        if not dependent:
            return []
        by_type: dict[str, list[str]] = {}
        for entity in dependent:
            by_type.setdefault(entity.entity_type, []).append(entity.id)
        summary = "; ".join(f"{t}: {', '.join(ids)}" for t, ids in by_type.items())
        return [self.make_finding(
            f"{len(dependent)} record(s) in scope were established on the superseded "
            f"'{'/'.join(sorted(superseded))}' basis ({summary}). Conclusions that rest on "
            f"them do not carry over to the proposed '{context.current_basis}' basis "
            f"without re-assessment.",
            _refs(context, [change.id] + [e.id for e in dependent], closure),
            self.display_name,
            rationale=("Set comparison of each record's declared basis against the basis "
                       f"{change.id} supersedes."),
            tags=["basis_conflict", "cross_domain"],
            detail={"records": [e.id for e in dependent], "by_type": by_type,
                    "superseded": sorted(superseded), "current": context.current_basis},
            prefix="BAS")]

    # -- evidence transferability --------------------------------------------
    def _transferability(self, context, change, closure) -> list[Finding]:
        results = _in_closure(context, closure, "TestResult")
        evidence = _in_closure(context, closure, "Evidence")
        if not results and not evidence:
            return []
        findings: list[Finding] = []
        rows = []
        by_source = {}
        for record in evidence:
            if record.get("source_record_id"):
                by_source.setdefault(record.get("source_record_id"), []).append(record.id)

        for result in results:
            test = context.get(result.get("test_id"))
            requirements = [r for r in (test.get("verifies_requirements") or [])
                            if context.has(r)] if test else []
            stale = context.is_stale(result)
            status = result.result_status or "unknown"
            reason = context.transferability_reason(result)
            rows.append({"id": result.id, "entity_type": "TestResult",
                         "title": test.title if test else result.id,
                         "test": test.id if test else None, "requirements": requirements,
                         "status": status, "basis": result.get("basis") or "not stated",
                         "transferable": not stale,
                         "evidence_records": by_source.get(result.id, []),
                         "criterion_established": (test.acceptance_criterion_established
                                                   if test else None),
                         "reason": reason or ""})
            if stale and status == "pass":
                ids = [result.id] + ([test.id] if test else []) + requirements \
                      + by_source.get(result.id, []) + [change.id]
                findings.append(self.make_finding(
                    f"Passing evidence {result.id} ({test.title if test else result.id}) "
                    f"is not transferable: {reason or 'the record is marked non-transferable.'} "
                    f"Requirement(s) {', '.join(requirements) or 'none linked'} are therefore "
                    f"not evidenced for the proposed change.",
                    _refs(context, ids, closure), self.display_name,
                    rationale=(f"{result.id} records basis '{result.get('basis')}'; "
                               f"{change.id} supersedes that basis. A pass obtained on a "
                               "superseded basis does not count as coverage."),
                    tags=["transferability", "evidence_not_transferable"],
                    detail={"result": result.id, "test": test.id if test else None,
                            "requirements": requirements,
                            "basis": result.get("basis"),
                            "current_basis": context.current_basis},
                    prefix="TRF"))

        for record in evidence:
            source = context.get(record.get("source_record_id") or "")
            if source is not None and source.entity_type == "TestResult":
                continue   # represented through its source result above
            stale = context.is_stale(record)
            rows.append({"id": record.id, "entity_type": "Evidence", "title": record.title,
                         "test": None,
                         "requirements": [r for r in (record.get("supports_requirements") or [])
                                          if context.has(r)],
                         "status": record.get("status") or "", "basis":
                         record.get("basis") or "not stated", "transferable": not stale,
                         "evidence_records": [],
                         "reason": context.transferability_reason(record) or ""})

        transferable = [r for r in rows if r["transferable"]]
        findings.insert(0, self.make_finding(
            f"{len(rows)} evidence item(s) bear on the scope of {change.id}: "
            f"{len(transferable)} transfer to the proposed basis and "
            f"{len(rows) - len(transferable)} do not.",
            _refs(context, [r["id"] for r in rows][:10], closure), self.display_name,
            rationale="Each evidence item's declared basis compared with the basis under "
                      "analysis; items without a basis are treated as basis-independent "
                      "only where the record says nothing to the contrary.",
            tags=["transferability_summary"],
            detail={"rows": rows},
            prefix="TRF"))
        return findings

    # -- verification coverage ---------------------------------------------
    def _unverified_requirements(self, context, change, closure) -> list[Finding]:
        uncovered = [r for r in _in_closure(context, closure, "Requirement")
                     if not context.tests_for_requirement(r.id)]
        if not uncovered:
            return []
        ids = [r.id for r in uncovered]
        return [self.make_finding(
            f"{len(ids)} requirement(s) in scope have no verification activity defined: "
            f"{_listing(ids)}.",
            _refs(context, ids, closure), self.display_name,
            rationale="No test case in the retrieved context lists these requirements "
                      "in verifies_requirements.",
            tags=["verification_gap"],
            detail={"requirements": ids},
            prefix="VER")]

    # -- what the change record does not say ------------------------------
    def _unrecorded_inputs(self, context, change, closure) -> list[Finding]:
        missing = change.get("unrecorded_design_inputs") or []
        if not missing:
            return []
        return [self.make_finding(
            f"{change.id} does not record {len(missing)} design input(s) the assessment "
            f"depends on: " + "; ".join(missing) + ".",
            _refs(context, [change.id], closure), self.display_name,
            classification=Classification.UNKNOWN,
            rationale="Declared as not recorded in the change record. No value has been "
                      "assumed for any of them.",
            tags=["design_input_unknown"],
            detail={"inputs": missing},
            unknowns=[f"{change.id}: {m} - not recorded" for m in missing],
            prefix="UNK")]
