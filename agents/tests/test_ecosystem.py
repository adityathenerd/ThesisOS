import unittest

from agents.examples import test_context
from agents.models import Observation, seal_context
from agents.research_graph import (EcosystemAssertionSpec, EntitySpec, ProviderResponseGroup, ResearchGraph, TemporalScope,
    TopicInterestSpec, build_research_graph)


def packet():
    ctx=test_context()
    observations=[Observation(id=f"post{i}",subject_kind="company",subject_id=ctx.company_id,claim="synthetic_sourced_post",
        summary=f"Synthetic test source reports founder and peer coauthoring work{i} on a microscopy topic; no real-world claim.",
        source_key=f"synthetic-post-{i}",source_url=f"https://synthetic.example/post{i}",observed_at=f"2026-10-{day}T00:00:00Z",retrieved_at="2026-10-24T09:00:00Z",data_mode="synthetic",freshness="current")
        for i,day in [(1,"01"),(2,"15")]]
    return seal_context(ctx.model_copy(update={"evidence":ctx.evidence+observations}))


def scope(day):return TemporalScope(precision="day",value=f"2026-10-{day}",basis="event")


def specs():
    entities=[EntitySpec(id="peer",kind="person",label="Synthetic peer",evidence_ids=["post1"]),
        EntitySpec(id="paper1",kind="post",label="Synthetic dated paper1",evidence_ids=["post1"],temporal_scope=scope("01")),
        EntitySpec(id="paper2",kind="post",label="Synthetic dated paper2",evidence_ids=["post2"],temporal_scope=scope("15")),
        EntitySpec(id="topic",kind="topic",label="Microscopy",evidence_ids=["post1"]),
        EntitySpec(id="event",kind="event",label="Synthetic public session",evidence_ids=["post1"],temporal_scope=scope("01")),
        EntitySpec(id="award",kind="award",label="Synthetic reported award",evidence_ids=["post1"]),
        EntitySpec(id="institute",kind="organisation",label="Synthetic affiliation",evidence_ids=["post1"])]
    def edge(id,origin,target,relation,evidence="post1",**extra):
        return EcosystemAssertionSpec(id=id,from_id=origin,to_id=target,relation=relation,label=relation,evidence_ids=[evidence],support_status="supported",limitation="Synthetic source; not friendship or founder quality",**extra)
    edges=[edge("author","test-person","paper1","authored",temporal_scope=scope("01")),
        edge("content","paper1","topic","posted_about"),edge("mention","paper1","peer","mentions"),
        edge("co1","test-person","peer","coauthored_with",event_ref="paper1",temporal_scope=scope("01")),
        edge("co2","test-person","peer","coauthored_with",evidence="post2",event_ref="paper2",temporal_scope=scope("15")),
        edge("react","peer","paper1","reacted_to",temporal_scope=scope("01")),
        edge("participation","test-person","event","participated_in"),edge("award-edge","test-person","award","received_award",event_ref="event"),
        edge("affiliation","test-person","institute","affiliated_with")]
    return entities,edges


def graph(**changes):
    entities,assertions=specs()
    return build_research_graph(packet(),generated_at="2026-10-24T09:00:00Z",entities=changes.pop("entities",entities),assertions=changes.pop("assertions",assertions),include_ecosystem_coverage=True,**changes)


