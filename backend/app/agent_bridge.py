"""Proposal-only agent bridge and explicit durable human qualification review.

Pure agent DTOs use backend Pydantic. Graph executes in agents/.venv via JSON.
No default semantic runtime activation, model transport or second scheduler.
"""
import json
import os
import subprocess
from typing import Literal

from pydantic import Field
from agents.models import CaseContext, Criterion, MatcherResult, Observation, Person, Relationship, Policy, Resources, VersionRef, SemanticAssessment, Capability, seal_context

from .assessments import AssessmentContext, InternalModel, content_version
from .errors import ServiceError
from .models import CaseStatus, QualificationReviewInput
from .settings import APP_ROOT
from .state import now, uid


def comparison_packet(context: AssessmentContext, *, output_tokens: int) -> CaseContext:
    reference = context.reference_material
    if reference is None:
        raise ServiceError("reference_unavailable", "Agent comparison needs an explicit pinned reference", 409)
    vocabulary = json.loads(reference.outline_text or "{}")
    # No inferred required/rejecting constraints: this is comparison vocabulary.
    criteria = [Criterion(id=c["id"], description=c["name"], lens="founder" if c["id"] == "C2" else "company", required_for_qualification=False, reject_on_failure=False) for c in vocabulary.get("shared_criteria", [])]
    policy = Policy(mandate_id=context.mandate.id, thesis_text=reference.document_text, thesis_version=context.mandate.thesis_version, policy_version=1, approved=False, fit_rule="Reference comparison only. Detailed operational gate normalization is not approved.", attractiveness_gate="human_review", criteria=criteria, reference_source=reference.document_path, reference_version=reference.document_version, reference_direction_reviewed=True, reference_document_hash=reference.document_sha256)
    research = context.research_context or {}
    subjects = research.get("subjects", {})
    observations = [Observation(id=e.id, subject_kind=subjects.get(e.id, {}).get("kind", "company"), subject_id=subjects.get(e.id, {}).get("id", context.company.id), claim=e.claim_type, summary=e.summary, source_key=e.source_key, source_url=e.source_url, observed_at=e.observed_at, retrieved_at=e.retrieved_at, data_mode=e.data_mode.value, freshness="unknown") for e in context.evidence]
    follow=research.get('follow_up',{})
    if follow:
        policy=policy.model_copy(update={'fit_rule':policy.fit_rule+' Existing-case follow-through: recorded source attempts and accepted new facts are supplied. Compare their material effect with the prior assessment. Do not repeat an unchanged question as unexplained pursuit: unresolved owner/private-access/scientific questions need a precise human research point and decision consequence. Source-reported profile history or social interaction is not product proof, friendship, endorsement, grit or investment qualification.'})
    return seal_context(CaseContext(policy=policy, ref=VersionRef(case_id=context.case.id, case_version=context.case.version, thesis_version=context.mandate.thesis_version, policy_version=1, evidence_hash=""), company_id=context.company.id, company_name=context.company.name, people=[Person.model_validate(p) for p in research.get("people", [])], relationships=[Relationship.model_validate(r) for r in research.get("relationships", [])], evidence=observations, prior_assessment=SemanticAssessment.model_validate(research['prior_assessment']) if research.get('prior_assessment') else None, prior_ref=VersionRef.model_validate(research['prior_ref']) if research.get('prior_ref') else None, changed_evidence_ids=research.get('changed_evidence_ids',[]), attempted_investigation_keys=follow.get('attempted_investigation_keys',[]), capabilities=[Capability.model_validate(c) for c in follow.get('capabilities',[])], resources=Resources(remaining_calls=follow.get('remaining_calls',0), remaining_output_tokens=output_tokens), mode="reference_comparison", test_fixture=context.case.data_mode == "synthetic"))


