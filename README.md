# Fire Engineering Knowledge Intelligence

**Evidence-grounded technical decision support for fire engineering**

*BB7 × University of Leeds KTP Demonstrator — synthetic public demonstration data, not BB7
internal data.*

> ## Read this first
>
> - **This is an independent public demonstrator.** It was **not commissioned, supplied or
>   endorsed by BB7** (or the University of Leeds), is not deployed at or used by BB7, and has
>   **no access to BB7 internal systems or data**.
> - **All data is synthetic.** It is **not BB7 internal data**, and not client, project or
>   OEM data. It is **not an OEM implementation**.
> - **It is not production safety certification software**, and not fire-safety design,
>   assessment or decision software. It has no authority over any fire-engineering decision;
>   every output would require review by a competent fire engineer.
> - **Human review is demonstrated but is session-scoped and unauthenticated**: reviewer names
>   are self-declared, decisions last for a browser session, and nothing here is identity,
>   approval or sign-off.
> - **Purpose:** to show an **architectural hypothesis for the problem described publicly for
>   the BB7 × University of Leeds KTP** — how engineering knowledge can be structured,
>   retrieved with provenance, reasoned over auditably, bounded by explicit unknowns and
>   reviewed by an engineer.
> - **Prior work:** the same underlying engineering-intelligence pattern was **previously
>   developed in an automotive engineering context**. That automotive reference demonstration
>   (synthetic data) is retained in this repository to show the engine is domain-neutral.

---

## What this is

One engineering-intelligence architecture, demonstrated in two domains:

| | Previously developed (reference) | KTP-specific demonstrator |
|---|---|---|
| Domain | Automotive engineering | Fire engineering |
| What it shows | Engineering knowledge intelligence demonstrated in an automotive engineering environment | The same architectural principles applied to the fire-engineering knowledge-management and training problem described publicly by BB7 |
| Scenario | `SCN-001` energy storage capacity increase (and 11 more) | `SCN-F01` Level 3 office-to-residential change of use |
| Dataset | Synthetic automotive simulation dataset (`packs/simulation`, MIT) | `packs/fire-engineering` synthetic corpus |
| Main output | DVP&R | Verification & Evidence Plan |

**Context.** BB7 Consulting is a fire-engineering and built-environment consultancy. Its
May 2026 public announcement describes a 2.5-year Knowledge Transfer Partnership with the
University of Leeds, supported by Innovate UK, to develop a Knowledge Management and Training
Platform using Explainable AI and Machine Learning, beginning with fire engineering, to
capture, organise and share technical expertise. This demonstrator responds to that
**publicly described** problem. **BB7 did not commission it**, and nothing here describes or
implies any BB7 internal system, technology or data. Source: see
[docs/SOURCE-REGISTER.csv](docs/SOURCE-REGISTER.csv).

## Two product surfaces, one engine

The application serves a **domain-specific product surface** on top of one shared
intelligence engine. The surface is chosen per browser session from the active domain:

| | Fire engineering (default) | Automotive reference |
|---|---|---|
| Opens at | `/` for a new visitor | `/domain/automotive` |
| Identity | Fire Engineering Knowledge Intelligence | Engineering Knowledge Intelligence |
| Navigation | Overview · Analyse Change · Requirements · Evidence · Reasoning · Verification Plan · Review · Architecture | Intelligence · Architecture · Data sources · Engineering outputs · Evidence |
| Architecture view | Fire Engineering Knowledge Intelligence Architecture (knowledge sources → … → technical decision output) | Enterprise appliance architecture and connector catalogue |
| Main output | Verification & Evidence Plan | DVP&R |
| Templates | `appliance/api/templates/fire/` | `appliance/api/templates/` |
| Content | `packs/fire-engineering/surface.yaml` | built in |

Analysing a scenario selects its domain's surface; `/domain/fire-engineering` returns to the
fire surface. The pipeline, evidence gate, provenance, confidence scoring, workflow engine and
review control are the same code in both.