class EcosystemTests(unittest.TestCase):
    def test_typed_entities_engagement_and_observed_coverage_not_density_score(self):
        g=graph();self.assertEqual(ResearchGraph.model_validate_json(g.model_dump_json()),g)
        self.assertTrue({"post","topic","award","event"}<={n.kind for n in g.nodes})
        self.assertIsNone(g.ecosystem_coverage.full_network_density)
        self.assertEqual(len(g.ecosystem_coverage.repeated_dated_ties),1)
        self.assertEqual(g.ecosystem_coverage.repeated_dated_ties[0].event_refs,["paper1","paper2"])
        self.assertFalse(any("friend" in e.relation for e in g.edges))

    def test_one_event_multiple_notes_or_overlapping_date_precision_is_not_repeat(self):
        entities,edges=specs()
        for changes in [{"event_ref":"paper1"},{"temporal_scope":TemporalScope(precision="year",value="2026",basis="event")}]:
            altered=[e.model_copy(update=changes) if e.id=="co2" else e for e in edges]
            self.assertEqual(graph(assertions=altered).ecosystem_coverage.repeated_dated_ties,[])

    def test_wrong_typed_endpoint_or_orphan_event_fails(self):
        entities,edges=specs()
        for changes in [{"to_id":"institute","relation":"reacted_to"},{"event_ref":"missing"}]:
            with self.assertRaises(ValueError):graph(assertions=[edges[0].model_copy(update=changes),*edges[1:]])

    def test_explicit_cited_dated_topic_is_interpretation_not_personality(self):
        interest=TopicInterestSpec(id="topic-interpretation",person_id="test-person",topic_id="topic",supporting_edge_ids=["author","content"],evidence_ids=["post1"],
            temporal_scope=TemporalScope(precision="interval",start="2026-10-01",end="2026-10-31",basis="observation"),explanation="One sourced authorship on this topic during the bounded window, not a stable trait.")
        g=graph(topic_interests=[interest]);e=next(e for e in g.edges if e.relation=="interest_in")
        self.assertEqual(e.assertion_kind,"inferred");self.assertEqual(e.interpretation_ref,interest.id)
        self.assertEqual(len(g.ecosystem_interpretations),1)

    def test_retrieval_date_or_outside_window_cannot_create_interest(self):
        interest=TopicInterestSpec(id="interest",person_id="test-person",topic_id="topic",supporting_edge_ids=["author","content"],evidence_ids=["post1"],
            temporal_scope=TemporalScope(precision="interval",start="2026-10-10",end="2026-10-31",basis="observation"),explanation="Unsupported window")
        with self.assertRaises(ValueError):graph(topic_interests=[interest])
        entities,edges=specs();edges=[e.model_copy(update={"temporal_scope":TemporalScope(precision="day",value="2026-10-24",basis="retrieval")}) if e.id=="author" else e for e in edges]
        with self.assertRaises(ValueError):graph(assertions=edges,topic_interests=[interest])

    def test_single_provider_response_groups_claims_but_distinct_retrievals_fail(self):
        ctx=test_context();group=ProviderResponseGroup(response_ref="synthetic-test-response",evidence_ids=["e-company","e-prototype"])
        g=build_research_graph(ctx,generated_at="2026-10-24T09:00:00Z",provider_response_groups=[group])
        self.assertEqual(len(g.sources),2)
        self.assertTrue(any(set(s.evidence_ids)=={"e-company","e-prototype"} for s in g.sources))
        different=seal_context(ctx.model_copy(update={"evidence":[e.model_copy(update={"retrieved_at":"2026-10-23T09:00:00Z"}) if e.id=="e-prototype" else e for e in ctx.evidence]}))
        with self.assertRaises(ValueError):build_research_graph(different,generated_at="2026-10-24T09:00:00Z",provider_response_groups=[group])

    def test_fake_coverage_rejected_and_old_graph_shape_still_valid(self):
        g=graph();data=g.model_dump();data['ecosystem_coverage']['unique_entities']=999
        with self.assertRaises(ValueError):ResearchGraph.model_validate(data)
        legacy=build_research_graph(test_context(),generated_at="2026-10-24T09:00:00Z").model_dump()
        legacy.pop('ecosystem_interpretations');legacy.pop('ecosystem_coverage')
        for edge in legacy['edges']:edge.pop('event_ref',None)
        self.assertIsNone(ResearchGraph.model_validate(legacy).ecosystem_coverage)

    def test_extra_unsourced_person_or_invented_friend_relation_is_not_typed_spec(self):
        with self.assertRaises(ValueError):EcosystemAssertionSpec(id="fake",from_id="a",to_id="b",relation="friend_of",label="Invented friendship",evidence_ids=["post1"],limitation="Not supported")
        entities,edges=specs()
        with self.assertRaises(ValueError):graph(entities=[*entities,EntitySpec(id="invented",kind="person",label="Unattributed",evidence_ids=[])])

    def test_corporate_authorship_does_not_create_person_interest_from_a_mention(self):
        entities,edges=specs()
        edges=[e.model_copy(update={"from_id":"institute"}) if e.id=="author" else e for e in edges]
        g=graph(assertions=edges)
        self.assertEqual(next(e for e in g.edges if e.id=="author").from_id,"institute")
        interest=TopicInterestSpec(id="interest",person_id="test-person",topic_id="topic",supporting_edge_ids=["author","content"],evidence_ids=["post1"],
            temporal_scope=TemporalScope(precision="interval",start="2026-10-01",end="2026-10-31",basis="observation"),explanation="Cannot infer a person's interests from corporate authorship")
        with self.assertRaises(ValueError):graph(assertions=edges,topic_interests=[interest])

    def test_joint_publication_dates_can_describe_repeated_coauthorship_not_meeting(self):
        entities,edges=specs()
        edges=[e.model_copy(update={"temporal_scope":e.temporal_scope.model_copy(update={"basis":"publication"})}) if e.id in {"co1","co2"} else e for e in edges]
        tie=graph(assertions=edges).ecosystem_coverage.repeated_dated_ties[0]
        self.assertEqual(tie.relation,"coauthored_with")
        self.assertEqual(tie.dates,["2026-10-01","2026-10-15"])


if __name__=="__main__":unittest.main()
