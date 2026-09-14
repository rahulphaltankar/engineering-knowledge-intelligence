"""Reusable output section builders.

Deriving every output from a dozen section types is what makes 25 outputs a
configuration exercise rather than 25 applications, and what lets one renderer
and one exporter serve all of them.

Each builder is a pure function of (context, findings, closure, params) and
returns a Section carrying its own provenance and confidence. No builder
contains engineering methodology - that lives in the vendored upstream skills.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from ..core.context import EngineeringContext
from ..core.provenance import Classification, Confidence, Finding


class Section(BaseModel):
    key: str
    kind: str
    title: str
    rows: list[dict] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    text: str = ""
    columns: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    classification: Classification = Classification.DERIVED
    note: str = ""
    empty_reason: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.rows or self.items or self.text)


BUILDERS: dict[str, Callable] = {}


def builder(name: str):
    def register(fn):
        BUILDERS[name] = fn
        return fn
    return register


def _tagged(findings: list[Finding], tags: list[str] | None) -> list[Finding]:
    if not tags:
        return findings
    wanted = set(tags)
    return [f for f in findings if wanted & set(f.tags)]


# -- human review ----------------------------------------------------------
# Review state is held OUTSIDE the Finding model and handed to builders as
# params["_reviews"]: {finding_id: review record}. A builder never edits a
# finding; it decides how a reviewed finding is presented.
def _review(params: dict, finding_id: str | None) -> dict | None:
    return (params.get("_reviews") or {}).get(finding_id or "")


def _rejected(params: dict) -> set[str]:
    return {fid for fid, r in (params.get("_reviews") or {}).items()
            if r.get("decision") == "rejected"}


def _review_label(review: dict | None) -> str:
    if not review:
        return "pending review"
    label = f"{review['decision'].upper()} by {review['reviewer']}"
    return label + (f": {review['note']}" if review.get("note") else "")


def _drop_empty_columns(rows: list[dict], keep: tuple[str, ...] = ()) -> list[dict]:
    """Remove columns no row populates, so a domain whose data has no ASIL or
    S/O/D rating is not shown an empty ASIL or S/O/D column."""
    if not rows:
        return rows
    empty = [k for k in rows[0] if k not in keep
             and all(r.get(k) in (None, "", []) for r in rows)]
    return [{k: v for k, v in r.items() if k not in empty} for r in rows]


# --------------------------------------------------------------------------
@builder("finding_list")
def build_finding_list(context, findings, closure, params) -> Section:
    rejected = _rejected(params)
    tagged = _tagged(findings, params.get("tags"))
    withheld = [f for f in tagged if f.id in rejected]
    selected = [f for f in tagged if f.id not in rejected]
    limit = params.get("limit", 40)
    rows = []
    for finding in selected[:limit]:
        rows.append({"id": finding.id, "statement": finding.statement,
                     "classification": finding.classification.value,
                     "confidence": finding.confidence.value,
                     "confidence_score": finding.confidence_score,
                     "evidence": finding.evidence_ids,
                     "produced_by": ", ".join(finding.produced_by),
                     "rationale": finding.rationale,
                     "review": _review_label(_review(params, finding.id))})
    note = ""
    if withheld:
        note = (f"{len(withheld)} finding(s) withheld after reviewer rejection: "
                + ", ".join(f.id for f in withheld)
                + ". See the human review record.")
    return Section(key=params.get("key", "findings"), kind="finding_list",
                   title=params.get("title", "Findings"),
                   columns=["Finding", "Classification", "Confidence", "Evidence"],
                   rows=rows, note=note,
                   evidence_ids=sorted({e for f in selected for e in f.evidence_ids}),
                   empty_reason=("No findings of this type were produced from the "
                                 "retrieved context." if not withheld else
                                 "Every finding of this type was rejected by the reviewer.")
                                if not rows else "")


@builder("impacted_systems")
def build_impacted_systems(context, findings, closure, params) -> Section:
    rows = []
    for finding in _tagged(findings, ["impacted_system"]):
        detail = finding.detail
        rows.append({"system": detail.get("system_id"),
                     "name": (context.get(detail.get("system_id")).title
                              if context.get(detail.get("system_id")) else ""),
                     "domain": detail.get("domain") or "",
                     "hops": detail.get("hops", 0),
                     "route": "direct" if detail.get("direct") else "cross-domain",
                     "path": finding.rationale,
                     "confidence": finding.confidence.value,
                     "classification": finding.classification.value,
                     "finding_id": finding.id,
                     "review": _review_label(_review(params, finding.id))})
    rows.sort(key=lambda r: (r["hops"], r["system"] or ""))
    return Section(key="impacted_systems", kind="table",
                   title=params.get("title",
                                    "Impacted systems, with the path that justifies each"),
                   columns=["System", "Name", "Domain", "Hops", "Route", "Justifying path"],
                   rows=rows,
                   evidence_ids=[r["system"] for r in rows if r["system"]],
                   empty_reason="No system was reachable from the subject within the "
                                "configured traversal depth." if not rows else "")


@builder("requirements_impact")
def build_requirements_impact(context, findings, closure, params) -> Section:
    rows = []
    seen = set()
    for finding in _tagged(findings, ["requirements_impact"]):
        for group, label in (("direct", "stated"), ("inferred", "inferred via allocation"),
                             ("requirements", "flagged")):
            for req_id in finding.detail.get(group, []) or []:
                if req_id in seen:
                    continue
                requirement = context.get(req_id)
                if requirement is None:
                    continue
                seen.add(req_id)
                rows.append({"requirement": req_id, "title": requirement.title,
                             "level": requirement.get("level") or "",
                             "type": requirement.get("requirement_type") or "",
                             "asil": requirement.get("asil") or "",
                             "status": requirement.get("status") or "",
                             "linkage": label})
    rows.sort(key=lambda r: r["requirement"])
    rows = _drop_empty_columns(rows, keep=("requirement", "title"))
    return Section(key="requirements", kind="table",
                   title="Requirements in the impact scope",
                   columns=["Requirement", "Title", "Level", "Type", "ASIL",
                            "Status", "Linkage"],
                   rows=rows, evidence_ids=[r["requirement"] for r in rows],
                   empty_reason="No requirement was reached from the subject."
                                if not rows else "")


@builder("risk_table")
def build_risk_table(context, findings, closure, params) -> Section:
    rows = []
    for finding in _tagged(findings, ["risk"]):
        detail = finding.detail
        fm_id = detail.get("failure_mode_id")
        if fm_id:
            mode = context.get(fm_id)
            rows.append({"failure_mode": fm_id,
                         "mode": mode.get("failure_mode") if mode else "",
                         "effect": mode.get("failure_effect") if mode else "",
                         "severity": detail.get("severity") or (mode.get("severity") if mode else ""),
                         "action_priority": mode.get("action_priority") if mode else "",
                         "cause": detail.get("cause") or "",
                         "confidence": finding.confidence.value,
                         "finding_id": finding.id})
        else:
            for item in detail.get("failure_modes", []) or []:
                mode = context.get(item)
                if mode is None:
                    continue
                rows.append({"failure_mode": item,
                             "mode": mode.get("failure_mode"),
                             "effect": mode.get("failure_effect"),
                             "severity": mode.get("severity"),
                             "action_priority": mode.get("action_priority"),
                             "cause": mode.get("failure_cause"),
                             "confidence": finding.confidence.value,
                             "finding_id": finding.id})
    unique, seen = [], set()
    for row in rows:
        if row["failure_mode"] in seen:
            continue
        seen.add(row["failure_mode"])
        unique.append(row)
    unique.sort(key=lambda r: (-(int(r["severity"] or 0)), r["failure_mode"]))
    unique = _drop_empty_columns(unique, keep=("failure_mode", "mode"))
    return Section(key="risks", kind="table",
                   title=params.get("title", "Risk and failure modes"),
                   columns=["Failure mode", "Mode", "Effect", "S", "AP", "Cause"],
                   rows=unique, evidence_ids=[r["failure_mode"] for r in unique],
                   empty_reason="No failure mode was reached from the subject."
                                if not unique else "")


@builder("dvpr_table")
def build_dvpr_table(context, findings, closure, params) -> Section:
    """DVP&R rows built from the actual requirement -> failure mode -> test graph.

    THE CRITICAL BEHAVIOUR: where the context does not establish an acceptance
    criterion, the row says so. No threshold is ever synthesised. The simulation
    dataset contains six deliberately unestablished criteria to test exactly this.

    Each row also carries its full trace - requirement -> test -> result ->
    evidence record -> the findings that justify the row's action - and the
    reviewer's decision on those findings. A rejected finding withdraws the
    action it justified until it is re-assessed; the row stays visible.
    """
    placeholder = params.get("unestablished_criterion") or (
        "REQUIRES PROGRAMME SPECIFICATION - not established in the available context")
    placeholder = " ".join(str(placeholder).split())
    requirements = [context.get(eid) for eid in closure
                    if context.get(eid) and context.get(eid).entity_type == "Requirement"]

    # Evidence records by the result they were derived from.
    evidence_by_result: dict[str, list[str]] = {}
    for record in context.by_type("Evidence"):
        source = record.get("source_record_id")
        if source:
            evidence_by_result.setdefault(source, []).append(record.id)

    # Findings that justify a row, indexed by (requirement, test, result).
    justifying: dict[tuple, list[str]] = {}
    by_result: dict[str, list[str]] = {}
    for finding in findings:
        for item in finding.detail.get("items", []) or []:
            key = (item.get("requirement"), item.get("test"), item.get("result"))
            justifying.setdefault(key, []).append(finding.id)
        if finding.detail.get("result") and "transferability" in finding.tags:
            by_result.setdefault(finding.detail["result"], []).append(finding.id)

    rows = []
    unresolved = 0
    for requirement in sorted(requirements, key=lambda r: r.id):
        for test in sorted(context.tests_for_requirement(requirement.id), key=lambda t: t.id):
            results = context.results_for_test(test.id)
            fm_ids = test.get("addresses_failure_modes") or []
            if test.acceptance_criterion_established:
                criterion = test.acceptance_criterion or ""
            else:
                criterion = placeholder
                unresolved += 1
            base = {"requirement": requirement.id, "test": test.id,
                    "title": test.title, "method": test.get("method") or "",
                    "failure_modes": ", ".join(fm_ids) or "NOT LINKED",
                    "conditions": test.get("conditions") or "",
                    "acceptance_criterion": criterion,
                    "criterion_established": test.acceptance_criterion_established,
                    "sample_size": test.get("sample_size") or "",
                    "phase": test.get("phase") or ""}
            if results:
                for result in results:
                    stale = context.is_stale(result)
                    status = result.result_status or "unknown"
                    linked = list(dict.fromkeys(
                        justifying.get((requirement.id, test.id, result.id), [])
                        + by_result.get(result.id, [])))
                    rows.append(_reviewed_row({
                        **base, "result": result.id, "status": status,
                        "basis": result.get("basis") or "",
                        "transferable": not stale,
                        "evidence_records": evidence_by_result.get(result.id, []),
                        "findings": linked,
                        "action": _dvpr_action(status, stale,
                                               test.acceptance_criterion_established)},
                        params))
            else:
                linked = justifying.get((requirement.id, test.id, None), [])
                rows.append(_reviewed_row({
                    **base, "result": None, "status": "no_result", "basis": "",
                    "transferable": False, "evidence_records": [],
                    "findings": list(linked),
                    "action": "EXECUTE - no result recorded"}, params))
    rows = _drop_empty_columns(rows, keep=("requirement", "test", "result", "status",
                                           "acceptance_criterion", "criterion_established",
                                           "transferable", "findings", "action", "review"))
    held = sum(1 for r in rows if r.get("review", "").startswith("REJECTED"))
    note = (f"Every row is linked to the requirement and "
            f"{params.get('hazard_noun', 'failure modes')} that justify it. "
            f"{unresolved} row(s) have no acceptance criterion established in the "
            "available context and are marked accordingly - no threshold has been "
            "synthesised.")
    if held:
        note += (f" {held} row(s) rest on a finding the reviewer rejected; their action "
                 "is held pending re-assessment.")
    return Section(key=params.get("key", "dvpr"), kind="table",
                   title=params.get("title", "DVP&R"),
                   columns=["Requirement", "Test", "Failure modes", "Method",
                            "Acceptance criterion", "Sample", "Phase", "Status", "Action"],
                   rows=rows, note=note,
                   evidence_ids=sorted({r["test"] for r in rows}
                                       | {r["result"] for r in rows if r["result"]}
                                       | {e for r in rows for e in r.get("evidence_records", [])}),
                   classification=Classification.DERIVED,
                   empty_reason="No requirement/test pair was reachable from the subject."
                                if not rows else "")


def _reviewed_row(row: dict, params: dict) -> dict:
    """Attach the reviewer's decisions on the findings that justify a row."""
    reviews = [(fid, _review(params, fid)) for fid in row.get("findings", [])]
    rejected = [(fid, r) for fid, r in reviews if r and r["decision"] == "rejected"]
    accepted = [(fid, r) for fid, r in reviews if r and r["decision"] == "accepted"]
    if rejected:
        notes = "; ".join(f"{fid} by {r['reviewer']}: {r['note']}" for fid, r in rejected)
        row["review"] = f"REJECTED - {notes}"
        row["action"] = (f"HELD - reviewer rejected the supporting finding "
                         f"({', '.join(fid for fid, _ in rejected)}); re-assess before "
                         f"acting. Original action: {row['action']}")
    elif accepted and len(accepted) == len(reviews):
        row["review"] = "ACCEPTED - " + "; ".join(f"{fid} by {r['reviewer']}"
                                                  for fid, r in accepted)
    elif row.get("findings"):
        row["review"] = "pending review"
    else:
        row["review"] = "no finding raised"
    return row


