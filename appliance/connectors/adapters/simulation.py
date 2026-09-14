"""Simulation Connector.

A first-class implementation of the universal contract over the vendored
engineering-intelligence-simulation dataset: 956 entity records, 2,018 typed
relationship edges, 12 scenarios.

This is NOT a mock standing in for the real thing - it is the first
implementation of the real interface. `tests/test_architecture.py`
asserts that no `connector == "simulation"` branch exists anywhere above this
module. If simulation needed special agent logic, the "swap the adapter and
nothing above changes" claim would be false.

Every returned record carries its data classification, so the UI can always
label simulated data honestly.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

import yaml

from ...core.entities import EngineeringEntity, Relationship
from ...core.errors import ConnectorError
from ..base import CANONICAL_OPERATIONS, Connector

# Collection file -> canonical entity type. Alias views are excluded so ids are
# not double counted.
COLLECTIONS = {
    "programmes.json": "Programme", "vehicles.json": "Vehicle",
    "configurations.json": "Configuration", "systems.json": "System",
    "subsystems.json": "Subsystem", "components.json": "Component",
    "suppliers.json": "Supplier", "standards.json": "Standard",
    "signals.json": "Signal", "requirements.json": "Requirement",
    "engineering_changes.json": "EngineeringChange", "fmea.json": "FMEA",
    "failure_modes.json": "FailureMode", "risks.json": "Risk",
    "tests.json": "TestCase", "test_results.json": "TestResult",
    "vv_activities.json": "VVActivity", "quality_issues.json": "QualityIssue",
    "ncrs.json": "NCR", "root_causes.json": "RootCause",
    "corrective_actions.json": "CorrectiveAction",
    "supplier_issues.json": "SupplierIssue", "documents.json": "Document",
    "measurements.json": "Measurement", "evidence.json": "Evidence",
}

SEARCH_FIELDS = ("title", "name", "statement", "description", "failure_mode",
                 "failure_effect", "failure_cause", "abstract", "conditions",
                 "acceptance_criterion", "measured_summary", "notes",
                 "risk_statement", "identifier", "path", "deviation")


class SimulationConnector(Connector):
    connector_id = "SIMULATION"
    connector_name = "Simulation / Public Data Connector"
    category = "Simulation"
    mode = "read_only"
    write_capable = False

    # Provenance defaults for the vendored automotive simulation dataset. A pack
    # that ships its own dataset declares these in its pack.yaml instead.
    DEFAULT_SOURCE_URL = "https://github.com/rahulphaltankar/engineering-intelligence-simulation"
    DEFAULT_LICENCE = "MIT"

    def __init__(self, pack_dir: str | None = None, connector_id: str | None = None,
                 connector_name: str | None = None) -> None:
        # One adapter, several datasets: a second instance over a different pack
        # is registered under its own catalogue id, so nothing above the adapter
        # needs to know which dataset answered.
        if connector_id:
            self.connector_id = connector_id
        if connector_name:
            self.connector_name = connector_name
        self.pack_dir = pack_dir
        self.source_url = self.DEFAULT_SOURCE_URL
        self.licence = self.DEFAULT_LICENCE
        self._entities: dict[str, EngineeringEntity] = {}
        self._by_type: dict[str, list[EngineeringEntity]] = defaultdict(list)
        self._out: dict[str, list[Relationship]] = defaultdict(list)
        self._in: dict[str, list[Relationship]] = defaultdict(list)
        self._relationships: list[Relationship] = []
        self._scenarios: dict[str, dict] = {}
        self._classification = ""
        self._loaded = False

    # -- lifecycle ---------------------------------------------------------
    def configure(self, config: dict) -> None:
        self.pack_dir = config.get("pack_dir", self.pack_dir)
        if not self.pack_dir or not os.path.isdir(self.pack_dir):
            raise ConnectorError(
                "Simulation pack directory not found. Run `python scripts/vendor_packs.py`.",
                connector=self.connector_id, pack_dir=self.pack_dir)
        self._load()

    def _load(self) -> None:
        manifest = os.path.join(self.pack_dir, "pack.yaml")
        if os.path.exists(manifest):
            with open(manifest, "r", encoding="utf-8") as fh:
                meta = yaml.safe_load(fh) or {}
            dataset = meta.get("dataset") or {}
            self.source_url = dataset.get("source_url") or self.source_url
            self.licence = dataset.get("licence") or self.licence
            self.connector_name = dataset.get("connector_name") or self.connector_name
        data_dir = os.path.join(self.pack_dir, "data")
        for filename, entity_type in COLLECTIONS.items():
            path = os.path.join(data_dir, filename)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self._classification = payload.get("data_classification", self._classification)
            for record in payload.get("records", []):
                entity = EngineeringEntity(
                    id=record["id"], entity_type=entity_type,
                    attributes={k: v for k, v in record.items() if k != "id"},
                    provenance=self.stamp(
                        record["id"], source_version=filename,
                        data_classification=payload.get("data_classification"),
                        licence=self.licence, source_url=self.source_url))
                self._entities[entity.id] = entity
                self._by_type[entity_type].append(entity)

        rel_path = os.path.join(data_dir, "relationships.json")
        if os.path.exists(rel_path):
            with open(rel_path, "r", encoding="utf-8") as fh:
                for edge in json.load(fh)["records"]:
                    rel = Relationship(**{k: edge.get(k) for k in
                                          ("source_type", "source_id", "relationship",
                                           "target_type", "target_id", "note")})
                    self._relationships.append(rel)
                    self._out[rel.source_id].append(rel)
                    self._in[rel.target_id].append(rel)

        scen_dir = os.path.join(self.pack_dir, "scenarios")
        if os.path.isdir(scen_dir):
            for name in sorted(os.listdir(scen_dir)):
                if not name.startswith("SCN-") or not name.endswith(".json"):
                    continue
                with open(os.path.join(scen_dir, name), "r", encoding="utf-8") as fh:
                    scenario = json.load(fh)
                self._scenarios[scenario["scenario_id"]] = scenario
        self._loaded = True

    def test_connection(self) -> dict:
        if not self._loaded:
            return {"ok": False, "diagnosis": "not_configured",
                    "detail": "configure() has not been called."}
        if not self._entities:
            return {"ok": False, "diagnosis": "empty_source",
                    "detail": f"No records loaded from {self.pack_dir}."}
        return {"ok": True, "diagnosis": "connected",
                "detail": f"{len(self._entities)} records, "
                          f"{len(self._relationships)} relationship edges, "
                          f"{len(self._scenarios)} scenarios."}

    def status(self) -> dict:
        return {"connector_id": self.connector_id, "connector_name": self.connector_name,
                "mode": self.mode, "write_capable": self.write_capable,
                "records_loaded": len(self._entities),
                "relationship_edges": len(self._relationships),
                "entity_counts": {k: len(v) for k, v in sorted(self._by_type.items())},
                "data_classification": self._classification}

    def capabilities(self) -> dict:
        return {"operations": list(CANONICAL_OPERATIONS),
                "entity_types": sorted(self._by_type),
                "supports_search": True, "supports_traversal": True,
                "write_capable": False}

    # -- reads -------------------------------------------------------------
    def get_entity(self, entity_id: str) -> EngineeringEntity | None:
        return self._entities.get(entity_id)

    def list_by_type(self, entity_type: str) -> list[EngineeringEntity]:
        return list(self._by_type.get(entity_type, []))

    def relationships_for(self, entity_id: str) -> list[Relationship]:
        return list(self._out.get(entity_id, [])) + list(self._in.get(entity_id, []))

    def all_relationships(self) -> list[Relationship]:
        return list(self._relationships)

    def search_engineering_context(self, query: str, entity_type: str | None = None,
                                   limit: int = 40) -> list[dict]:
        """Term-coverage-first ranking: transparent and debuggable rather than
        sophisticated. An appliance may swap in embeddings later; the signature
        does not change."""
        terms = [t for t in query.lower().split() if len(t) > 2]
        if not terms:
            return []
        scored = []
        for entity in self._entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
            blob = " ".join(str(entity.attributes.get(f, "")) for f in SEARCH_FIELDS).lower()
            covered = sum(1 for t in terms if t in blob)
            if not covered:
                continue
            scored.append((covered, sum(blob.count(t) for t in terms), entity))
        scored.sort(key=lambda x: (-x[0], -x[1], x[2].id))
        return [{"id": e.id, "entity_type": e.entity_type,
                 "term_coverage": f"{c}/{len(terms)}", "match_count": h,
                 "summary": e.summary}
                for c, h, e in scored[:limit]]

    # -- scenarios (demonstration support) ---------------------------------
    def list_scenarios(self) -> list[dict]:
        return [{"scenario_id": s["scenario_id"], "title": s["title"],
                 "category": s["category"], "one_liner": s["one_liner"],
                 "initial_input": s["initial_input"],
                 "domain": s.get("domain") or "automotive",
                 "connector_id": self.connector_id}
                for s in sorted(self._scenarios.values(), key=lambda x: x["scenario_id"])]

    def get_scenario(self, scenario_id: str) -> dict | None:
        return self._scenarios.get(scenario_id)
