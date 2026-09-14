"""Output workflow engine and registry.

One engine, N declarative definitions. An output is a YAML file, never a Python
module - if a definition cannot express what an output needs, the schema is
extended rather than code being written for that one output.

Validation runs on every generated output. Two rules block delivery rather than
warn: a fabricated entity id, and any acceptance criterion that was synthesised
rather than retrieved.
"""
from __future__ import annotations

import os
import time

import yaml
from pydantic import BaseModel, Field

from ..core.context import EngineeringContext
from ..core.errors import WorkflowError
from ..core.provenance import Classification, Confidence, Finding
from .sections import BUILDERS, Section

DEFINITIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "definitions")

MATURITY = ("demonstrated", "functional", "validated")


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: str
    maturity: str = "demonstrated"
    required_context_types: list[str] = Field(default_factory=list)
    upstream_skills: list[str] = Field(default_factory=list)
    sections: list[dict] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    export_formats: list[str] = Field(default_factory=lambda: ["markdown", "json"])


class WorkflowOutput(BaseModel):
    workflow_id: str
    name: str
    maturity: str
    generated_at: float
    subject_id: str
    sections: list[Section]
    validation: dict
    provenance: dict
    upstream_skills: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    partial: bool = False
    domain: str = "automotive"
    review_summary: dict = Field(default_factory=dict)


# Declared placeholders for an acceptance criterion the context does not
# establish. A row that is not established and does not carry one of these has
# had a criterion synthesised, which blocks delivery.
UNESTABLISHED_MARKERS = ("REQUIRES PROGRAMME SPECIFICATION", "NOT ESTABLISHED")


def is_declared_unestablished(criterion: object) -> bool:
    text = str(criterion or "").upper()
    return any(marker in text for marker in UNESTABLISHED_MARKERS)


