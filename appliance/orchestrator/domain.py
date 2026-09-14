"""Domain profiles: what changes when the same appliance serves another domain.

The orchestration, context, evidence gate, workflow engine and provenance are
domain-neutral. What a domain supplies is small and declarative:

- which specialist fills the DOMAIN role (the only role with domain reasoning)
- which vendored or authored definition backs each specialist role
- the connector that holds the domain's dataset
- the vocabulary the interface and outputs use
- per-workflow presentation variants (a DVP&R in automotive is a Verification &
  Evidence Plan in fire engineering - same engine, same traceability rules)

A pack declares its profile in `pack.yaml` under `domain_profile:`. The
automotive profile is built in, because the automotive packs are vendored
verbatim from upstream and carry no appliance-specific manifest.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field

import yaml

DEFAULT_VOCABULARY: dict[str, str] = {
    "product_name": "Engineering Intelligence",
    "change_heading": "What changed",
    "affected_heading": "What is affected",
    "affected_metric": "Systems affected",
    "cross_domain_metric": "Beyond the change",
    "gaps_metric": "Verification gaps",
    "attention_heading": "What needs attention",
    "actions_heading": "What engineering should do next",
    "unknowns_heading": "What the appliance could not establish",
    "risk_heading": "Highest-severity failure modes in scope",
    "risk_rating": "sod",
    "analyse_button": "Analyse impact",
    "subject_noun": "engineering change",
}


@dataclass
class DomainProfile:
    domain: str
    label: str
    specialist: str
    definitions: dict[str, str] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    connector_id: str | None = None
    vocabulary: dict[str, str] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    presentation: str = "standard"          # standard | knowledge
    pack: str | None = None
    disclaimer: str = ""
    # Per-workflow presentation variants: name, description, upstream_skills,
    # sections, validation_rules. Same engine, same builders, same rules.
    workflows: dict[str, dict] = field(default_factory=dict)
    catalogue_names: dict[str, str] = field(default_factory=dict)
    # Domain wording for the shared specialists and labels for entity types,
    # record fields and output columns. Defaults are the automotive wording.
    terms: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    workflow_aliases: dict[str, str] = field(default_factory=dict)
    # A dedicated product surface (templates/<surface>/) and its content.
    surface: str | None = None
    surface_content: dict = field(default_factory=dict)

    def word(self, key: str) -> str:
        return self.vocabulary.get(key) or DEFAULT_VOCABULARY.get(key, key)

    def label_for(self, key: str) -> str:
        return self.labels.get(key) or key.replace("_", " ")

    def alias_for(self, workflow_id: str) -> str:
        for alias, target in self.workflow_aliases.items():
            if target == workflow_id:
                return alias
        return workflow_id

    def workflow_variant(self, workflow_id: str) -> dict:
        return dict(self.workflows.get(workflow_id) or {})

    def as_dict(self) -> dict:
        data = asdict(self)
        data["vocabulary"] = {**DEFAULT_VOCABULARY, **self.vocabulary}
        return data


AUTOMOTIVE = DomainProfile(
    domain="automotive",
    label="Automotive engineering",
    specialist="automotive",
    definitions={"domain": "automotive-engineer", "quality": "fmea-reviewer",
                 "requirements": "apqp", "evidence": "dvp-test-plan"},
    connector_id="SIMULATION",
)


def load_profiles(packs_dir: str) -> dict[str, DomainProfile]:
    """Built-in automotive profile plus any profile a pack declares."""
    profiles = {AUTOMOTIVE.domain: AUTOMOTIVE}
    if not os.path.isdir(packs_dir):
        return profiles
    for name in sorted(os.listdir(packs_dir)):
        manifest = os.path.join(packs_dir, name, "pack.yaml")
        if not os.path.exists(manifest):
            continue
        with open(manifest, "r", encoding="utf-8") as fh:
            meta = yaml.safe_load(fh) or {}
        raw = meta.get("domain_profile")
        if not isinstance(raw, dict) or not raw.get("domain"):
            continue
        surface_file = os.path.join(packs_dir, name, "surface.yaml")
        if os.path.exists(surface_file):
            with open(surface_file, "r", encoding="utf-8") as fh:
                meta["surface"] = yaml.safe_load(fh) or {}
        profile = DomainProfile(
            domain=raw["domain"], label=raw.get("label") or raw["domain"],
            specialist=raw.get("specialist") or raw["domain"],
            definitions=dict(raw.get("definitions") or {}),
            display_names=dict(raw.get("display_names") or {}),
            connector_id=raw.get("connector_id"),
            vocabulary=dict(raw.get("vocabulary") or {}),
            outputs=list(raw.get("outputs") or []),
            presentation=raw.get("presentation") or "standard",
            pack=name, disclaimer=str(raw.get("disclaimer") or "").strip(),
            workflows=dict(raw.get("workflows") or {}),
            catalogue_names=dict(raw.get("catalogue_names") or {}),
            terms=dict(raw.get("terms") or {}),
            labels=dict(raw.get("labels") or {}),
            workflow_aliases=dict(raw.get("workflow_aliases") or {}),
            surface=raw.get("surface"),
            surface_content=dict(meta.get("surface") or {}))
        profiles[profile.domain] = profile
    return profiles
