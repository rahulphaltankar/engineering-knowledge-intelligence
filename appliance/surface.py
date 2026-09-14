"""Domain product-surface view-models.

A domain pack may ship its own product surface (templates/<surface>/ plus a
`surface.yaml` of presentation content). This module turns that content into
view-models by reading the ACTUAL corpus, the ACTUAL analysis result and the
ACTUAL service state:

- a knowledge-source category is "represented" only if records match it
- a fire-engineering domain shows the records that carry it
- every architecture layer states what is really running

Nothing here reasons about engineering. It selects, counts and labels.
"""
from __future__ import annotations

from .core.provenance import Classification
from .presentation import GAP_ACTION, GAP_DETAIL, GAP_LABELS, GAP_SEVERITY, knowledge


def _matches(entity, rule: dict) -> bool:
    if rule.get("entity_type") and entity.entity_type != rule["entity_type"]:
        return False
    for key, allowed in (rule.get("where") or {}).items():
        allowed = allowed if isinstance(allowed, list) else [allowed]
        if entity.get(key) not in allowed:
            return False
    return True


def knowledge_sources(service, profile, records, scope: set[str] | None = None) -> list[dict]:
    content = profile.surface_content
    specialists = [d for d in service.skills.all() if d.pack == profile.pack]
    rows = []
    for source in content.get("knowledge_sources", []):
        rules = source.get("match") or []
        matched, profiles = [], []
        for rule in rules:
            if rule.get("specialist_profiles"):
                profiles = [d.name for d in specialists]
                continue
            matched += [e for e in records if _matches(e, rule)
                        and (scope is None or e.id in scope)]
        ids = sorted({e.id for e in matched})
        types = sorted({profile.label_for(e.entity_type) for e in matched})
        represented = bool(ids or profiles)
        rows.append({"name": source["name"], "description": source.get("description", ""),
                     "represented": represented, "count": len(ids) + len(profiles),
                     "ids": ids[:8], "more": max(len(ids) - 8, 0), "types": types,
                     "profiles": profiles,
                     "status": ("Represented in the synthetic corpus" if ids else
                                "Represented by specialist profiles" if profiles else
                                "Conceptual - not represented in this demonstrator")})
    return rows


def domain_coverage(profile, records, result: dict | None = None) -> list[dict]:
    closure = set((result or {}).get("closure") or {})
    impacted = {}
    for finding in (result or {}).get("findings", []):
        if "impacted_system" in finding.tags:
            impacted[finding.detail.get("system_id")] = finding
    rows = []
    for domain in profile.surface_content.get("domains", []):
        carrying = [e for e in records if domain["name"] in (e.get("domain_areas") or [])]
        systems = [e for e in carrying if e.entity_type == "System"]
        in_scope = [e for e in carrying if e.id in closure]
        reached = [impacted[s.id] for s in systems if s.id in impacted]
        rows.append({
            "name": domain["name"], "description": domain.get("description", ""),
            "note": domain.get("note", ""),
            "records": len(carrying), "in_scope": len(in_scope),
            "by_type": _count_types(profile, carrying),
            "systems": [{"id": s.id, "name": s.title} for s in systems],
            "impacted": bool(reached),
            "finding_ids": [f.id for f in reached],
            "routes": ["direct" if f.detail.get("direct") else
                       f"{f.detail.get('hops')}-step relationship path" for f in reached],
        })
    return rows


def _count_types(profile, entities) -> list[str]:
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
    return [f"{n} {profile.label_for(t)}" for t, n in sorted(counts.items())]


def architecture_facts(service, profile, records) -> dict[str, str]:
    session = service.session
    result = session.result if session.has_analysis else None
    try:
        connector = service.registry.get(profile.connector_id)
        status = connector.status()
        sources = (f"{status['connector_name']} ({profile.connector_id}) - read-only, "
                   f"{status['records_loaded']} records, {status['relationship_edges']} "
                   f"relationships. {status['data_classification']}.")
        edges = status["relationship_edges"]
    except Exception:  # connector disabled or missing: say so
        sources, edges = f"{profile.connector_id} is not active.", 0
    specialists = []
    for role, definition in profile.definitions.items():
        loaded = service.skills.get(definition) is not None
        specialists.append(f"{profile.display_names.get(role, role)}"
                           f"{'' if loaded else ' (profile not loaded)'}")
    facts = {
        "sources": sources,
        "structure": "; ".join(_count_types(profile, records)) + ".",
        "relationships": (f"{edges} typed relationships; traversal depth "
                          f"{service.config.traversal_depth} with structural completion."),
        "retrieval": (f"Scoped to {profile.connector_id}; no other domain's records enter "
                      f"the analysis."
                      + (f" Current analysis reached {len(result['closure'])} of "
                         f"{len(result['context'])} records." if result else "")),
        "reasoning": ("Specialists: " + ", ".join(specialists) + f". Execution mode: "
                      f"{service.provider.describe().get('execution_mode')}."),
        "provenance": ("Evidence gate verifies every citation; confidence is scored "
                       "deterministically."
                       + (f" Current analysis: {len(result['findings'])} findings passed, "
                          f"{result['gate_report']['fabricated_citation_count']} fabricated "
                          f"citations." if result else "")),
        "review": (f"Session scoped · unauthenticated · demonstrator only. "
                   f"{len(session.review_log)} decision(s) recorded in this session."),
        "outputs": ("; ".join(
            f"{profile.workflow_variant(wid).get('name') or wid}"
            for wid in profile.workflow_aliases.values()) + "."),
    }
    return facts


