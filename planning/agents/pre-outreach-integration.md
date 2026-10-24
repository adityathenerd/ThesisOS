# Pre-outreach calibration: implemented additive seam

24 October2026. Newly authorized by the human after the current strict enrichment version was ready. This supersedes the earlier deferred-only note for this implementation. Originalv0.3, prompt0.3, genuine model assessments, section9 readiness, evidence, graph IDs and human qualification remain unchanged.

## Exact implementation

agents.pre_outreach.build_pre_outreach_review(context:CaseContext,matcher_result:MatcherResult,*,assessment_ref:str,overlay:PreOutreachOverlay,guidance:PreOutreachGuidance,current_ref:VersionRef|None=None)->PreOutreachReview.

The mapper is pure: no file/source/model/provider calls, persistence, activation, scheduling or sending. Backend owns the registry, byte-hash verification, atomic current-version acceptance and ready/stale/unavailable HTTP envelope. Frontend renders the new stage label as a derived interpretation rather than model output, qualified or outreach_ready.

Exact schemas: agents/artifacts/pre-outreach-review.schema.json, pre-outreach-guidance.schema.json, pre-outreach-overlay.schema.json. All105agent tests pass:96baseline+9risk-based calibration checks. Tests cover credible leads with incomplete private diligence, unresolved identity/current operators, contrary scientific facts versus affirmative mismatch, no invented people/routes, stale bindings and genuine future-merit triggers.

## Meaning

outreach_candidate requires enough exact identity/scope, concrete source-described product/program/problem and source-supported conversation reason to justify human intro review. Private demonstrations, detailed contribution, rights/access and validation can remain one or two explicit call questions. They do not silently become proved or cease to matter for stricter review.

research_first requires a specific unresolved pre-intro premise, especially current identity/operator/status or a missing useful rationale. monitor requires a sourced future event that would create merit not present now; budget exhaustion or missing private material alone is not such a trigger. outside_scope requires an affirmative sourced mismatch, never missing publicity. No scores, quotas or forced category distribution.

Relevant-person status and contact-route status are separate. A credible project with no named builder/route may remain an outreach_candidate while next_step=resolve_person_or_route_for_human_review. No founder, address, current role or personal channel is invented. Current named people require source-supported canonical role links; company routes cannot masquerade as verified personal routes.

Review provenance is human-authorized_stage_calibration_interpretation_using_existing_evidence, with author, original assessment/prompt/input refs and overlay/guidance version+hash. Output explicitly says newly_executed_model=false, changes_formal_readiness=false, changes_qualification=false, sending_authorized=false. It does not falsely set or revoke the underlying case's actual qualification state.

## Source pins and nine-case audit

Policy planning/investment-thesis/pre-outreach-overlay-v0.1.md, version0.1, raw SHA2568decb2846efa18e776c987a8e07ee872a742bb7e9568c72fe108f6eda4816f85.

Guidance planning/investment-thesis/pre-outreach-nine-case-triage.json, version0.1, raw SHA2567c772f52ca6da64a8f736f2d5d58f490cc842d8034bca58838c08fdcfee8534f. UTF8BOM is part of these exact bytes; parse with utf-8-sig while retaining raw hash. Backend verifies both policy/guidance against its registry and full current backend_versions.

Pure existing-evidence audit planning/agents/pre-outreach-existing-nine-audit.json passes all nine exact case/evidence/assessment/citation/snapshot bindings without old artifact changes. The actual guidance yields eight outreach_candidate and Cadex research_first; the mapper contains no company names or category quotas. Cadex's blocker is current operator/operating continuity, not missing complete validation. Find Nuclei's unknown person/contact remains separate from conversation merit.

Adapter detail: pinned Cadex call_questions[0].text is null. Preserve the pinned file/hash. A faithful normalized question uses the same entry's decisive_blocker.text AND decisive_blocker.evidence_ids, with an explicit adapter note. Do not keep the null question's different evidence IDs or invent new content. Backend/thesis owners were notified; allnineaudit uses this bounded adaptation.

Other mappings: category->suggested_category; minimum_basis.identity_scope->minimum.identity_and_scope; concrete_product_program_problem->concrete_product_program_or_problem; useful_conversation_reason unchanged. Each supported=true becomes IntroCondition.status=supported. Named people use bound_people canonical IDs/role evidence; no contact route was established by this source mapping. Cadex blocker kind maps to current_operator_or_status. Contrary facts default limits_claim unless the specific sourced intro-blocking effect is explicit.

## Continuous worker handoff

Backend confirmed no new agent-paid worker is required. Reuse its accepted context -> comparison_packet -> ScriptedGraphTransport(live_authorized=True) -> genuine frozen0.3 graph -> AgentAssessmentStore -> agents.brief.to_case_brief -> saved_research_graph. Agent owner makes no paid calls. Backend owns durable single-concurrent scheduler, deadlines/cumulative caps, exact identity, source collection and state acceptance. Current scope is at most4newcases/20Crustdata requests/50credits/4model assessments, no automatic retry/qualification.

Minimum source guards: persist raw response before normalization; require exact canonical company/domain and usable homepage body rather than merelyHTTP200; explicit same-company-ID people/role claims only, past/unknown kept as such. A CEO title does not imply founder, a source-reported role does not imply contribution, aggregate engagement does not identify people. Failed source candidates are deferred rather than completed. Successful genuine assessments may retain unknowns. On timeout a model request may already have been made; preserve attempt/unknown billing and do not silently retry.

The nine-case editorial guidance applies only to its bound nine cases. New continuous cases must not inherit those names/categories or pretend a new human-authored interpretation exists. Their true defaults may be stage-interpretation unavailable/pending while saved genuine briefs/graphs remain reviewable. Root owns Git/repository changes; no Git mutations here.
