"""Read-only v0.3 reference loader and captured research comparison packet.

Reviewed thesis direction is NOT automatic approval of runtime gates. Evidence
below is explicitly the preserved research handoff's account of first-party
claims, not a new provider call, independent verification or inspected product.
"""
import hashlib
import json
from pathlib import Path

from .models import CaseContext, Criterion, Observation, Person, Policy, Relationship, Resources, VersionRef, seal_context

PROJECT = Path(__file__).resolve().parent.parent


def reviewed_reference_policy() -> Policy:
    root = PROJECT / "planning" / "investment-thesis"
    text = (root / "scouting-mandate.md").read_text(encoding="utf-8-sig")
    guide = json.loads((root / "comparison-guide.json").read_text(encoding="utf-8-sig"))
    if guide["version"] != "0.3":
        raise ValueError("Reference version changed; review the mapping before reusing it")
    criteria = [Criterion(id=c["id"], description=c["name"], lens="founder" if c["id"] == "C2" else "company",
        required_for_qualification=c["id"] == "C4", reject_on_failure=False) for c in guide["shared_criteria"]]
    return Policy(mandate_id="reviewed-health-bio-v03-comparison", thesis_text=text,
        thesis_version=3, policy_version=1, approved=False,
        fit_rule="REFERENCE COMPARISON ONLY: use C1–C8 within H/R/D/T and comparable milestone; do not invent weights, hard cutoffs, pedigree/revenue/geographic gates or make all C1–C8 mandatory. Apply v0.3 partner-review conditions: track-appropriate product/experimental evidence, articulable problem/program, attributed founder contribution and differentiated approach, material contradictions resolved or explicitly presented to the human, remaining risks visible. Agents recommend; HUMAN APPROVES QUALIFICATION. Do not reopen that settled owner decision. Only consequential specific evidence/gate interpretations and separate draft-review counting remain open; this comparison cannot accept a qualification.",
        attractiveness_gate="human_review", criteria=criteria,
        reference_source="planning/investment-thesis/scouting-mandate.md", reference_version="0.3",
        reference_direction_reviewed=True, reference_document_hash=hashlib.sha256(text.encode()).hexdigest())


def allodirect_reference_context() -> CaseContext:
    url = "https://www.allo.direct/news/allodirect-pre-seed-round-m25"
    def evidence(id, kind, subject, claim, summary):
        return Observation(id=id, subject_kind=kind, subject_id=subject, claim=claim, summary=summary,
            source_key=f"research-handoff-v0.3:S10:{id}", source_url=url, observed_at="2026-09-25T00:00:00Z",
            retrieved_at="2026-10-24T00:00:00Z", data_mode="captured", freshness="unknown")
    ctx = CaseContext(policy=reviewed_reference_policy(), ref=VersionRef(case_id="research-allodirect-v03", case_version=1,
        thesis_version=3, policy_version=1, evidence_hash=""), company_id="research-allodirect", company_name="AlloDirect",
        people=[Person(id="research-rhett-barker", name="Rhett Barker"), Person(id="research-james-casavant", name="James A. Casavant")],
        relationships=[Relationship(id="role-barker", person_id="research-rhett-barker", company_id="research-allodirect", role="CEO; founder status unknown", status="supported", evidence_ids=["ad-role-ceo"]),
                       Relationship(id="role-casavant", person_id="research-james-casavant", company_id="research-allodirect", role="CTO; founder status unknown", status="supported", evidence_ids=["ad-role-cto"])],
        evidence=[evidence("ad-product", "company", "research-allodirect", "product_and_use_claim",
            "Captured research notes from comparison-examples.md v0.3 report a company-controlled release describing tissue-ordering software for surgical facilities and claiming production orders since September 2025. The underlying working application/workflow was NOT inspected; product-page access failed. This does not establish independent functionality, repeat usage or measured benefit."),
            evidence("ad-funding", "company", "research-allodirect", "financing_announcement",
            "Captured research notes report a pre-seed announcement published 25 September 2026. YC backing is unknown. No current verified novelty, revenue floor, investment availability or verified regulatory/payment catalyst is established."),
            evidence("ad-role-ceo", "relationship", "role-barker", "company_attributed_CEO_role",
            "The research handoff records the first-party release identifying Rhett Barker as CEO. Founder status and individual product contribution remain unverified."),
            evidence("ad-role-cto", "relationship", "role-casavant", "company_attributed_CTO_role",
            "The research handoff records the first-party release identifying James A. Casavant as CTO. Founder status and individual product contribution remain unverified."),
            evidence("ad-operator", "person", "research-rhett-barker", "company_claimed_operator_background",
            "The research handoff reports the release describing Barker's orthopedic sales background. Relevant operator signal, not independently verified founder status or attributable software execution.")],
        prior_assessment=None, changed_evidence_ids=[], attempted_investigation_keys=[], capabilities=[],
        resources=Resources(remaining_calls=0, remaining_output_tokens=7000), mode="reference_comparison", test_fixture=False)
    return seal_context(ctx)
