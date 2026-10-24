"""Pure sourced research projection. No graph DB, model call or business mutation."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from .models import CaseContext, MatcherResult, Model, VersionRef, evidence_hash

AssertionKind = Literal["source_reported", "observed", "inferred"]
SupportStatus = Literal["supported", "mixed", "contradicted", "unknown"]
EntityKind = Literal["person", "organisation", "product", "asset", "project", "event", "post", "topic", "award", "claim", "source"]
EcosystemRelation = Literal["authored", "coauthored", "coauthored_with", "affiliated_with", "participated_in", "received_award", "award_at",
                            "posted_about", "mentions", "reacted_to", "commented_on", "collaborated_on", "collaborated_with", "interest_in"]
ECOSYSTEM_ENDPOINTS = {
    "authored": ({"person", "organisation"}, {"post", "project", "asset"}), "coauthored": ({"person", "organisation"}, {"post", "project", "asset"}),
    "coauthored_with": ({"person"}, {"person"}), "affiliated_with": ({"person"}, {"organisation"}),
    "participated_in": ({"person", "organisation"}, {"event"}), "received_award": ({"person", "organisation"}, {"award"}),
    "award_at": ({"award"}, {"event"}), "posted_about": ({"post", "project"}, {"topic"}),
    "mentions": ({"post"}, {"person", "organisation", "product", "asset", "project", "event", "topic", "award"}),
    "reacted_to": ({"person"}, {"post"}), "commented_on": ({"person"}, {"post"}),
    "collaborated_on": ({"person"}, {"project", "asset", "event"}), "collaborated_with": ({"person"}, {"person"}),
    "interest_in": ({"person"}, {"topic"}),
}


def _date_precision(value: str) -> str:
    if re.fullmatch(r"\d{4}", value):
        date(int(value), 1, 1)
        return "year"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        date.fromisoformat(value + "-01")
        return "month"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        date.fromisoformat(value)
        return "day"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or "T" not in value:
        raise ValueError("Datetime must retain an explicit timezone")
    return "datetime"


class TemporalScope(Model):
    precision: Literal["unknown", "year", "month", "day", "datetime", "interval"] = "unknown"
    value: str | None = None
    start: str | None = None
    end: str | None = None
    basis: Literal["unknown", "publication", "observation", "retrieval", "event", "reported_as_of"] = "unknown"
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_precision(self):
        if self.precision == "unknown":
            if any(v is not None for v in [self.value, self.start, self.end]):
                raise ValueError("Unknown time cannot contain invented values")
        elif self.precision == "interval":
            if self.value is not None or (self.start is None and self.end is None):
                raise ValueError("Interval needs a bound and no point value")
            for bound in [self.start, self.end]:
                if bound is not None:
                    _date_precision(bound)
            if self.start is not None and self.end is not None and self.start > self.end:
                raise ValueError("Interval bounds are reversed")
        elif self.value is None or self.start is not None or self.end is not None or _date_precision(self.value) != self.precision:
            raise ValueError("Temporal value must match its stated precision")
        return self


class CanonicalEntityRef(Model):
    kind: str
    id: str = Field(min_length=1)


class ResearchSource(Model):
    id: str = Field(min_length=1)
    evidence_ids: list[str]
    source_url: str | None
    source_keys: list[str]
    source_type: str
    source_quality: str
    data_mode: Literal["live", "captured", "synthetic"]
    publication_time: TemporalScope
    observation_times: list[TemporalScope]
    retrieval_times: list[TemporalScope]
    limitations: list[str]

    @model_validator(mode="after")
    def safe_source(self):
        if not self.evidence_ids or not (self.source_url or self.source_keys):
            raise ValueError("Source must retain attributable observation IDs and provenance")
        if self.source_url:
            parsed = urlsplit(self.source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Source URLs must be public-style HTTP(S) references without credentials")
        return self


class ResearchNode(Model):
    id: str = Field(min_length=1)
    kind: EntityKind
    label: str = Field(min_length=1, max_length=240)
    canonical_entity_ref: CanonicalEntityRef | None = None
    source_refs: list[str] = Field(default_factory=list)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)

    @model_validator(mode="after")
    def bounded_attributes(self):
        if len(self.attributes) > 16:
            raise ValueError("Keep attributes bounded; use source records for raw payloads")
        for key, value in self.attributes.items():
            if len(key) > 80 or isinstance(value, str) and len(value) > 2400:
                raise ValueError("Attribute too large")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Non-finite graph attribute")
        return self


class ResearchEdge(Model):
    id: str = Field(min_length=1)
    from_id: str
    to_id: str
    relation: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=300)
    evidence_ids: list[str]
    source_refs: list[str]
    assertion_kind: AssertionKind
    support_status: SupportStatus
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)
    limitation: str = Field(min_length=1, max_length=2400)
    interpretation_ref: str | None = None
    event_ref: str | None = None


class ResearchQuestion(Model):
    id: str
    target_node_ids: list[str]
    target_edge_ids: list[str] = Field(default_factory=list)
    criterion_ids: list[str] = Field(default_factory=list)
    question: str = Field(min_length=1)
    decision_consequence: str = Field(min_length=1)


class MatcherInterpretationRef(Model):
    id: str
    assessment_ref: str
    input_ref: VersionRef
    prompt_version: str
    driver_kind: Literal["scripted", "semantic"]
    criterion_id: str
    target_node_ids: list[str]
    evidence_ids: list[str]
    counterevidence_ids: list[str]
    source_refs: list[str]
    comparison_state: Literal["supported", "mixed", "contradicted", "unknown", "not_applicable"]
    interpretation: str
    authority: Literal["model_interpretation_not_new_evidence"] = "model_interpretation_not_new_evidence"


class ResearchInterpretationAnswer(Model):
    summary: str
    evidence_ids: list[str]
    source_refs: list[str]
    objections: list[str]
    unknowns: list[str]


class MatcherResearchSummary(Model):
    assessment_ref: str
    input_ref: VersionRef
    prompt_version: str
    driver_kind: Literal["scripted", "semantic"]
    why_this: ResearchInterpretationAnswer
    why_them: ResearchInterpretationAnswer
    why_now: ResearchInterpretationAnswer
    team_problem_fit: ResearchInterpretationAnswer
    authority: Literal["model_interpretation_not_new_evidence"] = "model_interpretation_not_new_evidence"


class ResearchDecisionSpec(Model):
    """Explicit next-action classification, not a public case status or approval."""
    assessment_ref: str
    input_ref: VersionRef
    decision: Literal["pursue", "monitor"]
    next_action: str = Field(min_length=1)
    decision_consequence: str = Field(min_length=1)
    future_trigger: str | None = None
    evidence_ids: list[str]

    @model_validator(mode="after")
    def concrete_monitor(self):
        if self.decision == "monitor" and not (self.future_trigger and self.future_trigger.strip()):
            raise ValueError("Monitor needs a concrete future trigger")
        return self


class ResearchDecision(ResearchDecisionSpec):
    source_refs: list[str]
    assertion_kind: Literal["inferred"] = "inferred"
    qualification_note: Literal["Research next-action recommendation only; human qualification approval remains separate"] = "Research next-action recommendation only; human qualification approval remains separate"


class EcosystemInterpretation(Model):
    id: str
    input_ref: VersionRef
    person_id: str
    topic_id: str
    supporting_edge_ids: list[str]
    evidence_ids: list[str]
    source_refs: list[str]
    temporal_scope: TemporalScope
    explanation: str
    authority: Literal["derived_observed_topic_engagement_not_personality_or_friendship"] = "derived_observed_topic_engagement_not_personality_or_friendship"


class RepeatedDatedTie(Model):
    from_id: str
    to_id: str
    relation: str
    event_refs: list[str]
    dates: list[str]
    evidence_ids: list[str]


class EcosystemCoverage(Model):
    unique_entities: int
    entities_by_kind: dict[str, int]
    supported_typed_edges: int
    typed_relationship_types: list[str]
    dated_event_ids: list[str]
    repeated_dated_ties: list[RepeatedDatedTie]
    full_network_density: None = None
    limitations: list[str]


class ResearchGraph(Model):
    schema_version: Literal["0.1"] = "0.1"
    graph_id: str
    case_id: str | None
    research_example_ref: str | None
    snapshot_ref: VersionRef
    generated_at: str
    nodes: list[ResearchNode]
    edges: list[ResearchEdge]
    sources: list[ResearchSource]
    open_questions: list[ResearchQuestion]
    matcher_interpretations: list[MatcherInterpretationRef] = Field(default_factory=list)
    matcher_summary: MatcherResearchSummary | None = None
    research_decision: ResearchDecision | None = None
    limitations: list[str]
    ecosystem_interpretations: list[EcosystemInterpretation] = Field(default_factory=list)
    ecosystem_coverage: EcosystemCoverage | None = None

    @model_validator(mode="after")
    def integrity(self):
        if (self.case_id is None) == (self.research_example_ref is None):
            raise ValueError("Use either a stored case ID or an explicit separate research-example reference")
        if self.case_id is not None and self.case_id != self.snapshot_ref.case_id:
            raise ValueError("Case ID differs from the input snapshot")
        if _date_precision(self.generated_at) != "datetime":
            raise ValueError("generated_at must be a timezone-aware timestamp")
        for group in [self.nodes, self.edges, self.sources, self.open_questions, self.matcher_interpretations, self.ecosystem_interpretations]:
            if len({v.id for v in group}) != len(group):
                raise ValueError("Duplicate IDs in graph projection")
        nodes, edges = {n.id for n in self.nodes}, {e.id for e in self.edges}
        sources = {s.id: s for s in self.sources}
        interpretations = {v.id for v in self.matcher_interpretations} | {v.id for v in self.ecosystem_interpretations}
        if len(interpretations) != len(self.matcher_interpretations) + len(self.ecosystem_interpretations):
            raise ValueError("Interpretation IDs cannot collide across authorities")
        node_map = {n.id: n for n in self.nodes}
        def source_refs(refs, evidence_ids=None):
            if not set(refs) <= sources.keys():
                raise ValueError("Dangling source reference")
            if evidence_ids is not None and not set(evidence_ids) <= {eid for ref in refs for eid in sources[ref].evidence_ids}:
                raise ValueError("Evidence IDs are not backed by the referenced source records")
        for node in self.nodes:
            source_refs(node.source_refs)
        for edge in self.edges:
            if edge.from_id not in nodes or edge.to_id not in nodes:
                raise ValueError("Orphan edge endpoint")
            if edge.event_ref is not None and (edge.event_ref not in nodes or node_map[edge.event_ref].kind not in {"event", "post", "project", "asset"}):
                raise ValueError("Relationship event reference must name an existing event/work artifact")
            if edge.relation in ECOSYSTEM_ENDPOINTS:
                origins, targets = ECOSYSTEM_ENDPOINTS[edge.relation]
                if node_map[edge.from_id].kind not in origins or node_map[edge.to_id].kind not in targets:
                    raise ValueError("Typed ecosystem relationship has incompatible endpoint kinds")
                if edge.relation == "interest_in" and edge.assertion_kind != "inferred":
                    raise ValueError("Interest topic must remain an explicit derived interpretation")
            source_refs(edge.source_refs, edge.evidence_ids)
            if not edge.evidence_ids or not edge.source_refs:
                raise ValueError("Fact/assertion edges need actual supporting or contrary observations")
            if edge.assertion_kind == "inferred" and edge.interpretation_ref not in interpretations:
                raise ValueError("An inferred edge needs an explicit matcher interpretation reference")
            if edge.assertion_kind != "inferred" and edge.interpretation_ref is not None:
                raise ValueError("Model interpretation cannot be relabeled as a source assertion")
        for item in self.ecosystem_interpretations:
            source_refs(item.source_refs, item.evidence_ids)
            if item.input_ref != self.snapshot_ref or item.person_id not in nodes or item.topic_id not in nodes or not set(item.supporting_edge_ids) <= edges:
                raise ValueError("Ecosystem interpretation has stale or dangling references")
        for question in self.open_questions:
            if not set(question.target_node_ids) <= nodes or not set(question.target_edge_ids) <= edges:
                raise ValueError("Open question refers to absent graph targets")
        for item in self.matcher_interpretations:
            if not set(item.target_node_ids) <= nodes:
                raise ValueError("Interpretation refers to an absent entity")
            source_refs(item.source_refs, item.evidence_ids + item.counterevidence_ids)
            if item.input_ref != self.snapshot_ref:
                raise ValueError("Interpretation refers to a different input snapshot")
        if self.matcher_summary:
            if self.matcher_summary.input_ref != self.snapshot_ref:
                raise ValueError("Matcher summary refers to a different input snapshot")
            for key in ["why_this", "why_them", "why_now", "team_problem_fit"]:
                answer = getattr(self.matcher_summary, key)
                source_refs(answer.source_refs, answer.evidence_ids)
        if self.research_decision:
            source_refs(self.research_decision.source_refs, self.research_decision.evidence_ids)
            if self.research_decision.input_ref != self.snapshot_ref:
                raise ValueError("Research decision refers to a different input snapshot")
        if self.ecosystem_coverage is not None and self.ecosystem_coverage != ecosystem_coverage(self):
            raise ValueError("Ecosystem coverage must describe this actual sourced graph")
        return self


class ObservationGraphMetadata(Model):
    evidence_id: str
    original_source_id: str | None = None
    assertion_kind: Literal["source_reported", "observed"] = "source_reported"
    support_status: SupportStatus = "unknown"
    source_type: str = "attributed_observation"
    source_quality: str = "not_independently_verified"
    publication_time: TemporalScope = Field(default_factory=TemporalScope)
    observation_time: TemporalScope | None = None
    retrieval_time: TemporalScope | None = None
    limitations: list[str] = Field(default_factory=list)


class EntitySpec(Model):
    id: str
    kind: Literal["person", "organisation", "product", "asset", "project", "event", "post", "topic", "award"]
    label: str
    evidence_ids: list[str]
    canonical_entity_ref: CanonicalEntityRef | None = None
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)


class AssertionSpec(Model):
    id: str
    from_id: str
    to_id: str
    relation: str
    label: str
    evidence_ids: list[str]
    assertion_kind: AssertionKind = "source_reported"
    support_status: SupportStatus = "unknown"
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)
    limitation: str
    interpretation_ref: str | None = None
    event_ref: str | None = None


class EcosystemAssertionSpec(AssertionSpec):
    relation: EcosystemRelation


class TopicInterestSpec(Model):
    id: str
    person_id: str
    topic_id: str
    supporting_edge_ids: list[str] = Field(min_length=2)
    evidence_ids: list[str] = Field(min_length=1)
    temporal_scope: TemporalScope
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_window(self):
        if self.temporal_scope.precision != "interval" or self.temporal_scope.start is None or self.temporal_scope.end is None or self.temporal_scope.basis not in {"event", "observation", "reported_as_of"}:
            raise ValueError("Derived interest needs an explicit bounded observation/event window")
        return self


class ProviderResponseGroup(Model):
    response_ref: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


def _time(value, basis):
    if value is None:
        return TemporalScope()
    return TemporalScope(precision=_date_precision(value), value=value, basis=basis)


def _date_bounds(value):
    """Calendar bounds for containment only; never replace reported precision."""
    import calendar
    if len(value) == 4:
        return value + "-01-01", value + "-12-31"
    if len(value) == 7:
        year, month = map(int, value.split("-"))
        return value + "-01", value + f"-{calendar.monthrange(year, month)[1]:02d}"
    return value[:10], value[:10]


def _topic_interpretations(context, nodes, edges, specs, refs):
    interpretations = []
    node_map = {n.id: n for n in nodes}
    edge_map = {e.id: e for e in edges}
    for spec in specs:
        if spec.person_id not in node_map or node_map[spec.person_id].kind != "person" or spec.topic_id not in node_map or node_map[spec.topic_id].kind != "topic":
            raise ValueError("Interest interpretation requires canonical person and topic nodes")
        if not set(spec.supporting_edge_ids) <= edge_map.keys():
            raise ValueError("Interest interpretation cites absent relationships")
        supporting = [edge_map[eid] for eid in spec.supporting_edge_ids]
        if any(e.assertion_kind == "inferred" or e.support_status != "supported" for e in supporting):
            raise ValueError("Interest interpretation needs supported factual acts, not other model conclusions")
        if {eid for e in supporting for eid in e.evidence_ids} != set(spec.evidence_ids):
            raise ValueError("Interest interpretation must retain exactly its supporting evidence")
        if any(not e.admissible for e in context.evidence if e.id in spec.evidence_ids):
            raise ValueError("Inadmissible observations cannot support a derived interest")
        lo, _ = _date_bounds(spec.temporal_scope.start)
        _, hi = _date_bounds(spec.temporal_scope.end)
        linked = False
        for actor in supporting:
            if actor.from_id != spec.person_id or actor.relation not in {"authored", "coauthored", "commented_on", "reacted_to"}:
                continue
            time = actor.temporal_scope
            allowed_time_basis = {"event", "observation", "reported_as_of"} | ({"publication"} if actor.relation in {"authored", "coauthored"} else set())
            if time.value is None or time.basis not in allowed_time_basis:
                continue
            start, end = _date_bounds(time.value)
            if lo <= start and end <= hi and any(e.from_id == actor.to_id and e.to_id == spec.topic_id and e.relation == "posted_about" for e in supporting):
                linked = True
        if not linked:
            raise ValueError("No dated person-to-content-to-topic evidence within the declared window")
        interpretations.append(EcosystemInterpretation(id=spec.id, input_ref=context.ref, person_id=spec.person_id, topic_id=spec.topic_id,
            supporting_edge_ids=spec.supporting_edge_ids, evidence_ids=spec.evidence_ids, source_refs=refs(spec.evidence_ids),
            temporal_scope=spec.temporal_scope, explanation=spec.explanation))
        edges.append(ResearchEdge(id="edge:" + spec.id, from_id=spec.person_id, to_id=spec.topic_id, relation="interest_in",
            label="Observed topic engagement: " + node_map[spec.topic_id].label, evidence_ids=spec.evidence_ids, source_refs=refs(spec.evidence_ids),
            assertion_kind="inferred", support_status="supported", temporal_scope=spec.temporal_scope, interpretation_ref=spec.id,
            limitation="Derived only from cited acts in this window; not stable belief, expertise, grit, friendship or network quality."))
    return interpretations


def ecosystem_coverage(graph: ResearchGraph) -> EcosystemCoverage:
    """Describe this observed subgraph; never estimate the unobserved network."""
    counts, identities = {}, set()
    node_map = {n.id: n for n in graph.nodes}
    for node in graph.nodes:
        if node.kind in {"source", "claim"} or not node.source_refs:
            continue
        ref = node.canonical_entity_ref
        key = (ref.kind, ref.id) if ref else (node.kind, node.id)
        if key not in identities:
            identities.add(key)
            counts[node.kind] = counts.get(node.kind, 0) + 1
    factual = [e for e in graph.edges if e.relation in ECOSYSTEM_ENDPOINTS and e.assertion_kind != "inferred" and e.support_status == "supported"]
    ties = {}
    for edge in factual:
        allowed_time_basis = {"event", "observation", "reported_as_of"} | ({"publication"} if edge.relation == "coauthored_with" else set())
        if edge.relation not in {"coauthored_with", "collaborated_with"} or not edge.event_ref or edge.temporal_scope.value is None or edge.temporal_scope.basis not in allowed_time_basis:
            continue
        key = (edge.from_id, edge.to_id, edge.relation)
        ties.setdefault(key, []).append(edge)
    repeated = []
    for (origin, target, relation), items in sorted(ties.items()):
        events = sorted({e.event_ref for e in items})
        dates = sorted({e.temporal_scope.value for e in items})
        # Two references to the same paper/event, or only one date, are not repeat evidence.
        separate_dates = any(_date_bounds(a)[1] < _date_bounds(b)[0] or _date_bounds(b)[1] < _date_bounds(a)[0] for a in dates for b in dates)
        if len(events) >= 2 and separate_dates:
            repeated.append(RepeatedDatedTie(from_id=origin, to_id=target, relation=relation, event_refs=events, dates=dates,
                evidence_ids=sorted({eid for e in items for eid in e.evidence_ids})))
    return EcosystemCoverage(unique_entities=len(identities), entities_by_kind=dict(sorted(counts.items())),
        supported_typed_edges=len(factual), typed_relationship_types=sorted({e.relation for e in factual}),
        dated_event_ids=sorted(n.id for n in node_map.values() if n.kind == "event" and n.source_refs and n.temporal_scope.value is not None and n.temporal_scope.basis in {"event", "observation", "reported_as_of"}),
        repeated_dated_ties=repeated, full_network_density=None,
        limitations=["Counts describe only this sourced observed subgraph; total network size and density are unknown.",
            "Distinct URLs, engagement counts and repeated ties are not founder quality, grit, access or friendship scores.",
            "Repeated collaboration requires distinct sourced works/events and dates; one engagement never establishes it."])


def build_research_graph(context: CaseContext, *, generated_at: str, research_example_ref: str | None = None,
                         observation_metadata: list[ObservationGraphMetadata] | None = None,
                         entities: list[EntitySpec] | None = None, assertions: list[AssertionSpec] | None = None,
                         questions: list[ResearchQuestion] | None = None,
                         matcher_result: MatcherResult | None = None, assessment_ref: str | None = None,
                         decision: ResearchDecisionSpec | None = None, limitations: list[str] | None = None,
                         provider_response_groups: list[ProviderResponseGroup] | None = None,
                         topic_interests: list[TopicInterestSpec] | None = None,
                         include_ecosystem_coverage: bool = False) -> ResearchGraph:
    """Project an attributable snapshot; explicit specs never run extraction/inference.

    Caller supplies sourced entity/event mappings. Raw prose is never mined for
    founding, meeting, collaboration, grit or temporal facts. Backend still owns
    validation/acceptance of observations and canonical identity.
    """
    if context.ref.evidence_hash != evidence_hash(context) or context.ref.thesis_version != context.policy.thesis_version or context.ref.policy_version != context.policy.policy_version:
        raise ValueError("Factual snapshot hash is stale")
    evidence = {e.id: e for e in context.evidence}
    people = {p.id: p for p in context.people}
    relationships = {r.id: r for r in context.relationships}
    if len(evidence) != len(context.evidence) or len(people) != len(context.people) or len(relationships) != len(context.relationships):
        raise ValueError("Duplicate input observation/entity IDs")
    metadata_items = observation_metadata or []
    metadata = {m.evidence_id: m for m in metadata_items}
    if len(metadata) != len(metadata_items) or not set(metadata) <= evidence.keys():
        raise ValueError("Duplicate or nonexistent evidence annotations")
    grouped = set()
    for group in provider_response_groups or []:
        if not set(group.evidence_ids) <= evidence.keys() or grouped & set(group.evidence_ids):
            raise ValueError("Provider response group has unknown or multiply grouped evidence")
        observations = [evidence[eid] for eid in group.evidence_ids]
        if len({(e.source_url, e.data_mode, e.retrieved_at) for e in observations}) != 1:
            raise ValueError("One provider response cannot mix URLs, retrieval times or data modes")
        source_id = "source:provider-response:" + hashlib.sha256(group.response_ref.encode()).hexdigest()[:24]
        for observation in observations:
            info = metadata.get(observation.id, ObservationGraphMetadata(evidence_id=observation.id))
            if info.original_source_id is not None and info.original_source_id != source_id:
                raise ValueError("Provider response conflicts with an explicit source grouping")
            metadata[observation.id] = info.model_copy(update={"original_source_id": source_id})
        grouped.update(group.evidence_ids)
    for rel in context.relationships:
        if rel.person_id not in people or rel.company_id != context.company_id or not set(rel.evidence_ids) <= evidence.keys():
            raise ValueError("Relationship attribution is outside the supplied snapshot")
    sources, evidence_source = {}, {}
    for observation in context.evidence:
        if not (observation.source_key or observation.source_url):
            raise ValueError("Graph observations require a source key or URL")
        info = metadata.get(observation.id, ObservationGraphMetadata(evidence_id=observation.id))
        source_id = info.original_source_id or f"source:{observation.id}"
        if source_id in evidence:
            raise ValueError("Source ID must not impersonate an evidence ID")
        observation_time = info.observation_time or _time(observation.observed_at, "observation")
        retrieval_time = info.retrieval_time or _time(observation.retrieved_at, "retrieval")
        values = dict(id=source_id, evidence_ids=[observation.id], source_url=observation.source_url,
                      source_keys=[observation.source_key] if observation.source_key else [], source_type=info.source_type,
                      source_quality=info.source_quality, data_mode=observation.data_mode, publication_time=info.publication_time,
                      observation_times=[observation_time], retrieval_times=[retrieval_time], limitations=info.limitations)
        if source_id in sources:
            prior = sources[source_id]
            for key in ["source_url", "source_type", "source_quality", "data_mode", "publication_time"]:
                if getattr(prior, key) != values[key]:
                    raise ValueError("One original-source group has inconsistent provenance")
            for key in ["evidence_ids", "source_keys", "observation_times", "retrieval_times", "limitations"]:
                values[key] = list(getattr(prior, key))
                for value in ([observation.id] if key == "evidence_ids" else
                              ([observation.source_key] if observation.source_key else []) if key == "source_keys" else
                              [observation_time] if key == "observation_times" else [retrieval_time] if key == "retrieval_times" else info.limitations):
                    if value not in values[key]:
                        values[key].append(value)
        sources[source_id] = ResearchSource(**values)
        evidence_source[observation.id] = source_id
    def refs(ids):
        if not set(ids) <= evidence.keys():
            raise ValueError("Projection cites nonexistent evidence")
        return sorted({evidence_source[eid] for eid in ids})

    nodes, edges = [], []
    open_questions = list(questions or [])
    if any(not set(question.criterion_ids) <= {c.id for c in context.policy.criteria} for question in open_questions):
        raise ValueError("Open question refers to an unrecognized criterion")
    company_evidence = [e.id for e in context.evidence if e.subject_kind == "company" and e.subject_id == context.company_id]
    nodes.append(ResearchNode(id=context.company_id, kind="organisation", label=context.company_name,
        canonical_entity_ref=CanonicalEntityRef(kind="company", id=context.company_id), source_refs=refs(company_evidence),
        attributes={"identity_source": "supplied_snapshot", "qualification_implied": False}))
    for person in context.people:
        ids = [e.id for e in context.evidence if e.subject_kind == "person" and e.subject_id == person.id]
        ids += [eid for rel in context.relationships if rel.person_id == person.id for eid in rel.evidence_ids]
        nodes.append(ResearchNode(id=person.id, kind="person", label=person.name,
            canonical_entity_ref=CanonicalEntityRef(kind="person", id=person.id), source_refs=refs(ids),
            attributes={"identity_source": "supplied_snapshot"}))
        if not any(rel.person_id == person.id for rel in context.relationships):
            open_questions.append(ResearchQuestion(id=f"question:attribution:{person.id}", target_node_ids=[person.id, context.company_id],
                question="What sourced relationship links this person to this company, and in what role?",
                decision_consequence="Would resolve attribution; shared employer, name or coauthorship is insufficient."))
    if not context.people:
        open_questions.append(ResearchQuestion(id="question:missing-team", target_node_ids=[context.company_id],
            criterion_ids=[c.id for c in context.policy.criteria if c.lens == "founder"],
            question="Who are the relevant founders/operators, and what sources establish their actual roles and attributable work?",
            decision_consequence="Team evidence is unavailable, not adverse; obtain it if it could change the next research action."))
    for spec in entities or []:
        if not spec.evidence_ids:
            raise ValueError("Additional products/assets/projects/events need attributable evidence")
        nodes.append(ResearchNode(id=spec.id, kind=spec.kind, label=spec.label, canonical_entity_ref=spec.canonical_entity_ref,
                                  source_refs=refs(spec.evidence_ids), attributes=spec.attributes, temporal_scope=spec.temporal_scope))
    for source in sources.values():
        nodes.append(ResearchNode(id=source.id, kind="source", label=(source.source_url or source.source_keys[0])[:240],
            canonical_entity_ref=CanonicalEntityRef(kind="source", id=source.id), source_refs=[source.id],
            attributes={"data_mode": source.data_mode, "source_type": source.source_type, "source_quality": source.source_quality}))
    entity_ids = {n.id for n in nodes}
    for observation in context.evidence:
        info = metadata.get(observation.id, ObservationGraphMetadata(evidence_id=observation.id))
        target = observation.subject_id
        if observation.subject_kind == "relationship":
            if target not in relationships:
                raise ValueError("Observation refers to an absent relationship")
            target = relationships[target].person_id
        if target not in entity_ids:
            raise ValueError("Observation subject needs a supplied canonical/explicit entity node")
        node_id = f"claim:{observation.id}"
        nodes.append(ResearchNode(id=node_id, kind="claim", label=observation.claim[:240],
            canonical_entity_ref=CanonicalEntityRef(kind="evidence", id=observation.id), source_refs=refs([observation.id]),
            attributes={"summary": observation.summary[:2400], "summary_truncated": len(observation.summary) > 2400,
                "assertion_kind": info.assertion_kind, "support_status": info.support_status, "freshness": observation.freshness,
                "admissible_for_assessment": observation.admissible},
            temporal_scope=info.observation_time or _time(observation.observed_at, "observation")))
        limitation = "; ".join(info.limitations) or "A sourced observation/report is not independent verification of the underlying claim."
        edges.append(ResearchEdge(id=f"edge:claim:{observation.id}", from_id=target, to_id=node_id, relation="has_claim",
            label="Reported observation" if info.assertion_kind == "source_reported" else "Observed evidence",
            evidence_ids=[observation.id], source_refs=refs([observation.id]), assertion_kind=info.assertion_kind,
            support_status=info.support_status, limitation=limitation))
        edges.append(ResearchEdge(id=f"edge:source:{observation.id}", from_id=evidence_source[observation.id], to_id=node_id,
            relation="records", label="Records this claim", evidence_ids=[observation.id], source_refs=refs([observation.id]),
            assertion_kind=info.assertion_kind, support_status=info.support_status, limitation=limitation))
    for rel in context.relationships:
        if rel.status == "unknown" or not rel.evidence_ids:
            open_questions.append(ResearchQuestion(id=f"question:relationship:{rel.id}", target_node_ids=[rel.person_id, context.company_id],
                question=f"What attributable source establishes {rel.role} for this person at this company?",
                decision_consequence="Could resolve role attribution; absence is unknown, not a founder penalty."))
            continue
        infos = [metadata.get(eid, ObservationGraphMetadata(evidence_id=eid)) for eid in rel.evidence_ids]
        kind = "observed" if all(i.assertion_kind == "observed" for i in infos) else "source_reported"
        # Reporting/observation dates never become role start/end dates.
        edges.append(ResearchEdge(id=f"edge:relationship:{rel.id}", from_id=rel.person_id, to_id=context.company_id,
            relation="held_role_at", label=f"Reported role: {rel.role}", evidence_ids=rel.evidence_ids, source_refs=refs(rel.evidence_ids),
            assertion_kind=kind, support_status=rel.status,
            temporal_scope=TemporalScope(limitation="Role start/end dates are not established by retrieval or publication dates."),
            limitation="Role attribution is limited to the cited source; no founding, current-employment or collaboration history is inferred."))
    for spec in assertions or []:
        if spec.assertion_kind == "observed" and any(metadata.get(eid, ObservationGraphMetadata(evidence_id=eid)).assertion_kind != "observed" for eid in spec.evidence_ids):
            raise ValueError("Source-reported material cannot be promoted to observed by an edge spec")
        edges.append(ResearchEdge(id=spec.id, from_id=spec.from_id, to_id=spec.to_id, relation=spec.relation, label=spec.label,
            evidence_ids=spec.evidence_ids, source_refs=refs(spec.evidence_ids), assertion_kind=spec.assertion_kind,
            support_status=spec.support_status, temporal_scope=spec.temporal_scope, limitation=spec.limitation,
            interpretation_ref=spec.interpretation_ref, event_ref=spec.event_ref))
    interpretations, matcher_summary = [], None
    if matcher_result is not None:
        if matcher_result.ref != context.ref or matcher_result.assessment is None or not assessment_ref:
            raise ValueError("Matcher interpretation needs its actual matching snapshot and explicit assessment artifact/record reference")
        criteria = {c.id for c in context.policy.criteria}
        for finding in matcher_result.assessment.findings:
            if finding.criterion_id not in criteria or not set(finding.person_ids) <= people.keys():
                raise ValueError("Interpretation refers to unrecognized criteria or people")
            ids = finding.evidence_ids + finding.counterevidence_ids
            state = finding.comparison_state or ("mixed" if finding.conflicted else {"meets": "supported", "fails": "contradicted", "unknown": "unknown"}[finding.result])
            interpretations.append(MatcherInterpretationRef(id=f"interpretation:{finding.criterion_id}", assessment_ref=assessment_ref,
                input_ref=matcher_result.ref, prompt_version=matcher_result.prompt_version, driver_kind=matcher_result.driver_kind,
                criterion_id=finding.criterion_id, target_node_ids=[context.company_id, *finding.person_ids],
                evidence_ids=finding.evidence_ids, counterevidence_ids=finding.counterevidence_ids, source_refs=refs(ids),
                comparison_state=state, interpretation=finding.rationale))
        answers = {}
        for key in ["why_this", "why_them", "why_now", "team_problem_fit"]:
            answer = getattr(matcher_result.assessment, key)
            answers[key] = ResearchInterpretationAnswer(**answer.model_dump(), source_refs=refs(answer.evidence_ids))
        matcher_summary = MatcherResearchSummary(assessment_ref=assessment_ref, input_ref=matcher_result.ref,
            prompt_version=matcher_result.prompt_version, driver_kind=matcher_result.driver_kind, **answers)
        brief = matcher_result.assessment.case_brief
        if decision is not None and brief is not None:
            if (decision.decision != brief.research_posture or decision.next_action != brief.next_action
                    or decision.future_trigger != brief.future_trigger):
                raise ValueError("Graph research decision must match the saved case brief posture, action and trigger")
    ecosystem_interpretations = _topic_interpretations(context, nodes, edges, topic_interests or [], refs)
    graph = ResearchGraph(graph_id="pending", case_id=None if research_example_ref else context.ref.case_id,
        research_example_ref=research_example_ref, snapshot_ref=context.ref, generated_at=generated_at,
        nodes=nodes, edges=edges, sources=list(sources.values()), open_questions=open_questions,
        matcher_interpretations=interpretations, matcher_summary=matcher_summary, ecosystem_interpretations=ecosystem_interpretations,
        research_decision=ResearchDecision(**decision.model_dump(), source_refs=refs(decision.evidence_ids)) if decision else None,
        limitations=["Graph is a sourced research projection, not independent verification, a personality score or qualification approval.",
            "Missing founder/collaboration/setback history is a question, not negative evidence; a pivot can reflect learning.",
            "Matcher interpretations are separate references and create no new source/evidence records.",
            "Source-reported, observed and inferred assertions retain their provenance; source DataMode does not change assertion kind.", *(limitations or [])])
    if include_ecosystem_coverage:
        graph = graph.model_copy(update={"ecosystem_coverage": ecosystem_coverage(graph)})
    content = graph.model_dump(mode="json", exclude={"graph_id", "generated_at"})
    if not graph.ecosystem_interpretations:
        content.pop("ecosystem_interpretations", None)
    if graph.ecosystem_coverage is None:
        content.pop("ecosystem_coverage", None)
    for edge in content["edges"]:
        if edge.get("event_ref") is None:
            edge.pop("event_ref", None)
    graph_id = "research-graph:" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    return ResearchGraph.model_validate(graph.model_copy(update={"graph_id": graph_id}).model_dump())


def decision_from_matcher(result: MatcherResult, *, assessment_ref: str, action_timing: Literal["now", "future"] | None = None,
                          decision_consequence: str, future_trigger: str | None = None) -> ResearchDecisionSpec:
    """Prefer the saved brief's semantic posture; legacy callers classify timing.

    No NLP heuristic invents a pursue label from a score or converts it to human
    approval. Explicit contradictory caller timing is rejected, never used to
    turn a useful pursue into monitor because execution has no remaining calls.
    """
    if result.outcome not in {"assessment", "needs_approval"} or result.assessment is None:
        raise ValueError("A valid rich comparison/assessment is required for a research recommendation")
    brief = result.assessment.case_brief
    next_action = result.assessment.next_action
    ids = [eid for finding in result.assessment.findings for eid in finding.evidence_ids + finding.counterevidence_ids]
    if brief is not None:
        expected_timing = "now" if brief.research_posture == "pursue" else "future"
        if action_timing is not None and action_timing != expected_timing:
            raise ValueError("Explicit research timing contradicts the saved case brief")
        if future_trigger is not None and future_trigger != brief.future_trigger:
            raise ValueError("Explicit future trigger contradicts the saved case brief")
        action_timing, future_trigger, next_action = expected_timing, brief.future_trigger, brief.next_action
        for claim in [brief.company_description, brief.main_reason, brief.decisive_doubt, *brief.strongest_facts, *brief.founder_signals]:
            ids.extend(claim.evidence_ids)
    if action_timing not in {"now", "future"}:
        raise ValueError("Legacy assessment without a brief requires explicit research action timing")
    return ResearchDecisionSpec(assessment_ref=assessment_ref, input_ref=result.ref, decision="pursue" if action_timing == "now" else "monitor",
        next_action=next_action, decision_consequence=decision_consequence,
        future_trigger=future_trigger, evidence_ids=list(dict.fromkeys(ids)))


def to_mermaid(graph: ResearchGraph) -> str:
    """Portable network source for inspection; frontend owns interactive rendering."""
    aliases = {node.id: f"n{i}" for i, node in enumerate(graph.nodes)}
    def label(text):
        return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", " ")
    lines = ["flowchart LR"]
    lines += [f'  {aliases[node.id]}["{label(node.label)}"]' for node in graph.nodes]
    for edge in graph.edges:
        arrow = "-.->" if edge.support_status in {"unknown", "mixed", "contradicted"} or edge.assertion_kind == "inferred" else "-->"
        lines.append(f'  {aliases[edge.from_id]} {arrow}|"{label(edge.label)}"| {aliases[edge.to_id]}')
    return "\n".join(lines) + "\n"
