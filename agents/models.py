"""Internal proposal contracts. These are deliberately independent of HTTP v0.1."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .prompts import PROMPT_VERSION


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Criterion(Model):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    lens: Literal["company", "founder", "timing"]
    required_for_qualification: bool
    reject_on_failure: bool


class Policy(Model):
    mandate_id: str
    thesis_text: str
    thesis_version: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    approved: bool
    fit_rule: str
    attractiveness_gate: Literal["required", "human_review"]
    criteria: list[Criterion]
    reference_source: str | None = None
    reference_version: str | None = None
    reference_direction_reviewed: bool = False
    reference_document_hash: str | None = None

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion IDs must be unique")
        return self


class Observation(Model):
    id: str
    subject_kind: Literal["company", "person", "relationship", "market", "precedent"]
    subject_id: str
    claim: str
    summary: str
    source_key: str | None
    source_url: str | None
    observed_at: str | None
    retrieved_at: str
    data_mode: Literal["live", "captured", "synthetic"]
    admissible: bool = True
    freshness: Literal["current", "stale", "unknown"] = "unknown"


class Person(Model):
    id: str
    name: str


class Relationship(Model):
    id: str
    person_id: str
    company_id: str
    role: str
    status: Literal["supported", "contradicted", "unknown"]
    evidence_ids: list[str]


class VersionRef(Model):
    case_id: str
    case_version: int = Field(ge=0)
    thesis_version: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    evidence_hash: str


class Resources(Model):
    remaining_calls: int = Field(ge=0)
    remaining_output_tokens: int = Field(ge=0)
    deadline_expired: bool = False


class Capability(Model):
    action: str
    subject_kinds: list[Literal["company", "person", "relationship", "market"]]
    purpose: Literal["discovery", "investigation"] = "investigation"


class Finding(Model):
    criterion_id: str
    result: Literal["meets", "fails", "unknown"]
    evidence_sufficient: bool
    conflicted: bool
    evidence_ids: list[str]
    person_ids: list[str]
    rationale: str = Field(min_length=1)
    comparison_state: Literal["supported", "mixed", "contradicted", "unknown", "not_applicable"] | None = None
    counterevidence_ids: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None


class Answer(Model):
    summary: str = Field(min_length=1)
    evidence_ids: list[str]
    objections: list[str]
    unknowns: list[str]


class Investigation(Model):
    criterion_id: str
    subject_kind: Literal["company", "person", "relationship", "market"]
    subject_id: str
    action: str
    question: str = Field(min_length=1)
    decision_consequence: str = Field(min_length=1)
    query: str = Field(min_length=1)
    max_calls: int = Field(ge=1)


class BriefClaim(Model):
    text: str = Field(min_length=1, max_length=450)
    evidence_ids: list[str]


class SourcedBriefClaim(BriefClaim):
    evidence_ids: list[str] = Field(min_length=1)


class FounderSignal(Model):
    person_id: str
    contribution: str = Field(min_length=1, max_length=300)
    relevance: str = Field(min_length=1, max_length=300)
    evidence_ids: list[str] = Field(min_length=1)
    source_strength: Literal["first_party_claim", "inspectable_work", "independent_report", "mixed"]


class CaseBrief(Model):
    """Concise sourced view of an assessment, never a new evidence record."""
    company_description: BriefClaim
    research_posture: Literal["pursue", "monitor"]
    main_reason: BriefClaim
    strongest_facts: list[SourcedBriefClaim] = Field(max_length=2)
    founder_signals: list[FounderSignal] = Field(max_length=2)
    founder_unknowns: list[str] = Field(max_length=3)
    decisive_doubt: BriefClaim
    next_action: str = Field(min_length=1, max_length=500)
    future_trigger: str | None
    operational_limitations: list[str] = Field(max_length=3)

    @model_validator(mode="after")
    def monitor_needs_trigger(self):
        if self.research_posture == "monitor" and not (self.future_trigger or "").strip():
            raise ValueError("Monitor research posture requires a substantive future trigger")
        return self


class SemanticAssessment(Model):
    """Model findings, not an authoritative case state or executable tool call."""
    findings: list[Finding]
    why_this: Answer
    why_them: Answer
    why_now: Answer
    team_problem_fit: Answer
    fit: Literal["passes", "fails", "unknown"]
    attractiveness: Literal["promising", "weak", "unknown"]
    actionability: Literal["ready", "incomplete", "unknown"]
    proposed_disposition: Literal["reject", "monitor", "qualify"]
    investigation: Investigation | None
    interpretation_question: str | None
    next_action: str = Field(min_length=1)
    stop_or_reopen_condition: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    case_brief: CaseBrief | None = None


class CaseContext(Model):
    policy: Policy
    ref: VersionRef
    company_id: str
    company_name: str
    people: list[Person]
    relationships: list[Relationship]
    evidence: list[Observation]
    prior_assessment: SemanticAssessment | None
    changed_evidence_ids: list[str]
    attempted_investigation_keys: list[str]
    capabilities: list[Capability]
    resources: Resources
    mode: Literal["initial_assessment", "reassess", "reopen_check", "reference_comparison"] = "initial_assessment"
    prior_ref: VersionRef | None = None
    test_fixture: bool = False


def evidence_hash(context: CaseContext) -> str:
    """Order-independent factual manifest; semantic summaries are not evidence."""
    payload = {"company_id": context.company_id}
    for name in ("people", "relationships", "evidence"):
        payload[name] = sorted((v.model_dump(mode="json") for v in getattr(context, name)), key=lambda v: v["id"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def seal_context(context: CaseContext) -> CaseContext:
    return context.model_copy(update={"ref": context.ref.model_copy(update={"evidence_hash": evidence_hash(context)})})


def investigation_key(case_id: str, investigation: Investigation) -> str:
    # Stable within a case across unchanged observations; backend must decide when
    # a genuinely new source/signal justifies resetting an exhausted attempt.
    values = [case_id, investigation.criterion_id, investigation.subject_kind, investigation.subject_id,
              investigation.action, " ".join(investigation.query.casefold().split())]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


class MatcherResult(Model):
    outcome: Literal["assessment", "needs_approval", "stale_input", "invalid_input", "invalid_output", "model_failed", "waiting"]
    ref: VersionRef
    disposition: Literal["reject", "monitor", "qualify"] | None
    assessment: SemanticAssessment | None
    investigation: Investigation | None
    missing_required_claims: list[str]
    guard_notes: list[str]
    explanation: str
    driver_kind: Literal["scripted", "semantic"]
    prompt_version: str = PROMPT_VERSION
    input_tokens: int = 0
    output_tokens: int = 0
    test_fixture: bool = False
    evidence_modes: list[str] = Field(default_factory=list)
    criterion_evidence_sufficient: dict[str, bool] = Field(default_factory=dict)
    requires_human_qualification_review: bool = False


class HumanQualificationApproval(Model):
    """Backend-supplied durable human action, never an agent-generated output.

    Backend computes current after checking the stored review/assessment/case
    versions. Unrelated row-version changes need not invalidate material evidence.
    """
    review_record_id: str = Field(min_length=1)
    assessment_id: str = Field(min_length=1)
    thesis_version: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    evidence_hash: str
    current: bool


class CaseSummary(Model):
    ref: VersionRef
    company_id: str
    judgment: Literal["discovered", "monitor", "rejected", "qualified", "outreach_ready"]
    assessed_evidence_hash: str | None
    assessment: SemanticAssessment | None
    proposed_investigation: Investigation | None
    readiness_current: bool
    review_accepted: bool
    assessment_id: str | None = None
    qualification_approval: HumanQualificationApproval | None = None
    qualification_review_pending: bool = False

    def has_current_human_qualification(self) -> bool:
        approval = self.qualification_approval
        return bool(approval and approval.current and self.assessment_id and approval.assessment_id == self.assessment_id
                    and approval.thesis_version == self.ref.thesis_version and approval.policy_version == self.ref.policy_version
                    and approval.evidence_hash == self.ref.evidence_hash and self.assessed_evidence_hash == self.ref.evidence_hash)


class Intent(Model):
    kind: Literal["discover", "evaluate_case", "investigate_claim", "prepare_outreach"]
    case_id: str | None
    action: str | None
    investigation: Investigation | None
    max_calls: int = Field(ge=0)
    rationale: str = Field(min_length=1)
    discovery_branch_id: str | None = None


class DiscoveryBranch(Model):
    """Human/backend-reviewed search option, not LLM-generated provider syntax."""
    id: str
    action: str
    criterion_ids: list[str]
    hypothesis: str
    semantic_checks: list[str]
    recall_limitations: list[str]
    approved: bool
    max_calls: int = Field(ge=1)


class SemanticPlan(Model):
    intents: list[Intent]
    explanation: str = Field(min_length=1)
    interpretation_question: str | None
    discovery_hypotheses: list[DiscoveryHypothesis] = Field(default_factory=list)


class DiscoveryHypothesis(Model):
    id: str
    criterion_ids: list[str]
    track: Literal["H", "R", "D", "T", "general"]
    route: Literal["company_first", "people_first"]
    hypothesis: str = Field(min_length=1)
    problem_terms: list[str]
    user_or_buyer_terms: list[str]
    artifact_or_milestone_terms: list[str]
    semantic_checks: list[str]
    recall_risks: list[str]


class MandateContext(Model):
    policy: Policy
    snapshot_id: str
    cases: list[CaseSummary]
    active_work_keys: list[str]
    completed_work_keys: list[str]
    attempted_investigation_keys: list[str]
    capabilities: list[Capability]
    resources: Resources
    target_count: int = Field(ge=1)
    review_required_to_count: bool
    discovery_exhausted: bool
    discovery_branches: list[DiscoveryBranch] = Field(default_factory=list)
    mode: Literal["reconcile", "discovery_planning"] = "reconcile"


def intent_key(context: MandateContext, intent: Intent) -> str:
    if intent.kind == "investigate_claim" and intent.investigation is not None and intent.case_id:
        return investigation_key(intent.case_id, intent.investigation)
    case = next((c for c in context.cases if c.ref.case_id == intent.case_id), None)
    identity = [context.policy.mandate_id, context.policy.thesis_version, context.policy.policy_version,
                intent.kind, intent.case_id, case.ref.evidence_hash if case else None, intent.action, intent.discovery_branch_id]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


class OrchestratorResult(Model):
    outcome: Literal["intents", "discovery_plan_proposal", "needs_approval", "waiting", "completion_proposal", "shortfall_proposal", "invalid_input", "invalid_output", "stale_input", "model_failed"]
    snapshot_id: str
    intents: list[Intent]
    intent_keys: list[str]
    guard_notes: list[str]
    explanation: str
    driver_kind: Literal["scripted", "semantic"]
    prompt_version: str = PROMPT_VERSION
    input_tokens: int = 0
    output_tokens: int = 0
    discovery_hypotheses: list[DiscoveryHypothesis] = Field(default_factory=list)


SemanticPlan.model_rebuild()
