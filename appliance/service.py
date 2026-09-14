"""The single orchestration service entry point.

Every interface - API, UI, CLI, chat - calls this. No interface implements its
own orchestration, so they cannot drift into behaving differently.

Session state holds the context, closure and findings from the last analysis, so
the three output workflows are generated from THE SAME reasoning context rather
than by re-analysing. That is what makes an Impact Assessment and a DVP&R
generated from one analysis mutually consistent.

That state is per CLIENT, not per process. One appliance holds one loaded
dataset, but two people opening the demonstration must not overwrite each
other's analysis, and one pressing Reset must not clear the other's. The active
session is bound to the calling context - one HTTP request, one context - so
isolation needs neither a database nor a lock around the analysis itself.
"""
from __future__ import annotations

import datetime as _dt
import os
import threading
import time
import uuid
from collections import OrderedDict
from contextvars import ContextVar

from .agents.skill_loader import SkillRegistry
from .config.schema import ApplianceConfig, load_config
from .connectors.adapters.simulation import SimulationConnector
from .connectors.registry import ConnectorRegistry
from .core.errors import ApplianceError, ReviewError, WorkflowError
from .core.provenance import Finding
from .models.provider import build_provider
from .orchestrator.domain import AUTOMOTIVE, DomainProfile, load_profiles
from .orchestrator.pipeline import Limits, OrchestrationPipeline
from . import architecture as architecture_model
from . import presentation
from .workflows.catalogue import build_catalogue, catalogue_summary
from .workflows.engine import WorkflowEngine, WorkflowRegistry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "packs")

# The session bound to the calling context. Unset - direct library use, the CLI,
# the tests - falls back to a single default session, so nothing outside the web
# layer has to know that sessions exist at all.
_ACTIVE_SESSION: ContextVar[str | None] = ContextVar("appliance_session", default=None)
DEFAULT_SESSION_ID = "default"
MAX_SESSIONS = 64

REVIEW_CONTROL_LABEL = "Demonstrator review control — session scoped, unauthenticated"
REVIEW_DECISIONS = {"accept": "accepted", "accepted": "accepted",
                    "reject": "rejected", "rejected": "rejected"}
MAX_REVIEWER_CHARS = 80
MAX_NOTE_CHARS = 2000


class Session:
    """State from the last analysis, shared by every output workflow."""

    def __init__(self, surface: str = AUTOMOTIVE.domain) -> None:
        self.run_id: str | None = None
        self.result: dict | None = None
        self.outputs: dict[str, object] = {}
        self.last_output: str | None = None
        self.started_at: float = 0.0
        self.domain: str = surface
        # The product surface this client is looking at. Survives Reset and a
        # new analysis; changed by choosing a domain or analysing its scenario.
        self.surface: str = surface
        # Human review is held beside the findings, never written into them:
        # the latest decision per finding, and an append-only audit log.
        self.reviews: dict[str, dict] = {}
        self.review_log: list[dict] = []

    def clear(self) -> None:
        self.__init__(self.surface)

    @property
    def has_analysis(self) -> bool:
        return self.result is not None and self.result.get("status") == "ok"


