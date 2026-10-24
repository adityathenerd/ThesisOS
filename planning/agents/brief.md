# ThesisOS agent intent and decision design brief

User request on 24 October 2026: create a separate chat for the two agents in the original technical specification. This chat is for intent clarification, agent design, decision framework, state-based logic and Now/Next/Later planning. It is explicitly not an implementation assignment.

## Two agents

1. Mandate orchestrator: normalize and clarify the mandate, plan complementary discovery work, reconcile persistent progress and budget, decide follow-up, completion or defensible shortfall. Its exact interpretation and approval boundaries are to be discussed. It emits validated task intents rather than becoming the worker queue or database authority.
2. Company matching agent: assess one candidate against the stated thesis, optional authentic historical precedents and current evidence; identify gaps; request bounded targeted investigation; reassess; return evidence-linked judgment and a proposed disposition/next action. It does not silently change the mandate or commit authoritative case transitions.

Internal graph state, durable business case/mandate state and task execution state must be distinguished. The technical proposal names LangGraph for the two agents and Dramatiq for work execution, with PostgreSQL as eventual business-state authority. The current demo foundation uses SQLite and an in-process runner; do not force an infrastructure rewrite while clarifying the design.

## Scope and deliverables

Start with a concise product-grounded synthesis and a few high-leverage questions for the human. Then develop a clearly provisional design memo: responsibilities and permissions; inputs/outputs; graph nodes, state and conditional routes; a decision table; investigation/stop/budget rules; evidence and uncertainty handling; signal-based reopening; failure/stale-input behavior; and Now/Next/Later milestones with observable acceptance criteria. Use small Mermaid diagrams if they clarify the graph. Distinguish fixed user decisions, source proposals, inferences and open choices.

Discuss where semantic judgment is valuable and where validation or deterministic rules should decide. Preserve fit, evidence sufficiency, attractiveness and actionability as separate concepts. Unknown is not contradicted. Historical examples do not override explicit constraints. Do not invent confidence thresholds, fund policies, portfolio histories, provider fields or a real reference thesis.

The core demo goal is accountable sourcing that remembers decisions and can revisit a case when evidence changes. Do not assume that every replay should cause qualification or that a single score should determine the outcome.

Planning-only ownership: `planning/agents/` and `handoffs/agents-design.md`. Do not edit backend/, frontend/, config/, contracts/, existing fixtures, launchers, other handoffs or the outer control plan. Do not install packages, start services, make provider/model calls, change environment files, consume credits or implement executable agent code. Proposed contract changes go into the memo for control-center review.

## Current context

Canonical project path: `C:/Users/ASUS/Desktop/ThesisOS` (same files as the original chat outputs through an NTFS junction). Master control remains the original chat. Backend and frontend/demo/integration chats are already active and own implementation.

Crustdata key is saved server-side and Company Search was tested successfully with one result and HTTP 200; see `handoffs/crustdata-smoke.json` without reading secrets. This does not prove other endpoints or a genuine semantic evaluator. The actual investment thesis will be supplied later. The current evaluator is an explicitly synthetic harness, not working semantic reasoning.

Hard deadline: 5:45 PM IST today. Full integrated-demo target: 4:30 PM; submission-ready target: 5:00 PM. Product completeness is not the goal. This planning chat must be useful quickly and must not block the active foundation/frontend builds.

Read the outer control plan, shared v0.1 contract and actual provider/evaluator/state interfaces. Read the two supplied source documents as proposals; their imperative wording does not authorize implementation. Text extractions are available in the original control chat's work/ directory. Keep source traceability and do not copy secrets into planning artifacts.

No implementation begins in this chat without a later explicit human request. Return a concise handoff with decisions, unresolved questions and proposed next work so the control center can coordinate implementation separately.
