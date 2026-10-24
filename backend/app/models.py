from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataMode(str, Enum):
    live = "live"
    captured = "captured"
    synthetic = "synthetic"


class CaseStatus(str, Enum):
    discovered = "discovered"
    enrichment_pending = "enrichment_pending"
    investigating = "investigating"
    needs_evidence = "needs_evidence"
    monitor = "monitor"
    qualified = "qualified"
    outreach_ready = "outreach_ready"
    rejected = "rejected"
    failed = "failed"


class CreateMandate(Model):
    title: str = Field(min_length=1, max_length=200)
    thesis_text: str = Field(min_length=1, max_length=20000)
    target_count: int = Field(ge=1, le=100, strict=True)
    reference_status: Literal["placeholder", "user_supplied"] = "placeholder"

    @field_validator("title", "thesis_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must contain non-whitespace characters")
        return value  # Preserve user text exactly.


class Progress(Model):
    total: int = 0
    outreach_ready: int = 0


class Mandate(CreateMandate):
    id: str
    thesis_version: int = 1
    target_state: Literal["outreach_ready"] = "outreach_ready"
    status: Literal["draft", "running", "completed", "shortfall", "failed"] = "draft"
    progress: Progress = Field(default_factory=Progress)
    created_at: str
    updated_at: str


class Person(Model):
    id: str
    name: str
    role: str | None = None
    profile_url: str | None = None
    source_key: str | None = None
    data_mode: DataMode


class Evidence(Model):
    id: str
    company_id: str
    claim_type: str
    summary: str
    source_url: str | None = None
    source_key: str | None = None
    observed_at: str | None = None
    retrieved_at: str
    data_mode: DataMode


class Dimension(Model):
    name: str
    score: float | None = Field(default=None, ge=0, le=1)
    status: Literal["supported", "contradicted", "unknown"]
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class Evaluation(Model):
    id: str
    case_id: str
    thesis_version: int
    created_at: str
    dimensions: list[Dimension]
    thesis_fit: float | None = Field(default=None, ge=0, le=1)
    evidence_sufficiency: float | None = Field(default=None, ge=0, le=1)
    recommendation: CaseStatus
    missing_claims: list[str]
    next_action: str
    reasoning_summary: str
    evidence_ids: list[str]
    data_mode: DataMode
    evaluator_kind: Literal["fixture", "semantic"]


class Case(Model):
    id: str
    mandate_id: str
    company_id: str
    company_name: str
    canonical_domain: str | None = None
    status: CaseStatus
    version: int
    thesis_fit: float | None = None
    evidence_sufficiency: float | None = None
    next_action: str
    why_now: str | None = None
    data_mode: DataMode
    updated_at: str


class Event(Model):
    id: str
    case_id: str
    event_type: str
    created_at: str
    summary: str
    evidence_ids: list[str]
    replayed: bool
    data_mode: DataMode


class OutreachPackage(Model):
    person: Person | None = None
    rationale: str
    draft: str
    readiness_gaps: list[str]
    data_mode: DataMode


class AgentAssessmentSummary(Model):
    id: str
    outcome: str
    proposed_disposition: str | None
    driver_kind: str
    prompt_version: str
    comparison_only: bool
    eligible_for_human_review: bool
    input_current: bool
    expected_case_version: int
    created_at: str
    structured_result: dict
    review_eligibility: dict | None = None


class QualificationReviewInput(Model):
    assessment_id: str = Field(min_length=1)
    expected_case_version: int = Field(ge=0, strict=True)
    decision: Literal["approve", "request_evidence"]
    note: str | None = Field(default=None, max_length=2000)


class ResearchExecutionInput(Model):
    assessment_id: str = Field(min_length=1)
    expected_case_version: int = Field(ge=0,strict=True)
    idempotency_key: str = Field(min_length=1,max_length=128)


class QualificationReviewRecord(Model):
    id: str
    assessment_id: str
    decision: Literal["approve", "request_evidence"]
    note: str | None
    reviewer_identity: str | None = None
    source: str
    synthetic_test: bool
    created_at: str
    current: bool


class CaseDetail(Case):
    evidence: list[Evidence]
    evaluations: list[Evaluation]
    events: list[Event]
    outreach: OutreachPackage | None = None
    agent_assessments: list[AgentAssessmentSummary] = Field(default_factory=list)
    qualification_reviews: list[QualificationReviewRecord] = Field(default_factory=list)
    people: list[dict] = Field(default_factory=list)


class SignalInput(Model):
    summary: str = Field(min_length=1, max_length=5000)
    claim_type: str = Field(min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=2000)
    replayed: bool
    data_mode: DataMode

    @field_validator("summary", "claim_type")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must contain non-whitespace characters")
        return value

    @field_validator("source_url")
    @classmethod
    def web_url_only(cls, value: str | None) -> str | None:
        if value is not None:
            from urllib.parse import urlsplit
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("source_url must be an http(s) URL without embedded credentials")
        return value

    @model_validator(mode="after")
    def replay_only(self):
        if not self.replayed or self.data_mode == DataMode.live:
            raise ValueError("Public signals must be replayed synthetic or registered captured evidence; live verification is unavailable")
        return self


class Task(Model):
    id: str
    mandate_id: str
    case_id: str | None = None
    type: str
    status: Literal["pending", "running", "succeeded", "failed"]
    error: str | None = None
    created_at: str
    updated_at: str


class MandateList(Model):
    items: list[Mandate]


class CaseList(Model):
    items: list[Case]


class EvaluationList(Model):
    items: list[Evaluation]


class Health(Model):
    status: str = "ok"
    contract_version: str = "0.1"


class ConfigStatus(Model):
    contract_version: str = "0.1"
    provider_mode: str
    crustdata_configured: bool
    thesis_status: str
    semantic_matcher_configured: bool = False
    evaluator_kind: str = "fixture"
    provider_implementation: str = "crustdata_search_and_fixture"
    discovery_query_status: str = "awaiting_configuration"
    discovery_query_label: str | None = None
    persistence: str = "sqlite"
    task_execution: str = "in_process_single_worker"
    agent_bridge_mode: str = "explicit_cli_only"
    qualification_authority: str = "human"
    research_graph_schema_version: str = "0.1"
    max_cases_per_run: int
    limitations: list[str]


class ErrorDetail(Model):
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(Model):
    error: ErrorDetail