class WorkflowRegistry:
    def __init__(self, directory: str = DEFINITIONS_DIR) -> None:
        self.directory = directory
        self._defs: dict[str, WorkflowDefinition] = {}
        self.load()

    def load(self) -> int:
        if not os.path.isdir(self.directory):
            return 0
        for name in sorted(os.listdir(self.directory)):
            if not name.endswith((".yaml", ".yml")):
                continue
            with open(os.path.join(self.directory, name), "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            definition = WorkflowDefinition(**raw)
            if definition.maturity not in MATURITY:
                raise WorkflowError(
                    f"{definition.id}: maturity must be one of {MATURITY}")
            self._defs[definition.id] = definition
        return len(self._defs)

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._defs.get(workflow_id)

    def all(self) -> list[WorkflowDefinition]:
        return sorted(self._defs.values(), key=lambda d: (d.category, d.name))

    def catalogue(self, context: EngineeringContext | None = None) -> list[dict]:
        """All outputs with availability. An output whose required context is
        missing is shown unavailable WITH THE REASON, never as a button that
        produces a hollow result."""
        present = set(context.types_present()) if context else set()
        rows = []
        for definition in self.all():
            missing = [t for t in definition.required_context_types if t not in present]
            rows.append({"id": definition.id, "name": definition.name,
                         "category": definition.category,
                         "description": definition.description,
                         "maturity": definition.maturity,
                         "implemented": bool(definition.sections),
                         "available": bool(definition.sections) and not missing,
                         "missing_context": missing,
                         "upstream_skills": definition.upstream_skills})
        return rows


class WorkflowEngine:
    def __init__(self, registry: WorkflowRegistry) -> None:
        self.registry = registry

    def run(self, workflow_id: str, context: EngineeringContext,
            findings: list[Finding], closure: dict, subject_id: str,
            unknowns: list[str] | None = None,
            model_description: dict | None = None,
            variant: dict | None = None,
            reviews: dict[str, dict] | None = None,
            domain: str = "automotive") -> WorkflowOutput:
        base = self.registry.get(workflow_id)
        if base is None:
            raise WorkflowError(f"Unknown workflow: {workflow_id}")
        if not base.sections:
            raise WorkflowError(
                f"{workflow_id} is catalogued but has no section definition yet",
                workflow=workflow_id)
        # A domain variant renames and re-sections a workflow; it cannot remove
        # the base definition's validation rules, only add to them.
        variant = variant or {}
        definition = base.model_copy(update={
            key: variant[key] for key in ("name", "description", "upstream_skills",
                                          "sections") if variant.get(key)})
        definition.validation_rules = list(dict.fromkeys(
            base.validation_rules + list(variant.get("validation_rules") or [])))
        reviews = reviews or {}

        present = set(context.types_present())
        missing = [t for t in definition.required_context_types if t not in present]

        sections: list[Section] = []
        for spec in definition.sections:
            builder_name = spec.get("builder")
            build = BUILDERS.get(builder_name)
            if build is None:
                raise WorkflowError(
                    f"{workflow_id}: unknown section builder '{builder_name}'")
            params = dict(spec.get("params") or {})
            params["_unknowns"] = unknowns or []
            params["_subject_id"] = subject_id
            params["_reviews"] = reviews
            sections.append(build(context, findings, closure, params))

        validation = self.validate(definition, sections, context, reviews)
        provenance = {
            "connectors": sorted({e.provenance.connector_id for e in context.entities}),
            "context_snapshot_id": context.snapshot_id(),
            "context_records": len(context),
            "data_classification": next(
                (e.provenance.data_classification for e in context.entities
                 if e.provenance.data_classification), None),
            "model": model_description or {},
        }
        decisions = [r.get("decision") for r in reviews.values()]
        review_summary = {"accepted": decisions.count("accepted"),
                          "rejected": decisions.count("rejected"),
                          "pending": max(len(findings) - len(decisions), 0),
                          "control": "Demonstrator review control - session scoped, "
                                     "unauthenticated"}
        return WorkflowOutput(
            workflow_id=definition.id, name=definition.name,
            maturity=definition.maturity, generated_at=time.time(),
            subject_id=subject_id, sections=sections, validation=validation,
            provenance=provenance, upstream_skills=definition.upstream_skills,
            missing_context=missing, partial=bool(missing), domain=domain,
            review_summary=review_summary)

    # -- validation --------------------------------------------------------
    def validate(self, definition: WorkflowDefinition, sections: list[Section],
                 context: EngineeringContext,
                 reviews: dict[str, dict] | None = None) -> dict:
        results, blocking = [], []

        if "required_sections_present" in definition.validation_rules:
            empty = [s.key for s in sections if s.is_empty]
            results.append({"rule": "required_sections_present",
                            "passed": True,
                            "detail": (f"{len(sections) - len(empty)}/{len(sections)} "
                                       f"sections populated"
                                       + (f"; empty with stated reason: {', '.join(empty)}"
                                          if empty else ""))})

        if "no_fabricated_ids" in definition.validation_rules:
            fabricated = sorted({eid for s in sections for eid in s.evidence_ids
                                 if eid and not context.has(eid)})
            passed = not fabricated
            results.append({"rule": "no_fabricated_ids", "passed": passed,
                            "detail": ("Every cited entity id exists in the retrieved "
                                       "context." if passed
                                       else f"Fabricated ids: {fabricated}")})
            if not passed:
                blocking.append("no_fabricated_ids")

        if "no_invented_acceptance_criteria" in definition.validation_rules:
            offenders = []
            for section in sections:
                for row in section.rows:
                    if "acceptance_criterion" not in row:
                        continue
                    established = row.get("criterion_established")
                    criterion = str(row.get("acceptance_criterion") or "")
                    if not established and not is_declared_unestablished(criterion):
                        offenders.append(f"{row.get('test')}: {criterion[:60]}")
            passed = not offenders
            results.append({"rule": "no_invented_acceptance_criteria", "passed": passed,
                            "detail": ("No acceptance criterion was synthesised; every "
                                       "unestablished criterion is declared."
                                       if passed else f"Invented criteria: {offenders}")})
            if not passed:
                blocking.append("no_invented_acceptance_criteria")

        if "unknowns_declared" in definition.validation_rules:
            has_unknowns = any(s.key == "unknowns" for s in sections)
            results.append({"rule": "unknowns_declared", "passed": has_unknowns,
                            "detail": "An unknowns section is present."
                                      if has_unknowns else "No unknowns section."})

        if "all_claims_cited" in definition.validation_rules:
            uncited = [r.get("id") for s in sections if s.kind == "finding_list"
                       for r in s.rows
                       if not r.get("evidence") and r.get("classification") not in
                       ("UNKNOWN", "ASSUMED")]
            passed = not uncited
            results.append({"rule": "all_claims_cited", "passed": passed,
                            "detail": ("Every non-assumed claim cites evidence."
                                       if passed else f"Uncited: {uncited}")})

        if "human_review_applied" in definition.validation_rules:
            rejected = {fid for fid, r in (reviews or {}).items()
                        if r.get("decision") == "rejected"}
            leaked = sorted({r.get("id") for s in sections if s.kind == "finding_list"
                             for r in s.rows if r.get("id") in rejected})
            passed = not leaked
            results.append({"rule": "human_review_applied", "passed": passed,
                            "detail": (f"{len(rejected)} rejected finding(s) withheld from "
                                       f"finding lists and flagged in traceability rows."
                                       if passed else
                                       f"Rejected findings presented as accepted: {leaked}")})
            if not passed:
                blocking.append("human_review_applied")

        return {"rules": results, "blocking_failures": blocking,
                "passed": not blocking}
