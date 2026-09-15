# Live Acceptance Test — Public Deployment

**Result: PASS WITH FINDINGS** — 16/16 acceptance criteria passed; 4 low-severity findings,
**none blocking**.

| | |
|---|---|
| Live URL | <https://bb7-engineering-intelligence-900435835951.europe-west2.run.app/> |
| Date | 15 September 2026 (review actions recorded at 00:17–00:18 UTC) |
| Test type | Black-box, production-style acceptance test of the deployed application |
| Method | Browser automation against the live URL in a fresh session with no Google authentication: real navigation, clicks, typed input and form submissions. Citation integrity was additionally checked through the application's own read-only explain endpoint within the same browser session. |
| Deployment changes | None. No code, configuration, Cloud Run, GCP or GitHub settings were changed during the test. |
| Evidence | Screenshots were captured at each checkpoint during the test session; they are not stored in this repository. Observed values below are transcribed from the rendered UI. |
| Scope note | The deployed build was tested as a black box; its revision was not mapped to a specific repository commit. |

This is a public demonstrator on **synthetic data**. The test verifies that an external user can
exercise the demonstrator's mechanisms; it is not a validation of fire-engineering conclusions.

---

## Acceptance results

| # | Criterion | Expected | Observed | Result |
|---|---|---|---|---|
| 1 | Public access | HTTPS, no login, application renders | HTTP 200 over HTTPS; no Google login; no Cloud Run error page; no console errors on load. Title "Fire Engineering Knowledge Intelligence", subtitle "Evidence-grounded technical decision support for fire engineering". Notice strip: "BB7 × University of Leeds KTP Demonstrator · Synthetic public demonstration data — not BB7 internal data · Independent demonstrator — not commissioned, supplied or endorsed by BB7 or the University of Leeds · Not production safety or certification software". `/health`: status ok, no errors, deterministic mode. | PASS |
| 2 | SCN-F01 execution | Scenario runs from the selector | SCN-F01 was the only scenario offered and was pre-selected on *Analyse Change*. *Assess change* produced all ten narrative steps. | PASS |
| 3 | 4 domains | 4 | 4: *Means of escape and evacuation* (Direct); *Fire detection and alarm*, *Compartmentation and structural fire protection*, *Sprinklers and fire service facilities* (via relationships). | PASS |
| 4 | 10 requirements | 10 | FREQ-001 … FREQ-010; 8 *applies*, FREQ-008 and FREQ-010 *to be confirmed*. | PASS |
| 5 | 9 evidence items | 9 | FEV-006, FTR-001 … FTR-008, each with source (e.g. `FIRE_SIMULATION / FTR-001 · test_results.json`) and "SIMULATED — PUBLIC DEMONSTRATOR DATA". | PASS |
| 6 | FTR-001 non-transferable | Distinguished from PASS | Evidence card: status **PASS**, basis *office*. Transferability card: **NOT TRANSFERABLE** — "Obtained on the 'office' basis; the change under analysis establishes the 'residential' basis, so this evidence does not transfer." Plan rows: transferable *no*, action "RE-RUN - existing pass does not cover this case". | PASS |
| 7 | 4 UNKNOWN findings | 4 | Confidence panel: 4 UNKNOWN, 22 DERIVED. The four: no acceptance criterion on 2 requirement/test pairs; applicability of FREQ-008 not established; applicability of FREQ-010 not established; FEC-001 does not record 4 design inputs. None labelled as a failure. | PASS |
| 8 | 2 NOT ESTABLISHED criteria | 2 | FTST-003 and FTST-007: "NOT ESTABLISHED - no acceptance criterion is recorded for this verification activity … none has been assumed." Output check *No invented acceptance criteria* passed. | PASS |
| 9 | 0 fabricated citations | 0 | UI: "0 fabricated citations"; "Evidence gate: 26 findings passed, 0 removed, 0 downgraded". Independent check: **100/100 citations across 26 findings resolved to displayed records with provenance** (connector, source record, source file); no finding text referenced a non-existent identifier. | PASS |
| 10 | Auditable derivation | Evidence, paths, confidence, rationale | For FTR-001 (finding TRF-0088): classification DERIVED with reason; confidence 0.76 with its basis; evidence gate outcome; derivation rationale; transferability reasoning; assumptions ("None"); 6 supporting records each with relationship path and provenance. No model reasoning transcript is exposed. | PASS |
| 11 | Human review — accept | Succeeds; state and audit shown | "ACCEPTED by Acceptance Tester (external) at 2026-09-15T00:17:22+00:00"; audit row with finding snapshot; session summary 1 accepted; plan on screen updated to 1 accepted / 25 pending. | PASS |
| 12 | Reject without note | Blocked | "Not recorded: Rejecting a finding requires a note explaining why." State remained *Pending review*; 0 rejected; plan not held. | PASS |
| 13 | Reject with note → HELD / 1 rejected | HELD and 1 rejected | "REJECTED by Acceptance Tester (external) at 2026-09-15T00:18:31+00:00" with the note retained. Plan updated in place: "1 ACCEPTED 1 REJECTED 24 PENDING"; both FTR-001 rows **HELD** ("reviewer rejected the supporting finding (TRF-0088); re-assess before acting"); "1 finding(s) withheld after reviewer rejection". | PASS |
| 14 | No DVP&R in fire output | None | Fire outputs are *Verification & Evidence Plan*, *Fire Engineering Change Impact Assessment* and *Evidence Assessment*. No DVP&R or automotive terminology in those outputs or any of the ten fire pages scanned. | PASS |
| 15 | Automotive regression | SCN-001 → DVP&R | Via the documented route `/domain/automotive`: SCN-001 produced **DVP&R** (956 records, connector SIMULATION) with all five output checks passing. | PASS |
| 16 | Session-scoped review | Immediate; not presented as sign-off | Decisions carried across pages within the session (Review page: 1 accepted, 1 rejected, 24 pending, audit trail). A separate cookie-less request saw 0 reviews. UI: "Session scoped · unauthenticated · demonstrator only … not identity, competence verification, approval or sign-off." | PASS |

