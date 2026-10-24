# Research graph artifact v0.1 — exact agent export mapping

24 October 2026. Implements agent-owned portion of contracts/research-graph-v0.1.md and supports contracts/first-scout-milestone.md. No backend/frontend changes, database, model/provider calls or qualification-policy changes.

## Files and entrypoints

- agents/research_graph.py: pure typed models, validation, build_research_graph, decision_from_matcher and to_mermaid.
- agents/research_graph_example.py: captured AlloDirect projection and JSON/schema/Mermaid exporter.
- agents/artifacts/research-graph.schema.json: exact Pydantic JSON Schema.
- agents/artifacts/allodirect-research-graph.json: complete captured example JSON.
- agents/artifacts/allodirect-research-graph.mmd: portable source for an actual network sketch; interactive rendering belongs to frontend.
- agents/tests/test_research_graph.py: 17 artifact/provenance/integrity/decision tests; full local suite is 57 passing tests.

From project root:

    agents/.venv/Scripts/python.exe -m agents.research_graph_example
    agents/.venv/Scripts/python.exe -m unittest discover -s agents/tests -q

Use --output-dir PATH to export elsewhere; --without-matcher omits the optional saved historical model capture explicitly. No synthetic model fallback or network access occurs.

## Pure builder call

    from agents.research_graph import build_research_graph, decision_from_matcher

    decision = decision_from_matcher(
        matcher_result,
        assessment_ref=stored_assessment_id,
        action_timing="now",  # explicit useful next action now; "future" requires a concrete trigger
        decision_consequence="This targeted check could resolve the named evidence gap.",
    )
    artifact = build_research_graph(
        agent_case_context,
        generated_at=utc_timestamp,
        observation_metadata=source_annotations,
        entities=sourced_entity_specs,
        assertions=sourced_assertion_specs,
        questions=known_research_questions,
        matcher_result=matcher_result,
        assessment_ref=stored_assessment_id,
        decision=decision,
    )
    portable_json = artifact.model_dump(mode="json")

For an actual saved case, leave research_example_ref unset: case_id is context.ref.case_id. For a separate capture/demo, supply an explicit research_example_ref: case_id becomes null. Never relabel the captured AlloDirect example as the company from a new live search.

Caller supplies a valid agent CaseContext, including the existing canonical company/person/evidence IDs and sourced role links. Backend's own saved content/version hash remains authoritative; the agent factual-manifest hash is a separate precondition, not a replacement. The builder rejects inconsistent input hashes/versions. It reads no database and accepts no transition.

## Exact JSON envelope

Fields: schema_version="0.1", graph_id, case_id|null, research_example_ref|null, snapshot_ref (existing VersionRef), generated_at, nodes[], edges[], sources[], open_questions[], matcher_interpretations[], matcher_summary|null, research_decision|null, limitations[]. Exactly one of case_id/research_example_ref is present as nonnull. All generated_at values are timezone-aware timestamps.

graph_id is a content hash over the projection excluding graph_id/generated_at, with the prefix research-graph:. Re-exporting unchanged content at another time preserves graph_id. A changed snapshot or changed projection produces a new graph_id. Node/edge IDs remain stable for unchanged records. Persistence/history/version acceptance belong to backend, not this function.

## Node/edge/source shapes

**ResearchNode:** id, kind, label, canonical_entity_ref|null ({kind,id}), source_refs[], bounded attributes{}, temporal_scope. Initial kinds: person, organisation, product, asset, project, event, claim, source. Attributes allow only bounded primitive scalars; full raw payloads stay in stored source evidence. Company/person nodes reuse their existing IDs. Claim nodes use claim:<evidence_id> and retain canonical_entity_ref.kind=evidence. Products/assets/projects/events are explicit evidence-linked EntitySpec inputs, not inferred from model prose.

**ResearchEdge:** id, from_id, to_id, relation, label, evidence_ids[], source_refs[], assertion_kind (source_reported|observed|inferred), support_status (supported|mixed|contradicted|unknown), temporal_scope, limitation, interpretation_ref|null. IDs/endpoints/source references are validated. No actual assertion edge has empty supporting/contrary evidence. Inferred edges require a separate matcher_interpretations reference; model narrative cannot act as an evidence ID.

**ResearchSource:** id, evidence_ids[], source_url|null, source_keys[], source_type, source_quality, data_mode (live|captured|synthetic), publication_time, observation_times[], retrieval_times[], limitations[]. Source references point to these records, not directly to a URL. Every edge's evidence IDs must be included in its referenced source records. URLs are HTTP(S) without embedded credentials.

ObservationGraphMetadata attaches optional original_source_id, assertion_kind, support_status, source type/quality, precision-aware publication/observation/retrieval times and limitations to an EXISTING evidence_id. Metadata cannot create observations. Defaults are conservative source_reported/unknown/not_independently_verified. DataMode comes from the original observation, never from model wording.

Explicit original_source_id groups claims from one actual underlying source. AlloDirect's five observations map to one release S10, avoiding five supposed independent corroborations. Incompatible URL/type/quality/DataMode/publication provenance cannot be silently merged. Without explicit original-source grouping, separate evidence records remain distinct; consumers must not infer independence from record count.

## Entity/relationship mapping

