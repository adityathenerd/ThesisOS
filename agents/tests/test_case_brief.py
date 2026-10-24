import json
from pathlib import Path
import unittest

from agents.brief import CaseBriefProjection, to_case_brief
from agents.drivers import ScriptedDriver
from agents.examples import scripted_assessment, test_context, with_founder_evidence
from agents.graphs import build_matcher
from agents.models import BriefClaim, CaseBrief, FounderSignal, Resources, SourcedBriefClaim
from agents.reference import reviewed_reference_policy
from agents.research_graph import build_research_graph, decision_from_matcher
from agents.search import CompanySearchCatalog, RankedSearch, ScopedDiscoveryApproval, compile_ranked_company_search
from agents.models import DiscoveryBranch


def brief(**updates):
    values = dict(company_description=BriefClaim(text="Synthetic company builds referral-routing software for clinic administrators.", evidence_ids=["e-company"]),
                  research_posture="pursue", main_reason=BriefClaim(text="A demonstrated workflow merits verifying the builder's relevant execution.", evidence_ids=["e-prototype"]),
                  strongest_facts=[SourcedBriefClaim(text="The synthetic demonstration completes referral routing.", evidence_ids=["e-prototype"])],
                  founder_signals=[], founder_unknowns=["Relevant execution is unresolved."],
                  decisive_doubt=BriefClaim(text="A founder title does not establish deployment work.", evidence_ids=["e-role"]),
                  next_action="Inspect attributable founder deployment work.", future_trigger=None,
                  operational_limitations=["Execution allowance may be exhausted; no action is scheduled by this brief."])
    values.update(updates)
    return CaseBrief(**values)


def match(ctx, view):
    assessment = scripted_assessment().model_copy(update={"case_brief": view})
    return build_matcher(ScriptedDriver(assessment)).invoke({"context": ctx})["result"]


