"""Bounded LangGraph passes. These functions have no persistence/tool authority."""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from .drivers import Driver, ModelCallError
from .models import (
    CaseContext, MandateContext, MatcherResult, OrchestratorResult, SemanticAssessment,
    SemanticPlan, VersionRef, evidence_hash, intent_key, investigation_key,
)
from .prompts import system_prompt


class MatcherState(TypedDict, total=False):
    context: CaseContext
    current_ref: VersionRef | None
    assessment: SemanticAssessment
    input_tokens: int
    output_tokens: int
    result: MatcherResult


def _matcher_result(driver, ctx, outcome, explanation, **kwargs):
    return MatcherResult(outcome=outcome, ref=ctx.ref, disposition=None, assessment=None,
                         investigation=None, missing_required_claims=[], guard_notes=[],
                         explanation=explanation, driver_kind=driver.kind, test_fixture=ctx.test_fixture,
                         evidence_modes=sorted({e.data_mode for e in ctx.evidence}), **kwargs)


def _packet_errors(ctx: CaseContext) -> list[str]:
    errors = []
    for group in (ctx.people, ctx.relationships, ctx.evidence):
        if len({x.id for x in group}) != len(group):
            errors.append("Duplicate entity/evidence IDs")
    people, evidence = {p.id for p in ctx.people}, {e.id for e in ctx.evidence}
    for relationship in ctx.relationships:
        if relationship.company_id != ctx.company_id or relationship.person_id not in people:
            errors.append("Relationship refers to an absent person or another company")
        if not set(relationship.evidence_ids) <= evidence:
            errors.append("Relationship cites unknown evidence")
    if not set(ctx.changed_evidence_ids) <= evidence:
        errors.append("Delta cites unknown evidence")
    for observation in ctx.evidence:
        if observation.subject_kind == "company" and observation.subject_id != ctx.company_id:
            errors.append("Observation belongs to another company")
        if observation.subject_kind == "person" and observation.subject_id not in people:
            errors.append("Observation belongs to an absent person")
        if observation.subject_kind == "relationship" and observation.subject_id not in {r.id for r in ctx.relationships}:
            errors.append("Observation belongs to an absent relationship")
    return errors


def _assessment_errors(ctx, assessment):
    errors = []
    criteria = {c.id: c for c in ctx.policy.criteria}
    ids = [f.criterion_id for f in assessment.findings]
    if len(ids) != len(set(ids)) or set(ids) != set(criteria):
        errors.append("Output must contain exactly one finding per approved criterion")
    evidence = {e.id: e for e in ctx.evidence}
    for item in [*assessment.findings, assessment.why_this, assessment.why_them, assessment.why_now, assessment.team_problem_fit]:
        if not set(item.evidence_ids) <= evidence.keys():
            errors.append("Output cites nonexistent evidence")
    for finding in assessment.findings:
        if not set(finding.counterevidence_ids) <= evidence.keys():
            errors.append("Output cites nonexistent counterevidence")
        if not set(finding.person_ids) <= {p.id for p in ctx.people}:
            errors.append("Output refers to an absent person")
    brief = assessment.case_brief
    if brief is not None:
        for claim in [brief.company_description, brief.main_reason, brief.decisive_doubt, *brief.strongest_facts]:
            if not set(claim.evidence_ids) <= evidence.keys():
                errors.append("Case brief cites nonexistent evidence")
        for claim in brief.strongest_facts:
            if any(not evidence[eid].admissible or not (evidence[eid].source_key or evidence[eid].source_url)
                   or evidence[eid].freshness == "stale" or (evidence[eid].data_mode == "synthetic" and not ctx.test_fixture)
                   for eid in claim.evidence_ids if eid in evidence):
                errors.append("Positive case-brief fact requires admissible sourced current evidence")
        for signal in brief.founder_signals:
            if signal.person_id not in {p.id for p in ctx.people}:
                errors.append("Case brief refers to an absent person")
            if not set(signal.evidence_ids) <= evidence.keys():
                errors.append("Founder signal cites nonexistent evidence")
            elif not _has_supported_relationship(ctx, signal.person_id, evidence):
                errors.append("Founder signal requires a supported sourced company-role link")
            elif not any(evidence[eid].subject_kind == "person" and evidence[eid].subject_id == signal.person_id
                         for eid in signal.evidence_ids):
                errors.append("Founder signal requires evidence attributed to that person's work")
            elif any(not evidence[eid].admissible or not (evidence[eid].source_key or evidence[eid].source_url)
                     or evidence[eid].freshness == "stale" or (evidence[eid].data_mode == "synthetic" and not ctx.test_fixture)
                     for eid in signal.evidence_ids):
                errors.append("Positive founder signal requires admissible sourced current evidence")
    return errors


