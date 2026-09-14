"""The appliance architecture model, with honest implementation status.

The architecture view is allowed to communicate the INTENDED product
architecture. It is not allowed to imply that everything in it is built.

Every component therefore carries a status and, where it claims to be
implemented, the module that implements it. `verify()` checks those modules
actually exist on disk, so a component cannot silently claim to be implemented
after the code behind it is removed.

Status vocabulary
-----------------
IMPLEMENTED  working today, backed by a module in this repository
PARTIAL      a working subset exists; the rest is not built
PLANNED      intended architecture, not built
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))

IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
PLANNED = "PLANNED"

# (name, status, module_or_none, note)
LAYERS: tuple[tuple[str, str, tuple[tuple[str, str, str | None, str], ...]], ...] = (
    ("1", "Connector Framework", (
        ("Connector Manager", IMPLEMENTED, "connectors/registry.py",
         "Registry, catalogue and runtime enable/disable."),
        ("Credential Boundary", IMPLEMENTED, "models/provider.py",
         "SecretRef raises if a credential is ever interpolated into a prompt or log."),
        ("Data Ingestion", IMPLEMENTED, "connectors/adapters/simulation.py",
         "Capability-aware fan-out across every enabled connector."),
        ("Schema Mapping / Normalisation", PARTIAL, "core/entities.py",
         "Adapters map to canonical entities. The declarative field-mapping layer "
         "for new customer connectors is not built."),
        ("Data Quality / Validation", IMPLEMENTED, "core/context.py",
         "Reference integrity and provenance completeness checked before reasoning."),
        ("Batch / Real-time Sync", PLANNED, None,
         "Single read per analysis today. Scheduled and streaming sync not built."),
    )),
    ("2", "Data and Context", (
        ("Engineering Data Store", IMPLEMENTED, "core/context.py",
         "In-memory canonical store; 956 records in the current environment."),
        ("Relationship Graph", IMPLEMENTED, "core/context.py",
         "2,018 typed edges with forward and reverse adjacency."),
        ("Context Store", IMPLEMENTED, "core/context.py",
         "Content-addressed snapshot id; identical retrieval yields an identical id."),
        ("Relationship Index", IMPLEMENTED, "core/context.py",
         "Path-carrying traversal - every reached record knows why it was reached."),
        ("Metadata Catalog", PARTIAL, "core/provenance.py",
         "Provenance and entity typing are present. A separate catalogue service is not."),
        ("Vector / Semantic Store", PLANNED, None,
         "Deliberately deferred: deterministic traversal outperforms "
         "embedding search at this corpus size and is reproducible."),
    )),
    ("3", "Intelligence and Agent Orchestration", (
        ("Agent Orchestrator", IMPLEMENTED, "orchestrator/pipeline.py",
         "Bounded acyclic pipeline with hard execution limits."),
        ("Automotive Engineering", IMPLEMENTED, "agents/specialists/analysts.py",
         "Wraps the upstream automotive-engineer profile verbatim."),
        ("Quality / FMEA", IMPLEMENTED, "agents/specialists/analysts.py",
         "Backed by the upstream fmea-reviewer and FMEA skills."),
        ("Requirements Analysis", IMPLEMENTED, "agents/specialists/analysts.py",
         "Allocation, baseline status and safety-integrity visibility."),
        ("Evidence / Validation", IMPLEMENTED, "agents/specialists/analysts.py",
         "Coverage and gap assembly across the impacted requirements."),
        ("Skill Substrate", IMPLEMENTED, "agents/skill_loader.py",
         "33 upstream definitions loaded verbatim under a per-item MIT gate."),
        ("RCA Specialist", PLANNED, None,
         "The upstream RCA skills are loaded but no specialist wrapper is wired."),
        ("Test Engineering Specialist", PLANNED, None, "Not wired."),
        ("Compliance Specialist", PLANNED, None,
         "The upstream audit skills are loaded but no specialist wrapper is wired."),
        ("Supplier Quality Specialist", PLANNED, None,
         "The upstream SCAR skill is loaded but no specialist wrapper is wired."),
    )),
    ("4", "Analytics and Inference", (
        ("Impact Analysis", IMPLEMENTED, "core/context.py",
         "Graph closure with structural completion."),
        ("Requirements Impact", IMPLEMENTED, "agents/specialists/analysts.py",
         "Direct versus allocation-inferred, with inferred edges discounted."),
        ("Risk Analysis", IMPLEMENTED, "agents/specialists/analysts.py",
         "Ranked by severity within the highest action-priority band present."),
        ("Verification Analysis", IMPLEMENTED, "core/context.py",
         "Requirement to test to result, with non-transferable evidence detected."),
        ("Evidence Analysis", IMPLEMENTED, "orchestrator/synthesis.py",
         "Citation verification and evidence sufficiency gating."),
        ("Recommendation", PARTIAL, "workflows/sections.py",
         "Per-row verification actions are derived. A general recommendation "
         "engine is not built."),
        ("Deterministic Reasoning", IMPLEMENTED, "core/context.py",
         "Reproducible: the same context and query always return the same evidence."),
        ("LLM / AI Engine", PARTIAL, "models/provider.py",
         "Provider abstraction and BYOK are implemented. No credentials are "
         "configured, so the appliance runs deterministic analysis only and says so."),
        ("Root Cause Engine", PLANNED, None, "Not built."),
    )),
    ("5", "Security and Governance", (
        ("Read-Only Enforcement", IMPLEMENTED, "connectors/base.py",
         "Structural: the connector contract has no write method at all."),
        ("Credential Isolation", IMPLEMENTED, "models/provider.py",
         "Credentials never enter prompts, context, logs or traces."),
        ("Provenance and Classification", IMPLEMENTED, "core/provenance.py",
         "FACT / DERIVED / INFERRED / ASSUMED / UNKNOWN, capped on propagation."),
        ("Connector Isolation", IMPLEMENTED, "connectors/registry.py",
         "A disabled connector is unreachable through any code path."),
        ("Audit / Logging", PARTIAL, "orchestrator/pipeline.py",
         "Stage records and run metadata exist. An append-only audit trail does not."),
        ("Data Privacy", PARTIAL, None,
         "No external egress by default. Formal egress allowlisting is not built."),
        ("Access Control", PLANNED, None, "No identity or RBAC layer today."),
        ("Policy Engine", PLANNED, None, "Per-agent connector policy is not enforced."),
        ("Encryption", PLANNED, None, "A deployment-layer concern, not addressed today."),
    )),
    ("6", "Interactive Chat (optional)", (
        ("Conversational Interface", PLANNED, None,
         "Designed as a second interface over the SAME context and agents, "
         "never a separate intelligence engine."),
    )),
)

DATA_FLOW = (
    ("Input Connectors", "Customer systems remain outside the appliance."),
    ("Ingestion and Normalisation", "Vendor payloads become canonical entities."),
    ("Data and Context", "One connector-neutral engineering context."),
    ("Agent Orchestration", "Only the relevant specialists are invoked."),
    ("Analytics and Inference", "Impact, risk, verification and evidence."),
    ("Engineering Outputs", "One context, many engineering deliverables."),
)

PRINCIPLES = (
    ("Plug and play connectors", IMPLEMENTED,
     "Enable or disable at runtime with no restart and no image rebuild."),
    ("Many connectors active simultaneously", IMPLEMENTED,
     "Capability-aware fan-out merges results into one context."),
    ("Read-only by default", IMPLEMENTED,
     "No write method exists on the connector contract."),
    ("No automatic write-back", IMPLEMENTED,
     "Designed but deliberately not implemented."),
    ("Model agnostic and BYOK", IMPLEMENTED,
     "No provider SDK is imported outside the model layer; a test enforces it."),
    ("Enterprise independent", IMPLEMENTED,
     "Runs with zero connectors; agents never reference a vendor."),
    ("Provenance aware", IMPLEMENTED,
     "Provenance is mandatory at construction and propagates through reasoning."),
    ("Evidence aware", IMPLEMENTED,
     "Every cited id is verified; unsupported claims are downgraded or removed."),
    ("Customer controlled", IMPLEMENTED,
     "Configuration and credentials are supplied at runtime, never baked in."),
    ("Portable and containerised", IMPLEMENTED,
     "Runs offline from a container image with no embedded model."),
)


def verify() -> list[str]:
    """A component claiming IMPLEMENTED must have its module on disk."""
    problems = []
    for _, layer, components in LAYERS:
        for name, status, module, _note in components:
            if status in (IMPLEMENTED, PARTIAL) and module:
                if not os.path.exists(os.path.join(HERE, module)):
                    problems.append(f"{layer} / {name}: missing module {module}")
            if status == IMPLEMENTED and module is None:
                problems.append(f"{layer} / {name}: claims IMPLEMENTED with no module")
    return problems


def model() -> dict:
    layers = []
    for number, name, components in LAYERS:
        rows = [{"name": n, "status": s, "module": m, "note": note}
                for n, s, m, note in components]
        layers.append({
            "number": number, "name": name, "components": rows,
            "counts": {status: sum(1 for r in rows if r["status"] == status)
                       for status in (IMPLEMENTED, PARTIAL, PLANNED)},
        })
    total = [c for _, _, comps in LAYERS for c in comps]
    return {
        "layers": layers,
        "data_flow": [{"stage": s, "note": n} for s, n in DATA_FLOW],
        "principles": [{"name": n, "status": s, "note": note}
                       for n, s, note in PRINCIPLES],
        "summary": {
            "components": len(total),
            IMPLEMENTED: sum(1 for c in total if c[1] == IMPLEMENTED),
            PARTIAL: sum(1 for c in total if c[1] == PARTIAL),
            PLANNED: sum(1 for c in total if c[1] == PLANNED),
        },
        "verification_problems": verify(),
    }
