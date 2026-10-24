"""Internal proposal contract; no graph runtime, prompts or investment policy.

Coordinator is the legacy fixture execution path, not a semantic scheduler.
StateService owns snapshots and conditional acceptance, never evaluator calls.
"""
import hashlib
import json
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .errors import ServiceError
from .models import Case, CaseStatus, DataMode, Dimension, Evaluation, Evidence, Mandate, OutreachPackage


def content_version(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyReference(InternalModel):
    reference: str | None = None
    version: int = Field(default=0, ge=0)
    status: Literal["unavailable", "draft", "approved"] = "unavailable"
    # A reference slot is not policy activation. No semantic adapter is enabled.


class EvidenceManifestEntry(InternalModel):
    evidence_id: str
    company_id: str
    content_version: str


class ReferenceMaterial(InternalModel):
    """Pinned source text/outline; never compiled or activated investment policy."""
    document_path: str
    document_version: str
    review_status: Literal["human_reviewed_direction_only"]
    document_sha256: str
    document_text: str
    outline_path: str | None = None
    outline_sha256: str | None = None
    outline_text: str | None = None
    policy_active: Literal[False] = False


def load_reference_material(root: Path, registry_path: Path | None) -> ReferenceMaterial | None:
    """Load/pin a server-selected reference before opening any database context."""
    if registry_path is None:
        return None
    path = registry_path if registry_path.is_absolute() else root / registry_path
    registry = json.loads(path.read_text(encoding="utf-8-sig"))
    text = (root / registry["document_path"]).read_text(encoding="utf-8-sig")
    outline_path = registry.get("outline_path")
    outline = (root / outline_path).read_text(encoding="utf-8-sig") if outline_path else None
    return ReferenceMaterial(**registry, document_text=text, document_sha256=hashlib.sha256(text.encode()).hexdigest(), outline_text=outline, outline_sha256=hashlib.sha256(outline.encode()).hexdigest() if outline is not None else None)


class InputVersions(InternalModel):
    case_id: str
    mandate_id: str
    company_id: str
    case_version: int
    case_content_version: str
    thesis_version: int
    thesis_content_version: str
    policy: PolicyReference
    policy_content_version: str
    company_content_version: str
    evidence_manifest: tuple[EvidenceManifestEntry, ...]
    prior_evaluation_id: str | None
    prior_findings_version: str
    reference_content_version: str | None = None
    research_content_version: str | None = None


class CompanyContext(InternalModel):
    id: str
    source_key: str
    name: str
    canonical_domain: str | None
    data_mode: DataMode


class UnavailableContext(InternalModel):
    status: Literal["unavailable", "partial"] = "unavailable"
    reason: str


class AssessmentContext(InternalModel):
    snapshot_id: str
    captured_at: str
    versions: InputVersions
    case: Case
    mandate: Mandate
    company: CompanyContext
    evidence: tuple[Evidence, ...]
    prior_evaluation: Evaluation | None
    prior_findings: tuple[Dimension, ...]
    current_gaps: tuple[str, ...]
    people: UnavailableContext
    relationships: UnavailableContext
    market: UnavailableContext
    reference_material: ReferenceMaterial | None = None
    research_context: dict | None = None


class InvestigationSuggestion(InternalModel):
    """One case-scoped question only. This never creates or authorizes a task."""
    case_id: str
    decision_question: str = Field(min_length=1, max_length=2000)
    missing_claim: str = Field(min_length=1, max_length=500)
    evidence_ids: tuple[str, ...] = ()
    suggested_source: str | None = None


class AssessmentDraft(InternalModel):
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
    outreach: OutreachPackage | None = None
    investigation: InvestigationSuggestion | None = None


class AssessmentProposal(InternalModel):
    invocation_id: str
    snapshot_id: str
    input_versions: InputVersions
    result: AssessmentDraft


class EvaluatorAdapter(Protocol):
    def evaluate(self, context: AssessmentContext, invocation_id: str) -> AssessmentProposal: ...


class AssessmentCoordinator:
    """Explicit fixture auto-assessment only; agents will propose work later."""

    def __init__(self, state, adapter: EvaluatorAdapter):
        self.state, self.adapter = state, adapter

    def assess_case(self, case_id: str, *, replayed=False, task_id=None) -> Evaluation:
        context = self.state.load_assessment_context(case_id)
        invocation_id = self.state.begin_assessment(context, replayed=replayed, task_id=task_id)
        try:
            # Context is detached; no connection/transaction survives either call.
            try:
                proposal = self.adapter.evaluate(context, invocation_id)
                proposal = AssessmentProposal.model_validate_json(proposal.model_dump_json())
            except Exception:
                # Adapter exceptions and validation objects may echo provider
                # payloads or input. They never become public task/event errors.
                raise ServiceError("evaluator_unavailable", "Evaluator failed or returned an invalid shape. Observations remain saved; retry the pending assessment.", 503, True) from None
            if proposal.invocation_id != invocation_id:
                raise ServiceError("invalid_proposal", "Evaluator returned a different invocation identity", 422)
            return self.state.accept_assessment(proposal)
        except ServiceError as error:
            self.state.record_assessment_failure(invocation_id, error.code, error.message)
            raise
        except Exception:
            message = "Assessment failed operationally. Saved observations and prior accepted judgments remain; rerun the mandate or repeat the catalog replay to retry."
            self.state.record_assessment_failure(invocation_id, "evaluator_unavailable", message)
            raise ServiceError("evaluator_unavailable", message, 503, True) from None

    def complete_discovery(self, task_id, candidates):
        # Candidate batch is committed first. Per-case acceptance is independent.
        pending = self.state.persist_discovery(task_id, candidates)
        for case_id in pending:
            self.assess_case(case_id, task_id=task_id)
        self.state.complete_task(task_id)

    def replay_signal(self, case_id, signal, catalog):
        if self.state.ingest_replay(case_id, signal, catalog):
            self.assess_case(case_id, replayed=True)
        return self.state.detail(case_id)
