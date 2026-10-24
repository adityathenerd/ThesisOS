# Ecosystem intake and research follow-through: exact producer contract

24 October 2026. Agent code/schema ready; prompt0.3 is FROZEN. Existing nine scouts only. Backend owns provider calls, normalization, accepted evidence and worker execution; frontend owns rendering. No new model prompt or discovery is needed to use this pure projection.

## Intake order and ownership

1. Preserve the raw response/receipt FIRST, with actual request/response id, retrieval timestamp, page/cursor scope, cost/failure and source mode. No credentials/contact lists enter the graph.
2. Resolve canonical company/person/post/work/event identity. A provider mention id or name is not a resolved founder. Do not merge similarly named products or people.
3. Accept attributable observations and new entities/relationships into the selected case, increment factual version, and rebuild agents.models.CaseContext. Every entity/edge below references accepted observation IDs. Keep publication/event/retrieval times separate and at their known precision.
4. Build pure graph specs from the accepted record, call build_research_graph, persist the versioned snapshot. No extractor inside this function invents facts from prose.
5. Reassess the materially changed joint company/team/market context under frozen prompt0.3. Feed the stored result plus truthful task attempts into plan_follow_through. Execute its permitted bounded intents; save failures/no answer/new evidence; reassess after accepted delta. If the agent cannot resolve the remaining question, show human_research_points before further pursuit.

Read backend/work/enrichment-pass receipts as collection, not accepted graph facts. A successful provider request or a profile/social description alone does not complete company research or qualify it.

## Exact graph call

```python
build_research_graph(
    context,
    generated_at=aware_utc_iso,
    observation_metadata=[ObservationGraphMetadata(...)],
    entities=[EntitySpec(...)],
    assertions=[EcosystemAssertionSpec(...)],
    provider_response_groups=[ProviderResponseGroup(...)],
    topic_interests=[TopicInterestSpec(...)],
    include_ecosystem_coverage=True,
    matcher_result=current_saved_result, assessment_ref=stored_assessment_id,
    decision=current_research_decision,
)
```

Keep matcher_result/decision absent rather than attach a stale pre-delta interpretation. They must bind the graph's exact factual snapshot. Historical assessment stays available separately. Legacy graph schema_version0.1 remains; additive keys are ecosystem_interpretations[] and ecosystem_coverage|null. ResearchEdge gains event_ref|null; new node kinds are post/topic/award, plus extra sourced person nodes. Untouched legacy projection IDs remain stable when extensions are not used. Consumers should accept new kinds and show explicit fallbacks instead of discarding the graph.

Exact schemas in agents/artifacts/: research-graph, ecosystem-entity, ecosystem-assertion, topic-interest, provider-response-group, ecosystem-coverage (each .schema.json). Previous EntitySpec/AssertionSpec call sites remain valid.

## EntitySpec

Fields: id, kind, label, evidence_ids, optional canonical_entity_ref:{kind,id}, attributes:{bounded scalar values}, temporal_scope. kind is person|organisation|product|asset|project|event|post|topic|award. IDs must be canonical/reused. All extra entities need actual accepted supporting evidence IDs. Backend can use post attributes such as share_urn, public_url, author_type, content_type, without inserting raw contact or API payloads.

Company-owned posts retain organisation authorship. A post about a founder is not that founder's authored post. A third-party mention is not evidence of friendship. Extra ecosystem people do not become case founders or acquire an employment relationship automatically.

## EcosystemAssertionSpec

Exact fields: id,from_id,to_id,relation,label,evidence_ids,assertion_kind, support_status,temporal_scope,limitation,interpretation_ref|null,event_ref|null. Type defaults are source_reported/unknown; set supported only for what the cited source actually supports. Allowed relations/endpoints:

| Relation | From -> to | Evidence limit |
|---|---|---|
| authored / coauthored | person or organisation -> post/project/asset | Actual attribution; corporate authorship is not individual authorship |
| coauthored_with | person -> person; event_ref identifies joint work | Acknowledgment/co-presence is not coauthorship |
| affiliated_with | person -> organisation | Actual role and as-of/start/end precision; logo is insufficient |
| participated_in | person/organisation -> event | Label actual supported role, e.g. speaker/attendee/judge; event roster does not establish friendship |
| received_award | person/organisation -> award | Recipient, award and dated claim must be attributable |
| award_at | award -> event | Actual ceremony/selection relationship |
| posted_about | post/project -> topic | Explicit attributable topic; no person-interest inference from a mention alone |
| mentions | post -> person/organisation/product/asset/project/event/topic/award | Mention only |
| reacted_to / commented_on | person -> post | Identified actor and actual reaction/comment; aggregate counts are not named people |
| collaborated_on | person -> project/asset/event | Attributable contribution, not shared employer alone |
| collaborated_with | person -> person; event_ref identifies shared work | Explicit sourced collaboration; no friendship or compatibility inference |
| interest_in | person -> topic | Builder-generated inferred edge with explicit EcosystemInterpretation; do not supply it as a factual assertion |

event_ref, when supplied, must refer to an actual graph event/post/project/asset. It links a coauthor/collaboration claim to the joint work. Dates never become meeting, founding or tenure dates without a source.

## TopicInterestSpec and observed coverage

