# Agent foundation: implemented boundary and proposed next slice

24 October 2026. Backend-owned internal implementation notes. Authority/scope: contracts/agent-foundation-v0.1.md. Public contracts/v0.1.md remains unchanged. No executable LangGraph, prompt installation, model/provider request, thesis activation or semantic scheduling policy was introduced by this slice.

## Implemented runtime contract

The execution seam is `AssessmentCoordinator` in app/assessments.py, using `EvaluatorAdapter.evaluate(context: AssessmentContext, invocation_id: str) -> AssessmentProposal`. The coordinator explicitly runs the legacy fixture path; it is not the future orchestrator or a second agent scheduler. StateService no longer receives or invokes an evaluator.

1. `StateService.load_assessment_context(case_id)` opens one explicit short read transaction, loads the joined input and closes its connection before returning detached validated data.
2. `begin_assessment(context, replayed=False, task_id=None)` records the exact server-issued snapshot and a distinct invocation ID in a short write transaction. A supplied parent task must belong to the mandate and be running. The connection closes before invocation.
3. The coordinator invokes the adapter outside **all** database transactions. `FixtureEvaluatorAdapter` owns fixture-key translation and discards the legacy draft evaluation identity; `fixture_key` is not a required context field. An adapter exception/invalid shape becomes a safe operational failure, not rejected investment state.
4. `accept_assessment(proposal)` opens a short `BEGIN IMMEDIATE` transaction. It compares the returned references to the saved server-issued snapshot and rebuilds current references from the database. It checks case/thesis/policy/company/evidence/prior-findings versions, case ownership, enabled evaluator restrictions and all cited evidence. A parent task must still be running. It then assigns the accepted evaluation's ID/time, atomically writes the immutable evaluation, case transition, current gaps, event, invocation receipt and mandate progress.
5. Stale/invalid acceptance records its outcome in the invocation ledger and returns a typed ServiceError (`stale_version` 409, `invalid_evidence`/`invalid_proposal` 422, or `invalid_transition` 409). It never overwrites case/readiness/current gaps/progress. The coordinator adds one safe operational-failure event. Repeating the identical already-accepted proposal returns its original evaluation without another transition/event; a different result cannot reuse that invocation.

### Actual internal models (app/assessments.py)

| Model | Current fields/meaning |
|---|---|
| `PolicyReference` | reference nullable, version, status unavailable/draft/approved. Stored reference slot only; no policy activation API or semantic adapter is enabled. Absent row yields unavailable/version 0. Draft/user-supplied text is never implicitly approval. |
| `EvidenceManifestEntry` | evidence_id, company_id, content_version (SHA-256 of the complete normalized evidence record). Evidence content hashes are the version mechanism for the currently immutable observations. |
| `InputVersions` | mandate/case/company IDs, case integer version and full case digest, thesis integer version and input digest, policy reference/digest, company row digest, evidence manifest, prior accepted evaluation ID and prior-findings/current-gaps digest. A content change without an integer version bump is still stale. |
| `CompanyContext` | ID, provider source key, company name, canonical domain, data mode. |
| `UnavailableContext` | explicit unavailable status and reason. People, role-tenure relationships and separate market context are currently unavailable. A fixture outreach contact is not a sourced founding team. |
| `AssessmentContext` | snapshot ID/time, versions, mandate, case, company, detached observations, prior accepted evaluation/findings, current gaps and the three unavailable context sections. No live DB object or lazy query escapes. |
| `ReferenceMaterial` | exact source path/version, full source and outline text, SHA-256 hashes, human_reviewed_direction_only status and policy_active=false. Loaded/pinned before any DB context, independently of mandate text and active policy. |
| `AssessmentDraft` | evidence-linked dimensions/findings; proposed public status; null-capable scores; missing claims; next action; reasoning; evidence IDs; evaluator/data-mode labels; optional outreach and investigation suggestion. No accepted evaluation ID. |
| `InvestigationSuggestion` | one case-scoped decision question, missing claim, supplied evidence IDs, optional source description. It does not authorize or enqueue anything; resource limits/actions are not inferred from it. |
| `AssessmentProposal` | invocation ID, snapshot ID, exact input versions and draft result. |

The JSON stored in the invocation ledger is the trusted input snapshot. Models are detached/frozen at the outer internal boundary; nested public v0.1 models are copied data, not live state. Acceptance compares against the stored server snapshot, not an evaluator-mutated copy. Findings must cite only evidence in the supplied manifest, and every supplied observation must be attributed to the case company and linked to that case. Supported/contradicted findings require evidence IDs. Result-level, finding-level and investigation evidence references are all checked.