The fire surface never shows automotive product-lifecycle or quality vocabulary (DVP&R,
PLM/CAD/BOM, FMEA, supplier quality, the connector catalogue); a test scans every fire page,
derivation panel, review response and output for it. Its knowledge-source categories are
**conceptual** and labelled as such; their coverage, and the coverage of the nine
fire-engineering domains, is computed from the synthetic corpus at runtime.

## The flow it demonstrates

```
INPUT                     engineering change / scenario
  ↓ CLASSIFICATION        change type, and the design basis it moves from and to
  ↓ APPLICABLE REQUIREMENTS   requirements in scope and the references they trace to
  ↓ KNOWLEDGE / RELATIONSHIPS graph traversal with a justifying path per record
  ↓ EVIDENCE RETRIEVAL    results, evidence records and documents in scope
  ↓ IMPACT / RISK REASONING   domains reached, prioritised hazards
  ↓ EVIDENCE TRANSFERABILITY  does existing evidence still apply to the new basis?
  ↓ UNKNOWN / GAP DETECTION   not run · inconclusive · no criterion · not transferable · no result
  ↓ CONFIDENCE + PROVENANCE   deterministic confidence; evidence gate; source of every record
  ↓ HUMAN REVIEW          accept / reject each finding (reject requires a note)
  ↓ VERIFICATION / ACTION OUTPUT  plan traced requirement → test → result/evidence → finding
```

Every step in the UI's *Evidence and reasoning trace* panel is populated from the pipeline
stages that actually ran. Every finding has an **Explain** control that opens its
**Auditable derivation**: classification and why, deterministic confidence basis, evidence
IDs with source and provenance, relationship paths, assumptions, unknowns, the evidence-gate
outcome, and the reviewer control.

## SCN-F01

> Change of use on Level 3 of an existing 8-storey mixed-use building from office use to six
> residential apartments. Single stair. Category L2 fire alarm. Existing fire strategy is
> based on simultaneous evacuation of the office population. Sprinklers are not fitted above
> Level 1.

The synthetic corpus deliberately contains:

| Condition | Where |
|---|---|
| Test not run | `FTR-006` flat entrance doorsets, `FTR-007` sprinkler assessment |
| Inconclusive result with deviation | `FTR-002` Level 3 alarm cause-and-effect |
| Acceptance criterion not established | `FTST-003` detection in flats, `FTST-007` sprinklers |
| Evidence not transferable (office basis, residential use) | `FTR-001` stair capacity assessment |
| No result recorded | `FTST-008` fire service access survey |
| Clean passes | `FTR-004`, `FTR-005`, `FTR-008` |
| Applicability not established | `FREQ-008` sprinklers, `FREQ-010` higher-risk building status |
| Design inputs not recorded | building height, residential evacuation strategy, sprinkler extension |

The engine never invents an acceptance criterion: unestablished rows read
`NOT ESTABLISHED`, and a validation rule blocks any output where a criterion was synthesised.

## Run it

Quick start for the public demo, from a fresh clone:

```bash
git clone https://github.com/rahulphaltankar/engineering-knowledge-intelligence.git
cd engineering-knowledge-intelligence
python -m pip install -r requirements.txt
python -m uvicorn appliance.api.app:app --host 127.0.0.1 --port 8077
```

Open <http://127.0.0.1:8077>. The fire-engineering surface opens with `SCN-F01` as the hero
scenario. No credentials, no internet. The automotive reference demonstration is at
<http://127.0.0.1:8077/domain/automotive>.

Everything the demonstrator needs is in this repository: the synthetic fire-engineering
corpus, the fire-engineering specialist profiles, and the MIT-licensed upstream packs used by
the automotive reference demonstration (`packs/simulation`, `packs/quality-engineering`,
`packs/automotive-engineering`, each with its licence file and hashed in `packs/MANIFEST.json`).
No external files, services, credentials or model keys are required. Python 3.12 or later is
recommended.

Regenerate the synthetic corpus (deterministic):

```bash
python scripts/generate_fire_corpus.py
```

Run the tests (pytest is a development dependency):

