import unittest
from unittest.mock import patch

from agents.drivers import ScriptedDriver
from agents.examples import scripted_assessment, test_context
from agents.graphs import build_matcher
from agents.models import Observation, Person, Relationship, seal_context
from agents.research_graph import (
    AssertionSpec, EntitySpec, ObservationGraphMetadata, ResearchGraph, ResearchQuestion,
    TemporalScope, build_research_graph, decision_from_matcher, to_mermaid,
)
from agents.research_graph_example import allodirect_graph

GENERATED = "2026-10-24T07:00:00Z"


def graph(context=None, **kwargs):
    return build_research_graph(context or test_context(), generated_at=GENERATED, **kwargs)


class GraphIntegrity(unittest.TestCase):
    def test_reuses_ids_and_roundtrips_exact_schema(self):
        ctx = test_context()
        output = graph(ctx)
        self.assertEqual(output.case_id, ctx.ref.case_id)
        self.assertIsNone(output.research_example_ref)
        self.assertIn(ctx.company_id, {n.id for n in output.nodes})
        self.assertIn(ctx.people[0].id, {n.id for n in output.nodes})
        self.assertEqual({eid for source in output.sources for eid in source.evidence_ids}, {e.id for e in ctx.evidence})
        self.assertEqual(ResearchGraph.model_validate_json(output.model_dump_json()), output)
        self.assertIn("ResearchDecision", ResearchGraph.model_json_schema()["$defs"])

    def test_orphan_endpoint_dangling_source_and_duplicate_node_rejected(self):
        output = graph()
        payload = output.model_dump()
        payload["edges"][0]["to_id"] = "absent"
        with self.assertRaises(ValueError):
            ResearchGraph.model_validate(payload)
        payload = output.model_dump()
        payload["nodes"][0]["source_refs"] = ["absent-source"]
        with self.assertRaises(ValueError):
            ResearchGraph.model_validate(payload)
        payload = output.model_dump()
        payload["nodes"].append(payload["nodes"][0])
        with self.assertRaises(ValueError):
            ResearchGraph.model_validate(payload)

    def test_unknown_evidence_and_missing_provenance_rejected(self):
        with self.assertRaises(ValueError):
            graph(observation_metadata=[ObservationGraphMetadata(evidence_id="fabricated")])
        with self.assertRaises(ValueError):
            graph(entities=[EntitySpec(id="new-product", kind="product", label="Unsupported product", evidence_ids=[])])
        ctx = test_context()
        ctx = seal_context(ctx.model_copy(update={"evidence": [ctx.evidence[0].model_copy(update={"source_key": None, "source_url": None}), *ctx.evidence[1:]]}))
        with self.assertRaises(ValueError):
            graph(ctx)

    def test_stale_snapshot_and_unsafe_urls_rejected(self):
        ctx = test_context()
        with self.assertRaises(ValueError):
            graph(ctx.model_copy(update={"company_name": "Different label", "ref": ctx.ref.model_copy(update={"evidence_hash": "wrong"})}))
        bad = ctx.evidence[0].model_copy(update={"source_url": "javascript:alert(1)"})
        with self.assertRaises(ValueError):
            graph(seal_context(ctx.model_copy(update={"evidence": [bad, *ctx.evidence[1:]]})))

    def test_stable_content_id_and_new_snapshot_version_without_mutation(self):
        ctx = test_context()
        first = graph(ctx)
        second = build_research_graph(ctx, generated_at="2026-10-24T08:00:00Z")
        self.assertEqual(first.graph_id, second.graph_id)
        revised = seal_context(ctx.model_copy(update={"evidence": [ctx.evidence[0].model_copy(update={"summary": "New attributable observation"}), *ctx.evidence[1:]]}))
        self.assertNotEqual(first.graph_id, graph(revised).graph_id)
        self.assertEqual(first.snapshot_ref, ctx.ref)

    def test_captured_example_is_separate_and_has_product_event_and_gaps(self):
        with patch("agents.drivers.OpenAIResponsesDriver.from_project", side_effect=AssertionError("No model call permitted")):
            output = allodirect_graph(generated_at=GENERATED, include_existing_matcher=False)
        self.assertIsNone(output.case_id)
        self.assertIn("comparison-examples.md", output.research_example_ref)
        self.assertEqual(len(output.sources), 1)
        self.assertEqual(len(output.sources[0].evidence_ids), 5)
        self.assertEqual(output.sources[0].data_mode, "captured")
        self.assertEqual(len(output.open_questions), 5)
        self.assertEqual({"person", "organisation", "product", "event", "source", "claim"} - {n.kind for n in output.nodes}, set())
        self.assertFalse(output.matcher_interpretations)
        self.assertTrue(all(e.assertion_kind == "source_reported" for e in output.edges))

    def test_unknown_roles_and_absent_team_are_questions(self):
        ctx = test_context()
        unresolved = ctx.relationships[0].model_copy(update={"status": "unknown"})
        output = graph(seal_context(ctx.model_copy(update={"relationships": [unresolved]})))
        self.assertFalse(any(e.relation == "held_role_at" for e in output.edges))
        self.assertTrue(any("relationship" in q.id for q in output.open_questions))
        minimal = seal_context(ctx.model_copy(update={"people": [], "relationships": [], "evidence": ctx.evidence[:2]}))
        self.assertTrue(any(q.id == "question:missing-team" for q in graph(minimal).open_questions))

    def test_shared_employer_and_raw_narrative_never_create_collaboration_or_dates(self):
        ctx = test_context()
        obs = ctx.evidence[0].model_copy(update={"id": "background", "subject_kind": "person", "subject_id": "test-person",
            "summary": "Worked at the same employer as Person Two; may have met in 2019 and perhaps collaborated."})
        other = Person(id="second-person", name="Person Two")
        ctx = seal_context(ctx.model_copy(update={"people": [*ctx.people, other], "relationships": [], "evidence": [*ctx.evidence[:2], obs]}))
        output = graph(ctx)
        self.assertFalse(any(e.relation in {"cofounder", "collaborated_on", "met", "founded"} for e in output.edges))
        self.assertFalse(any(n.kind == "event" for n in output.nodes))
        self.assertTrue(any(q.id == "question:attribution:second-person" for q in output.open_questions))


