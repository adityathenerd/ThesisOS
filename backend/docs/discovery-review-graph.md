# Discovery, rich agent results, human review and research graph

24 October 2026. This supplements agent-foundation.md. Schema 3 is additive over the earlier schema-2 snapshot/acceptance boundary. Existing HTTP v0.1 required fields/statuses remain intact. Default automatic evaluation remains the explicit fixture/development route; the real first-scout comparison is saved separately.

## Actual first scout — do not repeat paid calls

One genuine ranked Company Search, limit 1, returned **Nurture Bridge Marketing, LLC** (`nurturebridgemarketing.com`) in 8.376 seconds. The saved historical semantic orchestrator H-referral-workflow hypothesis preceded that search and is reused with the exact v0.3 document hash, explicitly labeled prompt0.1 historical output. The actual reviewed query was:

```json
{"search":{"query":"referral intake workflow products for referral coordinators and clinic operations managers, with a working product or attributable deployment","mode":"hybrid"},"fields":["basic_info.name","basic_info.primary_domain"],"limit":1}
```

This was a faithful small branch under the human's direct first-scout authorization. It predates control's later limit-3/name-domain-description scope record and **does not claim to be an exact execution of that later record**. No second request was made to match the later example. Neither source was qualification-policy approval. No headcount, revenue, geography, pedigree or AI exclusion was used.

Saved actual identifiers:

- Mandate: `mandate_400f07654daf4e43acc6c991ff29cc8f`.
- Case: `case_201e1de12eea4da49abc6f8de3317e5a`.
- Assessment: `assessment_960ba2c8c0c743e5aa12fc73e9d8dffd`.
- Graph: `research-graph:a65194cdf52b63cb2a224e35`, case version 2.

Ten public-source observations, explicit founder/CEO attribution, reported background, two named methods, prior-organisation claims and a dated publisher release were saved. Sources remain source-reported, with separate live retrieval dates and unknown tenure. Six public URL fetches included four successes, a 404 case-studies page and a 403 profile page; the inaccessible profile text was not imported as a live source. Current direct service-page text says consulting/advisory and no proprietary software platform. This is an important result, not a failed demo to hide: product evidence and a reusable differentiated core are unestablished.

One genuine compiled matcher call used `gpt-6.1-sol`, low reasoning, prompt0.2: 44.951 seconds, 9,577 input / 2,461 output tokens. Full `needs_approval` comparison and proposed monitor disposition are immutable. No accepted Evaluation/qualification was forged. The research recommendation is **monitor** until an accessible worked workflow or attributable deployment identifies the reusable component, intended user, baseline and founder contribution. YC backing/novelty stay unknown. This is not a novel-YC count, human-approved qualification or outreach package.

Graph: 24 nodes, 28 edges, 6 source groups, 4 open questions, 8 separate matcher interpretation references. It is a runtime saved case, not the AlloDirect captured example. Proof/portable artifacts live under backend/work/first-scout/: search.json, sources/receipts.json, research.json, matcher.json, milestone.json, research-graph.json/.mmd, scout-result.json. Search/matcher CLI receipt guards prevent duplicate spend. Do not run independent smoke calls merely to inspect the result.

## Verified catalog and discovery-only approval

Official sources:

