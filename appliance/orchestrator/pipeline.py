"""The bounded orchestration pipeline.

    intent -> evidence plan -> retrieval -> specialist fan-out -> synthesis
    -> evidence gate -> result

Bounded and acyclic by design. No agent-to-agent loops, no dynamic replanning,
no unbounded tool calls. That is a deliberate product decision: unpredictable
cost and latency is how agentic systems become unshippable in an enterprise.

Every stage is recorded, so the UI activity timeline shows real events rather
than a progress animation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..agents.specialists.analysts import (AutomotiveSpecialist, EvidenceSpecialist,
                                           QualityRiskSpecialist, RequirementsSpecialist)
from ..agents.specialists.base import Specialist
from ..agents.specialists.fire import FireEngineeringSpecialist
from ..connectors.registry import ConnectorRegistry
from ..core.context import EngineeringContext
from ..core.entities import EngineeringEntity
from ..core.provenance import Classification, Finding
from ..models.provider import ModelProvider
from .domain import AUTOMOTIVE, DomainProfile
from .synthesis import EvidenceGate, collect_unknowns, synthesise

# Intent taxonomy. One request commonly carries several.
INTENTS = ("change_impact", "requirements_impact", "risk_assessment",
           "evidence_gap", "verification_planning", "traceability",
           "root_cause", "regression_impact")

INTENT_KEYWORDS = {
    "change_impact": ("change", "impact", "affect", "consequence", "modif"),
    "requirements_impact": ("requirement", "spec", "baseline"),
    "risk_assessment": ("risk", "failure", "fmea", "hazard", "severity"),
    "evidence_gap": ("evidence", "gap", "missing", "unverified", "coverage"),
    "verification_planning": ("verif", "validat", "test", "dvp", "re-verif", "reverif"),
    "traceability": ("trace", "linkage", "coverage matrix"),
    "root_cause": ("root cause", "why", "investigat", "defect", "failure occurred"),
    "regression_impact": ("regression", "re-run", "rerun", "invalidat"),
}

# Which specialist ROLES serve which intent. Configuration, not code branching.
# "domain" is filled by the active domain profile's specialist - the automotive
# engineer for an automotive change, the fire engineer for a fire-safety change.
INTENT_SPECIALISTS = {
    "change_impact": ("domain", "requirements", "quality", "evidence"),
    "requirements_impact": ("requirements", "evidence"),
    "risk_assessment": ("quality", "domain"),
    "evidence_gap": ("evidence", "requirements"),
    "verification_planning": ("evidence", "quality", "requirements"),
    "traceability": ("requirements", "evidence"),
    "root_cause": ("domain", "quality", "evidence"),
    "regression_impact": ("evidence", "requirements", "domain"),
}

SPECIALIST_CLASSES = {
    "requirements": RequirementsSpecialist,
    "quality": QualityRiskSpecialist,
    "evidence": EvidenceSpecialist,
}

# The domain role's implementation, keyed by the profile's `specialist`.
DOMAIN_SPECIALISTS: dict[str, type[Specialist]] = {
    "automotive": AutomotiveSpecialist,
    "fire-engineering": FireEngineeringSpecialist,
}

# Upstream definition backing each role for the built-in automotive profile.
SPECIALIST_DEFINITION = dict(AUTOMOTIVE.definitions)


@dataclass
class StageRecord:
    name: str
    status: str = "pending"
    detail: str = ""
    duration_ms: int = 0
    items: list[str] = field(default_factory=list)


@dataclass
class Limits:
    """Hard limits. Exceeding one is a reportable outcome, not a crash."""
    max_specialists: int = 8
    max_traversal_depth: int = 2
    max_context_records: int = 2000
    max_wall_clock_s: float = 120.0


class OrchestrationPipeline:
    def __init__(self, registry: ConnectorRegistry, provider: ModelProvider,
                 skills=None, limits: Limits | None = None,
                 profile: DomainProfile | None = None,
                 connector_ids: list[str] | None = None) -> None:
        self.registry = registry
        self.provider = provider
        self.skills = skills
        self.limits = limits or Limits()
        self.profile = profile or AUTOMOTIVE
        # None = every enabled connector (the original behaviour).
        self.connector_ids = connector_ids

    # -- stage 1 -----------------------------------------------------------
    def classify_intent(self, request: str) -> list[dict]:
        text = request.lower()
        scored = []
        for intent, keywords in INTENT_KEYWORDS.items():
            hits = sum(1 for k in keywords if k in text)
            if hits:
                scored.append({"intent": intent, "score": hits})
        if not scored:
            scored = [{"intent": "change_impact", "score": 0}]
        scored.sort(key=lambda x: -x["score"])
        total = sum(s["score"] for s in scored) or 1
        for item in scored:
            item["confidence"] = round(item["score"] / total, 2)
        return scored

    # -- stage 2 -----------------------------------------------------------
    def plan_evidence(self, intents: list[str], subject_id: str) -> dict:
        required = {"change_impact": ["EngineeringChange", "System", "Subsystem",
                                      "Component", "Requirement", "FailureMode"],
                    "requirements_impact": ["Requirement", "EngineeringChange"],
                    "risk_assessment": ["FailureMode", "Risk", "FMEA"],
                    "evidence_gap": ["Requirement", "TestCase", "TestResult", "Evidence"],
                    "verification_planning": ["Requirement", "TestCase", "TestResult",
                                              "FailureMode"],
                    "traceability": ["Requirement", "TestCase", "TestResult", "Evidence"],
                    "root_cause": ["QualityIssue", "FailureMode", "TestResult"],
                    "regression_impact": ["TestCase", "TestResult", "Configuration"]}
        wanted: list[str] = []
        for intent in intents:
            for entity_type in required.get(intent, []):
                if entity_type not in wanted:
                    wanted.append(entity_type)
        return {"subject_id": subject_id, "required_entity_types": wanted,
                "traversal_depth": self.limits.max_traversal_depth}

    # -- stage 3 -----------------------------------------------------------
    def retrieve(self, subject_id: str, plan: dict) -> tuple[EngineeringContext, dict]:
        context = EngineeringContext()
        ledger = {"requested": plan["required_entity_types"], "obtained": [],
                  "unavailable": [], "no_connector_supports": [], "participation": {}}

        within = self.connector_ids
        enabled = self.registry.enabled_connectors(within)
        if not enabled:
            ledger["unavailable"] = plan["required_entity_types"]
            ledger["reason"] = "No connector is enabled."
            return context, ledger

        # Load every entity and edge the in-scope connectors expose, then build
        # the closure. At simulation scale this is fast and fully deterministic.
        for entity_type in sorted({t for c in enabled
                                   for t in c.capabilities().get("entity_types", [])}):
            for entity in self.registry.list_by_type(entity_type, within=within):
                context.add_entity(entity, reason="connector_load")
        for rel in self.registry.all_relationships(within=within):
            context.add_relationship(rel)

        # A subject that declares the basis it moves from and to makes evidence
        # transferability a set operation rather than a reading of free text.
        subject = context.get(subject_id)
        if subject is not None and subject.get("proposed_basis"):
            context.set_evidence_basis(subject.get("proposed_basis"),
                                       [subject.get("baseline_basis")])
            ledger["evidence_basis"] = {"current": context.current_basis,
                                        "superseded": sorted(context.superseded_basis)}

        obtained = set(context.types_present())
        ledger["obtained"] = sorted(obtained & set(plan["required_entity_types"]))
        ledger["unavailable"] = sorted(set(plan["required_entity_types"]) - obtained)
        ledger["participation"] = {c.connector_id: c.status().get("records_loaded", 0)
                                   for c in enabled}
        ledger["total_records"] = len(context)
        return context, ledger

    def build_closure(self, context: EngineeringContext, subject_id: str) -> dict:
        closure = context.impact_closure(
            subject_id, depth=self.limits.max_traversal_depth,
            max_records=self.limits.max_context_records)
        return context.structural_completion(closure)

    # -- stage 4 -----------------------------------------------------------
    def select_specialists(self, intents: list[str]) -> list[tuple[str, Specialist, str]]:
        keys: list[str] = []
        for intent in intents:
            for key in INTENT_SPECIALISTS.get(intent, ()):
                if key not in keys:
                    keys.append(key)
        selected = []
        profile = self.profile
        for key in keys[: self.limits.max_specialists]:
            definition = None
            if self.skills:
                definition = self.skills.get(profile.definitions.get(key, ""))
            cls = (DOMAIN_SPECIALISTS[profile.specialist] if key == "domain"
                   else SPECIALIST_CLASSES[key])
            selected.append((key, cls(self.provider, definition,
                                      display_name=profile.display_names.get(key),
                                      terms=profile.terms),
                             f"selected for intent(s): "
                             f"{', '.join(i for i in intents if key in INTENT_SPECIALISTS.get(i, ()))}"))
        return selected

    # -- full run ----------------------------------------------------------
    def run(self, request: str, subject_id: str) -> dict:
        started = time.time()
        stages: list[StageRecord] = []

        def stage(name: str) -> StageRecord:
            record = StageRecord(name=name, status="running")
            stages.append(record)
            return record

        # 1 intent
        s = stage("Understanding change")
        t0 = time.time()
        intents = self.classify_intent(request)
        intent_names = [i["intent"] for i in intents]
        s.status, s.duration_ms = "done", int((time.time() - t0) * 1000)
        s.detail = ", ".join(intent_names)
        s.items = intent_names

        # 2 evidence plan
        s = stage("Planning required evidence")
        t0 = time.time()
        plan = self.plan_evidence(intent_names, subject_id)
        s.status, s.duration_ms = "done", int((time.time() - t0) * 1000)
        s.detail = f"{len(plan['required_entity_types'])} entity types required"
        s.items = plan["required_entity_types"]

        # 3 retrieval
        s = stage("Retrieving engineering context")
        t0 = time.time()
        context, ledger = self.retrieve(subject_id, plan)
        closure = self.build_closure(context, subject_id) if len(context) else {}
        s.status = "done" if len(context) else "degraded"
        s.duration_ms = int((time.time() - t0) * 1000)
        s.detail = (f"{len(context)} records loaded, {len(closure)} reached from "
                    f"{subject_id} at depth {plan['traversal_depth']}")

        # impact_closure always seeds itself with the origin, so membership in
        # the closure proves nothing. The subject must exist as a RECORD, or the
        # analysis would return an empty "ok" result for a subject nobody has -
        # a silent wrong answer.
        if not len(context) or not context.has(subject_id):
            return self._insufficient(request, subject_id, stages, ledger, context,
                                      started)

        # 4 specialists
        specialists = self.select_specialists(intent_names)
        raw: list[Finding] = []
        activity = []
        for key, specialist, rationale in specialists:
            s = stage(f"{specialist.display_name}")
            t0 = time.time()
            try:
                produced = specialist.analyse(context, subject_id, closure)
            except Exception as exc:  # isolate specialist failure
                s.status, s.detail = "failed", str(exc)[:200]
                s.duration_ms = int((time.time() - t0) * 1000)
                activity.append({"specialist": specialist.display_name,
                                 "status": "failed", "findings": 0,
                                 "rationale": rationale, "error": str(exc)[:200]})
                continue
            raw.extend(produced)
            s.status, s.duration_ms = "done", int((time.time() - t0) * 1000)
            s.detail = f"{len(produced)} finding(s)"
            s.items = [f.id for f in produced]
            activity.append({"specialist": specialist.display_name, "status": "done",
                             "findings": len(produced), "rationale": rationale,
                             "attribution": specialist.attribution,
                             "uses_model": specialist.uses_model})

        # 5 synthesis
        s = stage("Synthesising across specialists")
        t0 = time.time()
        merged, conflicts = synthesise(raw)
        s.status, s.duration_ms = "done", int((time.time() - t0) * 1000)
        s.detail = f"{len(raw)} raw -> {len(merged)} synthesised, {len(conflicts)} conflict(s)"

        # 6 evidence gate
        s = stage("Evidence sufficiency gate")
        t0 = time.time()
        gate = EvidenceGate(context)
        gated = gate.apply(merged)
        gate_report = gate.report()
        s.status, s.duration_ms = "done", int((time.time() - t0) * 1000)
        s.detail = (f"{len(gated)} finding(s) passed, "
                    f"{len(gate_report['removed'])} removed, "
                    f"{len(gate_report['downgraded'])} downgraded, "
                    f"{gate_report['fabricated_citation_count']} fabricated citation(s)")

        unknowns = collect_unknowns(gated)
        return {
            "status": "ok",
            "request": request,
            "subject_id": subject_id,
            "domain": self.profile.as_dict(),
            "intents": intents,
            "evidence_plan": plan,
            "evidence_ledger": ledger,
            "context": context,
            "closure": closure,
            "findings": gated,
            "conflicts": conflicts,
            "gate_report": gate_report,
            "unknowns": unknowns,
            "activity": activity,
            "stages": [vars(s) for s in stages],
            "execution_mode": self.provider.execution_mode,
            "model": self.provider.describe(),
            "duration_ms": int((time.time() - started) * 1000),
            "context_snapshot_id": context.snapshot_id(),
        }

    def _insufficient(self, request, subject_id, stages, ledger, context, started) -> dict:
        """'The context does not support an answer' is a successful outcome."""
        return {
            "status": "insufficient_evidence",
            "request": request, "subject_id": subject_id,
            "domain": self.profile.as_dict(),
            "intents": [], "evidence_plan": {}, "evidence_ledger": ledger,
            "context": context, "closure": {}, "findings": [], "conflicts": [],
            "gate_report": {"removed": [], "downgraded": [],
                            "fabricated_citations": [], "fabricated_citation_count": 0},
            "unknowns": [f"Subject {subject_id} was not found in the retrieved context, "
                         f"or no connector supplied it."],
            "activity": [], "stages": [vars(s) for s in stages],
            "execution_mode": self.provider.execution_mode,
            "model": self.provider.describe(),
            "duration_ms": int((time.time() - started) * 1000),
            "context_snapshot_id": context.snapshot_id(),
        }