def _has_supported_relationship(ctx, person_id, evidence):
    for rel in ctx.relationships:
        if rel.person_id != person_id or rel.status != "supported" or not rel.evidence_ids:
            continue
        if all(eid in evidence and evidence[eid].admissible and
               (evidence[eid].source_key or evidence[eid].source_url) and evidence[eid].freshness != "stale"
               and (evidence[eid].data_mode != "synthetic" or ctx.test_fixture)
               for eid in rel.evidence_ids):
            return True
    return False


def _finding_sufficient(ctx, finding):
    evidence = {e.id: e for e in ctx.evidence}
    if finding.result == "unknown" or finding.conflicted or finding.comparison_state in {"mixed", "unknown", "not_applicable"} or not finding.evidence_sufficient or not finding.evidence_ids:
        return False
    if any(not evidence[eid].admissible or not (evidence[eid].source_key or evidence[eid].source_url)
           or evidence[eid].freshness == "stale" or (evidence[eid].data_mode == "synthetic" and not ctx.test_fixture)
           for eid in finding.evidence_ids):
        return False
    criterion = next(c for c in ctx.policy.criteria if c.id == finding.criterion_id)
    if criterion.lens == "founder":
        if not finding.person_ids or any(not _has_supported_relationship(ctx, pid, evidence) for pid in finding.person_ids):
            return False
        # A company fact or famous name alone is insufficient founder evidence.
        if not any(evidence[eid].subject_kind == "person" and evidence[eid].subject_id in finding.person_ids for eid in finding.evidence_ids):
            return False
    return True


def _valid_investigation(ctx, assessment, disposition):
    request = assessment.investigation
    if request is None:
        return None, []
    notes = []
    criterion = next((c for c in ctx.policy.criteria if c.id == request.criterion_id), None)
    finding = next((f for f in assessment.findings if f.criterion_id == request.criterion_id), None)
    capability = next((a for a in ctx.capabilities if a.purpose == "investigation" and a.action == request.action and request.subject_kind in a.subject_kinds), None)
    scope = {"company": {ctx.company_id}, "person": {p.id for p in ctx.people},
             "relationship": {r.id for r in ctx.relationships}, "market": {e.subject_id for e in ctx.evidence if e.subject_kind == "market"}}
    if disposition != "monitor":
        notes.append("Investigation suppressed: case has a decisive disposition")
    if criterion is None or finding is None or not criterion.required_for_qualification:
        notes.append("Investigation suppressed: not an approved required gap")
    elif finding.result == "meets" and _finding_sufficient(ctx, finding):
        notes.append("Investigation suppressed: required finding already resolved")
    if capability is None or request.subject_id not in scope[request.subject_kind]:
        notes.append("Investigation suppressed: action or subject is not available")
    if request.max_calls > ctx.resources.remaining_calls or ctx.resources.deadline_expired:
        notes.append("Investigation suppressed: resource limit")
    if investigation_key(ctx.ref.case_id, request) in ctx.attempted_investigation_keys:
        notes.append("Investigation suppressed: source/query already attempted")
    return (None if notes else request), notes


