"""Context serialisation for prompts.

Renders an EngineeringContext into a compact, id-stable textual form under a
token budget.

The important property is what happens when the budget is exceeded: the output
SAYS SO, naming how many records were omitted and of what type. A silently
truncated context is how a system produces a confidently wrong answer with no
signal that anything was missing.
"""
from __future__ import annotations

from .context import EngineeringContext

# Fields worth showing per entity type. Everything else stays out of the prompt:
# the extensions blob in particular is large and rarely aids reasoning.
FIELDS = {
    "EngineeringChange": ("title", "description", "change_type", "status", "driver", "phase"),
    "System": ("name", "domain", "description"),
    "Subsystem": ("name", "description"),
    "Component": ("name", "part_number", "revision", "supplier_id"),
    "Requirement": ("title", "statement", "level", "requirement_type", "asil", "status"),
    "FailureMode": ("failure_mode", "failure_effect", "failure_cause", "severity",
                    "occurrence", "detection", "action_priority"),
    "FMEA": ("title", "fmea_type", "status"),
    "Risk": ("title", "risk_statement", "action_priority", "risk_class"),
    "TestCase": ("title", "method", "conditions", "acceptance_criterion",
                 "acceptance_criterion_established", "phase"),
    "TestResult": ("status", "measured_summary", "deviation", "configuration_id", "notes"),
    "QualityIssue": ("title", "description", "origin", "severity", "occurrence_count"),
    "Evidence": ("title", "evidence_type", "strength", "status"),
    "Standard": ("identifier", "title", "body", "scope_tag"),
    "Supplier": ("name", "tier", "risk_class", "quality_score"),
    "Document": ("title", "document_type", "status", "abstract"),
    "Vehicle": ("name", "body_class", "usable_energy_kwh", "kerb_mass_kg"),
    "Configuration": ("name", "phase", "build_date"),
}

DEFAULT_FIELDS = ("title", "name", "description", "status")


def _render(entity, fields: tuple[str, ...]) -> str:
    parts = [f"{entity.entity_type} {entity.id}"]
    for field in fields:
        value = entity.get(field)
        if value in (None, "", [], {}):
            continue
        text = str(value)
        if len(text) > 240:
            text = text[:237] + "..."
        parts.append(f"  {field}: {text}")
    return "\n".join(parts)


def serialise_context(context: EngineeringContext,
                      focus_ids: list[str] | None = None,
                      max_chars: int = 24000) -> str:
    """Relevance-ordered, budget-aware rendering. Entity ids always visible so a
    model can cite them and the evidence gate can verify the citation."""
    if focus_ids:
        ordered = [context.get(i) for i in focus_ids if context.get(i)]
    else:
        ordered = context.entities

    grouped: dict[str, list] = {}
    for entity in ordered:
        grouped.setdefault(entity.entity_type, []).append(entity)

    blocks: list[str] = []
    used = 0
    omitted: dict[str, int] = {}
    for entity_type in sorted(grouped):
        entities = sorted(grouped[entity_type], key=lambda e: e.id)
        fields = FIELDS.get(entity_type, DEFAULT_FIELDS)
        header = f"\n### {entity_type} ({len(entities)})"
        blocks.append(header)
        used += len(header)
        for entity in entities:
            text = _render(entity, fields)
            if used + len(text) > max_chars:
                omitted[entity_type] = omitted.get(entity_type, 0) + 1
                continue
            blocks.append(text)
            used += len(text)

    if omitted:
        detail = ", ".join(f"{count} {name}" for name, count in sorted(omitted.items()))
        blocks.append(
            f"\n### CONTEXT TRUNCATED\n{sum(omitted.values())} record(s) were omitted "
            f"to stay within the context budget: {detail}. Treat any conclusion that "
            f"would depend on the omitted records as unsupported.")
    return "\n".join(blocks)


def context_digest(context: EngineeringContext) -> str:
    counts = context.types_present()
    return ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
