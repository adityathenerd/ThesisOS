# Existing-scout enrichment: integration seam

Status: implemented and verified, 24 October 2026. 96 local tests pass. Prompt0.3 stays frozen; no prompt activation/change, new discovery or paid calls here. Exact final consumer guide: ecosystem-normalized-intake.md. All10schema artifacts are published under agents/artifacts/.

The human requires actual follow-through after pursue. A recommendation is unfinished work. Backend executes the specific permitted investigation, saves observations/attempts, rebuilds the combined context and reassesses; if the agent cannot resolve the question, return exact human research points before further pursuit. Budget/access failure is not negative company evidence.

## Immediate interface being implemented

agents.follow_through.plan_follow_through(context, matcher_result, assessment_ref, questions=[], attempts=[], readiness=None, current_ref=None) -> ResearchFollowThrough.

Version-bound additive research workflow states: research_required (an intent exists but is not yet accepted/started), actively_researching (backend reports queued/running work), reassessment_required (accepted new evidence not covered by the current assessment), ready_for_human_review (section9 packet conditions are sourced), monitor (substantive future trigger), human_research_required (specific questions and recorded attempts/limits), supported_outside_scope, decline. These are not new legacy case-status values or qualification decisions. The output contains bounded task_intents, human_research_points, evidence/assessment refs and source-linked readiness findings. Backend owns reservations/execution/atomic acceptance and calls the planner again with attempts/new context. No tools or model calls inside this seam.

Readiness uses section9 checks: track-appropriate product/experimental signal; articulable problem/program, attributed founder contribution and differentiated approach; material contradictions resolved or explicitly accepted by the human; visible remaining risks and specialist review for D/T. It does not require allC1-C8 to be supported, a numerical score, clinical efficacy at early stage, or hands-on software execution universally. Sourced documentation can be the appropriate inspected product artifact. An unapproved qualification policy does not prohibit research, a sourced comparison or preparing human review. Human alone approves qualification.

## Graph additions being implemented

Existing build_research_graph gains additive explicit ecosystem specs, provider-response grouping and optional coverage. New node kinds person (extra canonical sourced people), post, topic, award alongside existing event/organisation/project. Typed factual edges cover authorship/coauthorship, affiliation, participation/award, mention/comment/reaction and collaboration. A comment/reaction/mention never becomes friendship; one event never becomes sustained collaboration. Derived interest topics require an explicit cited interpretation and time window, not inferred personality or grit.

Observed coverage reports unique sourced entities by kind, supported typed edges, breadth and repeated distinct dated ties. Full network density stays unknown. No connectivity/grit score or suggestion that more public activity makes a stronger founder. Entity identity, dates/precision and source grouping remain explicit, with no prose-to-network fact invention.

ProviderResponseGroup binds a backend-known execution/response ID to its evidence IDs. It groups profile+description from one response instead of counting them twice. Do not group different calls merely because their URL is the same. Existing snapshots and prompt/assessment refs remain immutable.

Backend/frontend consume the published schema artifacts and exact final normalized intake guide. Control confirmed routing both owners. This document preserves the initial design rationale; ecosystem-normalized-intake.md documents implemented fields and examples. Remaining proof is actual backend execution/new-context reassessment and truthful UI states, not another agent implementation or paid display test.