The sole enabled adapter remains explicitly fixture/development. Synthetic catalog cases retain the existing predefined route. Genuine company cases cannot receive scores, qualification/rejection or outreach from this placeholder: they remain needs_evidence/monitor with null scores. Semantic proposals are refused because the real runtime/policy is not enabled. This is a capability boundary, not an invented fit threshold. Prior evaluation/history is retained even if a new observation leaves a required claim unresolved.

### Current reference direction: v0.3, not active policy

The human-reviewed current primary reference is planning/investment-thesis/scouting-mandate.md **v0.3**, with comparison-guide.json as a review outline. v0.2 is superseded as primary. config/reference-source.json selects those source files as metadata only; the JSON comparison outline is never executed as runtime policy. App construction pins their full text/hashes into ReferenceMaterial. InputVersions.reference_content_version includes that pinned material; explicitly reloading/revising it invalidates an in-flight proposal. Source edits are picked up on explicit process restart/reload, not silently midway through an invocation. Existing mandates, history, fixture outcomes and PolicyReference unavailable/version 0 are untouched. No extra schema migration was needed for these additive internal JSON fields.

The material preserves equally core healthtech/biosciences including therapeutics, H/R/D/T tracks, C1–C8 as non-additive vocabulary, track-specific product/experimental evidence, known-YC novelty exclusion with unknown backing retained as unknown, within-track/milestone comparison and specialist D/T review. Backend does not classify companies or certify these gates from the source text. Current company-search fields do not establish product/experimental evidence, founders, YC status or novelty. Current headcount query is **not** thesis-derived; no thesis-specific query or provider coverage is claimed. Research examples are not captures or qualified prospects.

Precise pending agent-interface mapping issues: agent Policy currently requires approved/fit-rule/criterion gates while reviewed direction still has unresolved detailed normalization/counting/limits; its flat criterion/three-state Finding does not losslessly represent mixed/not-applicable C1–C8 findings, track/milestone/product-gate/novelty/reviewer metadata. Public Dimension.status also has only supported/contradicted/unknown, so preserve richer internal findings and provenance before any lossy projection. Separate **source transport mode** (live/captured/synthetic) from **claim/evidence mode** (prediction, reported experiment, inspected artifact, human study, attestation, etc.); live API data does not imply inspected experiments or clinical validity. Partner-review readiness is not automatically qualified or outreach_ready. These choices need an explicit reviewed mapping; no new rule/enum was silently invented here.

## Persistence, migration and recovery

Schema **2** adds three tables; no existing projection/table columns are removed:

- `mandate_policy_refs`: mandate ID and typed policy-reference JSON, no active policy compilation. No rows are created merely by submitting thesis text.
- `case_assessment_state`: case ID, pending flag, accepted current-gaps projection, accepted evaluation ID, last safe operational error and timestamp.
- `assessment_invocations`: distinct invocation and snapshot IDs, immutable snapshot JSON, running/accepted/stale/invalid/failed status, optional parent task, accepted evaluation ID/proposal JSON, safe failure fields, one-time failure-notification marker and timestamps.

Startup supports schemas 0/1/2 and backfills missing assessment-state rows from existing accepted evaluations. Unchanged legacy cases remain assessed; migration does not re-evaluate them or rewrite public histories. Interrupted migration backfill is safe to resume (`INSERT OR IGNORE`). Back up the SQLite database before deployment. Old source accepting only schema 1 cannot directly open schema 2; rollback requires restoring that backup with the matching old source, or a reviewed compatibility change. Do not simply decrement user_version or delete state.

**Changed transaction granularity:** candidate identity/evidence/discovery-event writes remain one atomic candidate batch. The batch is committed before invoking any evaluator. Each case assessment is accepted independently. An evaluator failure cannot roll back observed companies or other accepted assessments. Remaining cases retain a durable pending flag, failed invocations/events and failed parent task when run through the runner. Existing accepted judgments and counts remain intact; no operational failure becomes investment rejection. A mandate rerun skips unchanged accepted cases and retries pending ones. The runner reports partial persistence honestly.

