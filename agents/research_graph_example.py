"""Export a clearly labeled captured AlloDirect example, without external calls."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from .models import MatcherResult
from .reference import allodirect_reference_context
from .research_graph import (
    AssertionSpec, EntitySpec, ObservationGraphMetadata, ResearchGraph,
    ResearchQuestion, TemporalScope, build_research_graph, decision_from_matcher, to_mermaid,
)


def allodirect_graph(*, generated_at=None, include_existing_matcher=True):
    context = allodirect_reference_context()
    publication = TemporalScope(precision="day", value="2026-09-25", basis="publication")
    retrieval = TemporalScope(precision="day", value="2026-10-24", basis="retrieval",
        limitation="Research handoff records an access date, not an exact clock time.")
    metadata = [ObservationGraphMetadata(evidence_id=e.id, original_source_id="source:allodirect-release-S10",
        assertion_kind="source_reported", support_status="supported", source_type="captured_research_note_about_first_party_release",
        source_quality="company_controlled_claim_not_independent_validation", publication_time=publication,
        observation_time=TemporalScope(), retrieval_time=retrieval,
        limitations=["Five preserved observations derive from one underlying company release; they are not independent corroboration.",
                    "Research notes were captured; the underlying application, customer outcomes and founder contribution were not inspected."])
        for e in context.evidence]
    product_id, event_id = "product:allodirect-tissue-ordering", "event:allodirect-financing-announcement-2026-09-25"
    entities = [EntitySpec(id=product_id, kind="product", label="Tissue-ordering software (reported)", evidence_ids=["ad-product"],
        attributes={"track": "H", "artifact_inspected": False, "product_gate": "partly_evidenced_not_cleared"}),
        EntitySpec(id=event_id, kind="event", label="Pre-seed announcement · 25 Sep 2026", evidence_ids=["ad-funding"],
            temporal_scope=TemporalScope(precision="day", value="2026-09-25", basis="event",
                limitation="Announcement publication date, not founding date or independently verified financing close."),
            attributes={"event_type": "financing_announcement", "assertion_kind": "source_reported"})]
    assertions = [AssertionSpec(id="edge:allodirect-offers-product", from_id=context.company_id, to_id=product_id,
        relation="offers", label="Reports offering tissue-ordering software", evidence_ids=["ad-product"], support_status="supported",
        limitation="Source reports a product/use claim; no working application or outcome was inspected."),
        AssertionSpec(id="edge:allodirect-announced-funding", from_id=context.company_id, to_id=event_id,
            relation="announced", label="Published a pre-seed financing announcement", evidence_ids=["ad-funding"], support_status="supported",
            temporal_scope=publication, limitation="Announcement is not independent confirmation of financing terms, a current round or investment availability.")]
    questions = [ResearchQuestion(id="question:founder-attribution", target_node_ids=[context.company_id, *[p.id for p in context.people], product_id], criterion_ids=["C2", "C4"],
        question="Which of the named operators are founders, and which specific product work did each own?",
        decision_consequence="Could establish attributable team–problem fit; titles and background alone do not resolve it."),
        ResearchQuestion(id="question:collaboration-and-setbacks", target_node_ids=[p.id for p in context.people], criterion_ids=["C2"],
            question="What sourced work history shows sustained building, collaboration, setbacks and responses? When and how did the team actually work together?",
            decision_consequence="Could contextualize learning and collaboration; missing history is unknown, not a grit/loyalty penalty, and a pivot may show learning."),
        ResearchQuestion(id="question:working-artifact", target_node_ids=[product_id], criterion_ids=["C4", "C5"],
            question="Can an attributable workflow demonstration or deployment record establish the reported functionality and its limits?",
            decision_consequence="Could resolve track-H product evidence; a release, financing event or graph density does not clear the review gate."),
        ResearchQuestion(id="question:role-chronology", target_node_ids=[context.company_id, *[p.id for p in context.people]],
            question="What establishes founding dates, role tenure and current roles?",
            decision_consequence="Would improve chronology/contact attribution; no meeting, founding or employment start dates are inferred from publication or retrieval."),
        ResearchQuestion(id="question:yc-status", target_node_ids=[context.company_id],
            question="What establishes YC backing and novelty against the declared known-company universe?",
            decision_consequence="Known backing would remove a novel-sourcing count without constituting a negative investment judgment; current status is unknown.")]
    result, assessment_ref = None, None
    capture = Path(__file__).parent / "work" / "live-smoke.json"
    if include_existing_matcher and capture.is_file():
        import json
        report = json.loads(capture.read_text(encoding="utf-8-sig"))
        stored = report.get("matcher", {}).get("result")
        if stored and stored.get("assessment"):
            result = MatcherResult.model_validate(stored)
            assessment_ref = "agents/work/live-smoke.json#/matcher/result"
    decision = decision_from_matcher(result, assessment_ref=assessment_ref, action_timing="future",
        decision_consequence="An attributable working-workflow record could resolve the product-evidence gap; it would not establish human approval.",
        future_trigger="Authorized access to a working-workflow demonstration or attributable deployment record becomes available.") if result else None
    return build_research_graph(context, generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        research_example_ref="planning/investment-thesis/comparison-examples.md#allodirect-v0.3",
        observation_metadata=metadata, entities=entities, assertions=assertions, questions=questions,
        matcher_result=result, assessment_ref=assessment_ref, decision=decision, limitations=[
        "This is a captured research example, separate from stored live-provider case state.",
        "Any matcher references are preserved historical prompt-v0.1 comparisons, not new evidence or current human approval."
        if result else "No saved matcher capture was supplied; there is no synthetic interpretation fallback."])


def export_graph(graph: ResearchGraph, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "allodirect-research-graph.json").write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "allodirect-research-graph.mmd").write_text(to_mermaid(graph), encoding="utf-8")
    import json
    (output_dir / "research-graph.schema.json").write_text(json.dumps(ResearchGraph.model_json_schema(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "artifacts")
    parser.add_argument("--without-matcher", action="store_true")
    args = parser.parse_args()
    graph = allodirect_graph(include_existing_matcher=not args.without_matcher)
    export_graph(graph, args.output_dir)
    print({"graph_id": graph.graph_id, "research_example_ref": graph.research_example_ref, "case_id": graph.case_id,
           "nodes": len(graph.nodes), "edges": len(graph.edges), "sources": len(graph.sources),
           "open_questions": len(graph.open_questions), "matcher_interpretations": len(graph.matcher_interpretations), "external_calls": 0})
