"""Human-authorized stage calibration of saved evidence; no model/tool/state calls."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import CaseContext, MatcherResult, Model, VersionRef, evidence_hash

Category = Literal["outreach_candidate", "research_first", "monitor", "outside_scope"]


class PreOutreachOverlay(Model):
    id: str = Field(min_length=1)
    version: Literal["0.1"] = "0.1"
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    base_reference_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authorization_ref: str = Field(min_length=1)


class CalibrationClaim(Model):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class IntroCondition(CalibrationClaim):
    status: Literal["supported", "unresolved", "contradicted"]


class IntroMinimum(Model):
    identity_and_scope: IntroCondition
    concrete_product_program_or_problem: IntroCondition
    useful_conversation_reason: IntroCondition


class IntroBlocker(CalibrationClaim):
    kind: Literal["identity", "scope", "current_operator_or_status", "missing_concrete_rationale"]
    what_to_resolve: str = Field(min_length=1)
    decision_consequence: str = Field(min_length=1)


class IntroContraryFact(CalibrationClaim):
    effect: Literal["limits_claim", "prevents_honest_intro", "confirmed_outside_scope"]


class RelevantPersonStatus(Model):
    status: Literal["source_attributed_current", "historical_or_uncertain", "unknown"]
    person_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)


class ContactRouteStatus(Model):
    status: Literal["source_supported_route", "not_established", "human_confirmation_needed"]
    route_kind: Literal["company_route", "person_route", "operator_record", "unknown"] = "unknown"
    route_ref: str | None = None
    person_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def route_claim_needs_reference(self):
        if self.status == "source_supported_route" and (not self.route_ref or self.route_kind == "unknown" or not self.evidence_ids):
            raise ValueError("A claimed source-supported route needs a real reference and evidence")
        if self.route_kind == "company_route" and self.person_id is not None:
            raise ValueError("A generic company channel is not a verified personal route")
        if self.route_kind == "person_route" and self.person_id is None:
            raise ValueError("A personal route needs its canonical person")
        return self


class PreOutreachGuidance(Model):
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    version: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    input_ref: VersionRef
    assessment_ref: str = Field(min_length=1)
    author: str = Field(min_length=1)
    suggested_category: Category
    rationale: CalibrationClaim
    minimum: IntroMinimum
    contrary_facts: list[IntroContraryFact] = Field(default_factory=list)
    call_questions: list[CalibrationClaim] = Field(min_length=1, max_length=2)
    pre_intro_blocker: IntroBlocker | None = None
    future_merit_trigger: CalibrationClaim | None = None
    relevant_person: RelevantPersonStatus
    contact_route: ContactRouteStatus


class PreOutreachReview(Model):
    schema_version: Literal["0.1"] = "0.1"
    input_ref: VersionRef
    assessment_ref: str
    assessment_prompt_version: str
    overlay: PreOutreachOverlay
    guidance_source_path: str
    guidance_source_sha256: str
    guidance_version: str
    guidance_entry_id: str
    author: str
    category: Category
    suggested_category: Category
    rationale: CalibrationClaim
    minimum: IntroMinimum
    contrary_facts: list[IntroContraryFact]
    call_questions: list[CalibrationClaim]
    pre_intro_blocker: IntroBlocker | None
    future_merit_trigger: CalibrationClaim | None
    relevant_person: RelevantPersonStatus
    contact_route: ContactRouteStatus
    next_step: Literal["human_review_intro", "resolve_person_or_route_for_human_review", "resolve_pre_intro_fact", "watch_stated_merit_trigger", "retain_scope_reason"]
    guard_notes: list[str]
    provenance: Literal["human-authorized_stage_calibration_interpretation_using_existing_evidence"] = "human-authorized_stage_calibration_interpretation_using_existing_evidence"
    newly_executed_model: Literal[False] = False
    changes_formal_readiness: Literal[False] = False
    changes_qualification: Literal[False] = False
    sending_authorized: Literal[False] = False


def build_pre_outreach_review(context: CaseContext, matcher_result: MatcherResult, *, assessment_ref: str,
                             overlay: PreOutreachOverlay, guidance: PreOutreachGuidance,
                             current_ref: VersionRef | None = None) -> PreOutreachReview:
    """Validate/apply the declared stage rule, never rejudge strict C4 or qualify.

    Backend verifies raw overlay/guidance hashes against its activation registry,
    supplies the human authorization reference and binds immutable accepted state.
    The pure mapper performs no file I/O, model call, source lookup or sending.
    """
    if evidence_hash(context) != context.ref.evidence_hash or current_ref is not None and current_ref != context.ref:
        raise ValueError("Pre-outreach input snapshot is stale")
    if matcher_result.ref != context.ref or guidance.input_ref != context.ref or guidance.assessment_ref != assessment_ref:
        raise ValueError("Overlay must bind the exact current case/evidence and immutable assessment")
    if matcher_result.assessment is None or matcher_result.outcome not in {"assessment", "needs_approval"}:
        raise ValueError("A saved rich assessment is required; configuration alone is not evidence")
    if overlay.base_reference_sha256 != context.policy.reference_document_hash:
        raise ValueError("Overlay targets a different reference thesis")
    if not (context.policy.approved or context.policy.reference_direction_reviewed):
        raise ValueError("A reviewed reference direction is required")
    evidence = {e.id: e for e in context.evidence}
    people = {p.id for p in context.people}
    def sourced(ids):
        return bool(ids) and all(eid in evidence and evidence[eid].admissible and evidence[eid].freshness != "stale"
            and (evidence[eid].source_key or evidence[eid].source_url)
            and (evidence[eid].data_mode != "synthetic" or context.test_fixture) for eid in ids)
    claims = [guidance.rationale, guidance.minimum.identity_and_scope, guidance.minimum.concrete_product_program_or_problem,
        guidance.minimum.useful_conversation_reason, *guidance.contrary_facts, *guidance.call_questions]
    if guidance.pre_intro_blocker: claims.append(guidance.pre_intro_blocker)
    if guidance.future_merit_trigger: claims.append(guidance.future_merit_trigger)
    if any(not set(c.evidence_ids) <= evidence.keys() for c in claims):
        raise ValueError("Calibration cites evidence outside the saved context")
    if any(not sourced(c.evidence_ids) for c in guidance.contrary_facts):
        raise ValueError("A contrary fact needs sourced evidence; missing data is not a contrary fact")
    person = guidance.relevant_person
    route = guidance.contact_route
    if not set(person.person_ids) <= people or route.person_id is not None and route.person_id not in people:
        raise ValueError("Person/contact identity is not present in the current context")
    if not set(person.evidence_ids + route.evidence_ids) <= evidence.keys():
        raise ValueError("Person/contact status cites unknown evidence")
    if person.status == "source_attributed_current":
        if not person.person_ids or not sourced(person.evidence_ids) or not all(any(r.person_id == pid and r.status == "supported" and sourced(r.evidence_ids) for r in context.relationships) for pid in person.person_ids):
            raise ValueError("Current relevant person requires a sourced canonical role link")
    if route.status == "source_supported_route" and not sourced(route.evidence_ids):
        raise ValueError("A contact route cannot be invented from a company or person's name")
    conditions = [guidance.minimum.identity_and_scope, guidance.minimum.concrete_product_program_or_problem, guidance.minimum.useful_conversation_reason]
    base_met = all(c.status == "supported" and sourced(c.evidence_ids) for c in conditions[:2])
    conversation_merit = conditions[2].status == "supported" and sourced(conditions[2].evidence_ids)
    category, notes = guidance.suggested_category, []
    outside = any(c.effect == "confirmed_outside_scope" for c in guidance.contrary_facts)
    prevents_intro = any(c.effect == "prevents_honest_intro" for c in guidance.contrary_facts)
    if outside:
        category = "outside_scope"
    elif guidance.pre_intro_blocker is not None or prevents_intro or not base_met:
        category = "research_first"
    elif category == "monitor":
        if conversation_merit:
            raise ValueError("A future-merit monitor label cannot replace an already supported current conversation reason")
        if guidance.future_merit_trigger is None or not sourced(guidance.future_merit_trigger.evidence_ids):
            raise ValueError("Monitor needs a substantive sourced future-merit trigger")
    elif not conversation_merit:
        category = "research_first"
    elif category == "outside_scope":
        raise ValueError("Outside scope needs an affirmative sourced mismatch, not a diligence gap")
    elif category == "research_first":
        raise ValueError("Research first needs a specific pre-intro blocker, not generic private diligence")
    if category != guidance.suggested_category:
        notes.append("Minimum premise or an explicit sourced contrary fact takes precedence over the suggested category.")
    rationale = guidance.rationale
    if category != guidance.suggested_category:
        facts = [c for c in guidance.contrary_facts if c.effect == ("confirmed_outside_scope" if category == "outside_scope" else "prevents_honest_intro")]
        if facts:
            rationale = CalibrationClaim(text="; ".join(c.text for c in facts), evidence_ids=list(dict.fromkeys(eid for c in facts for eid in c.evidence_ids)))
        elif guidance.pre_intro_blocker:
            rationale = CalibrationClaim(text=guidance.pre_intro_blocker.text, evidence_ids=guidance.pre_intro_blocker.evidence_ids)
        else:
            missing = [c for c in conditions if c.status != "supported" or not sourced(c.evidence_ids)]
            rationale = CalibrationClaim(text="Resolve the pre-intro premise: " + "; ".join(c.text for c in missing), evidence_ids=list(dict.fromkeys(eid for c in missing for eid in c.evidence_ids)))
    if category == "outreach_candidate" and not sourced(guidance.rationale.evidence_ids):
        raise ValueError("An outreach candidate needs a source-supported conversation rationale")
    actionable = person.status == "source_attributed_current" and route.status == "source_supported_route"
    next_step = ("human_review_intro" if actionable else "resolve_person_or_route_for_human_review") if category == "outreach_candidate" else {
        "research_first": "resolve_pre_intro_fact", "monitor": "watch_stated_merit_trigger", "outside_scope": "retain_scope_reason"}[category]
    notes.append("Private demos, contribution detail, rights/access and scientific validation can remain call questions; this does not satisfy or alter formal partner-review gates.")
    return PreOutreachReview(input_ref=context.ref, assessment_ref=assessment_ref, assessment_prompt_version=matcher_result.prompt_version,
        overlay=overlay, guidance_source_path=guidance.source_path, guidance_source_sha256=guidance.source_sha256,
        guidance_version=guidance.version, guidance_entry_id=guidance.entry_id, author=guidance.author,
        category=category, suggested_category=guidance.suggested_category, rationale=rationale, minimum=guidance.minimum,
        contrary_facts=guidance.contrary_facts, call_questions=guidance.call_questions, pre_intro_blocker=guidance.pre_intro_blocker,
        future_merit_trigger=guidance.future_merit_trigger, relevant_person=person, contact_route=route, next_step=next_step, guard_notes=notes)