def build_matcher(driver: Driver):
    def validate(state):
        ctx = state["context"]
        if state.get("current_ref") is not None and ctx.ref != state["current_ref"]:
            return {"result": _matcher_result(driver, ctx, "stale_input", "Input versions differ from the supplied current reference")}
        if ctx.ref.thesis_version != ctx.policy.thesis_version or ctx.ref.policy_version != ctx.policy.policy_version or ctx.ref.evidence_hash != evidence_hash(ctx):
            return {"result": _matcher_result(driver, ctx, "stale_input", "Policy version or factual snapshot hash mismatch")}
        errors = _packet_errors(ctx)
        if errors:
            return {"result": _matcher_result(driver, ctx, "invalid_input", "; ".join(errors))}
        comparison_only = ctx.mode == "reference_comparison" and ctx.policy.reference_direction_reviewed
        if (not ctx.policy.approved and not comparison_only) or not ctx.policy.criteria or not ctx.policy.fit_rule.strip():
            return {"result": _matcher_result(driver, ctx, "needs_approval", "An approved criterion interpretation and fit rule are required")}
        if ctx.resources.deadline_expired or ctx.resources.remaining_output_tokens == 0:
            return {"result": _matcher_result(driver, ctx, "waiting", "Model output allowance or deadline exhausted")}
        policy_changed = ctx.prior_ref is not None and (ctx.prior_ref.policy_version != ctx.ref.policy_version or ctx.prior_ref.thesis_version != ctx.ref.thesis_version)
        if ctx.mode != "initial_assessment" and not ctx.changed_evidence_ids and ctx.prior_assessment is not None and not policy_changed:
            return {"result": _matcher_result(driver, ctx, "waiting", "No evidence delta; unchanged work needs an explicit fresh task")}
        return {}

    def assess(state):
        ctx = state["context"]
        try:
            reply = driver.generate(system=system_prompt("matcher", ctx.mode), context=ctx,
                                    schema=SemanticAssessment, max_output_tokens=min(6000, ctx.resources.remaining_output_tokens))
            assessment = SemanticAssessment.model_validate(reply.value)
            return {"assessment": assessment, "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}
        except (ValidationError, ValueError, TypeError):
            return {"result": _matcher_result(driver, ctx, "invalid_output", "Structured model output did not match the assessment contract")}
        except ModelCallError as error:
            return {"result": _matcher_result(driver, ctx, "model_failed", f"{error.code}: {error}", input_tokens=error.input_tokens, output_tokens=error.output_tokens)}
        except Exception:
            return {"result": _matcher_result(driver, ctx, "model_failed", "Model call failed; no disposition was accepted")}

    def guard(state):
        ctx, assessment = state["context"], state["assessment"]
        usage = {"input_tokens": state.get("input_tokens", 0), "output_tokens": state.get("output_tokens", 0)}
        errors = _assessment_errors(ctx, assessment)
        if errors:
            return {"result": _matcher_result(driver, ctx, "invalid_output", "; ".join(errors), **usage)}
        if assessment.interpretation_question or not ctx.policy.approved:
            return {"result": MatcherResult(outcome="needs_approval", ref=ctx.ref, disposition=None,
                assessment=assessment, investigation=None, missing_required_claims=[], guard_notes=["Reference comparison only; no accepted case transition or human qualification approval"],
                explanation=assessment.interpretation_question or "Non-authoritative reference comparison: present specific evidence gaps and recommendation for human review under v0.3; human qualification authority is settled",
                driver_kind=driver.kind, test_fixture=ctx.test_fixture, evidence_modes=sorted({e.data_mode for e in ctx.evidence}), **usage)}
        findings = {f.criterion_id: f for f in assessment.findings}
        validated_sufficiency = {key: _finding_sufficient(ctx, finding) for key, finding in findings.items()}
        missing = [c.id for c in ctx.policy.criteria if c.required_for_qualification and
                   (findings[c.id].result != "meets" or not _finding_sufficient(ctx, findings[c.id]))]
        failures = [c.id for c in ctx.policy.criteria if c.reject_on_failure and findings[c.id].result == "fails" and _finding_sufficient(ctx, findings[c.id])]
        if failures:
            disposition, reason = "reject", "Supported approved boundary failure: " + ", ".join(failures)
        elif assessment.fit == "passes" and not missing and (ctx.policy.attractiveness_gate != "required" or assessment.attractiveness == "promising"):
            disposition, reason = "qualify", "Evidence gates support recommending human qualification review; no qualification or human approval is accepted by this graph"
        else:
            disposition, reason = "monitor", "Fit, required evidence or an approved attractiveness gate remains unresolved"
        request, notes = _valid_investigation(ctx, assessment, disposition)
        if assessment.proposed_disposition != disposition:
            notes.append(f"Model proposed {assessment.proposed_disposition}; deterministic gates require {disposition}")
        if disposition == "qualify":
            notes.append("Human approval bound to the current immutable assessment is required before qualified state or outreach preparation")
        return {"result": MatcherResult(outcome="assessment", ref=ctx.ref, disposition=disposition,
                                         assessment=assessment, investigation=request, missing_required_claims=missing,
                                         guard_notes=notes, explanation=reason, driver_kind=driver.kind,
                                         test_fixture=ctx.test_fixture, evidence_modes=sorted({e.data_mode for e in ctx.evidence}),
                                         criterion_evidence_sufficient=validated_sufficiency,
                                         requires_human_qualification_review=disposition == "qualify", **usage)}

    graph = StateGraph(MatcherState)
    graph.add_node("validate_snapshot", validate)
    graph.add_node("joint_assessment", assess)
    graph.add_node("guard_decision", guard)
    graph.add_edge(START, "validate_snapshot")
    graph.add_conditional_edges("validate_snapshot", lambda s: "end" if "result" in s else "assess", {"end": END, "assess": "joint_assessment"})
    graph.add_conditional_edges("joint_assessment", lambda s: "end" if "result" in s else "guard", {"end": END, "guard": "guard_decision"})
    graph.add_edge("guard_decision", END)
    return graph.compile()


class OrchestratorState(TypedDict, total=False):
    context: MandateContext
    current_snapshot_id: str | None
    plan: SemanticPlan
    input_tokens: int
    output_tokens: int
    result: OrchestratorResult


def build_orchestrator(driver: Driver):
    def result(ctx, outcome, explanation, **kwargs):
        return OrchestratorResult(outcome=outcome, snapshot_id=ctx.snapshot_id, intents=[], intent_keys=[], guard_notes=[],
                                  explanation=explanation, driver_kind=driver.kind, **kwargs)

    def reconcile(state):
        ctx = state["context"]
        if state.get("current_snapshot_id") is not None and ctx.snapshot_id != state["current_snapshot_id"]:
            return {"result": result(ctx, "stale_input", "Mandate snapshot superseded")}
        if len({c.ref.case_id for c in ctx.cases}) != len(ctx.cases):
            return {"result": result(ctx, "invalid_input", "Duplicate case IDs")}
        if len({b.id for b in ctx.discovery_branches}) != len(ctx.discovery_branches):
            return {"result": result(ctx, "invalid_input", "Duplicate discovery branch IDs")}
        planning_only = ctx.mode == "discovery_planning" and ctx.policy.reference_direction_reviewed
        if (not ctx.policy.approved and not planning_only) or not ctx.policy.criteria or not ctx.policy.fit_rule.strip():
            return {"result": result(ctx, "needs_approval", "Approved policy and fit rule are required")}
        if any(c.ref.thesis_version != ctx.policy.thesis_version or c.ref.policy_version != ctx.policy.policy_version for c in ctx.cases):
            return {"result": result(ctx, "stale_input", "Case projection was not reconciled to current policy")}
        if any(c.judgment in {"qualified", "outreach_ready"} and not c.has_current_human_qualification() for c in ctx.cases):
            return {"result": result(ctx, "invalid_input", "Qualified/ready semantic-route cases require a current durable human approval bound to the current assessment and policy/evidence")}
        ready = sum(c.judgment == "outreach_ready" and c.readiness_current and
                    (not ctx.review_required_to_count or c.review_accepted) for c in ctx.cases)
        if ready >= ctx.target_count:
            return {"result": result(ctx, "completion_proposal", "Accepted current outreach readiness reaches the supplied target")}
        if ctx.resources.deadline_expired or ctx.resources.remaining_output_tokens == 0:
            outcome = "waiting" if ctx.active_work_keys and not ctx.resources.deadline_expired else "shortfall_proposal"
            return {"result": result(ctx, outcome, "Deadline or model-output allowance exhausted; target not reached")}
        return {}

    def plan(state):
        ctx = state["context"]
        try:
            reply = driver.generate(system=system_prompt("orchestrator", ctx.mode), context=ctx, schema=SemanticPlan,
                                    max_output_tokens=min(4000, ctx.resources.remaining_output_tokens))
            return {"plan": SemanticPlan.model_validate(reply.value), "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}
        except (ValidationError, ValueError, TypeError):
            return {"result": result(ctx, "invalid_output", "Structured model output did not match the intent contract")}
        except ModelCallError as error:
            return {"result": result(ctx, "model_failed", f"{error.code}: {error}", input_tokens=error.input_tokens, output_tokens=error.output_tokens)}
        except Exception:
            return {"result": result(ctx, "model_failed", "Model call failed; no tasks were accepted")}

    def guard(state):
        ctx, proposal = state["context"], state["plan"]
        usage = {"input_tokens": state.get("input_tokens", 0), "output_tokens": state.get("output_tokens", 0)}
        if proposal.interpretation_question:
            return {"result": result(ctx, "needs_approval", proposal.interpretation_question, **usage)}
        if ctx.mode == "discovery_planning":
            criteria = {c.id for c in ctx.policy.criteria}
            hypotheses = proposal.discovery_hypotheses
            valid = (not proposal.intents and hypotheses and len({h.id for h in hypotheses}) == len(hypotheses)
                     and all(h.criterion_ids and set(h.criterion_ids) <= criteria for h in hypotheses))
            if not valid:
                return {"result": result(ctx, "invalid_output", "Discovery planning requires criterion-linked hypotheses and no executable intents", **usage)}
            return {"result": OrchestratorResult(outcome="discovery_plan_proposal", snapshot_id=ctx.snapshot_id,
                intents=[], intent_keys=[], guard_notes=["Provider mapping, recall limitations and operational approval remain required"],
                explanation=proposal.explanation, driver_kind=driver.kind, discovery_hypotheses=hypotheses, **usage)}
        cases = {c.ref.case_id: c for c in ctx.cases}
        notes, accepted, keys = [], [], []
        remaining = ctx.resources.remaining_calls
        for intent in proposal.intents:
            case = cases.get(intent.case_id)
            key = intent_key(ctx, intent)
            error = None
            if key in ctx.active_work_keys or key in ctx.completed_work_keys or key in keys:
                error = "duplicate/already active or completed work"
            elif intent.max_calls > remaining:
                error = "aggregate call allowance exceeded"
            elif intent.kind != "discover" and case is None:
                error = "unknown case"
            elif intent.kind == "evaluate_case":
                if intent.investigation or intent.action or intent.discovery_branch_id or intent.max_calls != 0:
                    error = "evaluation cannot execute provider actions"
                elif case.assessed_evidence_hash == case.ref.evidence_hash:
                    error = "no changed evidence snapshot"
            elif intent.kind == "investigate_claim":
                request = intent.investigation
                if (case.judgment != "monitor" or request is None or request != case.proposed_investigation
                    or intent.max_calls != request.max_calls or intent.action != request.action or intent.discovery_branch_id):
                    error = "investigation is not the accepted gap proposal for a monitored case"
                elif not any(a.purpose == "investigation" and a.action == request.action and request.subject_kind in a.subject_kinds for a in ctx.capabilities):
                    error = "unavailable investigation capability"
                elif key in ctx.attempted_investigation_keys:
                    error = "source/query already attempted"
            elif intent.kind == "prepare_outreach":
                if case.judgment != "qualified" or not case.has_current_human_qualification() or intent.investigation or intent.action or intent.discovery_branch_id or intent.max_calls != 0:
                    error = "package preparation requires a qualified case without provider side effects"
            elif intent.kind == "discover":
                branch = next((b for b in ctx.discovery_branches if b.id == intent.discovery_branch_id), None)
                if intent.case_id is not None or intent.investigation or ctx.discovery_exhausted or intent.max_calls < 1:
                    error = "discovery scope is exhausted or invalid"
                elif (branch is None or not branch.approved or branch.action != intent.action or intent.max_calls > branch.max_calls
                      or not branch.criterion_ids or not set(branch.criterion_ids) <= {c.id for c in ctx.policy.criteria}):
                    error = "discovery requires a reviewed thesis-linked branch within its call bound"
                elif not any(a.purpose == "discovery" and a.action == intent.action and "company" in a.subject_kinds for a in ctx.capabilities):
                    error = "unavailable discovery capability"
            if error:
                notes.append(f"Suppressed {intent.kind}: {error}")
            else:
                remaining -= intent.max_calls
                accepted.append(intent)
                keys.append(key)
        if accepted:
            outcome = "intents"
        elif ctx.active_work_keys or any(
            (c.qualification_review_pending and c.assessed_evidence_hash == c.ref.evidence_hash) or
            (c.judgment == "outreach_ready" and c.readiness_current and ctx.review_required_to_count and not c.review_accepted)
            for c in ctx.cases):
            outcome = "waiting"
        elif proposal.intents:
            outcome = "invalid_output"  # Invalid planning is not market exhaustion.
        else:
            # A model giving up is not by itself a defensible shortfall.
            pending_evaluation = any(c.assessed_evidence_hash != c.ref.evidence_hash for c in ctx.cases)
            pending_package = any(c.judgment == "qualified" and c.has_current_human_qualification() for c in ctx.cases)
            pending_gap = any(c.judgment == "monitor" and c.proposed_investigation is not None and
                              investigation_key(c.ref.case_id, c.proposed_investigation) not in ctx.attempted_investigation_keys and
                              c.proposed_investigation.max_calls <= remaining and
                              any(a.purpose == "investigation" and a.action == c.proposed_investigation.action and c.proposed_investigation.subject_kind in a.subject_kinds for a in ctx.capabilities)
                              for c in ctx.cases)
            can_discover = not ctx.discovery_exhausted and remaining > 0 and any(b.approved and b.max_calls <= remaining and
                any(a.purpose == "discovery" and a.action == b.action and "company" in a.subject_kinds for a in ctx.capabilities) for b in ctx.discovery_branches)
            outcome = "invalid_output" if pending_evaluation or pending_package or pending_gap or can_discover else "shortfall_proposal"
        return {"result": OrchestratorResult(outcome=outcome, snapshot_id=ctx.snapshot_id, intents=accepted,
                                              intent_keys=keys, guard_notes=notes, explanation=proposal.explanation,
                                              driver_kind=driver.kind, **usage)}

    graph = StateGraph(OrchestratorState)
    graph.add_node("reconcile_snapshot", reconcile)
    graph.add_node("select_work", plan)
    graph.add_node("guard_intents", guard)
    graph.add_edge(START, "reconcile_snapshot")
    graph.add_conditional_edges("reconcile_snapshot", lambda s: "end" if "result" in s else "plan", {"end": END, "plan": "select_work"})
    graph.add_conditional_edges("select_work", lambda s: "end" if "result" in s else "guard", {"end": END, "guard": "guard_intents"})
    graph.add_edge("guard_intents", END)
    return graph.compile()
