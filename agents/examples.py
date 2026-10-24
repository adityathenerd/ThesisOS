"""Explicit synthetic software-test policy/evidence, never a real fund mandate."""
from .models import (
    Answer, Capability, CaseContext, CaseSummary, Criterion, Finding, Investigation,
    MandateContext, Observation, Person, Policy, Relationship, Resources,
    SemanticAssessment, VersionRef, seal_context,
)


def test_context() -> CaseContext:
    policy = Policy(
        mandate_id="synthetic-software-test", thesis_text="SYNTHETIC SOFTWARE TEST ONLY: care-administration software with a demonstrated prototype and relevant founder execution evidence. Not an approved investment thesis.",
        thesis_version=1, policy_version=1, approved=True,
        fit_rule="For this synthetic test only: company solves care administration, has a demonstrated prototype, and founder has relevant execution evidence. Timing is informative, not a gate.",
        attractiveness_gate="human_review",
        criteria=[Criterion(id="company", description="Care-administration software", lens="company", required_for_qualification=True, reject_on_failure=True),
                  Criterion(id="prototype", description="A demonstrated working product prototype", lens="company", required_for_qualification=True, reject_on_failure=False),
                  Criterion(id="team", description="Relevant founder execution experience in care workflows", lens="founder", required_for_qualification=True, reject_on_failure=False),
                  Criterion(id="timing", description="Current adoption catalyst", lens="timing", required_for_qualification=False, reject_on_failure=False)],
    )
    def observation(id, kind, subject, claim, summary):
        return Observation(id=id, subject_kind=kind, subject_id=subject, claim=claim, summary=summary,
                           source_key=f"synthetic-test:{id}", source_url=None, observed_at="2026-10-24T06:00:00Z",
                           retrieved_at="2026-10-24T06:00:00Z", data_mode="synthetic", freshness="current")
    context = CaseContext(
        policy=policy, ref=VersionRef(case_id="test-case", case_version=1, thesis_version=1, policy_version=1, evidence_hash=""),
        company_id="test-company", company_name="Synthetic Care Workflow Example", people=[Person(id="test-person", name="Synthetic Founder")],
        relationships=[Relationship(id="test-role", person_id="test-person", company_id="test-company", role="founder", status="supported", evidence_ids=["e-role"])],
        evidence=[observation("e-company", "company", "test-company", "product_scope", "Synthetic test observation: company builds appointment-referral coordination software for clinic administrators; no clinical efficacy is asserted."),
                  observation("e-prototype", "company", "test-company", "working_prototype", "Synthetic test observation: an inspectable demonstration completes a referral-routing workflow; this is prototype evidence, not revenue or clinical validation."),
                  observation("e-role", "relationship", "test-role", "founder_role", "Synthetic test observation: this person is the founder of this exact company. No employment, education or execution history is available yet.")],
        prior_assessment=None, changed_evidence_ids=[], attempted_investigation_keys=[],
        capabilities=[Capability(action="test_person_profile", subject_kinds=["person"], purpose="investigation")],
        resources=Resources(remaining_calls=1, remaining_output_tokens=12000), test_fixture=True,
    )
    return seal_context(context)


def scripted_assessment(resolved=False) -> SemanticAssessment:
    def answer(text, evidence, unknowns=None):
        return Answer(summary=text, evidence_ids=evidence, objections=[], unknowns=unknowns or [])
    findings = [Finding(criterion_id="company", result="meets", evidence_sufficient=True, conflicted=False,
                        evidence_ids=["e-company"], person_ids=[], rationale="Synthetic company scope matches the synthetic criterion"),
                Finding(criterion_id="prototype", result="meets", evidence_sufficient=True, conflicted=False,
                        evidence_ids=["e-prototype"], person_ids=[], rationale="Demonstrated prototype, without inferring traction"),
                Finding(criterion_id="team", result="meets" if resolved else "unknown", evidence_sufficient=resolved, conflicted=False,
                        evidence_ids=["e-role", "e-person"] if resolved else ["e-role"], person_ids=["test-person"],
                        rationale="Relevant execution supported" if resolved else "Role identity does not establish execution experience"),
                Finding(criterion_id="timing", result="unknown", evidence_sufficient=False, conflicted=False,
                        evidence_ids=[], person_ids=[], rationale="No current timing evidence; not a qualification gate")]
    request = Investigation(criterion_id="team", subject_kind="person", subject_id="test-person", action="test_person_profile",
                            question="What sourced evidence shows this founder has executed care-workflow deployments?",
                            decision_consequence="Relevant execution evidence could resolve the required team gap; unrelated or absent history leaves monitor.",
                            query="test-person relevant care-workflow deployment history", max_calls=1)
    return SemanticAssessment(findings=findings,
        why_this=answer("Synthetic care-administration scope and working prototype fit this software test", ["e-company", "e-prototype"]),
        why_them=answer("Sourced founder-role link; relevant execution " + ("now supported" if resolved else "unknown"), ["e-role", "e-person"] if resolved else ["e-role"], [] if resolved else ["Relevant execution"]),
        why_now=answer("Timing unknown; no fabricated catalyst", [], ["Adoption catalyst"]),
        team_problem_fit=answer("Prior workflow deployments are relevant to this execution challenge" if resolved else "Cannot establish team–problem fit from a founder title", ["e-person"] if resolved else [], [] if resolved else ["Relevant execution"]),
        fit="passes" if resolved else "unknown", attractiveness="unknown", actionability="incomplete",
        proposed_disposition="qualify" if resolved else "monitor", investigation=None if resolved else request,
        interpretation_question=None, next_action="Prepare reviewable handoff" if resolved else "Verify the specific founder execution claim",
        stop_or_reopen_condition="Reassess material new evidence or required gaps", change_summary="Team execution gap resolved; timing remains unknown" if resolved else "Initial synthetic assessment; required founder experience missing")


def with_founder_evidence(context, prior):
    observation = Observation(id="e-person", subject_kind="person", subject_id="test-person", claim="relevant_execution",
        summary="Synthetic test observation: the same linked founder led implementation of referral-coordination workflows at three clinics, including product deployment and administrator onboarding. This does not establish current-company revenue, customer adoption or clinical effectiveness.",
        source_key="synthetic-test:e-person", source_url=None, observed_at="2026-10-24T06:05:00Z", retrieved_at="2026-10-24T06:05:00Z",
        data_mode="synthetic", freshness="current")
    return seal_context(context.model_copy(update={"evidence": context.evidence + [observation], "prior_assessment": prior,
        "prior_ref": context.ref, "mode": "reassess", "changed_evidence_ids": ["e-person"],
        "ref": context.ref.model_copy(update={"case_version": context.ref.case_version + 1})}))


def mandate_context(context, matcher_result):
    return MandateContext(policy=context.policy, snapshot_id="synthetic-mandate-snapshot-1",
        cases=[CaseSummary(ref=context.ref, company_id=context.company_id,
            judgment={"reject": "rejected", "qualify": "monitor", "monitor": "monitor"}[matcher_result.disposition],
            assessed_evidence_hash=context.ref.evidence_hash, assessment=matcher_result.assessment,
            proposed_investigation=matcher_result.investigation, readiness_current=False, review_accepted=False,
            qualification_review_pending=matcher_result.requires_human_qualification_review)],
        active_work_keys=[], completed_work_keys=[], attempted_investigation_keys=[], capabilities=context.capabilities,
        resources=context.resources, target_count=1, review_required_to_count=False, discovery_exhausted=True)