class ApplianceService:
    def __init__(self, config: ApplianceConfig | None = None) -> None:
        self.config = config or load_config()
        self.registry = ConnectorRegistry()
        self.skills = SkillRegistry()
        self.workflows = WorkflowRegistry()
        self.provider = build_provider(self.config.resolved_model())
        self.profiles: dict[str, DomainProfile] = load_profiles(PACKS)
        configured_default = self.config.default_domain
        self.default_domain = (configured_default if configured_default in self.profiles
                               else AUTOMOTIVE.domain)
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._sessions_lock = threading.Lock()
        self.boot_report: dict = {}
        self.bootstrap()

    # -- per-client sessions -----------------------------------------------
    def use(self, session_id: str | None) -> None:
        """Bind the calling context to one client's session.

        Called once per HTTP request, before any session state is touched.
        Contexts are per-request, so concurrent requests from different
        browsers never observe each other's analysis.
        """
        _ACTIVE_SESSION.set(session_id or DEFAULT_SESSION_ID)

    @property
    def session(self) -> Session:
        return self._session_for(_ACTIVE_SESSION.get() or DEFAULT_SESSION_ID)

    def _session_for(self, session_id: str) -> Session:
        """Fetch or create a client's session, evicting the least recently used
        once the cap is reached. An appliance serving a demonstration has no
        reason to accumulate sessions without bound."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(self.default_domain)
                self._sessions[session_id] = session
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > MAX_SESSIONS:
                for candidate in list(self._sessions):
                    if candidate not in (session_id, DEFAULT_SESSION_ID):
                        self._sessions.pop(candidate)
                        break
                else:
                    break
            return session

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    # -- bootstrap ---------------------------------------------------------
    def bootstrap(self) -> dict:
        report = {"packs": {}, "connectors": {}, "model": self.provider.describe(),
                  "workflows": 0, "errors": []}

        for pack in self.config.agent_packs or ["quality-engineering",
                                                "automotive-engineering"]:
            pack_dir = os.path.join(PACKS, pack)
            if not os.path.isdir(pack_dir):
                report["errors"].append(f"pack not found: {pack} "
                                        f"(run scripts/vendor_packs.py)")
                continue
            try:
                report["packs"][pack] = self.skills.load_pack(pack_dir, pack)
            except ApplianceError as exc:
                report["errors"].append(f"{pack}: {exc.message}")

        sim_dir = os.path.join(PACKS, "simulation")
        configured = {c.connector_id: c for c in self.config.connectors}
        sim_cfg = configured.get("SIMULATION")
        try:
            connector = SimulationConnector()
            self.registry.register(connector, {"pack_dir": sim_dir},
                                   enable=(sim_cfg.enabled if sim_cfg else True))
            report["connectors"]["SIMULATION"] = connector.test_connection()
        except ApplianceError as exc:
            report["errors"].append(f"SIMULATION: {exc.message}")

        # Domain packs that ship their own dataset get their own instance of the
        # same simulation adapter, registered under the pack's connector id.
        for profile in self.profiles.values():
            if not profile.pack or not profile.connector_id:
                continue
            cfg = configured.get(profile.connector_id)
            try:
                connector = SimulationConnector(connector_id=profile.connector_id)
                self.registry.register(connector,
                                       {"pack_dir": os.path.join(PACKS, profile.pack)},
                                       enable=(cfg.enabled if cfg else True))
                report["connectors"][profile.connector_id] = connector.test_connection()
            except ApplianceError as exc:
                report["errors"].append(f"{profile.connector_id}: {exc.message}")

        report["domains"] = sorted(self.profiles)
        report["workflows"] = len(self.workflows.all())
        report["skills"] = self.skills.summary()
        self.boot_report = report
        return report

    # -- health ------------------------------------------------------------
    def domain_records(self, profile: DomainProfile) -> list:
        """Every record the domain's connector holds (for coverage views)."""
        try:
            connector = self.registry.get(profile.connector_id)
        except ApplianceError:
            return []
        records = []
        for entity_type in connector.capabilities().get("entity_types", []):
            records.extend(connector.list_by_type(entity_type))
        return records

    def health(self) -> dict:
        summary = self.registry.summary()
        return {
            "status": "ok" if summary["active"] else "degraded",
            "version": "0.1.0",
            "profile": self.config.profile,
            "simulation_mode": self.config.simulation_mode,
            "model": self.provider.describe(),
            "connectors": summary,
            "packs": self.boot_report.get("packs", {}),
            "skills": self.boot_report.get("skills", {}),
            "workflows": len(self.workflows.all()),
            "errors": self.boot_report.get("errors", []),
        }

    def connector_catalogue(self) -> list[dict]:
        return self.registry.catalogue()

    # -- scenarios ---------------------------------------------------------
    def _scenario_connectors(self) -> list:
        return [c for c in self.registry.enabled_connectors()
                if hasattr(c, "list_scenarios")]

    def scenarios(self, domain: str | None = None) -> list[dict]:
        rows = []
        for connector in self._scenario_connectors():
            for row in connector.list_scenarios():
                if domain and (row.get("domain") or AUTOMOTIVE.domain) != domain:
                    continue
                profile = self.profile_for(row.get("domain"))
                rows.append({**row, "domain_label": profile.label,
                             "presentation": profile.presentation})
        # Domain packs (the demonstrator focus) first, then the built-in domain.
        return sorted(rows, key=lambda r: (r["domain"] == AUTOMOTIVE.domain,
                                           r["scenario_id"]))

    def scenario(self, scenario_id: str) -> dict | None:
        for connector in self._scenario_connectors():
            scenario = connector.get_scenario(scenario_id)
            if scenario is not None:
                return {**scenario, "connector_id": connector.connector_id,
                        "domain": scenario.get("domain") or AUTOMOTIVE.domain}
        return None

    def profile_for(self, domain: str | None) -> DomainProfile:
        return self.profiles.get(domain or AUTOMOTIVE.domain, AUTOMOTIVE)

    @property
    def profile(self) -> DomainProfile:
        """The domain profile of the current session's analysis - or, with no
        analysis, of the surface the client has chosen. An analysis is always
        presented and generated in its own domain."""
        if self.session.result is not None:
            return self.profile_for(self.session.domain)
        return self.profile_for(self.session.surface)

    @property
    def surface(self) -> DomainProfile:
        return self.profile_for(self.session.surface)

    def use_surface(self, domain: str) -> DomainProfile:
        """Switch this client's product surface. A different domain clears the
        analysis, so one domain's findings are never shown in another's surface."""
        if domain not in self.profiles:
            raise ApplianceError(f"Unknown domain {domain}")
        if domain != self.session.surface or self.session.domain != domain:
            self.session.surface = domain
            self.session.clear()
        return self.profile

    def resolve_workflow(self, workflow_id: str) -> str:
        """A domain may name a workflow by its own alias
        (verification-evidence-plan -> dvpr)."""
        for profile in (self.profile, self.surface):
            if workflow_id in profile.workflow_aliases:
                return profile.workflow_aliases[workflow_id]
        return workflow_id

    # -- analysis ----------------------------------------------------------
    def analyse(self, request: str, subject_id: str, domain: str | None = None,
                connector_ids: list[str] | None = None) -> dict:
        profile = self.profile_for(domain)
        pipeline = OrchestrationPipeline(
            self.registry, self.provider, self.skills,
            Limits(max_traversal_depth=self.config.traversal_depth),
            profile=profile, connector_ids=connector_ids)
        result = pipeline.run(request, subject_id)
        self.session.clear()
        self.session.run_id = uuid.uuid4().hex[:12]
        self.session.result = result
        self.session.domain = profile.domain
        self.session.surface = profile.domain
        self.session.started_at = time.time()
        return result

    def analyse_scenario(self, scenario_id: str) -> dict:
        scenario = self.scenario(scenario_id)
        if scenario is None:
            raise ApplianceError(f"Unknown scenario {scenario_id}")
        subject = self._scenario_subject(scenario)
        request = f"{scenario['one_liner']} {scenario['initial_input']}"
        result = self.analyse(request, subject, domain=scenario["domain"],
                              connector_ids=[scenario["connector_id"]])
        result["scenario"] = scenario
        return result

    @staticmethod
    def _scenario_subject(scenario: dict) -> str:
        """The entity the analysis starts from - the change if the scenario has
        one, otherwise the quality issue."""
        entities = scenario.get("relevant_entities", {})
        for key in ("engineering_changes", "quality_issues"):
            ids = entities.get(key) or []
            if ids:
                return ids[0]
        for ids in entities.values():
            if ids:
                return ids[0]
        raise ApplianceError(f"Scenario {scenario.get('scenario_id')} names no subject entity")

    # -- outputs -----------------------------------------------------------
    def output_catalogue(self) -> list[dict]:
        """Legacy view over the implemented workflows only."""
        context = self.session.result["context"] if self.session.has_analysis else None
        return self.workflows.catalogue(context)

    def full_output_catalogue(self) -> list[dict]:
        """All 25 engineering deliverables with a status resolved from the real
        workflow registry and the real analysis scope.

        Scope is the CLOSURE, not the whole loaded dataset. The meaningful
        question is "does this analysis reach a PFMEA?", not "does the connector
        hold one somewhere". Using the full dataset would mark every output
        applicable and quietly destroy the honesty of the status.
        """
        present = self.scope_types()
        profile = self.profile if self.session.has_analysis else None
        return build_catalogue(self.workflows, present, self.session.has_analysis,
                               profile)

    def scope_types(self) -> set[str]:
        """Entity types actually reached by the current analysis."""
        if not self.session.has_analysis:
            return set()
        result = self.session.result
        context = result["context"]
        types = set()
        for entity_id in result["closure"]:
            entity = context.get(entity_id)
            if entity is not None:
                types.add(entity.entity_type)
        return types

    def output_summary(self) -> dict:
        return catalogue_summary(self.full_output_catalogue())

    # -- architecture and presentation --------------------------------------
    def architecture(self) -> dict:
        """The intended product architecture with honest per-component status."""
        model = architecture_model.model()
        model["connectors"] = self.registry.summary()
        model["outputs"] = self.output_summary()
        model["skills"] = self.boot_report.get("skills", {})
        model["model"] = self.provider.describe()
        return model

    def executive(self) -> dict:
        """Level 1 view-model, derived entirely from the last analysis."""
        if not self.session.result:
            return {"answerable": False, "headline": "No analysis has been run."}
        return presentation.executive(self.session.result)

    def engineering_detail(self) -> dict:
        """Level 2 view-model."""
        if not self.session.result:
            return {"answerable": False}
        return presentation.engineering_detail(self.session.result)

    def generate(self, workflow_id: str):
        workflow_id = self.resolve_workflow(workflow_id)
        if not self.session.has_analysis:
            raise WorkflowError("Run an analysis before generating an output",
                                workflow=workflow_id)
        result = self.session.result
        engine = WorkflowEngine(self.workflows)
        profile = self.profile
        output = engine.run(workflow_id, result["context"], result["findings"],
                            result["closure"], result["subject_id"],
                            unknowns=result.get("unknowns"),
                            model_description=self.provider.describe(),
                            variant=profile.workflow_variant(workflow_id),
                            reviews=dict(self.session.reviews),
                            domain=profile.domain)
        self.session.outputs[workflow_id] = output
        self.session.last_output = workflow_id
        return output

    # -- explanation -------------------------------------------------------
    def explain(self, finding_id: str) -> dict:
        """'Why did you say that?' - the actual evidence and provenance chain.

        No chain-of-thought: evidence records, the traversal path that reached
        them, classification and confidence.
        """
        if not self.session.has_analysis:
            raise WorkflowError("No analysis in session")
        result = self.session.result
        context = result["context"]
        finding: Finding | None = next(
            (f for f in result["findings"] if f.id == finding_id), None)
        if finding is None:
            raise WorkflowError(f"Unknown finding {finding_id}")

        evidence = []
        for ref in finding.evidence:
            entity = context.get(ref.entity_id)
            if entity is None:
                continue
            evidence.append({
                "id": entity.id, "entity_type": entity.entity_type,
                "summary": entity.summary,
                "attributes": {k: v for k, v in entity.attributes.items()
                               if k in ("statement", "description", "status",
                                        "failure_mode", "failure_effect", "severity",
                                        "action_priority", "acceptance_criterion",
                                        "acceptance_criterion_established", "notes",
                                        "measured_summary", "deviation", "asil",
                                        "configuration_id", "domain", "basis",
                                        "regulatory_reference", "applicability",
                                        "applicability_note", "identifier",
                                        "content_policy", "method", "evidence_type",
                                        "source_record_id", "change_type")},
                "path": ref.path or result["closure"].get(entity.id, []),
                "provenance": entity.provenance.model_dump(),
                "classification": entity.classification.value,
                "transferable": (None if entity.entity_type not in ("TestResult", "Evidence")
                                 else not context.is_stale(entity)),
                "transferability_reason": context.transferability_reason(entity),
            })
        gate = result.get("gate_report", {})
        downgraded = next((d for d in gate.get("downgraded", [])
                           if d.get("id") == finding_id), None)
        return {
            "finding": finding.model_dump(),
            "finding_id": finding.id,
            "tags": finding.tags,
            "derivation": _derivation_steps(finding, result),
            "classification_meaning": CLASSIFICATION_MEANING.get(
                finding.classification.value, ""),
            "confidence_basis": _confidence_basis(finding),
            "gate_outcome": ("Downgraded to ASSUMED by the evidence gate: no verifiable "
                             "evidence." if downgraded else
                             "Passed the evidence gate: every cited id exists in the "
                             "retrieved context."),
            "review": self.session.reviews.get(finding.id),
            "review_history": [r for r in self.session.review_log
                               if r["finding_id"] == finding.id],
            "review_control": REVIEW_CONTROL_LABEL,
            "domain": self.profile.as_dict(),
            "evidence": evidence,
            "classification": finding.classification.value,
            "confidence": finding.confidence.value,
            "confidence_score": finding.confidence_score,
            "produced_by": finding.produced_by,
            "rationale": finding.rationale,
            "assumptions": finding.assumptions,
            "unknowns": finding.unknowns,
            "execution_mode": result["execution_mode"],
        }

    # -- human review -------------------------------------------------------
    def review(self, finding_id: str, decision: str, reviewer: str,
               note: str = "") -> dict:
        """Record a reviewer decision on ONE finding.

        Stored in the session beside the findings - the Finding itself is never
        modified, so the machine's statement and the human's decision remain
        separately auditable. Session scoped and unauthenticated: the reviewer
        name is self-declared and is not an identity.
        """
        if not self.session.has_analysis:
            raise ReviewError("Run an analysis before reviewing a finding.",
                              finding=finding_id)
        result = self.session.result
        finding = next((f for f in result["findings"] if f.id == finding_id), None)
        if finding is None:
            raise ReviewError(f"Unknown finding {finding_id}", finding=finding_id)
        normalised = REVIEW_DECISIONS.get((decision or "").strip().lower())
        if normalised is None:
            raise ReviewError("Decision must be Accept or Reject.", decision=decision)
        reviewer = " ".join((reviewer or "").split())
        note = (note or "").strip()
        if not reviewer:
            raise ReviewError("A reviewer name is required.", finding=finding_id)
        if len(reviewer) > MAX_REVIEWER_CHARS or len(note) > MAX_NOTE_CHARS:
            raise ReviewError("Reviewer name or note is too long.", finding=finding_id)
        if normalised == "rejected" and not note:
            raise ReviewError("Rejecting a finding requires a note explaining why.",
                              finding=finding_id)

        record = {
            "finding_id": finding.id,
            "decision": normalised,
            "reviewer": reviewer,
            "note": note,
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "finding_snapshot": {
                "statement": finding.statement,
                "classification": finding.classification.value,
                "confidence_score": finding.confidence_score,
                "evidence_ids": finding.evidence_ids,
            },
            "run_id": self.session.run_id,
            "context_snapshot_id": result.get("context_snapshot_id"),
            "control": REVIEW_CONTROL_LABEL,
        }
        self.session.reviews[finding.id] = record
        self.session.review_log.append(record)
        # Outputs generated before this decision no longer reflect it. The last
        # one shown is remembered so the interface can regenerate it at once.
        self.session.outputs.clear()
        return record

    def reviews(self) -> dict:
        return {"control": REVIEW_CONTROL_LABEL,
                "current": dict(self.session.reviews),
                "log": list(self.session.review_log)}

    # -- demonstration control --------------------------------------------
    def reset(self) -> dict:
        self.session.clear()   # keeps the surface
        return {"reset": True, "connectors": self.registry.summary()}


