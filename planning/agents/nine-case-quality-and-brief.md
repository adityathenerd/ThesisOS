# Nine-case sourcing and concise explanations

Status: agent slice ready; backend execution and frontend integration pending.
Updated: 24 October 2026. Prompt version 0.3. Plan: nine-case-product-program-v1.

## Governing thought

Research emerging teams with a concrete product or scientific program, then explain the strongest supported bet and decisive uncertainty plainly. Nine is the batch target; neither nine positives nor nine qualifications is promised.

The prior single referral query returned a healthcare workflow consultancy. It established sector proximity without establishing a reusable product. Separately, its long explanation obscured what the company did and mixed missing execution allowance into the research recommendation. Query targeting, evidence quality and communication therefore need distinct fixes.

The actual previous source packet remains historical. A concise rendering could say that it advises clinical operations teams on referral reliability and that proprietary software was not shown. This is presentation guidance based on the existing packet, not a new model result or a rewritten judgment.

## Scope and sources

- Binding batch bound: contracts/batch-scout-quality-v0.1.md. Backend alone makes at most four ranked searches, up to eight results each, no pagination or automatic retries, and one genuine assessment per selected case within the contract. No People/Enrich spend here.
- Investment direction: planning/investment-thesis/scouting-mandate.md v0.3, especially sections 2-6. C1-C8 remain vocabulary, not a sum or eight hard gates. Equal core H/R/D/T remains intact.
- Calibration: planning/investment-thesis/batch-scouting-review.md. Its alternative query families and example companies are neither extra calls nor preselected batch members. Follow its track-specific artifact, contribution, learning and services-hybrid distinctions.
- Query source: planning/agents/nine-case-discovery-plan.json. Exact query text, reviewed current source hash and scoped approval are bound by backend before execution. No approval record or model-generated discovery result is fabricated by this file.

## Sourcing and selection logic

Four hybrid queries sample H workflow products, R research tools, D diagnostic/device prototypes and T initial disease programs. Each asks for emerging teams and named artifacts/milestones. These are semantic retrieval hints. They introduce no funding, founding-date, headcount, revenue, geography, pedigree, AI or regulatory threshold. They may still return incumbents, agencies, weak metadata or duplicates; actual triage must show that attrition.

Preserve all encounters, rank/query lineage and source-supported deduplication. A current product/program page plus the most relevant accessible linked artifact supports initial triage. Product identity can be identified, unclear or services-only currently evidenced. Triage prioritizes research rather than accepting/rejecting an investment. A services business with an emerging reusable core remains researchable. Failed access is a recorded attempt, not disproof.

Prefer a concrete product/program, named user/population/problem and accessible attributable work; then specific founder contribution, relevant alternative and a meaningful unresolved bet. Prefer emerging teams and early-development milestones over incumbents for this research batch, with no new numeric maturity gate. Make each priority inspectable through saved evidence IDs, source type and limitations. Rankings are not suitability scores.

Take one researchable candidate per available track before revisiting a branch, then round-robin by evidence-supported research priority. This is transparent batch scheduling, not a fund allocation or equal-quality rule. Known YC-backed references do not fill novel-prospect slots; unknown backing remains unknown. If 32 encounters do not support nine unique researched cases, report the count and reason rather than padding the batch or silently adding searches.

## Exact additive brief contract

agents.models.SemanticAssessment gains optional case_brief: CaseBrief | null. Historical assessments without it remain valid and are not regenerated. New prompt0.3 requests a populated brief. The existing detailed findings and why_this/why_them/why_now/team_problem_fit remain available.

CaseBrief fields:

| Field | Shape and meaning |
|---|---|
| company_description | {text,evidence_ids}; one plain product/program or service + customer/population + concrete problem sentence |
| research_posture | pursue or monitor; semantic research priority, not accepted business state or authorization |
| main_reason | {text,evidence_ids}; one assertion explaining that posture |
| strongest_facts | At most two {text,evidence_ids}; positives require at least one admissible sourced non-stale evidence reference |
| founder_signals | At most two {person_id,contribution,relevance,evidence_ids,source_strength}; positive work must be linked to a supplied person with a supported company-role relationship and person-attributed evidence |
| founder_unknowns | At most three explicit unresolved questions; no guessed grit, cofounder consistency or tenure |
| decisive_doubt | {text,evidence_ids}; central counterfact or material gap; explicit unknowns may have no evidence IDs |
| next_action | One useful targeted action or monitor instruction, at most 500 characters |
| future_trigger | Nullable string; nonblank required for monitor |
| operational_limitations | At most three execution constraints, separately displayed |

