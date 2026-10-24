"""Pure v0.1 assessment projection. Does not accept or persist a transition."""
from .models import MatcherResult


def to_v01_evaluation(result: MatcherResult, *, evaluation_id: str, created_at: str) -> dict:
    if result.outcome != "assessment" or result.assessment is None or result.disposition is None:
        raise ValueError("A comparison/failed/unapproved result cannot become a v0.1 accepted evaluation")
    assessment = result.assessment
    dimensions = []
    for finding in assessment.findings:
        unresolved = not result.criterion_evidence_sufficient.get(finding.criterion_id, False)
        status = "unknown" if unresolved else ("supported" if finding.result == "meets" else "contradicted")
        extra = f" Reference comparison state: {finding.comparison_state}." if finding.comparison_state else ""
        if finding.counterevidence_ids:
            extra += " Counterevidence: " + ", ".join(finding.counterevidence_ids) + "."
        if unresolved and finding.result != "unknown":
            extra += " Application evidence gates did not establish this finding; it remains unknown."
        dimensions.append({"name": finding.criterion_id, "score": None, "status": status,
            "rationale": finding.rationale + extra, "evidence_ids": list(dict.fromkeys(finding.evidence_ids + finding.counterevidence_ids))})
    evidence_ids = list(dict.fromkeys(eid for finding in assessment.findings for eid in finding.evidence_ids + finding.counterevidence_ids))
    evidence_ids = list(dict.fromkeys(evidence_ids + [eid for answer in [assessment.why_this, assessment.why_them, assessment.why_now, assessment.team_problem_fit] for eid in answer.evidence_ids]))
    mode = "synthetic" if "synthetic" in result.evidence_modes or not result.evidence_modes else ("live" if result.evidence_modes == ["live"] else "captured")
    summary = "\n".join([f"Why this: {assessment.why_this.summary}", f"Why them: {assessment.why_them.summary}",
        f"Why now: {assessment.why_now.summary}", f"Team–problem fit: {assessment.team_problem_fit.summary}",
        f"Decision gates: {result.explanation}", f"What changed: {assessment.change_summary}"])
    if result.driver_kind == "scripted":
        summary = "SCRIPTED SOFTWARE TEST; not semantic investment judgment.\n" + summary
    if result.disposition == "qualify":
        summary = "AGENT RECOMMENDS QUALIFICATION REVIEW; human approval is required and has not been supplied by this graph.\n" + summary
    return {"id": evaluation_id, "case_id": result.ref.case_id, "thesis_version": result.ref.thesis_version,
        "created_at": created_at, "dimensions": dimensions, "thesis_fit": None, "evidence_sufficiency": None,
        # Legacy state code may directly apply recommendation. Keep this wire
        # projection conservative until backend accepts a separate human review.
        "recommendation": {"reject": "rejected", "monitor": "monitor", "qualify": "monitor"}[result.disposition],
        "missing_claims": result.missing_required_claims,
        "next_action": "Human review of this qualification recommendation; approval must be bound to the current immutable assessment before outreach preparation" if result.disposition == "qualify" else assessment.next_action,
        "reasoning_summary": summary, "evidence_ids": evidence_ids, "data_mode": mode,
        "evaluator_kind": "semantic" if result.driver_kind == "semantic" else "fixture"}
