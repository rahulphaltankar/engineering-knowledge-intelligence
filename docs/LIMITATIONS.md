# Limitations

## What this demonstrator is not

- **Not production software.** It is a public demonstrator of an architecture.
- **Not fire-safety design, assessment, certification or sign-off software.** It does not
  determine compliance with Building Regulations, Approved Documents, British Standards or
  legislation, and must not be used to make or support real fire-safety decisions.
- **Not BB7 internal data or a BB7 system.** BB7 did not commission it. Nothing in it
  describes BB7's internal technology, processes, knowledge or data.
- **Not an OEM implementation.** The automotive demonstration uses a synthetic dataset.
- **Not a source of standards content.** Standards and legislation are referenced by
  identifier and title only. Editions are deliberately not pinned; requirement statements are
  plain-language synthetic text, not quotations.

## Data

- The fire-engineering corpus is small (64 records, 117 relationships) and authored to
  exercise specific behaviours. It does not represent a real building, strategy or project.
- Regulatory references are indicative, at requirement level (for example Part B, B1). They
  are not a determination of which requirements apply to a material change of use; the
  demonstrator reports applicability it cannot establish as UNKNOWN.
- Failure-mode "review priority" is a qualitative label in synthetic data, not a fire risk
  assessment.

## Reasoning

- Deterministic mode (the default) computes findings from recorded attributes and graph
  structure. It cannot notice a hazard, requirement or evidence gap that the data does not
  represent.
- Transferability is a comparison of recorded `basis` values. Real transferability judgements
  (partial applicability, conservative bounding, engineering argument) are richer and belong
  to a competent engineer.
- Intent classification is keyword based; the change classification is read from the change
  record rather than inferred from free text.
- Traversal depth is fixed at 2 (configurable). Records beyond it are not reached.
- Model interpretation (optional, bring your own key) has not been evaluated for fire
  engineering; its findings are INFERRED, bounded, and removed if the evidence gate cannot
  verify their citations.

## Human review

- **Session scoped and unauthenticated.** The reviewer name is self-declared. There is no
  identity, role, competence check, approval workflow, signature or persistent audit trail.
- Reviews live in process memory, are lost on restart or session eviction (64 sessions),
  and are cleared by a new analysis.
- A rejection holds the actions its finding justified; it does not re-run analysis or record
  an alternative engineering position.

## Product surface

- Knowledge-source categories (fire strategies, drawings, calculations, lessons learned,
  previous project evidence, expert knowledge …) are conceptual. Only categories matched by
  records in the synthetic corpus are shown as represented; the rest are labelled conceptual.
  None describes any organisation's actual systems.
- Smoke control is not modelled as records in the corpus; it appears only as an unrecorded
  design input of the change.
- The surface is chosen per browser session. The automotive reference demonstration remains
  reachable at `/domain/automotive` and keeps its own terminology and DVP&R output.
- Knowledge-structure counts use simple labels ("4 Element") without pluralisation.

## Outputs

- Three outputs are executable: Engineering/Fire Change Impact Assessment, DVP&R /
  Verification & Evidence Plan, and Evidence Gap Analysis. Others in the catalogue are shown
  honestly as planned or not applicable.
- No export to document formats; JSON is available via the API.

## Packaging

- The MIT-licensed upstream packs for the automotive reference demonstration are included so
  a fresh clone is self-contained; the fire demonstrator does not depend on them.
- No container image definition is published; run with Python as described in the README.
- No authentication, TLS, rate limiting or multi-process session store; do not expose it
  beyond a controlled demonstration.