def _dvpr_action(status: str, stale: bool, criterion_established: bool) -> str:
    if status == "not_run":
        return "EXECUTE - no evidence exists"
    if not criterion_established:
        return "ESTABLISH CRITERION before the result can be judged"
    if status == "inconclusive":
        return "RE-RUN under representative conditions"
    if status == "fail":
        return "RESOLVE - result outside acceptance criterion"
    if status == "pass" and stale:
        return "RE-RUN - existing pass does not cover this case"
    if status == "pass":
        return "ACCEPT - transferable passing evidence"
    return "REVIEW"


@builder("evidence_gaps")
def build_evidence_gaps(context, findings, closure, params) -> Section:
    rows = []
    for finding in _tagged(findings, ["evidence_gap"]):
        gap_type = finding.detail.get("gap_type", "")
        for item in finding.detail.get("items", []) or []:
            rows.append({"gap_type": gap_type,
                         "requirement": item.get("requirement"),
                         "test": item.get("test"), "result": item.get("result"),
                         "reason": item.get("reason"),
                         "finding_id": finding.id,
                         "classification": finding.classification.value,
                         "review": _review_label(_review(params, finding.id))})
    severity = {"test_not_run": 0, "criterion_not_established": 1,
                "evidence_not_transferable": 2, "inconclusive": 3, "no_result_recorded": 4}
    rows.sort(key=lambda r: (severity.get(r["gap_type"], 9), r["requirement"] or ""))
    return Section(key="gaps", kind="table", title=params.get("title", "Evidence gaps"),
                   columns=["Gap type", "Requirement", "Test", "Result", "Reason"],
                   rows=rows,
                   evidence_ids=sorted({r["test"] for r in rows if r["test"]}),
                   note="Gaps are categorised, not merely counted. "
                        "'Criterion not established' and 'evidence not transferable' "
                        "are the classes most often missed by manual review.",
                   empty_reason="No evidence gap was identified in the impact scope."
                                if not rows else "")


