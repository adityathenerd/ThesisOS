# Internal agent foundation boundary version 0.1

Control-center integration brief, 24 October 2026. This document scopes backend foundation continuation; detailed Python models and schema migrations are for the existing backend owner to propose/refine against current code. It does not change the public HTTP v0.1 contract, approve an investment thesis, install prompts, or authorize executable LangGraph work in the planning chat.

## Authority and evidence

The human in the agent-design chat endorsed the combined-context loop and requested that control coordinate backend foundations with the existing backend owner while agent/LangGraph design remains in that chat. Verified human request: latest discussion in thread `01a16c65-cf68-78f0-becc-95dafb861edc`. Design sources: `handoffs/agents-design.md`, `planning/agents/loop-operating-spec.md`, `planning/agents/constitution-and-policy-draft.md`, and `planning/agents/system-prompts-draft.md`.

Read-only control inspection confirms `StateService._evaluate` calls `evaluator.evaluate` in the write path and directly applies the recommendation; both discovery completion and signal replay use it. The runner currently has a combined discover-and-evaluate task. These are adequate for fast labeled fixtures but are not an appropriate model-call boundary.

## Ownership

- Existing backend chat owns context assembly, typed interfaces, transaction/version/evidence validation, accepted transitions, task execution infrastructure, persistent history and resource enforcement.
- Existing agent-design chat owns the constitution, semantic decision framework, graph nodes/routes, prompt drafts and state-conditioned agent tasks. It remains planning only until the human requests executable agent work there.
- Orchestrator proposes which bounded work to prioritize; matcher proposes what the joint evidence means and what specific fact could change the assessment.
- Backend is the only authority for accepted state and work. Graph output alone is not a committed decision, executed task or reached target.
- Frontend/demo integration keeps its existing ownership and public projections. No new agent chat, second semantic scheduler, or required infrastructure migration.

## Implement now as the smallest backend slice

1. Load a consistent, detached context snapshot in a short read transaction; close it before evaluator invocation. Capture mandate/case/company identity; expected case and thesis versions; approved-policy reference/status if present; evidence IDs and content/version manifest; previous accepted findings/evaluation; and explicit unavailable team/relationship/market context. Exact model names may differ.
2. Invoke the current evaluator through a typed adapter outside all database transactions. Keep current fixture behavior explicitly labeled; do not install LangGraph, request models, or turn draft prompts into active policy. `fixture_key` may remain inside the fixture adapter for compatibility, not become a required semantic-agent input.
3. Return a detached assessment proposal containing input-version/snapshot references, evidence-linked findings, proposed outcome, missing claims and optional bounded investigation suggestion. Separate invocation identity from the ID assigned to an accepted immutable evaluation.
4. Accept in a short conditional write transaction: revalidate current case/thesis/policy/evidence references, allowed evidence ownership and result shape. Refuse stale/invalid acceptance without changing current case, readiness, gaps or progress. Atomically persist the accepted immutable evaluation, accepted transition, current gaps and event. A provider/model exception is an operational failure, not investment rejection.
5. Route both initial discovery assessment and signal reassessment through this boundary. Preserve discovery identity, catalog replay idempotency and the v0.1 HTTP shapes. Document any shift in transaction granularity; a failure after candidate persistence must leave an observable recoverable state, not falsely promise all-or-nothing discovery.

No numeric qualification cutoffs or inferred fund criteria. Draft/user-supplied text alone does not establish approved semantic policy. Preserve the existing explicitly synthetic demo route, while genuine semantic qualification remains unavailable without approved policy and an actual evaluator.

## First acceptance evidence

- A blocking fake evaluator can run while another connection writes to the database, proving the model boundary does not retain the write transaction or locks from a read transaction.
- A case, policy, thesis or evidence revision between snapshot and acceptance rejects the old proposal; current accepted judgment/history stays correct.
- Evidence outside the supplied manifest or linked case cannot support an accepted evaluation.
- Existing fixture discovery, repeat run, exact replay, reopen/history and safe error checks still pass; no public status renaming or hidden data-mode changes.
- One missing required claim can remain unresolved after a new observation; the harness must not force qualification. For now demonstrate through a labeled test double, not a claim of executed semantic reasoning.
- Evaluator failure and interrupted work remain visible and safely retryable without duplicate current evaluations or inconsistent target counts.

## Next backend foundation slice to propose

After the first boundary is verified, propose a minimal internal schema for sourced people/role-tenure relationships, criterion findings/gaps, typed assessment/investigation/task intents, attempted-source memory and resource reservations/usage. Missing people access stays unavailable, not synthetic team evidence. One outreach contact does not represent the founding team.

Task acceptance must validate allowed adapter action, dependencies and input versions; deduplicate; and reserve resources atomically. Usage must include unsuccessful and stale work. Numeric allowances are explicit configuration or human choices, not policy invented by the model.

Persist a mandate reconciliation cursor or equivalent dirty/version marker so an event arriving during a busy pass cannot be lost. Event dispatch wakes a short orchestrator invocation; accepted orchestrator intents schedule assessment or investigation. Do not add a competing independent evidence-to-evaluation policy scheduler. Legacy fixture auto-evaluation may remain explicitly isolated until the agent route is enabled; do not claim the event loop is implemented merely because fixture replay works.

## Semantic policy retained from the human discussion

Assess company, linked founding team and relevant market together against approved thesis. Explain why this, why them and why now. Pedigree is contextual; relevant expertise/execution can outweigh it unless a required criterion says otherwise. Timing is always assessed but gates qualification only when required. Reject supported boundary failures; otherwise retain monitor judgment until approved fit and every required evidence condition pass. Conceptual judgment is distinct from operational statuses such as needs_evidence/investigating; preserve existing wire enums and document their mapping rather than renaming them.

Still unresolved: exact reviewed thesis and required claims; independent attractiveness gate; whether human acceptance gates target counting; numeric allowances; freshness and materiality. These are not to be silently settled by backend code.

## Return to control

Update `handoffs/backend.md` with implemented versus proposed behavior, actual internal model names, migrations/compatibility, proof of transaction separation/stale rejection, run/test commands and remaining dependencies. Agent-design should be able to refine its planning from those files without guessing the runtime contract. No direct cross-chat messaging is required for this slice.
