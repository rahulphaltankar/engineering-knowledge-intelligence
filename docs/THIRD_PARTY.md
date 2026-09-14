# Third-party components and content

## Runtime dependencies (`requirements.txt`)

| Package | Version | Licence |
|---|---|---|
| FastAPI | 0.136.0 | MIT |
| Uvicorn | 0.44.0 | BSD-3-Clause |
| Pydantic | 2.13.1 | MIT |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| python-multipart | 0.0.26 | Apache-2.0 |

Development: pytest (MIT), httpx via Starlette's TestClient (BSD-3-Clause).

## Bundled front-end asset

| Asset | Version | Licence |
|---|---|---|
| `appliance/api/static/htmx.min.js` | htmx 1.9.12 | BSD-2-Clause |

Served locally; the UI makes no external requests.

## Vendored upstream content (included, MIT)

`packs/simulation`, `packs/quality-engineering` and `packs/automotive-engineering` are copied
verbatim from public repositories at pinned commits, hashed into `packs/MANIFEST.json`, and
redistributed here under their MIT licences so that a fresh clone is self-contained. Each pack
carries its upstream licence file. They back the automotive reference demonstration only; the
fire-engineering demonstrator does not depend on them. `scripts/vendor_packs.py` refreshes them
from upstream.

| Pack | Source (pinned commit in each `pack.yaml`) | Licence file |
|---|---|---|
| simulation | github.com/rahulphaltankar/engineering-intelligence-simulation | `packs/simulation/LICENSE` (MIT) |
| quality-engineering | github.com/RBraga01/Quality-Engineering-Skills | `packs/quality-engineering/LICENSE` (MIT; per-skill declarations; see its `THIRD_PARTY_CONTENT.md`) |
| automotive-engineering | github.com/K-Dense-AI/scientific-agents (automotive-engineer) | `packs/automotive-engineering/LICENSE.md` (MIT) |

The upstream quality-engineering skills describe publicly documented automotive quality
methods and name vehicle manufacturers when describing their published customer-specific
requirements. Those are upstream, public, third-party references; they are not clients of, or
data from, this project.

## Fire-engineering pack (committed)

`packs/fire-engineering` — specialist profiles, synthetic corpus, scenario and generator
(`scripts/generate_fire_corpus.py`) — is **original demonstrator content** written for this
repository. It reproduces no third-party text. Its frontmatter records
`license: original-demonstrator-content` and its datasets record
`Synthetic demonstrator data`; **the repository owner should set an explicit licence before
public redistribution.**

## Standards and legislation

Referenced by public identifier and title only; see `docs/SOURCE-REGISTER.csv`.

- British Standards (BS 9991, BS 5839-1, BS 5839-6, BS 9251) are copyright BSI and are not
  reproduced, summarised clause by clause, or redistributed.
- Approved Document B, the Building Regulations 2010 and the Building Safety Act 2022 are
  Crown copyright (Open Government Licence v3.0); the demonstrator nevertheless uses only
  identifiers, titles and requirement letters.

## Names

"BB7" and the University of Leeds are named only to identify the publicly announced
Knowledge Transfer Partnership that provides the demonstrator's context. No endorsement,
commission or affiliation is claimed or implied.