@builder("evidence_table")
def build_evidence_table(context, findings, closure, params) -> Section:
    rows = []
    requirements = [context.get(eid) for eid in closure
                    if context.get(eid) and context.get(eid).entity_type == "Requirement"]
    for requirement in sorted(requirements, key=lambda r: r.id):
        for row in context.evidence_for_requirement(requirement.id)["rows"]:
            rows.append({"requirement": row["requirement_id"], "test": row["test_id"],
                         "result": row["result_id"], "status": row["status"],
                         "configuration": row["configuration_id"] or "",
                         "basis": row.get("basis") or "",
                         "transferable": "no" if row["non_transferable"] else "yes",
                         "criterion_established": "yes" if row["criterion_established"] else "no",
                         "note": (row["notes"] or "")[:160]})
    rows.sort(key=lambda r: (r["requirement"], r["test"]))
    rows = _drop_empty_columns(rows, keep=("requirement", "test", "result", "status",
                                           "transferable", "criterion_established"))
    return Section(key="evidence", kind="table",
                   title=params.get("title", "Evidence available"),
                   columns=["Requirement", "Test", "Result", "Status", "Config",
                            "Transferable", "Criterion set"],
                   rows=rows,
                   evidence_ids=sorted({r["result"] for r in rows if r["result"]}),
                   empty_reason="No test evidence exists for the requirements in scope."
                                if not rows else "")