CLASSIFICATION_MEANING = {
    "FACT": "Retrieved directly from a source record.",
    "DERIVED": "Computed deterministically from retrieved records by graph traversal and "
               "set operations. The same context always yields the same finding.",
    "INFERRED": "Reasoned by a model from the evidence. Lower trust than a derived finding "
                "and verified by the evidence gate.",
    "ASSUMED": "Stated without verifiable supporting evidence; the assumption is declared.",
    "UNKNOWN": "The available evidence does not establish this. Nothing has been assumed "
               "in its place.",
}


def _confidence_basis(finding: Finding) -> str:
    return (f"Deterministic score {finding.confidence_score:.2f} ({finding.confidence.value}) "
            f"from {len(finding.evidence)} verified evidence reference(s), "
            f"{len(finding.produced_by)} contributing specialist(s) and classification "
            f"{finding.classification.value}. It is not model self-reported confidence.")


def _derivation_steps(finding: Finding, result: dict) -> list[dict]:
    """The recorded path from input to this finding - the pipeline stages that
    actually ran, not a narrative written after the fact."""
    stages = {s["name"]: s for s in result.get("stages", [])}
    producers = set(finding.produced_by)
    steps = []
    for name in ("Understanding change", "Planning required evidence",
                 "Retrieving engineering context"):
        if name in stages:
            steps.append({"step": name, "detail": stages[name]["detail"]})
    for name, stage in stages.items():
        if name in producers:
            steps.append({"step": f"Specialist: {name}", "detail": stage["detail"]})
    for name in ("Synthesising across specialists", "Evidence sufficiency gate"):
        if name in stages:
            steps.append({"step": name, "detail": stages[name]["detail"]})
    return steps