**16 / 16 criteria passed.**

---

## Findings

None of these findings is blocking.

### Finding 1 — SCN-F01 wording differs slightly from the test brief

| | |
|---|---|
| Observed | The scenario reads "…from office use to six residential apartments…". |
| Expected (brief) | "…from office (B1) to six residential apartments…". |
| Likely layer | Data / test specification |
| Severity | Low |
| Recommended action | Decide which text is authoritative. If a planning use class is added to the corpus, record it as data with its source rather than in free text. |

### Finding 2 — Not-run evidence displays transferable = yes

| | |
|---|---|
| Observed | In the Verification & Evidence Plan, FTR-006 and FTR-007 (status *not run*) show Transferable *yes*. |
| Expected | *n/a* — there is no result to transfer. The row actions ("EXECUTE - no evidence exists") are correct. |
| Likely layer | UI / output rendering |
| Severity | Low (could mislead a reviewer) |
| Recommended action | Render *n/a* whenever the result status is *not run*. |

### Finding 3 — HELD row tint lost on hover

| | |
|---|---|
| Observed | A HELD plan row loses its red tint while the pointer hovers over it (hover background overrides the held style). |
| Expected | HELD rows remain visibly distinguished. The HELD label and text are always shown. |
| Likely layer | UI (CSS) |
| Severity | Cosmetic |
| Recommended action | Give the held style precedence over the hover style. |

### Finding 4 — Automotive regression reached by documented direct URL

| | |
|---|---|
| Observed | SCN-001 is not linked from the fire-engineering navigation; the regression was run via the documented route `/domain/automotive`. |
| Expected | Consistent with the intended separation (no automotive terminology in the fire surface). |
| Likely layer | UI / information architecture |
| Severity | Informational / low |
| Recommended action | None required; keep the route documented for regression testing. |

---

## Verdict

**PASS WITH FINDINGS.** The live deployment runs the intended fire-engineering demonstrator, and
its evidence-constrained reasoning, provenance, uncertainty reporting and session-scoped human
review work through the browser UI. The four findings are low severity or cosmetic and do not
block acceptance.