@builder("unknowns")
def build_unknowns(context, findings, closure, params) -> Section:
    items = params.get("_unknowns") or []
    return Section(key="unknowns", kind="list",
                   title=params.get("title", "What the appliance could NOT establish"),
                   items=items, classification=Classification.UNKNOWN,
                   confidence=Confidence.NONE,
                   note="Shown as prominently as the findings. Burying what the system "
                        "does not know defeats the point of measuring it.",
                   empty_reason="No explicit unknowns were recorded for this analysis."
                                if not items else "")


@builder("confidence_summary")
def build_confidence_summary(context, findings, closure, params) -> Section:
    counts: dict[str, int] = {}
    for finding in findings:
        key = f"{finding.classification.value}/{finding.confidence.value}"
        counts[key] = counts.get(key, 0) + 1
    rows = [{"classification_confidence": k, "findings": v}
            for k, v in sorted(counts.items())]
    return Section(key="confidence", kind="table",
                   title=params.get("title", "Classification and confidence distribution"),
                   columns=["Classification / confidence", "Findings"], rows=rows,
                   note="FACT retrieved directly; DERIVED computed deterministically; "
                        "INFERRED reasoned by a model; ASSUMED unsupported premise; "
                        "UNKNOWN not established.")


@builder("executive_summary")
def build_executive_summary(context, findings, closure, params) -> Section:
    impacted = _tagged(findings, ["impacted_system"])
    risks = _tagged(findings, ["risk"])
    gaps = _tagged(findings, ["evidence_gap"])
    unknowns = params.get("_unknowns") or []
    subject = context.get(params.get("_subject_id", ""))
    cross = [f for f in impacted if f.detail.get("hops", 0) > 1]

    lines = []
    if subject is not None:
        lines.append(f"**Subject:** {subject.id} - {subject.title}")
        if subject.get("description"):
            lines.append(str(subject.get("description")))
    lines.append("")
    systems_label = params.get("systems_label", "system(s)")
    lines.append(f"- **{len(impacted)} {systems_label}** are in the impact scope, of which "
                 f"**{len(cross)}** are reached only through cross-domain relationships.")
    lines.append(f"- **{len(risks)}** risk finding(s) were raised from the associated "
                 f"{params.get('hazard_noun', 'failure modes')}.")
    total_gaps = sum(len(f.detail.get('items', []) or []) for f in gaps)
    lines.append(f"- **{total_gaps}** evidence gap(s) were identified across the "
                 f"impacted requirements.")
    lines.append(f"- **{len(unknowns)}** item(s) could not be established from the "
                 f"available context and are reported as unknown.")
    reviews = params.get("_reviews") or {}
    if reviews:
        decisions = [r["decision"] for r in reviews.values()]
        lines.append(f"- Reviewer decisions recorded: **{decisions.count('accepted')}** "
                     f"accepted, **{decisions.count('rejected')}** rejected "
                     f"(demonstrator review control - session scoped, unauthenticated).")
    return Section(key="executive", kind="text",
                   title=params.get("title", "Engineering executive summary"),
                   text="\n".join(lines),
                   evidence_ids=[subject.id] if subject else [])