| Available record | Projection | Boundary |
|---|---|---|
| Context company ID/name | organisation node with canonical company reference | Not an approval/novelty claim |
| Context person ID/name | person node with canonical person reference | No founder status inferred from name or title |
| Sourced supported/contradicted relationship | held_role_at edge with exact role and contrary/supporting source IDs | Role start/end remain unknown unless separately sourced; no founding/meeting dates invented |
| Unknown/unsourced relationship or unlinked person | open question referencing the actual person/company | No fabricated role/collaboration edge |
| No people available | explicit missing-team question | Missing evidence is not a negative founder judgment |
| Existing observation | claim:<id> node + subject→claim and source→claim edges | Prose is preserved as a source assertion; it is not mined for new historical facts |
| Explicit sourced product/asset/project/event mapping | EntitySpec node plus AssertionSpec edges | Each needs existing evidence; retrieval is not event time |
| Model criterion finding | separate MatcherInterpretationRef | No new source/evidence record; chronology or collaboration is not invented |
| Specific missing fact | ResearchQuestion | Target nodes/edges and approved criterion IDs validate |

For market/precedent observations whose subject is not the current company/person/relationship, supply the actual attributable entity mapping rather than aliasing it to the case company; the builder reports an unresolved subject instead of inventing identity. Explicit EntitySpec kinds currently support organisation/product/asset/project/event. Do not create a fake organisation merely to suppress an adapter error; extend the mapping deliberately if a different entity kind is needed.

## Temporal precision

TemporalScope fields: precision (unknown|year|month|day|datetime|interval), value|null, start|null, end|null, basis (unknown|publication|observation|retrieval|event|reported_as_of), limitation|null.

- Year/month/day values keep their original precision. Datetimes require a timezone.
- Intervals retain known bounds and allow an unknown end/start; reversed or invalid calendar values are rejected.
- Unknown has no invented point/bounds.
- Source publication/observation/retrieval clocks are separate. Generic role edges have unknown tenure unless a sourced explicit assertion supplies it.
- AlloDirect has a 25 September 2026 announcement-day event and 24 October access-date precision. It has no fabricated midnight event, founding date, cofounder meeting or employment-start date.

## Interpretation and pursue/monitor semantics

MatcherInterpretationRef fields: id, assessment_ref, input_ref, prompt_version, driver_kind, criterion_id, target_node_ids[], evidence_ids[], counterevidence_ids[], source_refs[], comparison_state, interpretation, authority="model_interpretation_not_new_evidence". It requires an actual MatcherResult and exact matching snapshot. References preserve mixed/not-applicable state and counterevidence. The original sources remain the only evidence records.

Optional matcher_summary makes the portable artifact self-contained for why_this, why_them, why_now and team_problem_fit. Each answer retains summary, evidence_ids, source_refs, objections and unknowns; the envelope retains assessment_ref/input_ref, prompt_version/driver_kind and authority=model_interpretation_not_new_evidence. This is a separate interpretive layer, not a new source or factual edge. All cited evidence/source/snapshot references validate.

Optional ResearchDecision fields: assessment_ref, input_ref, decision (pursue|monitor), next_action, decision_consequence, future_trigger|null, evidence_ids[], source_refs[], assertion_kind="inferred", qualification_note. This is a research-next-action projection, NOT a new public case status or accepted qualification.

decision_from_matcher accepts an existing rich assessment or reference comparison, including needs_approval + assessment; it does not require broad mandate reapproval just to present research. Caller explicitly chooses action_timing from the useful action now versus a future condition, not a numeric score or text heuristic. Monitor requires a concrete future_trigger. Backend owns whether an action is currently permitted/executable; the projection neither schedules it nor claims completion. Failed/no-assessment output cannot be labeled a valid research decision.

The captured example says monitor for authorized access to a working workflow/deployment record, reflecting the preserved zero-call/inaccessible-artifact research context. It is not a claim that a new actual scout was run or that its current next action must also be monitor. The actual saved scout can say pursue for a useful targeted check/human review while still retaining monitor/needs_evidence as its underlying case state.

## Current example and limits

Current export: graph_id research-graph:f1faac7becb02aeed6744e3b; 11 nodes, 14 labeled edges, one underlying source, five explicit questions, eight separate historical model criterion interpretations and the source-linked three-why/team-fit summary. It includes two company-attributed operator roles, reported tissue-ordering product and a dated financing announcement. Unknown founder contribution, collaboration/setback history, tenure, product inspection and YC novelty remain visible questions. No grit/pedigree score, human approval or clinical efficacy is inferred.

Historical matcher reference is agents/work/live-smoke.json#/matcher/result, prompt0.1, against exactly the same captured factual manifest. These annotations do not imply current policy approval; prompt0.2 human qualification semantics remain unchanged. If that saved capture is absent, interpretations/decision are absent with an explicit limitation, not synthesized.

17 new tests cover source/evidence/entity integrity, date precision, report-versus-observation, contradictory roles, stable IDs and changed snapshots, missing people/roles, lack of inferred collaboration from raw narrative, model-reference separation, safe URLs/labels and research-next-action semantics. Full suite: 57 pass. No paid calls for graph export.

## Owner integration and immediate milestone

Backend: project the actual saved search case into CaseContext; supply accepted source/role/event mappings and actual stored matcher reference; call this builder or use the exact typed JSON projection; persist/serve it with backend version authority. Publish actual case/read path. No new graph database is required.

Frontend: consume the exact JSON, render nodes/edges with source/date/uncertainty drill-down, bounded neighborhood and useful empty state. Interpretations and next-action decision are separate panels/layers; timeline filter uses temporal_scope precision. JSON/schema/Mermaid files unblock rendering before actual-case execution, but the final milestone must show the actual saved scout case after reload/export.

Agent: this pure projection/schema/support is complete. Existing build_matcher, build_orchestrator, prompt0.2 and human qualification semantics are unchanged. Backend alone owns the next single provider/model scout execution, avoiding duplicate spend. The captured example is NOT proof of that integrated milestone.
