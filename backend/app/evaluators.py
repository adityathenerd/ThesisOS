from typing import Protocol

from .models import Dimension, Evaluation, Evidence, Mandate, OutreachPackage
from .providers import FixtureCatalog
from .assessments import AssessmentContext, AssessmentDraft, AssessmentProposal


class Evaluator(Protocol):
    def evaluate(self, *, mandate: Mandate, case_id: str, fixture_key: str, evidence: list[Evidence], evaluation_id: str, created_at: str) -> tuple[Evaluation, OutreachPackage | None]: ...


class FixtureEvaluatorAdapter:
    """Keeps fixture_key and legacy draft IDs out of the agent-facing contract."""

    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator

    def evaluate(self, context: AssessmentContext, invocation_id: str) -> AssessmentProposal:
        source_key = context.company.source_key
        fixture_key = source_key.removeprefix("fixture:") if source_key.startswith("fixture:") else source_key
        evaluation, outreach = self.evaluator.evaluate(
            mandate=context.mandate, case_id=context.case.id, fixture_key=fixture_key,
            evidence=list(context.evidence), evaluation_id=f"draft:{invocation_id}", created_at=context.captured_at,
        )
        draft = evaluation.model_dump(exclude={"id", "case_id", "thesis_version", "created_at"})
        return AssessmentProposal(invocation_id=invocation_id, snapshot_id=context.snapshot_id, input_versions=context.versions, result=AssessmentDraft(**draft, outreach=outreach))


class FixtureEvaluator:
    """Replays catalog dispositions. Does not parse or semantically match a thesis."""

    def __init__(self, catalog: FixtureCatalog):
        self.catalog = catalog

    def evaluate(self, *, mandate, case_id, fixture_key, evidence, evaluation_id, created_at):
        company = self.catalog.companies.get(fixture_key)
        if company is None:
            # The wire contract currently permits fixture|semantic only. Until
            # semantic matching is installed, use an explicit development
            # placeholder assessment, never synthetic facts or ready scores.
            real = [e for e in evidence if e.data_mode in {"live", "captured"}]
            dimensions = [Dimension(name="Actual thesis match", score=None, status="unknown", rationale="No semantic evaluator is installed. Search query results do not establish thesis fit.", evidence_ids=[])]
            if len(real) < len(evidence):
                dimensions.append(Dimension(name="Unverified synthetic replay", score=None, status="unknown", rationale="Synthetic replay is retained separately and cannot verify a real company claim.", evidence_ids=[e.id for e in evidence if e not in real]))
            return Evaluation(
                id=evaluation_id, case_id=case_id, thesis_version=mandate.thesis_version, created_at=created_at,
                dimensions=dimensions, thesis_fit=None, evidence_sufficiency=None, recommendation="needs_evidence",
                missing_claims=["Reviewed thesis criteria", "Semantic evaluation", "Relevant founder and actionability evidence"],
                next_action="Review the query and supplied thesis; install genuine evaluation before qualification or outreach.",
                reasoning_summary="NON-SEMANTIC DEVELOPMENT PLACEHOLDER (evaluator_kind=fixture): real provider observations are saved, but no thesis judgment or outreach readiness is asserted. The search query is explicit server configuration, not inferred from the mandate.",
                evidence_ids=[e.id for e in real], data_mode="synthetic", evaluator_kind="fixture",
            ), None
        scenario = company["assessment"]
        for replay in company.get("signals", []):
            if any(e.source_key == f"fixture:{fixture_key}:signal:{replay['key']}" for e in evidence):
                scenario = replay["assessment"]
        trusted = [e for e in evidence if (e.source_key or "").startswith(f"fixture:{fixture_key}:")]
        dimensions = []
        for spec in scenario["dimensions"]:
            refs = [e.id for e in trusted if e.claim_type in spec.get("evidence_claims", [])]
            dimensions.append(Dimension(**{k: v for k, v in spec.items() if k != "evidence_claims"}, evidence_ids=refs))
        if len(trusted) < len(evidence):
            dimensions.append(Dimension(name="Unverified replay", status="unknown", rationale="Additional browser-supplied replay is retained as synthetic context. It is not verified and cannot change the fixture disposition.", evidence_ids=[e.id for e in evidence if e not in trusted]))
        result = Evaluation(
            id=evaluation_id, case_id=case_id, thesis_version=mandate.thesis_version, created_at=created_at,
            dimensions=dimensions, thesis_fit=scenario.get("thesis_fit"), evidence_sufficiency=scenario.get("evidence_sufficiency"),
            recommendation=scenario["recommendation"], missing_claims=scenario["missing_claims"], next_action=scenario["next_action"],
            reasoning_summary="SYNTHETIC FIXTURE: predefined development assessment, independent of the submitted thesis. " + scenario["reasoning_summary"],
            evidence_ids=[e.id for e in trusted], data_mode="synthetic", evaluator_kind="fixture",
        )
        outreach = OutreachPackage.model_validate(scenario["outreach"]) if scenario.get("outreach") else None
        return result, outreach