class ScriptedGraphTransport:
    """Runs the actual compiled graph, not a reimplementation of its policy."""
    def __init__(self, *, timeout_seconds=20, live_authorized=False):
        self.timeout_seconds = timeout_seconds
        self.live_authorized = live_authorized

    def invoke(self, packet: CaseContext, scripted_assessment: dict | None = None) -> MatcherResult:
        encoded = json.dumps({"context": packet.model_dump(mode="json"), "scripted_assessment": scripted_assessment, "driver": "semantic" if self.live_authorized else "scripted"}).encode()
        if len(encoded) > 250000:
            raise ServiceError("agent_input_limit", "Agent packet exceeds the bounded transport input", 422)
        executable = APP_ROOT / "agents/.venv/Scripts/python.exe"
        try:
            run = subprocess.run([str(executable), "-m", "backend.app.agent_bridge_worker"], input=encoded, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=APP_ROOT, timeout=self.timeout_seconds, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, check=False)
        except subprocess.TimeoutExpired:
            raise ServiceError("agent_unavailable", "Bounded agent subprocess timed out after dispatch; model execution and billing may have occurred. No retry or fallback was made.", 503, False) from None
        except OSError:
            raise ServiceError("agent_unavailable", "Agent subprocess could not start; no fallback was made.", 503, False) from None
        if run.returncode or len(run.stdout) > 250000:
            raise ServiceError("agent_unavailable", "Agent subprocess failed; raw output omitted", 503)
        try:
            self.last_metadata = json.loads(run.stdout).get("metadata", {})
            return MatcherResult.model_validate(json.loads(run.stdout)["result"])
        except (ValueError, KeyError):
            raise ServiceError("invalid_proposal", "Agent subprocess returned an invalid result envelope", 422) from None


class GateProof(InternalModel):
    name: Literal["product_or_experimental_proof", "problem_program", "attributed_founder_contribution", "differentiated_approach", "contradictions_reviewed"]
    status: Literal["met", "unknown", "contradicted"]
    evidence_ids: list[str]


class ReviewEligibility(InternalModel):
    scope: Literal["semantic", "synthetic_software_test"]
    track: str | None
    gates: list[GateProof]
    specialist_review: Literal["accepted", "required", "not_applicable", "unknown"]
    unresolved_required_claims: list[str]


