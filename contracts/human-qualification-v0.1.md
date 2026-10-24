# Human qualification boundary

User decision in the control chat, 24 October 2026: **Agents recommend; human approves qualification**, after the v0.3 evidence gates pass. This resolves the earlier conflict between automatic qualification and the researched human-qualified lifecycle. This document specifies required integration behavior; it is not proof the endpoint/UI is implemented.

## Policy

- Matcher returns an evidence-linked recommendation, findings, objections and remaining gaps. A recommendation is not an accepted qualification or outreach-ready state.
- Use the current v0.3 partner-review conditions: track-appropriate product/experimental evidence; an articulable problem/program, attributed founder contribution and differentiated approach; material contradictions resolved or explicitly presented for human review; remaining risks visible. Do not silently convert every C1-C8 item into a new non-negotiable criterion or invent numerical thresholds.
- Missing required proof remains needs-evidence/monitor. Schema-valid model output and search hits alone do not satisfy evidence gates.
- Human approval is an explicit recorded application action bound to an immutable assessment and the current case/policy/evidence version. A model, graph, task success, fixture replay or absence of objections cannot synthesize approval.
- Backend checks current eligibility and versions when accepting review. A new material fact or thesis revision makes an old pending review stale; it must be refreshed rather than approving the latest company using an old proposal.
- Qualified requires an accepted human approval. Outreach-ready additionally requires the appropriate current person/source, evidence-backed rationale and draft/readiness requirements. It does not imply outreach was sent or a meeting booked. Outbound contact remains human reviewed and outside this build's sending scope.
- Count only current outreach-ready packages under the existing target. Human qualification approval is now a prerequisite to that state for the semantic route. Any extra approval of the draft before counting is still a separate policy choice; do not invent it or conflate it with sending.
- Existing explicitly synthetic fixture scenarios can remain as development/test demonstrations, but must not be relabeled as human-approved real cases. Preserve original histories.

## Additive API proposal for owner alignment

Prefer one review action under the existing API rather than client-side status writes:

`POST /api/v1/cases/{case_id}/qualification-review`

Suggested request: `{assessment_id:string, expected_case_version:integer, decision:"approve"|"request_evidence", note:string|null}`. The assessment reference must identify the actual immutable stored recommendation/comparison; backend may refine the exact field name against its model, publishing the mapping in handoffs/backend.md before frontend integration.

Return current CaseDetail with additive optional review metadata, without changing existing v0.1 enums/required fields. Store a durable review event/record, the bound input versions, outcome and timestamp; do not fabricate reviewer identity. Reject stale or ineligible approval with a clear conflict/validation response and preserve prior state. An exact repeated request should be idempotent.

This app remains a loopback demo; no new authentication/hosting system is required for this slice. Browser code must not claim a review was accepted until the backend response confirms it.

## Acceptance slice

One case receives a genuine or clearly labeled scripted recommendation; model completion alone does not qualify it. Human review succeeds only for a current evidence-eligible assessment. Duplicate approval is safe; stale/unknown-required-evidence approval is refused. History shows assessment and human decision separately. Frontend can request evidence rather than approve. No paid call is needed merely to test these authority/version guards.