@builder("evidence_transferability")
def build_evidence_transferability(context, findings, closure, params) -> Section:
    """Whether each evidence item still applies to the case under analysis."""
    rows = []
    for finding in _tagged(findings, ["transferability_summary"]):
        for item in finding.detail.get("rows", []) or []:
            entity = context.get(item["id"])
            rows.append({"evidence": item["id"], "type": item["entity_type"],
                         "title": item["title"], "test": item.get("test") or "",
                         "requirements": ", ".join(item.get("requirements") or []),
                         "status": item["status"], "basis": item["basis"],
                         "transferable": "yes" if item["transferable"] else "NO",
                         "reason": item.get("reason") or "",
                         "source": (f"{entity.provenance.connector_id}:"
                                    f"{entity.provenance.source_object_id} "
                                    f"({entity.provenance.source_version})") if entity else "",
                         "finding_id": finding.id})
    basis = context.current_basis
    return Section(key="transferability", kind="table",
                   title="Evidence transferability",
                   rows=rows, evidence_ids=[r["evidence"] for r in rows],
                   note=(f"Each item's recorded basis compared with the basis under analysis"
                         + (f" ('{basis}')." if basis else ".")
                         + " A pass obtained on a superseded basis is not coverage."),
                   empty_reason="No evidence item in scope declares a basis that can be "
                                "compared." if not rows else "")


