# Architecture — one core, two domains

The fire-engineering demonstrator does **not** fork or rewrite the appliance. It adds a
domain pack and a small number of domain-neutral extension points. Everything that makes the
automotive demonstration credible — the pipeline, the context and traversal, the evidence
gate, deterministic confidence, provenance, the workflow engine and its validation rules —
is shared unchanged.

```
                    ┌─────────────────────────── appliance core (shared) ───────────────────────────┐
 scenario ──▶ service.analyse_scenario
                │  scenario → domain profile + its connector
                ▼
            OrchestrationPipeline(profile, connector_ids)
              1 intent classification
              2 evidence plan
              3 retrieval  ── registry.fan_out(within=[connector]) ──▶ SimulationConnector instance
                 closure + structural completion                      (SIMULATION | FIRE_SIMULATION)
                 evidence basis (baseline → proposed) from the subject record
              4 specialists: domain role ← profile.specialist
                              requirements / quality / evidence roles ← shared classes,
                              backed by the profile's definitions, renamed by the profile
              5 synthesis
              6 EvidenceGate
                ▼
            session: result · reviews (beside findings) · audit log
                ▼
            WorkflowEngine.run(variant ← profile.workflows[id], reviews)
              section builders · validation (no fabricated ids, no invented criteria,
              unknowns declared, human review applied)
                    └───────────────────────────────────────────────────────────────────────────────┘
```

## Product surfaces

The presentation layer is domain-aware; the engine is not forked.

```
request ──▶ session.surface (chosen domain) ──▶ templates/<surface>/…   page chrome, navigation
         └▶ session.domain  (analysed domain) ─▶ templates/<surface>/partials/…  analysis, explain,
                                                                        review, outputs
view-models: appliance/presentation.py (shared) + appliance/surface.py (surface-driven)
content:     packs/<pack>/surface.yaml   vocabulary: domain_profile.labels / terms / workflow_aliases
```

- `config/appliance.yaml` `default_domain: fire-engineering` makes the fire surface the first
  page a new visitor sees. `/domain/{domain}` switches a browser's surface and clears any
  analysis from another domain; analysing a scenario selects its domain's surface.
- `appliance/surface.py` computes, from the real corpus and result, which conceptual knowledge
  sources are represented, which fire-engineering domains carry records (via `domain_areas`
  on records), the architecture layers' live facts, gap classes and relationship paths. It
  selects, counts and labels; it does not reason.
- `labels` rename entity types, record fields and output columns for the surface;
  `terms` give the shared risk specialist its domain wording (fire hazard, review priority)
  with automotive wording as the default; `workflow_aliases` let the fire surface address
  workflows by its own names (`verification-evidence-plan`).
- Review responses update, out of band, only the regions the calling page reports it has, and
  regenerate the output already on screen so a decision is visible at once.

## The domain pack

`packs/fire-engineering/`

| Path | Role |
|---|---|
| `pack.yaml` | Pack metadata, dataset provenance and the `domain_profile` (labels, terms, workflow variants and aliases) |
| `surface.yaml` | Product-surface content: identity, notice, narrative, conceptual knowledge sources, domain taxonomy, capabilities, outputs, architecture layers |
| `agents/fire-engineer.md` | Operating profile for the DOMAIN role |
| `agents/fire-hazard-reviewer.md` | Profile for the quality/risk role |
| `agents/fire-requirements-analyst.md` | Profile for the requirements role |
| `agents/verification-evidence-planner.md` | Profile for the evidence role |
| `data/*.json` | Synthetic corpus in the simulation dataset format, each with the public envelope |
| `scenarios/SCN-F01.json` | The demonstrator scenario |

`domain_profile` declares: the specialist that fills the domain role, the definition backing
each role, display names, the connector id, UI vocabulary, the outputs relevant to the domain,
and per-workflow **variants** (for example `dvpr` → *Verification & Evidence Plan* with its own
section list). The automotive profile is built in (`appliance/orchestrator/domain.py`)
because the automotive packs are copied verbatim from upstream (MIT, see docs/THIRD_PARTY.md).

## Generic entity model — no new core types

The fire corpus uses only existing entity types: `EngineeringChange`, `System`, `Subsystem`,
`Component`, `Requirement`, `FailureMode`, `TestCase`, `TestResult`, `Evidence`, `Standard`,
`Document`, and the existing relationship vocabulary (`AFFECTS`, `ALLOCATED_TO`,
`VERIFIED_BY`, `PRODUCES`, `SUPPORTS`, `APPLIES_TO`, `HAS_FAILURE_MODE`, `DESCRIBES`, …).
There is no `Building`, `FireStrategy` or `EvacuationStrategy` type. Fire semantics live in
record attributes:

| Attribute | On | Meaning |
|---|---|---|
| `baseline_basis`, `proposed_basis` | change | The design basis the change moves from and to (`office` → `residential`) |
| `basis` | requirement, document, evidence, result | The basis the record was established on |
| `unrecorded_design_inputs` | change | Inputs the assessment needs that the record does not contain |
| `regulatory_reference`, `standard_ids` | requirement | What the requirement traces to (identifiers only) |
| `applicability`, `applicability_note` | requirement | `applies` or `to_be_confirmed`, with why |
| `acceptance_criterion_established` | test | Whether a criterion exists; `false` means the criterion is `null` |
| `action_priority`, `action_priority_method` | failure mode | Qualitative review priority, with its method declared |

## Changes to the core, and why each is domain-neutral

| Change | Where | Why it is not fire-specific |
|---|---|---|
| **Evidence basis** — `set_evidence_basis`, `transferability_reason`; `is_stale` checks a superseded basis, then an explicit `transferable` flag, then the existing free-text markers | `core/context.py` | A basis can be a build configuration, an occupancy or an operating envelope. The automotive text markers still work. |
| Pipeline sets the basis from the subject record when it declares one | `orchestrator/pipeline.py` | Reads two optional attributes; absent → unchanged behaviour |
| **Domain role** — `INTENT_SPECIALISTS` names a `domain` role filled from the profile; roles can be renamed and backed by a pack's definitions | `orchestrator/pipeline.py`, `orchestrator/domain.py`, `specialists/base.py` | Removes the accidental hard-wiring of the automotive engineer into every change analysis |
| `DomainSpecialist` base with shared impacted-system derivation | `specialists/analysts.py` | Graph traversal is identical for a vehicle and a building |
| Scoped retrieval — `fan_out(within=…)` | `connectors/registry.py` | An analysis of one dataset must not silently merge another's records |
| One adapter, several instances; provenance URL/licence from `pack.yaml` | `connectors/adapters/simulation.py` | Same adapter; the second instance is registered under its own catalogue id |
| Workflow **variants** and review-aware builders; `human_review_applied` validation; generic `NOT ESTABLISHED` marker | `workflows/engine.py`, `workflows/sections.py`, `workflows/catalogue.py` | Same engine and builders; a variant renames and re-sections, it cannot remove base validation rules |
| Rating fragment `(S/O/D)` only when the record carries ratings | `specialists/analysts.py` | A dataset without S/O/D ratings must not acquire them in prose |
| A pass with no established criterion is not counted as passing evidence | `specialists/analysts.py` | It cannot be judged, in any domain |
| Finding-level human review stored beside findings | `service.py`, `api/app.py` | Operates on any finding in any domain |

## The fire specialist

`appliance/agents/specialists/fire.py` — `FireEngineeringSpecialist(DomainSpecialist)`.
`derive()` is deterministic graph and set reasoning only:

- impacted domains (shared traversal)
- change classification from the change record
- applicable requirements grouped by the standard records they cite; UNKNOWN for each
  requirement whose applicability is not established
- records established on the superseded basis
- evidence transferability per result and evidence record
- requirements with no verification activity
- UNKNOWN for design inputs the change record does not contain

It contains no fire-engineering rules: every conclusion is a comparison of recorded
attributes. The engineering judgement lives in the pack data and its instructions, and with
the human reviewer.

## Human review

`POST /review/{finding_id}` (HTML) and `POST /api/review/{finding_id}` (JSON) record a decision
on one finding. Records are stored in the client's session (`Session.reviews`, latest per
finding, and `Session.review_log`, append-only), never on the `Finding`. Each holds
`decision`, `reviewer`, `note`, `timestamp`, `finding_snapshot {statement, classification,
confidence_score, evidence_ids}`, `run_id` and `context_snapshot_id`. Reject requires a
note. A new analysis starts with no reviews. Generated outputs are invalidated by a new
decision; regenerating applies it:

- finding lists withhold rejected findings and say so
- plan rows justified by a rejected finding show **REJECTED** and their action becomes
  **HELD … Original action: …**
- a *Human review record* section lists every decision with its snapshot
- `human_review_applied` validation blocks an output that presents a rejected finding

## Sessions

Per-browser isolation (existing): an opaque random cookie binds each request to its own
`Session` through a context variable; at most 64 sessions are held, least recently used first
out. Reviews inherit this isolation.