```bash
python -m pip install pytest
python -m pytest -q
```

### Demonstration path

1. **Overview** — the KTP context, the hero change, the fire-engineering domains and knowledge
   sources (with computed coverage), capabilities and outputs. Click **Analyse this change**.
2. **Analyse Change** — the narrative: Change → Impacted fire-safety domains → Applicable
   requirements → Knowledge / relationship paths → Evidence → Transferability → Unknown /
   evidence gaps → Confidence → Human review → Verification & Evidence Plan.
3. In step 10, **Generate Verification & Evidence Plan**.
4. In step 6, open **Explain & review** on `FTR-001`. The auditable derivation shows the
   classification reason, confidence basis, evidence gate outcome, derivation, transferability
   reasoning, assumptions, supporting evidence with relationship paths and provenance.
5. In **Engineering Review**, enter a reviewer; **Reject** without a reason is refused; reject
   with a reason. The plan on screen regenerates immediately: the `FTR-001` rows are *Held*
   with the reason, and the finding is withheld from finding lists.
6. **Requirements**, **Evidence**, **Reasoning**, **Verification Plan** and **Review** give the
   detailed views; **Review** holds the session audit trail.

### API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/analyse/{scenario_id}` | Run a scenario; findings, unknowns, gate, trace |
| `GET` | `/api/explain/{finding_id}` | Auditable derivation for one finding |
| `POST` | `/api/review/{finding_id}` | `{"decision": "accept"\|"reject", "reviewer": "...", "note": "..."}` |
| `GET` | `/api/reviews` | Current decisions and the session audit log |
| `GET` | `/api/output/verification-evidence-plan` | Verification & Evidence Plan as JSON (automotive: `/api/output/dvpr`) |
| `POST` | `/review/{finding_id}` | HTMX form endpoint used by the UI |
| `GET` | `/domain/{domain}` | Switch this browser's product surface (`fire-engineering`, `automotive`) |
| `POST` | `/run/{scenario_id}` | Analyse a scenario and continue to the page named in `next` |

Sessions are per browser (an opaque cookie); two people using the demonstrator do not see
each other's analysis or reviews.

## Deploy to Google Cloud Run

The `Dockerfile` runs the same application (`appliance.api.app:app`) with uvicorn on
`0.0.0.0:$PORT`, falling back to `8080` when `PORT` is not set, as a non-root user. The image
contains only the application code, `config/` and `packs/`; no credentials are needed.

```bash
docker build -t engineering-knowledge-intelligence .
docker run --rm -p 8080:8080 engineering-knowledge-intelligence
```

```bash
gcloud run deploy engineering-knowledge-intelligence --source . --region europe-west2 --max-instances 1 --session-affinity
```

Analysis sessions and engineering review decisions are held in process memory (see
[docs/LIMITATIONS.md](docs/LIMITATIONS.md)). The container therefore runs one uvicorn worker;
deploy with `--max-instances 1` (and session affinity) so a browser keeps reaching the instance
that holds its session. State is lost when Cloud Run restarts or scales the instance to zero.
Choose the service's access setting (authenticated or public) deliberately: the demonstrator
has no authentication of its own.

## Model behaviour

The appliance runs **deterministically** by default: findings are computed from the
engineering graph and classified DERIVED or UNKNOWN. When a model provider is configured
(bring your own key; see `config/appliance.yaml`), specialists add model interpretation that
is: given the domain pack's instructions as system context; given the engineering context as
explicitly **untrusted** data; required to cite exact entity IDs; told to say UNKNOWN rather
than estimate and never to state numeric criteria not in the context; bounded to six lines;
classified INFERRED (lower trust than deterministic findings); and removed by the
**EvidenceGate** if its citations cannot be verified.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the domain pack plugs into the unchanged core
- [docs/PROVENANCE.md](docs/PROVENANCE.md) — classification, confidence, provenance, the gate and review
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md) — what this demonstrator is not
- [docs/SOURCE-REGISTER.csv](docs/SOURCE-REGISTER.csv) — public sources and redistribution status
- [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md) — third-party components and content