@builder("applicable_requirements")
def build_applicable_requirements(context, findings, closure, params) -> Section:
    rows = []
    for finding in _tagged(findings, ["applicable_requirements"]):
        for item in finding.detail.get("rows", []) or []:
            rows.append({"requirement": item["requirement"], "title": item["title"],
                         "regulatory_reference": item["regulatory_reference"],
                         "standards": ", ".join(
                             f"{sid} {context.get(sid).get('identifier')}"
                             for sid in item["standards"] if context.get(sid)),
                         "applicability": item["applicability"],
                         "status": item["status"], "basis": item["basis"],
                         "finding_id": finding.id})
    return Section(key="applicable_requirements", kind="table",
                   title="Applicable requirements and their references",
                   rows=rows, evidence_ids=[r["requirement"] for r in rows],
                   note="Standards are referenced by identifier and title only; no clause "
                        "text is reproduced. Applicability marked to_be_confirmed is a "
                        "reviewer decision the appliance does not make.",
                   empty_reason="No requirement was reached from the subject."
                                if not rows else "")


@builder("review_record")
def build_review_record(context, findings, closure, params) -> Section:
    """The human review audit record for this output."""
    reviews = params.get("_reviews") or {}
    rows = []
    for fid, review in sorted(reviews.items(), key=lambda kv: kv[1]["timestamp"]):
        snapshot = review.get("finding_snapshot") or {}
        rows.append({"finding": fid, "decision": review["decision"].upper(),
                     "reviewer": review["reviewer"], "timestamp": review["timestamp"],
                     "note": review.get("note") or "",
                     "statement": snapshot.get("statement", ""),
                     "classification": snapshot.get("classification", ""),
                     "confidence_score": snapshot.get("confidence_score"),
                     "evidence": ", ".join(snapshot.get("evidence_ids") or []),
                     "effect": ("withheld from finding lists; dependent actions held"
                                if review["decision"] == "rejected"
                                else "presented as reviewer-accepted")})
    return Section(key="review_record", kind="table",
                   title="Human review record",
                   rows=rows, evidence_ids=[],
                   note="Demonstrator review control - session scoped, unauthenticated. "
                        "Not production identity, approval or sign-off.",
                   empty_reason="No reviewer decision has been recorded in this session. "
                                "Findings are presented as pending review." if not rows else "")