Signal ingestion now commits a labeled observation/event and case-version increment before reassessment. If reassessment fails, the observation remains saved and the HTTP request returns a safe operational error; earlier accepted evaluation stays intact. Repeating an exact catalog replay adds no duplicate observation/event, but retries assessment while pending. Once accepted, the same replay remains an exact no-op. Startup marks running invocations and unfinished tasks failed; saved pending work is retryable. A crash between ingest and invocation registration still leaves the pending marker. One-process/one-worker-per-database limitation remains.

### Verification

Run from `C:/Users/ASUS/Desktop/ThesisOS`:

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
```

Boundary tests in tests/test_assessments.py prove: a blocking fake evaluator allows an independent immediate write and WAL TRUNCATE checkpoint (no retained read or write transaction); a concurrent signal makes its proposal stale; case/thesis/policy/company/evidence content or manifest revisions invalidate old proposals; cross-company and same-company-but-unlinked evidence injection is refused in findings/results/investigation; exact acceptance retries are idempotent; failure/restart retries preserve observations and accepted history without duplicate current evaluations; v1 migration is non-destructive; and a labeled test double can keep a required team claim unresolved after a new observation. None of these tests claim executed semantic reasoning.

## Proposed next foundation slice — NOT implemented

Keep SQLite/in-process execution. Evolve the existing task machinery, not a competing semantic scheduler. Agent/LangGraph planning retains ownership of meanings, prioritization and graph/prompt design; backend enforces accepted intent/version/action/resource boundaries.

| Proposed internal record | Minimal proposed fields and constraints |
|---|---|
| `SourcedPerson` | id, provider identity key, observed name/profile fields, evidence references, data mode and content version. No synthetic people filling unavailable real-team context. |
| `CompanyPersonRole` | id, company_id, person_id, role kind/title, nullable valid_from/valid_to, observation/source references, attribution status unknown/supported/contradicted, content version. An outreach contact is separate from founder/team membership; current role alone is not a historical tenure claim. |
| `CriterionFinding` / `CaseGap` | case + reviewed criterion/policy version, supported/contradicted/unknown finding, evidence IDs, rationale; stable gap identity/question, required status only from approved policy, open/resolved/superseded, version. Do not infer which claims are required. Migrate current gap strings only as unclassified legacy gaps. |
| `AssessmentIntent` | mandate/case, expected snapshot/input versions, reason/event frontier, allowed assessment capability, dedupe key and dependencies. Validated by backend before task creation. |
| `InvestigationIntent` | case/gap, one decision question, allowed provider action ID and typed arguments, expected versions, dependencies, dedupe key and explicit resource request. A matcher suggestion alone cannot schedule it. |
| `TaskIntent` / accepted task | discriminated assessment/investigation/package action, version refs, dependency IDs, idempotency key, state, accepted adapter version. Reject unknown/disabled action IDs and arbitrary generated code. Keep conceptual judgment separate from operational task status. |
| `AttemptedSource` | case/gap, adapter/query fingerprint, input versions, attempt time/result, evidence received, no-new-evidence or exhaustion reason, failure retryability. Failed and negative attempts survive passes. |
| `ResourceReservation` / `ResourceUsage` | explicit configured/human allowance reference/version, unit, reserved quantity, task/invocation, status; append-only actual use and release/reconciliation entries. Check remaining allowance, dedupe, reserve and create task atomically. Record unsuccessful and stale work too; unknown cost remains unknown, never silently zero. Numeric budgets are unresolved. |
| `MandateReconcileState` | mandate, latest event sequence/dirty generation, last fully consumed frontier, running lease/generation and input/policy version. Snapshot a fixed frontier for each short pass; advance only to that frontier after accepting/rejecting its intents. If a later event arrived, leave dirty and wake again. Never clear dirty globally after a busy pass. Persist lease expiry/restart recovery. |

Suggested sequencing: first add sourced person/role and typed criterion/gap references without changing agent policy; next add typed intent acceptance and atomic resource reservations (with explicit configured allowances); then durable attempted-source memory and reconciliation cursor/lease semantics, tested with an event arriving during a blocked pass and restart. The event dispatcher only wakes the **one** orchestrator policy. Accepted orchestrator intents schedule assessment/investigation. Do not add an independent evidence-to-evaluation scheduler. Legacy fixture auto-assessment remains isolated until an agent route is separately authorized and enabled.

Still unresolved and deliberately not decided here: exact reviewed thesis/fit rule and required claims; independent attractiveness gate; whether human readiness review gates counted progress; numeric budgets; freshness and materiality; actual people/market provider coverage. The next slice needs those explicit inputs where enforcement depends on them. No draft is activated by this document.