BriefClaim text limit is 450 characters; contribution/relevance each 300. Length bounds are presentation constraints, not investment thresholds. source_strength is first_party_claim, inspectable_work, independent_report or mixed. It is the model's source interpretation, not deterministic verification, clinical validation or a new independent evidence record. Cite actual evidence and show the original source limitations.

Recommended wire addition at scout-result root: case_brief: CaseBriefProjection | null. Pure agents.brief.to_case_brief(result, assessment_ref=actual_saved_id) builds this envelope:

```json
{
  "schema_version": "0.1",
  "assessment_ref": "actual-saved-assessment-id",
  "input_ref": {"case_id":"actual-case-id","case_version":2,"thesis_version":1,"policy_version":1,"evidence_hash":"actual-hash"},
  "prompt_version": "0.3",
  "driver_kind": "semantic",
  "brief": {"...":"CaseBrief fields above"}
}
```

Exact standalone schema: agents/artifacts/case-brief.schema.json. Backend/frontend own adoption of this additive wire suggestion. The source output also remains accessible under agent_assessments[].structured_result.assessment.case_brief. Source references are evidence IDs; resolve these through the saved evidence ledger or graph sources[].evidence_ids, never by treating them as graph source IDs.

Projection accepts a saved comparison-only needs_approval result with assessment; it does not require accepted qualification. It makes no model call, adds no facts, and returns null for legacy/missing/failed briefs. It does not determine currentness: backend must bind the actual immutable assessment and input versions and expose whether they remain current. Do not substitute an old brief for a new current assessment without labeling it historical.

## Research posture and execution

Pursue means there is a specific useful next investigation or human-review action now. Zero call allowance can pause its execution while pursue remains semantically correct. Monitor requires a substantive reason to wait and an observable future trigger. Budget/capability exhaustion alone cannot justify monitor, establish poor fit, or become the decisive doubt. Both postures remain separate from human qualification.

For graph research_decision, decision_from_matcher now consumes the saved brief's research_posture, next_action and future_trigger directly. With a brief, omit action_timing/future_trigger; supply result, actual assessment_ref and a substantive decision_consequence. An explicit contradictory timing/trigger raises ValueError. Legacy outputs without a brief still require explicit action_timing. build_research_graph also rejects a manually supplied decision that contradicts the brief's posture/action/trigger. This prevents separate graph and brief recommendations at zero execution budget. Backend remains responsible for a faithful current explanation and actual permitted execution. Do not derive posture solely from remaining_calls or map pursue to qualified. Existing investment rejection boundaries continue independently; not every poor candidate must become a positive research opportunity.

## Minto display logic

Audience: investor deciding whether and why to spend the next unit of attention. Governing thought: the research recommendation plus its strongest supported reason. The argument map is product/problem -> source-backed reasons and named contribution -> decisive uncertainty -> decision-changing next action. Metadata, complete C1-C8, graph and history support this argument through progressive disclosure. They must not replace the opening explanation. Material scientific/first-party uncertainty stays visible.

## Now / Next / Later and verification

Now complete here: final four-query plan; prompt0.3 constitution and role/task changes; additive brief and pure projection; guards; schema; 75 local tests passing. Ten new checks cover legacy compatibility, separate zero-budget pursue, monitor trigger, citation/person identity, title-only false positive, supported attributable work, stale positive evidence, compiling all four exact query bodies under explicitly synthetic test scopes and consistent graph/brief posture with contradictory overrides rejected. These are software tests, not semantic calibration or a guarantee of candidate quality. No paid/provider/research calls were made here.

Next: backend executes the bounded pool, persists triage and selected cases, uses prompt0.3 before each genuine evaluation, and exposes the brief with graph/result. Frontend consumes the exact schema and validates a strong and uncertain case, evidence selection, reload/export and mobile. This chat supports concrete schema or guard issues without duplicate execution.

Later: audit actual batch relevance, source support and brevity; revise only with observed failures. Preserve old case and prompt versions. Any additional paid retry/expanded search is outside this file's authority and must follow the binding batch contract.

Cold pickup: open nine-case-discovery-plan.json and this document first, then handoffs/agents-design.md. Do not rerun historical model calls, insert calibration examples as discovered leads or reinterpret all criteria as required gates. Primary uncertainty is the actual candidate pool and source accessibility, not settled human qualification ownership.
