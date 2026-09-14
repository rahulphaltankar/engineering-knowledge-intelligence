"""Cross-specialist synthesis and the evidence sufficiency gate.

Synthesis turns several specialist reports into one coherent set. The evidence
gate is the appliance's core credibility control: it verifies that every cited
entity actually exists in the context, and downgrades or removes anything the
evidence does not support.

Citation verification is cheap and catches the most damaging failure mode there
is - a fabricated evidence id that makes an invented claim look sourced.
"""
from __future__ import annotations

import re
from collections import defaultdict

from ..core.context import EngineeringContext
from ..core.provenance import (Classification, Confidence, Finding,
                               score_confidence, weakest)

ID_PATTERN = re.compile(r"\b[A-Z]{2,6}-[A-Z]?-?\d{3,4}\b")


def _normalise(statement: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", statement.lower()).strip()


def synthesise(findings: list[Finding]) -> tuple[list[Finding], list[dict]]:
    """Deduplicate, attribute and re-score.

    Two specialists independently reaching the same conclusion from different
    evidence is a genuinely stronger signal, and confidence reflects that.
    Disagreement is surfaced, never resolved by picking the more confident
    specialist.
    """
    buckets: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        buckets[_normalise(finding.statement)[:120]].append(finding)

    merged: list[Finding] = []
    for group in buckets.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        primary = group[0]
        producers, evidence, tags, unknowns = [], [], [], []
        seen_ev = set()
        for item in group:
            producers.extend(item.produced_by)
            tags.extend(item.tags)
            unknowns.extend(item.unknowns)
            for ref in item.evidence:
                if ref.entity_id not in seen_ev:
                    seen_ev.add(ref.entity_id)
                    evidence.append(ref)
        classification = weakest([f.classification for f in group])
        band, score = score_confidence(
            evidence_count=len(evidence),
            independent_sources=len(set(producers)),
            classification=classification,
            agreeing_specialists=len(set(producers)))
        merged.append(primary.model_copy(update={
            "produced_by": sorted(set(producers)), "evidence": evidence,
            "tags": sorted(set(tags)), "unknowns": sorted(set(unknowns)),
            "classification": classification, "confidence": band,
            "confidence_score": score,
            "rationale": primary.rationale +
                         (f" Corroborated by {len(set(producers))} specialists."
                          if len(set(producers)) > 1 else "")}))

    conflicts = _detect_conflicts(merged)
    merged.sort(key=lambda f: (-f.confidence_score, f.id))
    return merged, conflicts


def _detect_conflicts(findings: list[Finding]) -> list[dict]:
    """Opposed claims about the same subject, reported rather than resolved."""
    conflicts = []
    for i, a in enumerate(findings):
        for b in findings[i + 1:]:
            shared = set(a.evidence_ids) & set(b.evidence_ids)
            if not shared:
                continue
            a_neg = " no " in f" {a.statement.lower()} " or "not " in a.statement.lower()
            b_neg = " no " in f" {b.statement.lower()} " or "not " in b.statement.lower()
            if a_neg != b_neg and _normalise(a.statement)[:40] == _normalise(b.statement)[:40]:
                conflicts.append({"finding_a": a.id, "finding_b": b.id,
                                  "shared_evidence": sorted(shared)})
    return conflicts


class EvidenceGate:
    """Blocks unsupported claims before they reach a user."""

    def __init__(self, context: EngineeringContext) -> None:
        self.context = context
        self.removed: list[dict] = []
        self.downgraded: list[dict] = []
        self.fabricated_citations: list[str] = []

    def apply(self, findings: list[Finding]) -> list[Finding]:
        kept: list[Finding] = []
        for finding in findings:
            verified = [ref for ref in finding.evidence if self.context.has(ref.entity_id)]
            fabricated = [ref.entity_id for ref in finding.evidence
                          if not self.context.has(ref.entity_id)]

            # Ids mentioned in prose but never cited are also checked.
            for candidate in ID_PATTERN.findall(finding.statement):
                if not self.context.has(candidate) and candidate not in fabricated:
                    fabricated.append(candidate)

            if fabricated:
                self.fabricated_citations.extend(fabricated)

            if finding.classification is Classification.UNKNOWN:
                kept.append(finding.model_copy(update={"evidence": verified}))
                continue

            if not verified:
                # A claim with no verifiable evidence is downgraded to ASSUMED
                # with the assumption stated, or removed if it cannot be stated
                # honestly at all.
                if finding.tags and "model_interpretation" in finding.tags:
                    self.removed.append({"id": finding.id, "statement": finding.statement,
                                         "reason": "no verifiable evidence in context"})
                    continue
                band, score = score_confidence(
                    evidence_count=0, independent_sources=0,
                    classification=Classification.ASSUMED)
                self.downgraded.append({"id": finding.id, "from": finding.classification.value,
                                        "to": "ASSUMED"})
                kept.append(finding.model_copy(update={
                    "classification": Classification.ASSUMED,
                    "confidence": band, "confidence_score": score,
                    "evidence": [],
                    "assumptions": finding.assumptions +
                                   ["Stated without verifiable supporting evidence "
                                    "in the retrieved context."]}))
                continue

            if len(verified) < len(finding.evidence):
                band, score = score_confidence(
                    evidence_count=len(verified), independent_sources=1,
                    classification=finding.classification)
                kept.append(finding.model_copy(update={
                    "evidence": verified, "confidence": band, "confidence_score": score}))
            else:
                kept.append(finding)
        return kept

    def report(self) -> dict:
        return {"removed": self.removed, "downgraded": self.downgraded,
                "fabricated_citations": sorted(set(self.fabricated_citations)),
                "fabricated_citation_count": len(set(self.fabricated_citations))}


def collect_unknowns(findings: list[Finding]) -> list[str]:
    """Every declared unknown, surfaced as prominently as the findings.

    Burying what the system does not know defeats the whole honesty design.
    """
    unknowns: list[str] = []
    for finding in findings:
        unknowns.extend(finding.unknowns)
        if finding.classification is Classification.UNKNOWN and finding.statement:
            unknowns.append(finding.statement)
    seen, ordered = set(), []
    for item in unknowns:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