class CaseBriefBoundaries(unittest.TestCase):
    def test_legacy_assessment_loads_without_brief_and_no_summary_is_invented(self):
        result = build_matcher(ScriptedDriver(scripted_assessment())).invoke({"context": test_context()})["result"]
        self.assertIsNone(result.assessment.case_brief)
        self.assertIsNone(to_case_brief(result, assessment_ref="stored-assessment"))

    def test_zero_tool_budget_preserves_useful_research_posture_without_execution_or_qualification(self):
        ctx = test_context().model_copy(update={"capabilities": [], "resources": Resources(remaining_calls=0, remaining_output_tokens=6000)})
        result = match(ctx, brief())
        self.assertEqual(result.outcome, "assessment")
        self.assertEqual(result.disposition, "monitor")
        self.assertIsNone(result.investigation)
        view = to_case_brief(result, assessment_ref="stored-assessment")
        self.assertEqual(view.brief.research_posture, "pursue")
        self.assertEqual(view.input_ref, ctx.ref)
        self.assertEqual(view.assessment_ref, "stored-assessment")
        self.assertEqual(CaseBriefProjection.model_validate_json(view.model_dump_json()), view)

    def test_monitor_requires_substantive_future_trigger_and_facts_are_bounded(self):
        for trigger in [None, "", " "]:
            with self.assertRaises(ValueError):
                brief(research_posture="monitor", future_trigger=trigger)
        with self.assertRaises(ValueError):
            brief(strongest_facts=[SourcedBriefClaim(text="Claim", evidence_ids=["e-company"])] * 3)
        with self.assertRaises(ValueError):
            SourcedBriefClaim(text="Unsupported positive", evidence_ids=[])

    def test_brief_references_cannot_invent_evidence_or_people(self):
        self.assertEqual(match(test_context(), brief(main_reason=BriefClaim(text="Claim", evidence_ids=["invented"]))).outcome, "invalid_output")
        signal = FounderSignal(person_id="invented", contribution="Built it", relevance="Relevant work", evidence_ids=["e-role"], source_strength="first_party_claim")
        self.assertEqual(match(test_context(), brief(founder_signals=[signal])).outcome, "invalid_output")

    def test_founder_title_alone_cannot_be_a_positive_work_signal(self):
        signal = FounderSignal(person_id="test-person", contribution="Founder title", relevance="Unestablished", evidence_ids=["e-role"], source_strength="first_party_claim")
        self.assertEqual(match(test_context(), brief(founder_signals=[signal])).outcome, "invalid_output")

    def test_supported_person_work_and_relationship_can_be_a_qualified_signal(self):
        ctx = with_founder_evidence(test_context(), scripted_assessment()).model_copy(update={"prior_assessment": None, "mode": "initial_assessment"})
        signal = FounderSignal(person_id="test-person", contribution="Led synthetic clinic workflow deployments.", relevance="Relevant to deploying this referral tool.", evidence_ids=["e-role", "e-person"], source_strength="first_party_claim")
        result = match(ctx, brief(founder_signals=[signal]))
        self.assertEqual(result.outcome, "assessment")
        self.assertEqual(result.assessment.case_brief.founder_signals[0].person_id, "test-person")
        bad_ctx = ctx.model_copy(update={"relationships": [ctx.relationships[0].model_copy(update={"status": "unknown"})]})
        from agents.models import seal_context
        self.assertEqual(match(seal_context(bad_ctx), brief(founder_signals=[signal])).outcome, "invalid_output")

    def test_stale_positive_fact_does_not_become_brief_evidence(self):
        from agents.models import seal_context
        ctx = test_context()
        ctx = seal_context(ctx.model_copy(update={"evidence": [e.model_copy(update={"freshness": "stale"}) if e.id == "e-prototype" else e for e in ctx.evidence]}))
        self.assertEqual(match(ctx, brief()).outcome, "invalid_output")

    def test_all_four_batch_queries_compile_with_explicit_test_scope_and_no_filters(self):
        plan = json.loads((Path(__file__).parents[2] / "planning/agents/nine-case-discovery-plan.json").read_text(encoding="utf-8"))
        self.assertEqual({b["track"] for b in plan["branches"]}, {"H", "R", "D", "T"})
        self.assertEqual(sum(b["limit"] for b in plan["branches"]), 32)
        policy = reviewed_reference_policy()
        catalog = CompanySearchCatalog(action="company_search", catalog_version="official-docs-2026-10-24", filters=[],
                                       projection_fields=plan["fields"], required_projection_fields=plan["fields"][:2], max_limit=8, ranked_modes=["hybrid"])
        for item in plan["branches"]:
            branch = DiscoveryBranch(id=item["id"], action="company_search", criterion_ids=item["criterion_ids"], hypothesis=item["rationale"],
                                     semantic_checks=item["artifact_hints"], recall_limitations=item["recall_risks"], approved=True, max_calls=1)
            approval = ScopedDiscoveryApproval(approval_ref="synthetic-software-test-not-real-approval", approved=True,
                                               mandate_id=policy.mandate_id, thesis_version=policy.thesis_version, policy_version=policy.policy_version,
                                               reference_document_hash=policy.reference_document_hash, branch_id=branch.id, criterion_ids=branch.criterion_ids,
                                               query=item["query"], mode=plan["mode"], max_results=8)
            result = compile_ranked_company_search(policy=policy, branch=branch, catalog=catalog, search=RankedSearch(query=item["query"], mode=plan["mode"]),
                                                   approval=approval, fields=plan["fields"], limit=item["limit"])
            self.assertEqual(result.provider_body(), {"search": {"query": item["query"], "mode": "hybrid"}, "fields": plan["fields"], "limit": 8})
            self.assertFalse(result.qualification_policy_approved)

    def test_graph_posture_uses_saved_brief_even_with_zero_budget_and_rejects_contradictory_override(self):
        ctx = test_context().model_copy(update={"capabilities": [], "resources": Resources(remaining_calls=0, remaining_output_tokens=6000)})
        result = match(ctx, brief())
        decision = decision_from_matcher(result, assessment_ref="stored-assessment", decision_consequence="Attributable execution could resolve the team gap.")
        self.assertEqual(decision.decision, "pursue")
        self.assertEqual(decision.next_action, result.assessment.case_brief.next_action)
        output = build_research_graph(ctx, generated_at="2026-10-24T08:00:00Z", matcher_result=result, assessment_ref="stored-assessment", decision=decision)
        self.assertEqual(output.research_decision.decision, result.assessment.case_brief.research_posture)
        with self.assertRaises(ValueError):
            decision_from_matcher(result, assessment_ref="stored-assessment", action_timing="future", decision_consequence="Budget zero", future_trigger="Get more calls")
        with self.assertRaises(ValueError):
            build_research_graph(ctx, generated_at="2026-10-24T08:00:00Z", matcher_result=result, assessment_ref="stored-assessment",
                                 decision=decision.model_copy(update={"decision": "monitor", "future_trigger": "Get more calls"}))

    def test_graph_monitor_uses_saved_trigger_and_preserves_legacy_explicit_timing(self):
        view = brief(research_posture="monitor", future_trigger="An attributable deployment record is published.", next_action="Wait for an attributable deployment record.")
        result = match(test_context(), view)
        decision = decision_from_matcher(result, assessment_ref="stored-assessment", decision_consequence="New deployment evidence could change the execution finding.")
        self.assertEqual(decision.decision, "monitor")
        self.assertEqual(decision.future_trigger, view.future_trigger)
        self.assertEqual(decision.next_action, view.next_action)
        legacy = result.model_copy(update={"assessment": result.assessment.model_copy(update={"case_brief": None})})
        with self.assertRaises(ValueError):
            decision_from_matcher(legacy, assessment_ref="legacy", decision_consequence="Unknown timing")
        self.assertEqual(decision_from_matcher(legacy, assessment_ref="legacy", action_timing="now", decision_consequence="Explicit legacy research action").decision, "pursue")


if __name__ == "__main__":
    unittest.main()
