"""Agent Skills markdown loader.

Parses the Anthropic Agent Skills format used by both upstream substrates:
YAML frontmatter plus a markdown body, with optional references/ and assets/.

The body is loaded VERBATIM and used as agent system context. It is never
summarised, restructured or "improved" - the upstream wording is the expertise,
and editing it creates attribution obligations and drift.

The loader is format-driven, not name-driven: adding a skill to a pack makes it
loadable with zero appliance code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

from ..core.errors import ConfigurationError


@dataclass
class AgentDefinition:
    name: str
    description: str
    body: str
    licence: str
    pack: str
    source_path: str
    kind: str                      # "agent" | "skill"
    category: str
    metadata: dict[str, Any] = field(default_factory=dict)
    _reference_dir: str | None = None

    def references(self) -> dict[str, str]:
        """Loaded lazily - some references are large and rarely needed."""
        out: dict[str, str] = {}
        if not self._reference_dir or not os.path.isdir(self._reference_dir):
            return out
        for name in sorted(os.listdir(self._reference_dir)):
            path = os.path.join(self._reference_dir, name)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as fh:
                    out[name] = fh.read()
        return out

    def attribution(self) -> str:
        return f"{self.name} ({self.pack}, {self.licence})"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 4:].lstrip("\n")
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), body


class SkillRegistry:
    """Every loaded agent and skill, indexed by name and searchable by intent."""

    def __init__(self) -> None:
        self._defs: dict[str, AgentDefinition] = {}
        self._skipped: list[dict] = []

    def load_pack(self, pack_dir: str, pack_name: str,
                  require_mit: bool = True) -> int:
        if not os.path.isdir(pack_dir):
            raise ConfigurationError(f"Pack directory not found: {pack_dir}")
        loaded = 0
        for root, _, files in os.walk(pack_dir):
            for filename in files:
                if filename not in ("SKILL.md", "AGENTS.md") and not (
                        os.path.basename(root) == "agents" and filename.endswith(".md")):
                    continue
                path = os.path.join(root, filename)
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
                meta, body = _parse_frontmatter(text)
                rel = os.path.relpath(path, pack_dir).replace("\\", "/")

                name = meta.get("name") or os.path.basename(root) or filename[:-3]
                licence = str(meta.get("license") or meta.get("licence") or "").upper()
                if require_mit and licence != "MIT" and filename == "SKILL.md":
                    # Per-item licence gate: never rely on a repo-level statement.
                    self._skipped.append({"path": rel, "reason": "no MIT declaration",
                                          "declared": licence or "(absent)"})
                    continue

                kind = "agent" if ("/agents/" in rel or filename == "AGENTS.md") else "skill"
                parts = rel.split("/")
                category = parts[1] if len(parts) > 2 and parts[0] == "skills" else pack_name

                self._defs[name] = AgentDefinition(
                    name=name,
                    description=str(meta.get("description") or "").strip(),
                    body=body, licence=licence or "MIT", pack=pack_name,
                    source_path=rel, kind=kind, category=category,
                    metadata=meta.get("metadata") or {},
                    _reference_dir=os.path.join(root, "references"))
                loaded += 1
        return loaded

    # -- access ------------------------------------------------------------
    def get(self, name: str) -> AgentDefinition | None:
        return self._defs.get(name)

    def all(self) -> list[AgentDefinition]:
        return sorted(self._defs.values(), key=lambda d: (d.kind, d.name))

    def agents(self) -> list[AgentDefinition]:
        return [d for d in self.all() if d.kind == "agent"]

    def skills(self) -> list[AgentDefinition]:
        return [d for d in self.all() if d.kind == "skill"]

    def skipped(self) -> list[dict]:
        return list(self._skipped)

    def skills_for(self, intent: str, limit: int = 5) -> list[AgentDefinition]:
        """Intent lookup derived from frontmatter, not a hardcoded map, so a new
        upstream skill becomes selectable with no code change."""
        terms = [t for t in intent.lower().split() if len(t) > 2]
        scored = []
        for definition in self._defs.values():
            blob = f"{definition.name} {definition.description} {definition.category}".lower()
            hits = sum(1 for t in terms if t in blob)
            if hits:
                scored.append((hits, definition))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [d for _, d in scored[:limit]]

    def summary(self) -> dict:
        return {"total": len(self._defs),
                "agents": len(self.agents()), "skills": len(self.skills()),
                "packs": sorted({d.pack for d in self._defs.values()}),
                "skipped": len(self._skipped)}
