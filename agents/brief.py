"""Additive sourced display projection; no inference, execution or acceptance."""
from .models import CaseBrief, MatcherResult, Model, VersionRef
from pydantic import Field
from typing import Literal


class CaseBriefProjection(Model):
    schema_version: Literal["0.1"] = "0.1"
    assessment_ref: str = Field(min_length=1)
    input_ref: VersionRef
    prompt_version: str
    driver_kind: Literal["scripted", "semantic"]
    brief: CaseBrief


def to_case_brief(result: MatcherResult, *, assessment_ref: str) -> CaseBriefProjection | None:
    """Use the saved assessment id; never generate a replacement for old outputs."""
    if result.outcome not in {"assessment", "needs_approval"} or result.assessment is None or result.assessment.case_brief is None:
        return None
    return CaseBriefProjection(assessment_ref=assessment_ref, input_ref=result.ref,
                               prompt_version=result.prompt_version, driver_kind=result.driver_kind,
                               brief=result.assessment.case_brief)
