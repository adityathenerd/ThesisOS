# Visible research evidence graph

User requirement, 24 October 2026: research must produce a graph-like artifact that a person can inspect visually, connecting people, organisations, events and other entities. The preceding founder discussion supplies research questions about sustained building, responses to setbacks, collaboration and team–problem fit. These are evidence questions, not newly approved numeric personality scores or qualification restrictions.

## Product outcome

Each researched case has a portable structured graph and an interactive graph view. A reader can select a person, organisation, product/asset, project or dated event; follow a labeled relationship; and see the supporting source, temporal scope, uncertainty and relevance to the investment case. The graph is linked to the same research/assessment record, not a separately invented story.

Demo slice: one company-focused graph from available attributable research, with founders/operators, their sourced roles or work, and dated events where actually supported. Allow a timeline filter and evidence drill-down. Start with available nodes rather than fabricate cofounder histories or a dense network. A captured research example may demonstrate the artifact while runtime case integration is pending, but is labeled and kept separate from saved live cases.

## Proposed additive projection

Use existing canonical company/person/evidence identifiers when they exist. Do not require a separate graph database. Backend and graph consumers should agree this small projection without changing required v0.1 case fields:

- Graph envelope: graph_id, case_id or explicit research-example reference, snapshot/version reference, generated_at, nodes, edges, sources and open_questions.
- Node: id, kind, label, optional canonical entity reference, source_refs and bounded attributes. Kinds initially include person, organisation, product, asset, project, event, claim and source.
- Edge: id, from_id, to_id, relation, readable label, source_refs, assertion_kind, support_status, optional temporal scope and a concise limitation/rationale. No orphan endpoints or dangling source references.
- Source: id, existing evidence_id if applicable, source URL/key, publication/observation/retrieval times where known, source type/quality and data_mode. Source-reported claims are not independently observed facts merely because the source was fetched live.
- assertion_kind: source_reported, observed or inferred. support_status: supported, mixed, contradicted or unknown. Preserve contradictory observations rather than overwrite them with one confident edge.
- Temporal values retain precision: exact day, month, year, interval or unknown. Retrieval date is not an employment start date; financing announcement is not when founding began.
- Open question: target node/edge/criterion references, question and decision consequence. Missing cofounder meeting history belongs here, not as an invented relationship edge.

Typical relations include held_role_at, built/worked_on, collaborated_on, participated_in, announced, concerns, supports and contradicts. Relation identity and source attribution matter more than a large vocabulary. Shared employer, coauthorship, same surname or a matching name does not establish cofounder relationship, current employment or collaboration. Different claims about the same relationship may coexist with their dates and sources.

## Founder interpretation

Research records attributable work, milestone chronology, collaboration, setbacks and responses where sourced. Matcher may interpret their relevance to this company's problem, with objections and uncertainty. Keep that interpretation separate from factual edges. Do not create an unsupported grit/loyalty/compatibility score, equate frequent posting/commits with execution, or treat a pivot as inconsistency by default. Scientific milestones need track-appropriate evidence; software cadence is not a universal standard.

Unknown relationship history is an explicit research gap, not a founder penalty. Human qualification approval remains required and is distinct from a graph's visual richness or node count.

## Owner assignments

- Agent owner: include graph-relevant evidence and source-linked findings in the research output; propose/implement a pure graph artifact builder/export under agents/. Keep graph projection separate from semantic invention and backend authority. Extend observation/relationship handling additively within owned interfaces; publish exact schema and mapping for backend. No further paid calls are needed merely to project current sourced observations.
- Backend owner: persist/serve graph projection from accepted observations/relationships and explicit research snapshots, preserving canonical IDs, provenance and versions. Prefer an additive `GET /api/v1/cases/{id}/research-graph` read surface; publish the actual JSON shape in handoff before UI consumption. Unknown/unavailable graph data must not be replaced by synthetic success. Do not block the existing assessment/review bridge on full network data coverage.
- Frontend/demo owner: add an inspectable Graph view to the singular case and/or clearly labeled research example. Provide selectable nodes/edges with source panel, readable relationship labels, zoom/pan or a suitable fit-to-view control, and a useful empty/partial-data state. Timeline/relationship-type filters and JSON download make it a usable artifact. Use a bounded neighborhood to keep it legible; keep current dashboard/case/history flows intact.
- Control owns this shared outcome/contract direction; consumers may refine exact fields against actual code and publish the mapping. No duplicate graph/agent chat.

## Acceptance

The visible output is an actual network, not only a biography table or decorative graph image. A selected relationship opens its evidence/limits and dates; unsupported links are visibly uncertain or open questions. Node and edge IDs/source refs validate; a new accepted observation updates the versioned graph without erasing history. A reader can identify what is known about the team, why the matcher considers it relevant, and what it still needs to learn. Captured, synthetic and live records remain distinguishable. No clinical efficacy, novel sourcing, human approval or outreach result is implied by visualization alone.


## Actual producer schema now available

Agent-owned source of exact implemented shape: agents/artifacts/research-graph.schema.json, generated from agents/research_graph.py. Use this schema for consumer mapping. Actual example: agents/artifacts/allodirect-research-graph.json. Backend/frontend have been notified. Example case_id is null and research_example_ref is present; it is a captured reference, not a saved newly discovered case. The generic outcome contract above remains the product requirement; the implemented schema refines names/source grouping/temporal fields.