- [Company Search reference](https://docs.crustdata.com/company-docs/search/reference): ranked modes, optional structured filters, operators, value types and restrictions.
- [Company Search guide](https://docs.crustdata.com/company-docs/search/introduction): name/domain/description projections and ranked body.
- [Value lists](https://docs.crustdata.com/company-docs/filter-values): published industry/category snapshots, with current autocomplete recommended for extensions.
- [Account permissions](https://docs.crustdata.com/general/permissions): free `GET /account/endpoints` read. One authenticated free check scoped to Company Search succeeded; no people/enrichment call was made.

config/provider-catalog/company-search.json is the narrow verified catalog (.2); .1 is archived for the actual first-scout request. API version 2025-11-01. Allowed filters: exact company name/domain, plus industry/category `=` or `in` against 433/801 published values. Taxonomy is a semantic proxy, not proof of fit, and requires explicit lossy-meaning review. Description is allowed as a **projection**, not an undocumented description filter. Ranked hybrid/lexical/semantic modes are documented; the actual H request proved hybrid account execution. Optional description/headcount and null total_count are handled without invented zero values. Identity, provider ID and optional description are retained; missing optional values remain null.

No marketing-page extrapolation to fake filter fields is used. The OpenAPI YAML URL redirected to HTML sign-in and was not treated as schema evidence. Official narrative reference plus published value snapshots and account permission metadata supply the enabled catalog. Source URLs/hashes and as-of quote are retained. Public source/body snapshots are ignored intermediates, not credentials.

`DiscoveryHypothesisInput` mirrors the agent's hypothesis JSON. `DiscoveryBranchInput` binds actual mandate, source path/version/hash, criterion vocabulary, problem/user terms, ranked mapping and optional predicates. `compile_discovery` validates a bounded exact body and records catalog/request hashes; it never approves operational qualification policy. C1–C8 linkage here is comparison vocabulary, not a list of newly required hard constraints. Four H/R/D/T proposed ranked branches in config/discovery-branches.proposed.json remain unapproved/nonexecutable. Unfilterable product/team/YC/scientific claims stay semantic checks.

`DiscoveryApproval` is **discovery_only**, bound to exact branch/request/catalog hashes, explicit reviewer authority and explicit call/result/quoted-credit allowance. There are no implicit numeric fund budgets. `DiscoveryStore.register(compiled,approval,catalog)` validates and stores an immutable receipt. Qualification PolicyReference may remain unavailable; policy.approved=True is not used to unlock discovery. A policy-reference change invalidates prior acceptance rather than silently changing search meaning.

Production live `ApprovedCompanySearchProvider` accepts only a selector JSON `{approval_id,attempt_key}` into backend-registered state. CRUSTDATA_SEARCH_CONFIG points to that selector. Raw request JSON and config/crustdata-search.example.json are access-test transport artifacts and are refused as mandate sourcing. Before any network call the backend atomically deduplicates the intent and reserves one call, result slots and conservative as-of quoted microcredits. Failed/interrupted uncertain work retains its reservation and unknown actual billed usage. No retries/pagination/enrichment. Successful repeated intent reuses saved observations with original retrieval time; it is not a hidden fallback or a fresh call. New deliberate attempts require a distinct key and remaining explicit allowance. No second scheduler is introduced.

Normalized observations retain execution/approval/branch/hypothesis/reference/catalog/policy lineage in evidence_discovery_refs and discovery_encounters; source keys include the execution. Existing genuine cases can gain new observations without duplicate case identity. Unchanged cached repeats do not create evaluations. Per-track coverage reports searched/not-executed/failure, known returned counts or unknown after failure, encounters and unique company records. Track is the branch hypothesis, not a verified company classification; complete H/R/D/T coverage/novelty is never inferred from one H hit.

The agent owner now separately supplies compile_ranked_company_search and scoped approval types. Backend's narrow validator/reservation boundary is a transport/authority guard, not another semantic planner. An adapter can use `.provider_body()` after verifying exact same hashes/approval scope. No agents/ code was edited by backend. The later control scope must not be relabeled onto an earlier different request.

## Dependency and rich-result bridge

Pure `agents.models` / `agents.research_graph` DTOs run under backend Pydantic. Actual compiled graphs execute through bounded JSON subprocess in **agents/.venv**, avoiding a LangGraph installation into backend or managed runtime. Worker: backend.app.agent_bridge_worker. Scripted transport never loads credentials or instantiates a network client. Live mode is explicit CLI opt-in under the human's authorization; the agent-owned `OpenAIResponsesDriver.from_project` loads agents/.env, timeout90, zero retries. No key is copied into arguments/results/handoffs.

`comparison_packet(AssessmentContext)` maps exact persisted company/person/role observations to a sealed agent CaseContext. Separate agent evidence hash does not replace backend references. People/relationship IDs and subjects must exactly match the accepted saved research packet; no outreach person, shared employer, name or coauthor is synthesized as a founder. Reference path/version/hash and case/mandate versions are bound; approved=False remains false for v0.3 direction. The original mandate text/version is retained separately from full pinned reference v0.3.

AgentAssessmentStore validates the rich result against its stored server snapshot and current InputVersions after inference, including research-packet hash. It retains full findings, mixed/not-applicable state, counterevidence, source modes, prompt version and token usage in semantic_assessments. This table name does not imply automatic semantic-state acceptance. needs_approval/comparison/failed results remain noncurrent diagnostics. A useful pursue/monitor research-next-action presentation may be saved without pretending normalization/qualification is approved. No comparison is converted to an accepted Evaluation. Default fixture evaluator remains isolated.

## Human qualification API

`POST /api/v1/cases/{case_id}/qualification-review`

```json
{"assessment_id":"stored assessment ID","expected_case_version":2,"decision":"approve","note":null}
```

Decision is `approve` or `request_evidence`; note optional/nullable. assessment_id is the actual immutable rich semantic_assessments record ID, **not** a v0.1 evaluation ID, invocation ID or graph ID. Returns CaseDetail. Exact repeats are idempotent only while their bound post-review versions remain current; stale inputs return409. Comparison-only/unknown required gate approval returns409 ineligible_qualification. A human cannot override missing required proof just by clicking approve. Request-evidence records the explicit action and preserves unknowns, without inventing criterion gates or executing investigation.

CaseDetail additively includes:

- `agent_assessments`: id, outcome, proposed_disposition, driver_kind, prompt_version, comparison_only, eligible_for_human_review, input_current, expected_case_version, created_at, **structured_result**, optional review_eligibility.
- `qualification_reviews`: id, assessment_id, decision, note, reviewer_identity (null rather than fabricated), source explicit_local_application_action, synthetic_test, created_at, current (backend-computed after current-input comparison).

Use BOTH eligible_for_human_review and input_current for an approval affordance; backend is authoritative. The actual first-scout needs_approval record is ineligible. Current real-policy normalization and full reviewed gate/people coverage are not established by the comparison. Scope-qualified eligibility needs exact reviewed policy definition plus track-appropriate product/program/team/mechanism/contradiction evidence, unresolved-required-claim checks and specialist D/T review where applicable; no numeric score or blanket new C1–C8 required list is invented. Real eligibility is conservatively unavailable until those bindings exist. Isolated scripted review tests are explicitly synthetic software-test records, never human-approved real sourcing claims.

An accepted human action can produce qualified, **not outreach_ready**. Current complete sourced package acceptance is still a separate future boundary; there is no sending. New evidence invalidates prior review and removes semantic-route readiness while keeping its historical record. Legacy synthetic fixture scenarios retain their explicit development route. A fixture mandate run cannot be used to rerun/pollute a genuine-research mandate.

## Read seams for frontend/control

- `GET /api/v1/mandates/{id}/discovery`: track coverage and novelty limits; no provider call.
- `GET /api/v1/cases/{id}`: existing detail plus rich-assessment/review metadata.
- `GET /api/v1/cases/{id}/scout-result`: case/version, assessment_id, current research_decision, decision_current, rich agent_assessments, qualification_accepted, novelty_status and graph_route.
- `GET /api/v1/cases/{id}/research-graph`: **exact agent-owned ResearchGraph schema_version 0.1**, grouped sources, typed canonical refs, TemporalScope, matcher_summary, matcher_interpretations, research_decision and open questions. Former prototype schema research-graph-v0.1 was removed. This route was exercised over actual HTTP with the real case, not just OpenAPI.

Graph projection calls the agent-owned pure builder. No graph DB/service/model call. Entity/event specs require attributable source mappings. Original source grouping prevents five observations from one URL becoming five independent corroborations; same-owner/promotional limitations remain visible. Source-reported edges do not become independently observed because transport is live; retrieval/publication are not employment-start dates. Graph export snapshots are durable and content-addressed; current backend versions are rechecked before cache acceptance. Old graphs and research packets remain stored when observations change.

## Verification and limits

Run `backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -q` from Desktop app root: **32 tests pass**. These include prior snapshot/write-lock/stale/evidence invariants, scoped compile/approval/reservation concurrency and interrupted usage, real compiled ScriptedDriver subprocess with concurrent writer, rich-result/reference rejection, comparison-only no qualification, explicit/idempotent/stale/unknown-gate review, persisted graph schema/cache/history, optional ranked fields and null counts. Scripted/mocked checks make no paid calls. A TestClient HTTPX deprecation warning remains nonblocking.

Actual paid milestone evidence is separate: one provider search + one genuine matcher. One free account permission request; no people/enrichment/API web calls. Public research retrieval was bounded and attributed. Original two fixture mandates/six cases were retained; one actual saved mandate/case was appended. Control independently completed actual-case browser graph/monitor/why-answer inspection, sourced-role selection, reload and matching JSON download. Its verified_complete report and screenshot are in the control outputs folder as ThesisOS_First_Scout_Verification.json and ThesisOS_First_Scout.png. This is completion of the bounded first-case milestone, not the whole autonomous product.