class ProvenanceAndTime(unittest.TestCase):
    def test_date_precision_and_no_role_start_invention(self):
        output = allodirect_graph(generated_at=GENERATED, include_existing_matcher=False)
        event = next(n for n in output.nodes if n.kind == "event")
        self.assertEqual(event.temporal_scope.precision, "day")
        self.assertEqual(event.temporal_scope.value, "2026-09-25")
        self.assertEqual(output.sources[0].retrieval_times[0].value, "2026-10-24")
        for edge in output.edges:
            if edge.relation == "held_role_at":
                self.assertEqual(edge.temporal_scope.precision, "unknown")
                self.assertIsNone(edge.temporal_scope.start)
        self.assertEqual(TemporalScope(precision="month", value="2025-09", basis="event").value, "2025-09")
        self.assertEqual(TemporalScope(precision="year", value="2025").precision, "year")
        self.assertEqual(TemporalScope(precision="interval", start="2025-09", end=None).start, "2025-09")
        for values in [{"precision": "unknown", "value": "2025"}, {"precision": "day", "value": "2025-02-30"},
                       {"precision": "month", "value": "2025-09-01"}, {"precision": "interval", "start": "2026-01", "end": "2025-01"}]:
            with self.assertRaises(ValueError):
                TemporalScope(**values)

    def test_live_mode_does_not_promote_source_report_to_observation(self):
        ctx = test_context()
        ctx = seal_context(ctx.model_copy(update={"evidence": [e.model_copy(update={"data_mode": "live"}) for e in ctx.evidence]}))
        output = graph(ctx)
        self.assertTrue(all(s.data_mode == "live" for s in output.sources))
        self.assertTrue(all(e.assertion_kind == "source_reported" for e in output.edges))
        bad = AssertionSpec(id="promoted", from_id=ctx.company_id, to_id=ctx.people[0].id, relation="knows",
            label="Unwarranted observation", evidence_ids=[ctx.evidence[0].id], assertion_kind="observed", support_status="supported", limitation="No actual observation")
        with self.assertRaises(ValueError):
            graph(ctx, assertions=[bad])

    def test_incompatible_provenance_cannot_merge_into_one_source(self):
        ctx = test_context()
        ctx = seal_context(ctx.model_copy(update={"evidence": [ctx.evidence[0].model_copy(update={"data_mode": "live"}), *ctx.evidence[1:]]}))
        with self.assertRaises(ValueError):
            graph(ctx, observation_metadata=[ObservationGraphMetadata(evidence_id=e.id, original_source_id="same-origin") for e in ctx.evidence])

    def test_contradictory_role_observations_are_retained(self):
        ctx = test_context()
        contrary = ctx.evidence[-1].model_copy(update={"id": "contrary-role", "subject_id": "contrary-relation", "summary": "A source disputes this role attribution"})
        rel = ctx.relationships[0].model_copy(update={"id": "contrary-relation", "status": "contradicted", "evidence_ids": ["contrary-role"]})
        ctx = seal_context(ctx.model_copy(update={"evidence": [*ctx.evidence, contrary], "relationships": [*ctx.relationships, rel]}))
        roles = [e for e in graph(ctx).edges if e.relation == "held_role_at"]
        self.assertEqual({r.support_status for r in roles}, {"supported", "contradicted"})
        self.assertEqual(len(roles), 2)


