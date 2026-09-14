"""Architectural invariants.

These are the properties the product's commercial claims rest on. If any of them
regresses, the claim becomes false, so they are tested rather than asserted in a
document.
"""
from __future__ import annotations

import os
import re

from appliance.connectors.base import Connector
from appliance.connectors.registry import ConnectorRegistry
from appliance.core.errors import ConnectorDisabledError, NotSupportedError
from appliance.models.provider import DeterministicProvider, SecretRef

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLIANCE = os.path.join(ROOT, "appliance")


def _sources(exclude: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    out = []
    for base, _, files in os.walk(APPLIANCE):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if any(x in rel for x in exclude):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                out.append((rel, fh.read()))
    return out


# -- read-only is structural ----------------------------------------------
def test_connector_contract_exposes_no_write_method():
    """Read-only is enforced by the shape of the interface, not a setting."""
    forbidden = ("create", "update", "delete", "write", "put", "post", "patch",
                 "save", "commit", "upsert")
    methods = [m for m in dir(Connector)
               if not m.startswith("_") and callable(getattr(Connector, m, None))]
    offenders = [m for m in methods if any(m.startswith(f) for f in forbidden)]
    assert not offenders, f"write-capable methods on the contract: {offenders}"


def test_simulation_connector_declares_no_write_capability(service):
    connector = service.registry.get("SIMULATION")
    assert connector.write_capable is False
    assert connector.mode == "read_only"
    assert connector.capabilities()["write_capable"] is False


# -- no simulation special-casing -----------------------------------------
def test_no_simulation_special_casing_above_the_adapter():
    """If simulation needed special agent logic, 'swap the adapter and nothing
    above changes' would be false."""
    pattern = re.compile(r'(==|!=)\s*["\']SIMULATION["\']|["\']SIMULATION["\']\s*(==|!=)')
    offenders = []
    for rel, source in _sources(exclude=("connectors/adapters/", "connectors/catalogue.py",
                                         "connectors/registry.py", "service.py")):
        if pattern.search(source):
            offenders.append(rel)
    assert not offenders, f"simulation-specific branching found in: {offenders}"


def test_agents_never_import_a_connector_adapter():
    offenders = []
    for rel, source in _sources():
        if not rel.startswith("appliance/agents/"):
            continue
        if "connectors.adapters" in source or "from ..connectors" in source:
            offenders.append(rel)
    assert not offenders, f"agents coupled to connector implementations: {offenders}"


# -- model neutrality ------------------------------------------------------
def test_no_provider_sdk_imported_outside_the_model_layer():
    """Provider neutrality is a commercial claim and must be architecturally real."""
    sdks = ("import anthropic", "import litellm", "import openai", "from openai",
            "from anthropic", "from litellm")
    offenders = []
    for rel, source in _sources(exclude=("models/",)):
        if any(s in source for s in sdks):
            offenders.append(rel)
    assert not offenders, f"provider SDK imported outside appliance/models: {offenders}"


def test_no_hardcoded_credentials_or_endpoints():
    patterns = [re.compile(r'sk-[A-Za-z0-9]{16,}'),
                re.compile(r'api_key\s*=\s*["\'][^"\']{8,}["\']'),
                re.compile(r'https://api\.(openai|anthropic)\.com')]
    offenders = []
    for rel, source in _sources():
        for pattern in patterns:
            if pattern.search(source):
                offenders.append(rel)
    assert not offenders, f"hardcoded credential or endpoint in: {offenders}"


def test_secretref_cannot_be_interpolated_into_a_prompt_or_log():
    secret = SecretRef("SOME_ENV_VAR")
    for attempt in (lambda: str(secret), lambda: f"{secret}", lambda: repr(secret)):
        try:
            attempt()
        except RuntimeError:
            continue
        raise AssertionError("SecretRef leaked its value into a string")


# -- honest execution mode -------------------------------------------------
def test_deterministic_provider_refuses_to_fabricate_a_completion():
    """With no credentials the appliance must decline, never invent a response."""
    provider = DeterministicProvider("no credentials in test")
    try:
        provider.complete("system", "prompt")
    except Exception as exc:
        assert exc.code == "MODEL_NOT_CONFIGURED"
        return
    raise AssertionError("a model call was faked")


def test_execution_mode_is_recorded_in_every_result(analysis):
    assert analysis["execution_mode"] in ("model", "deterministic")
    assert analysis["model"]["execution_mode"] == analysis["execution_mode"]


def test_findings_are_not_labelled_inferred_without_a_model(analysis):
    """In deterministic mode nothing may claim to be model-reasoned."""
    if analysis["execution_mode"] != "deterministic":
        return
    inferred = [f.id for f in analysis["findings"]
                if f.classification.value == "INFERRED"]
    assert not inferred, f"INFERRED findings without a model: {inferred}"


# -- connector registry ----------------------------------------------------
def test_disabled_connector_is_structurally_unreachable(service):
    registry = service.registry
    registry.disable("SIMULATION")
    try:
        raised = False
        try:
            registry.get("SIMULATION")
        except ConnectorDisabledError:
            raised = True
        assert raised
        # Other connectors (the fire-engineering dataset) stay reachable; the
        # disabled one is gone from every lookup.
        assert "SIMULATION" not in [c.connector_id for c in registry.enabled_connectors()]
        assert registry.enabled_connectors(["SIMULATION"]) == []
    finally:
        registry.enable("SIMULATION")


def test_enable_disable_takes_effect_without_restart(service):
    registry = service.registry
    active = registry.summary()["active"]
    assert active >= 1
    registry.disable("SIMULATION")
    assert registry.summary()["active"] == active - 1
    registry.enable("SIMULATION")
    assert registry.summary()["active"] == active


def test_catalogue_distinguishes_no_adapter_from_disabled(service):
    states = {row["display_state"] for row in service.connector_catalogue()}
    assert "NO ADAPTER" in states and "ACTIVE" in states, \
        "an unimplemented adapter must not be presented as merely disabled"


def test_catalogue_covers_the_universal_connector_categories(service):
    rows = service.connector_catalogue()
    assert len(rows) >= 50
    categories = {r["category"] for r in rows}
    for expected in ("Product lifecycle", "Quality", "Verification and validation",
                     "Manufacturing and supply chain", "Enterprise information"):
        assert expected in categories


def test_unsupported_operation_raises_rather_than_returning_empty():
    """Conflating 'cannot answer' with 'the answer is nothing' produces a false
    evidence gap, which looks like a finding."""
    class Bare(Connector):
        connector_id = "BARE"
        def configure(self, config): pass
        def test_connection(self): return {"ok": True}
        def status(self): return {}
        def capabilities(self): return {"operations": []}

    try:
        Bare().list_by_type("Requirement")
    except NotSupportedError:
        return
    raise AssertionError("unsupported operation returned a value")


# -- upstream reuse --------------------------------------------------------
def test_upstream_skills_are_loaded_not_reimplemented(service):
    summary = service.health()["skills"]
    assert summary["total"] >= 30, "the upstream substrates must actually be loaded"
    assert set(summary["packs"]) >= {"quality-engineering", "automotive-engineering"}


def test_no_quality_methodology_reimplemented_in_python():
    """8D, 5-Why, Fishbone, FMEA and the rest live in vendored markdown."""
    banned = ("def eight_d", "def five_why", "def fishbone", "def calculate_rpn",
              "def action_priority_table", "AP_TABLE", "SEVERITY_CRITERIA")
    offenders = []
    for rel, source in _sources():
        for token in banned:
            if token in source:
                offenders.append(f"{rel}: {token}")
    assert not offenders, f"upstream methodology reimplemented: {offenders}"