class AgentAssessmentStore:
    def __init__(self, state):
        self.state = state

    @staticmethod
    def validate_binding(context, packet, result):
        if (packet.ref.case_id, packet.ref.case_version, packet.ref.thesis_version, packet.company_id, packet.policy.mandate_id) != (context.case.id, context.case.version, context.mandate.thesis_version, context.company.id, context.mandate.id) or result.ref != packet.ref or seal_context(packet).ref != packet.ref:
            raise ServiceError("stale_version", "Agent packet/result references do not match the supplied backend snapshot", 409)
        if packet.policy.approved and context.versions.policy.status != "approved":
            raise ServiceError("invalid_transition", "Agent packet cannot approve unavailable/draft backend qualification policy", 409)
        if packet.policy.approved and (context.versions.policy.reference != "sha256:" + content_version(packet.policy) or context.versions.policy.version != packet.policy.policy_version):
            raise ServiceError("stale_version", "Agent normalized policy is not the exact backend-reviewed definition", 409)
        if context.reference_material and (packet.policy.reference_source, packet.policy.reference_version, packet.policy.reference_document_hash) != (context.reference_material.document_path, context.reference_material.document_version, context.reference_material.document_sha256):
            raise ServiceError("stale_version", "Agent source reference differs from the pinned backend reference", 409)
        expected = {e.id: e for e in context.evidence}
        research = context.research_context or {}
        if {e.id for e in packet.evidence} != set(expected) or [p.model_dump(mode="json") for p in packet.people] != research.get("people", []) or [r.model_dump(mode="json") for r in packet.relationships] != research.get("relationships", []):
            raise ServiceError("invalid_evidence", "Bridge cannot synthesize people/relationships or replace the supplied evidence manifest", 422)
        for observation in packet.evidence:
            source = expected[observation.id]
            subject = research.get("subjects", {}).get(source.id, {"kind": "company", "id": context.company.id})
            if (observation.subject_kind, observation.subject_id, observation.claim, observation.summary, observation.source_key, observation.source_url, observation.observed_at, observation.retrieved_at, observation.data_mode) != (subject["kind"], subject["id"], source.claim_type, source.summary, source.source_key, source.source_url, source.observed_at, source.retrieved_at, source.data_mode.value):
                raise ServiceError("invalid_evidence", "Agent observation differs from the bound backend evidence", 422)
        if result.assessment:
            citations = set()
            for finding in result.assessment.findings:
                citations.update(finding.evidence_ids + finding.counterevidence_ids)
                if not set(finding.person_ids) <= {p.id for p in packet.people}:
                    raise ServiceError("invalid_evidence", "Unavailable people cannot support agent findings", 422)
            for answer in (result.assessment.why_this, result.assessment.why_them, result.assessment.why_now, result.assessment.team_problem_fit):
                citations.update(answer.evidence_ids)
            if not citations <= set(expected):
                raise ServiceError("invalid_evidence", "Rich agent result cites evidence outside the backend manifest", 422)

    @staticmethod
    def eligible(context, packet, result, eligibility):
        if eligibility is None or result.outcome != "assessment" or result.disposition != "qualify" or not result.requires_human_qualification_review or result.assessment is None or result.missing_required_claims or result.assessment.fit != "passes":
            return False
        if eligibility.scope == "synthetic_software_test":
            if context.case.data_mode != "synthetic" or result.driver_kind != "scripted" or not result.test_fixture:
                return False
        elif not (result.driver_kind == "semantic" and context.versions.policy.status == "approved" and packet.policy.approved and context.versions.policy.reference == "sha256:" + content_version(packet.policy)) or context.people.status == "unavailable" or context.relationships.status == "unavailable":
            return False
        required = {"product_or_experimental_proof", "problem_program", "attributed_founder_contribution", "differentiated_approach", "contradictions_reviewed"}
        allowed = {e.id for e in context.evidence}
        if {g.name for g in eligibility.gates} != required or any(g.status != "met" or not g.evidence_ids or not set(g.evidence_ids) <= allowed for g in eligibility.gates) or eligibility.unresolved_required_claims or not eligibility.track:
            return False
        if eligibility.track in {"D", "T"} and eligibility.specialist_review != "accepted":
            return False
        return True

    def record(self, context, invocation_id, packet, result, *, eligibility=None, provenance="compiled_graph_scripted"):
        self.validate_binding(context, packet, result)
        is_eligible = self.eligible(context, packet, result, eligibility)
        with self.state.connection(write=True) as db:
            saved = db.execute("SELECT * FROM assessment_invocations WHERE id=?", (invocation_id,)).fetchone()
            if saved is None or saved["status"] != "running" or saved["snapshot_id"] != context.snapshot_id:
                raise ServiceError("invalid_transition", "Agent result needs its running backend invocation", 409)
            trusted = AssessmentContext.model_validate_json(saved["snapshot_json"])
            self.validate_binding(trusted, packet, result)
            is_eligible = self.eligible(trusted, packet, result, eligibility)
            current = self.state._assessment_context(db, context.case.id)
            if trusted.versions != context.versions or current.versions != trusted.versions:
                raise ServiceError("stale_version", "Backend inputs changed during agent execution; no recommendation was recorded as current", 409, True)
            assessment_id = uid("assessment")
            payload = {"backend_versions": context.versions.model_dump(mode="json"), "agent_context": packet.model_dump(mode="json"), "result": result.model_dump(mode="json"), "review_eligibility": eligibility.model_dump(mode="json") if eligibility else None, "eligible": is_eligible, "provenance": provenance, "classification": "recommendation" if result.outcome == "assessment" else "noncurrent_comparison_or_diagnostic"}
            db.execute("INSERT INTO semantic_assessments VALUES (?,?,?,?,?)", (assessment_id, context.case.id, invocation_id, json.dumps(payload), now()))
            db.execute("UPDATE assessment_invocations SET status='diagnostic',updated_at=? WHERE id=?", (now(), invocation_id))
            self.state._event(db, context.case.id, "agent_recommendation_recorded", f"Agent {payload['classification']} {assessment_id}: {result.outcome}; human qualification not accepted. Source: {provenance}.", [], data_mode="synthetic" if result.driver_kind == "scripted" else ("live" if result.evidence_modes == ["live"] else "captured"))
            return assessment_id

    def review(self, case_id, request: QualificationReviewInput):
        with self.state.connection(write=True) as db:
            context = self.state._assessment_context(db, case_id)
            record = db.execute("SELECT * FROM semantic_assessments WHERE id=? AND case_id=?", (request.assessment_id, case_id)).fetchone()
            if not record:
                raise ServiceError("not_found", "Stored agent assessment not found for this case", 404)
            key = content_version({"case_id": case_id, **request.model_dump(mode="json")})
            old = db.execute("SELECT payload FROM qualification_reviews WHERE request_key=?", (key,)).fetchone()
            if old:
                prior = json.loads(old[0])
                if prior["post_versions"] != context.versions.model_dump(mode="json"):
                    raise ServiceError("stale_version", "Prior review is no longer current; refresh assessment/evidence", 409)
                return self.state._detail(db, case_id)
            data = json.loads(record["payload"])
            if request.expected_case_version != context.case.version or data["backend_versions"] != context.versions.model_dump(mode="json"):
                raise ServiceError("stale_version", "Assessment/review versions are stale; refresh before review", 409)
            if request.decision == "approve" and not data["eligible"]:
                raise ServiceError("ineligible_qualification", "Assessment is comparison-only or lacks reviewed policy/product/team/track evidence gates; human approval cannot bypass missing proof", 409)
            case = context.case
            case.status = CaseStatus.qualified if request.decision == "approve" else CaseStatus.needs_evidence
            case.version += 1
            case.updated_at = now()
            case.next_action = "Human qualification accepted; prepare a complete sourced outreach package for review." if request.decision == "approve" else "Human requested additional evidence; no qualification accepted."
            db.execute("UPDATE cases SET payload=?,outreach=NULL WHERE id=?", (case.model_dump_json(), case_id))
            if request.decision == "request_evidence":
                db.execute("UPDATE case_assessment_state SET pending=1,updated_at=? WHERE case_id=?", (now(), case_id))
            self.state._reconcile(db, context.mandate)
            post = self.state._assessment_context(db, case_id)
            review = {"id": uid("review"), "assessment_id": request.assessment_id, "decision": request.decision, "note": request.note, "reviewer_identity": None, "source": "explicit_local_application_action", "synthetic_test": data["review_eligibility"] is not None and data["review_eligibility"]["scope"] == "synthetic_software_test", "created_at": now(), "bound_versions": data["backend_versions"], "post_versions": post.versions.model_dump(mode="json")}
            db.execute("INSERT INTO qualification_reviews VALUES (?,?,?,?,?)", (review["id"], case_id, request.assessment_id, key, json.dumps(review)))
            self.state._event(db, case_id, "human_qualification_review", f"Explicit local review: {request.decision}; assessment {request.assessment_id}. No sending or outreach-ready state was accepted.", [], data_mode=case.data_mode)
            return self.state._detail(db, case_id)


def run_scripted_comparison(state, case_id, scripted_assessment, *, output_tokens=1000, transport=None):
    context = state.load_assessment_context(case_id)
    invocation = state.begin_assessment(context)
    packet = comparison_packet(context, output_tokens=output_tokens)
    try:
        result = (transport or ScriptedGraphTransport()).invoke(packet, scripted_assessment)
        return AgentAssessmentStore(state).record(context, invocation, packet, result)
    except ServiceError as error:
        state.record_assessment_failure(invocation, error.code, error.message)
        raise