def findings_rows(profile, result: dict, reviews: dict) -> list[dict]:
    rows = []
    for finding in result.get("findings", []):
        rows.append({"id": finding.id, "statement": finding.statement,
                     "classification": finding.classification.value,
                     "confidence": finding.confidence.value,
                     "confidence_score": finding.confidence_score,
                     "evidence_count": len(finding.evidence),
                     "produced_by": ", ".join(finding.produced_by),
                     "tags": finding.tags, "review": reviews.get(finding.id)})
    return rows


def relationship_paths(profile, result: dict, entity_types=("System", "Requirement",
                                                            "TestResult", "Evidence")) -> list[dict]:
    context, closure = result["context"], result["closure"]
    rows = []
    for entity_id, path in closure.items():
        entity = context.get(entity_id)
        if entity is None or entity.entity_type not in entity_types or not path:
            continue
        rows.append({"id": entity.id, "type": profile.label_for(entity.entity_type),
                     "title": entity.title, "steps": path, "hops": len(path)})
    order = {t: i for i, t in enumerate(entity_types)}
    rows.sort(key=lambda r: (order.get(context.get(r["id"]).entity_type, 9), r["id"]))
    return rows


def confidence_profile(result: dict) -> dict:
    counts: dict[str, int] = {}
    for finding in result.get("findings", []):
        counts[finding.classification.value] = counts.get(finding.classification.value, 0) + 1
    scores = [f.confidence_score for f in result.get("findings", [])
              if f.classification is not Classification.UNKNOWN]
    return {"by_class": counts,
            "mean": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "gate": result.get("gate_report", {})}


def gap_classes(result: dict, profile=None) -> list[dict]:
    """Evidence conditions by class. A surface may word them for its domain."""
    content = getattr(profile, "surface_content", None) or {}
    labels = {**GAP_LABELS, **(content.get("gap_labels") or {})}
    details = {**GAP_DETAIL, **(content.get("gap_detail") or {})}
    actions = {**GAP_ACTION, **(content.get("gap_action") or {})}
    groups: dict[str, dict] = {}
    for finding in result.get("findings", []):
        if "evidence_gap" not in finding.tags:
            continue
        gap_type = finding.detail.get("gap_type", "")
        entry = groups.setdefault(gap_type, {"items": [], "finding_ids": []})
        entry["items"].extend(finding.detail.get("items", []) or [])
        entry["finding_ids"].append(finding.id)
    rows = []
    for gap_type in GAP_SEVERITY:
        if gap_type not in groups:
            continue
        rows.append({"gap_type": gap_type, "label": labels.get(gap_type, gap_type),
                     "detail": details.get(gap_type, ""),
                     "action": actions.get(gap_type, "Review"),
                     "pairs": groups[gap_type]["items"],
                     "finding_ids": groups[gap_type]["finding_ids"]})
    return rows


def analysis_view(service, profile) -> dict | None:
    """Everything the fire analysis pages render, for the bound session."""
    session = service.session
    if not session.has_analysis or session.domain != profile.domain:
        return None
    result = session.result
    context = result["context"]
    subject = context.get(result["subject_id"])
    k = knowledge(result)
    tagged = lambda tag: [f for f in result["findings"] if tag in f.tags]  # noqa: E731
    return {
        "result": result,
        "subject": subject,
        "k": k,
        "change_classification": next(iter(tagged("change_classification")), None),
        "design_inputs": next(iter(tagged("design_input_unknown")), None),
        "basis_conflict": next(iter(tagged("basis_conflict")), None),
        "applicability_unknown": tagged("applicability_unknown"),
        "unverified": tagged("verification_gap"),
        "transfer_findings": tagged("transferability"),
        "impacted": sorted(tagged("impacted_system"),
                           key=lambda f: (f.detail.get("hops", 0), f.detail.get("system_id"))),
        "hazards": [f for f in result["findings"] if f.detail.get("failure_mode_id")],
        "gaps": gap_classes(result, profile),
        "unknown_findings": [f for f in result["findings"]
                             if f.classification is Classification.UNKNOWN],
        "unknowns": result.get("unknowns", []),
        "paths": relationship_paths(profile, result),
        "confidence": confidence_profile(result),
        "findings": findings_rows(profile, result, session.reviews),
        "coverage": [{
            "requirement": context.get(r["requirement"]),
            "activities": [{
                "activity": test,
                "criterion_established": test.acceptance_criterion_established,
                "results": [{"result": res, "status": res.result_status,
                             "transferable": not context.is_stale(res)}
                            for res in context.results_for_test(test.id)],
            } for test in sorted(context.tests_for_requirement(r["requirement"]),
                                 key=lambda t: t.id)],
        } for r in k["requirements"]],
        "stages": result.get("stages", []),
        "activity": result.get("activity", []),
        "intents": result.get("intents", []),
        "plan": result.get("evidence_plan", {}),
        "context_types": context.types_present(),
        "standards": [context.get(s) for s in sorted(
            {sid for r in k["requirements"] for sid in (s["id"] for s in r["standards"])})],
    }
