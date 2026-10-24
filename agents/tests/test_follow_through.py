import unittest

from agents.drivers import ScriptedDriver
from agents.examples import scripted_assessment, test_context, with_founder_evidence
from agents.graphs import build_matcher
from agents.follow_through import (BoundaryConclusion, FounderReviewCheck, HumanContradictionAcceptance, MaterialContradiction,
    ProductReviewCheck, ResearchAttempt, ResearchPoint, ReviewCheck, Section9Readiness, plan_follow_through)
from agents.models import seal_context


def match(ctx=None, assessment=None):
    ctx = ctx or test_context()
    return build_matcher(ScriptedDriver(assessment or scripted_assessment())).invoke({"context": ctx})["result"]


def report(ctx):
    company = ReviewCheck(status="supported", explanation="Explicit synthetic software-test fact", evidence_ids=["e-company"])
    return Section9Readiness(assessment_ref="stored", input_ref=ctx.ref, primary_track="H", identity_and_scope=company,
        problem_or_program=company, differentiated_approach=company,
        founder_contribution=FounderReviewCheck(status="supported", explanation="Attributed work", evidence_ids=["e-person", "e-role"], person_ids=["test-person"]),
        product_or_experimental_gate=ProductReviewCheck(status="supported", explanation="Inspectable workflow documentation", evidence_ids=["e-prototype"], basis="inspected_documentation"),
        remaining_risks=["Commercial adoption unknown; this is a software fixture, not an approved real case."])