Fields: id,person_id,topic_id,supporting_edge_ids,evidence_ids,temporal_scope,explanation. temporal_scope must be a bounded interval with start/end and basis event|observation|reported_as_of. The exact supporting evidence IDs must match factual supported edges forming person -> authored/coauthored/commented/reacted content -> posted_about topic, with the person's act dated inside the window. Authored content may use its publication date; a reaction/comment cannot inherit the underlying post's publication date. Unknown activity dates and retrieval dates cannot establish this window. The resulting label means observed topic engagement, not stable expertise/belief/grit or personal friendship.

ecosystem_coverage computes sourced unique entities/by-kind, supported typed edges, relationship-type breadth, dated event IDs and repeated_dated_ties. Repeated coauthorship/collaboration requires distinct work/event IDs with nonoverlapping known date ranges; two notes from one event or uncertain overlapping year/month values are not repeated dated evidence. Coauthorship may be dated by joint publications; it does not establish when the people met or worked together. Reactions, follower counts and public verbosity do not become founder-quality scores. full_network_density is always null: the actual full network is unobserved. Coverage is recomputed/validated, never caller-authored counts.

## One provider response, one source

ProviderResponseGroup fields: response_ref (actual durable backend execution/response reference), evidence_ids. Example: name/domain plus indexed description from one Company Search execution belong together. The builder creates one source ID and retains all evidence IDs/source keys. It rejects unknown/multiply grouped evidence and inconsistent URL/retrieval-time/DataMode. Do not group different requests merely because their URLs match. Existing explicit original_source_id must agree; supply one consistent mapping. This is provenance grouping, not independent confirmation.

## Real collected example: careMESH post

backend/work/enrichment-pass/caremesh.com.posts.json contains a company-authored post (share urn urn:li:share:7501259084654997504) dated2026-09-04T17:20:51Z. It reports Peter Tippett attending the2026Cleveland Clinic AI Summit and discusses care-coordination follow-through. The post's actor is careMESH, not Tippett. Correct mappings after backend accepts the observation: organisation authored post; post mentions canonically resolved Tippett; Tippett participated_in summit, source_reported, event precision year2026. The September publication timestamp is NOT the summit/attendance timestamp. This does not establish friends, new cofounders, a repeated tie or a clinical outcome. Its seven total reactions and one comment do NOT identify seven people or a named commenter. No extra URL fetch or provider call is needed to read this saved record.

## Follow-through and section9

Exact schemas: research-point, research-attempt, research-follow-through, section9-readiness (agents/artifacts/*.schema.json). ResearchPoint has id,criterion_ids,question,decision_consequence,what_to_obtain,evidence_ids,investigation|null. Investigation uses the existing typed action/canonical subject/query/max_calls. It can concern any legitimate C1-C8 gap, not only hard qualification claims. Backend supplies actual permitted capabilities and net call allowance; the planner never executes or reserves tools.

ResearchAttempt has durable task_id,question_id,investigation_key|null,status,summary,accepted_evidence_ids,source_urls,attempted_at|null. Status is queued|running|succeeded|failed|inaccessible|no_answer|exhausted. Include only accepted evidence IDs present in the rebuilt context. source_urls are credential-free HTTP(S); attempted_at, when known, must be timezone-aware. Failed retrieval is a work result, not disconfirming company evidence. Same attempt/question is not automatically retried.

IMPORTANT: questions contains ONLY the remaining decisive questions from the CURRENT reassessment. Keep all completed attempts in history, but remove a succeeded, now-resolved question from this current list. A question that is still supplied after an attempt is treated as unresolved and handed to the human rather than retried unchanged. Success status alone is not resolution: an unrelated person-profile lookup cannot resolve a product or experimental question. Bind resolution to the current finding and accepted evidence. Supply only current queued/running tasks as active; historical completed records must not be mislabeled active.

ResearchFollowThrough states: research_required (unaccepted proposal), actively_researching (backend task exists), reassessment_required (new accepted facts/meaning), ready_for_human_review, monitor with concrete trigger, human_research_required with exact question/needed evidence/consequence/attempt history, supported_outside_scope, decline. Preserve legacy public case status. Human qualification remains separate. There is no completedPURSUE state.

Section9Readiness is an explicit sourced interpretation bound to current input_ref+assessment_ref, not a new score. H/R product basis inspected_documentation can include an attributable hospital deployment/workflow record with limitations; no universal hands-on or requirement for fully known current traction. D/T inspected_experiment can mean inspecting original study methods/results, not personally reproducing a wet-lab experiment. Product-page headlines alone are source_claim_only. Review still requires articulable problem/program, attributable founder contribution, differentiated approach and product/experimental gate, with risks visible. Not allC1-C8 are mandatory. Unknown rights/access are a visible risk unless the facts create a material contradiction or defeat the central case; do not add a universal rights-document gate. Unresolved material contradictions need a current durable human acceptance record, not simply a model presenting them. D/T routes to specialist_human. Nothing creates accepted qualification or sends outreach.

## Verification and continuation

96 tests pass:75baseline+11follow-through+10ecosystem, including current-question/history semantics, explicit human contradiction acceptance, nonrequired-criterion investigation, zero-budget human handoff, corporate authorship, publication/date precision, source grouping and rejected fake coverage. Prompt0.3 remains frozen. Backend/frontend consume these exact schemas; this chat can review an exact normalized sample or post-delta defect when saved. No provider/model calls or backend/frontend file edits by this chat.