class InterpretationAndDecision(unittest.TestCase):
    def setUp(self):
        self.ctx = test_context()
        self.result = build_matcher(ScriptedDriver(scripted_assessment())).invoke({"context": self.ctx})["result"]

    def test_matcher_interpretations_create_no_evidence_and_cannot_be_reused_as_sources(self):
        output = graph(self.ctx, matcher_result=self.result, assessment_ref="saved-assessment-1")
        self.assertEqual(len(output.matcher_interpretations), 4)
        self.assertEqual(output.matcher_summary.why_this.summary, self.result.assessment.why_this.summary)
        self.assertEqual(output.matcher_summary.why_now.unknowns, self.result.assessment.why_now.unknowns)
        self.assertEqual(output.matcher_summary.authority, "model_interpretation_not_new_evidence")
        self.assertEqual({eid for s in output.sources for eid in s.evidence_ids}, {e.id for e in self.ctx.evidence})
        self.assertTrue(all(i.authority == "model_interpretation_not_new_evidence" for i in output.matcher_interpretations))
        bad = AssertionSpec(id="bad-inference", from_id=self.ctx.company_id, to_id=self.ctx.people[0].id, relation="collaborated_on",
            label="Unsupported inference", evidence_ids=["interpretation:team"], assertion_kind="inferred", support_status="supported",
            interpretation_ref="interpretation:team", limitation="A model narrative is not evidence")
        with self.assertRaises(ValueError):
            graph(self.ctx, matcher_result=self.result, assessment_ref="saved-assessment-1", assertions=[bad])
        with self.assertRaises(ValueError):
            graph(self.ctx, matcher_result=self.result.model_copy(update={"ref": self.result.ref.model_copy(update={"case_version": 99})}), assessment_ref="old")

    def test_research_pursue_and_monitor_do_not_change_qualification(self):
        decision = decision_from_matcher(self.result, assessment_ref="saved-assessment-1", action_timing="now",
            decision_consequence="Resolve the existing required founder-execution gap")
        output = graph(self.ctx, matcher_result=self.result, assessment_ref="saved-assessment-1", decision=decision)
        self.assertEqual(output.research_decision.decision, "pursue")
        self.assertEqual(self.result.disposition, "monitor")
        self.assertIn("human qualification approval remains separate", output.research_decision.qualification_note)
        with self.assertRaises(ValueError):
            decision_from_matcher(self.result, assessment_ref="saved-assessment-1", action_timing="future", decision_consequence="Wait")
        monitor = decision_from_matcher(self.result, assessment_ref="saved-assessment-1", action_timing="future",
            decision_consequence="Could resolve attribution", future_trigger="An attributable founder work record becomes available")
        self.assertEqual(monitor.decision, "monitor")

    def test_unknown_question_target_and_inferred_edge_without_interpretation_rejected(self):
        with self.assertRaises(ValueError):
            graph(questions=[ResearchQuestion(id="unknown-target", target_node_ids=["missing"], question="What?", decision_consequence="Would change fit")])
        spec = AssertionSpec(id="missing-interpretation", from_id=self.ctx.company_id, to_id=self.ctx.people[0].id, relation="relevant_to",
            label="Model interpretation", evidence_ids=["e-company"], assertion_kind="inferred", support_status="unknown", limitation="Not fact")
        with self.assertRaises(ValueError):
            graph(self.ctx, assertions=[spec])

    def test_open_questions_cannot_invent_policy_criteria(self):
        with self.assertRaises(ValueError):
            graph(questions=[ResearchQuestion(id="invented-gate", target_node_ids=[self.ctx.company_id],
                criterion_ids=["grit-cutoff"], question="Meet this invented threshold?", decision_consequence="Unapproved policy")])

    def test_mermaid_has_actual_network_and_escaped_labels(self):
        ctx = self.ctx.model_copy(update={"company_name": 'Company "quoted" <script>| label'})
        source = to_mermaid(graph(ctx))
        self.assertIn("flowchart LR", source)
        self.assertIn("-->", source)
        self.assertIn("&quot;", source)
        self.assertNotIn("<script>", source)


if __name__ == "__main__":
    unittest.main()