class FollowThroughTests(unittest.TestCase):
    def test_comparison_only_can_request_bounded_research_without_qualifying(self):
        ctx = test_context()
        ctx = ctx.model_copy(update={"policy": ctx.policy.model_copy(update={"approved": False, "reference_direction_reviewed": True}), "mode": "reference_comparison"})
        result = match(ctx)
        self.assertEqual(result.outcome, "needs_approval")
        plan = plan_follow_through(ctx, result, assessment_ref="stored")
        self.assertEqual(plan.state, "research_required")
        self.assertEqual(len(plan.task_intents), 1)
        self.assertIsNone(result.disposition)
        self.assertEqual(plan.task_intents[0].investigation.subject_id, "test-person")

    def test_zero_budget_returns_specific_human_points_before_further_pursuit(self):
        ctx = test_context();ctx = ctx.model_copy(update={"resources": ctx.resources.model_copy(update={"remaining_calls": 0}), "capabilities": []})
        plan = plan_follow_through(ctx, match(ctx), assessment_ref="stored")
        self.assertEqual(plan.state, "human_research_required")
        self.assertFalse(plan.task_intents)
        self.assertIn("founder", plan.human_research_points[0].question)
        self.assertTrue(plan.human_research_points[0].what_to_obtain)
        self.assertNotEqual(plan.state, "monitor")

    def test_running_attempt_is_reported_only_from_backend_task_record(self):
        ctx = test_context();result = match(ctx)
        plan = plan_follow_through(ctx, result, assessment_ref="stored")
        task = plan.task_intents[0]
        attempt = ResearchAttempt(task_id="actual-task", question_id=task.question_id, status="running", summary="Backend says fetching source")
        active = plan_follow_through(ctx, result, assessment_ref="stored", attempts=[attempt])
        self.assertEqual(active.state, "actively_researching")
        self.assertEqual(active.active_task_ids, ["actual-task"])
        self.assertFalse(active.task_intents)

    def test_inaccessible_or_no_answer_stops_unchanged_retry_and_records_handoff(self):
        ctx = test_context();result = match(ctx);point_id = plan_follow_through(ctx, result, assessment_ref="stored").task_intents[0].question_id
        for status in ["inaccessible", "no_answer", "failed", "succeeded"]:
            attempt = ResearchAttempt(task_id="actual-task", question_id=point_id, status=status, summary="No decision-changing accepted observation")
            plan = plan_follow_through(ctx, result, assessment_ref="stored", attempts=[attempt])
            self.assertEqual(plan.state, "human_research_required")
            self.assertEqual(plan.human_research_points[0].attempted_task_ids, ["actual-task"])

    def test_accepted_delta_requires_reassessment_not_a_new_pursue_label(self):
        old = test_context();result = match(old);new = with_founder_evidence(old, result.assessment)
        plan = plan_follow_through(new, result, assessment_ref="stored", attempts=[ResearchAttempt(task_id="done", question_id="q", status="succeeded", summary="Accepted attributable work", accepted_evidence_ids=["e-person"])])
        self.assertEqual(plan.state, "reassessment_required")
        self.assertTrue(plan.reassessment_required)
        self.assertIn("e-person", plan.accepted_delta_evidence_ids)
        self.assertFalse(plan.task_intents)

    def test_section9_docs_can_be_ready_without_all_criteria_or_hands_on(self):
        ctx = with_founder_evidence(test_context(), scripted_assessment());result = match(ctx, scripted_assessment(True))
        plan = plan_follow_through(ctx, result, assessment_ref="stored", readiness=report(ctx))
        self.assertEqual(plan.state, "ready_for_human_review")
        self.assertEqual(plan.review_kind, "investment_human")
        self.assertEqual(result.assessment.findings[-1].result, "unknown")
        self.assertIn("not_qualification", plan.authority)

    def test_contradictions_need_current_explicit_human_acceptance(self):
        ctx = with_founder_evidence(test_context(), scripted_assessment());result = match(ctx, scripted_assessment(True))
        ready = report(ctx).model_copy(update={"material_contradictions": [MaterialContradiction(id="c", explanation="Material conflicting fact", evidence_ids=["e-company"], resolved=False)]})
        self.assertNotEqual(plan_follow_through(ctx, result, assessment_ref="stored", readiness=ready).state, "ready_for_human_review")
        accepted = HumanContradictionAcceptance(review_record_id="durable-human-record", assessment_ref="stored", input_ref=ctx.ref, contradiction_ids=["c"], current=True)
        self.assertEqual(plan_follow_through(ctx, result, assessment_ref="stored", readiness=ready.model_copy(update={"human_contradiction_acceptance": accepted})).state, "ready_for_human_review")
        with self.assertRaises(ValueError):
            plan_follow_through(ctx, result, assessment_ref="stored", readiness=ready.model_copy(update={"human_contradiction_acceptance": accepted.model_copy(update={"current": False})}))

    def test_stale_snapshot_unknown_evidence_and_unsupported_decline_fail(self):
        ctx = test_context();result = match(ctx)
        with self.assertRaises(ValueError):
            plan_follow_through(ctx, result, assessment_ref="stored", current_ref=ctx.ref.model_copy(update={"case_version": 9}))
        with self.assertRaises(ValueError):
            plan_follow_through(ctx, result, assessment_ref="stored", questions=[ResearchPoint(id="q", question="Question", decision_consequence="Changes decision", what_to_obtain="Evidence", evidence_ids=["invented"])])
        with self.assertRaises(ValueError):
            plan_follow_through(ctx, result, assessment_ref="stored", boundary=BoundaryConclusion(kind="decline", basis="confirmed_sector_mismatch", rationale="Cannot silently turn research scope into investment rejection", evidence_ids=["e-company"]))

    def test_total_budget_is_shared_and_nonrequired_criterion_can_be_researched(self):
        ctx = test_context();result = match(ctx);inv=result.assessment.investigation
        points=[ResearchPoint(id=str(i),criterion_ids=["timing"],question=inv.question,decision_consequence=inv.decision_consequence,what_to_obtain="Specific timing source",
            investigation=inv.model_copy(update={"criterion_id":"timing","query":str(i)})) for i in range(2)]
        plan=plan_follow_through(ctx,result,assessment_ref="stored",questions=points)
        self.assertEqual(len(plan.task_intents),1)
        self.assertEqual(len(plan.human_research_points),1)

    def test_diagnostics_documentation_alone_not_experimental_validation(self):
        ctx=with_founder_evidence(test_context(),scripted_assessment());result=match(ctx,scripted_assessment(True))
        ready=report(ctx).model_copy(update={"primary_track":"D"})
        plan=plan_follow_through(ctx,result,assessment_ref="stored",readiness=ready)
        self.assertIn("track_appropriate_experimental_or_prototype_evidence",plan.readiness_gaps)
        ready=ready.model_copy(update={"product_or_experimental_gate":ready.product_or_experimental_gate.model_copy(update={"basis":"inspected_experiment"})})
        self.assertEqual(plan_follow_through(ctx,result,assessment_ref="stored",readiness=ready).review_kind,"specialist_human")

    def test_resolved_question_stays_in_history_without_becoming_a_human_gap(self):
        ctx=with_founder_evidence(test_context(),scripted_assessment());result=match(ctx,scripted_assessment(True))
        old=ResearchAttempt(task_id="old-done",question_id="resolved-founder-question",status="succeeded",summary="Current assessment now supports founder work",accepted_evidence_ids=["e-person"])
        plan=plan_follow_through(ctx,result,assessment_ref="stored",questions=[],attempts=[old],readiness=report(ctx))
        self.assertEqual(plan.state,"ready_for_human_review")
        self.assertFalse(plan.human_research_points)


if __name__=="__main__":unittest.main()
