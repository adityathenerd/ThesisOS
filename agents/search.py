"""Compile reviewed thesis/filter mappings, never arbitrary model provider JSON.

This supports the documented Company Search envelope only. It does not assume
People Search uses the same schema, or prove account access to any new endpoint.
"""
from typing import Literal

from pydantic import Field, StrictFloat, StrictInt, StrictStr, field_validator

from .models import DiscoveryBranch, Model, Policy


class FilterCapability(Model):
    field: str
    operators: list[str]
    value_kind: Literal["number", "text", "text_list"]


class CompanySearchCatalog(Model):
    action: str
    catalog_version: str
    filters: list[FilterCapability]
    projection_fields: list[str]
    required_projection_fields: list[str]
    max_limit: int = Field(ge=1, le=100)
    ranked_modes: list[Literal["hybrid", "lexical", "semantic"]] = Field(default_factory=list)


class ReviewedPredicate(Model):
    criterion_id: str
    field: str
    operator: str
    value: StrictStr | StrictInt | StrictFloat | list[StrictStr]
    mapping: Literal["exact", "proxy"]
    mapping_explanation: str = Field(min_length=1)
    approved: bool
    lossy_filter_approved: bool = False


def _validate_branch_request(policy, branch, catalog, fields, limit):
    if not branch.approved or branch.action != catalog.action:
        raise ValueError("Reviewed branch and matching provider catalog are required")
    if not branch.criterion_ids or not set(branch.criterion_ids) <= {c.id for c in policy.criteria}:
        raise ValueError("Branch must reference supplied thesis criteria")
    if type(limit) is not int or not 1 <= limit <= catalog.max_limit:
        raise ValueError("Result limit exceeds approved catalog bound")
    if not set(fields) <= set(catalog.projection_fields) or not set(catalog.required_projection_fields) <= set(fields):
        raise ValueError("Projection has unsupported or missing required fields")


def _compile_predicates(branch, catalog, predicates):
    allowed = {f.field: f for f in catalog.filters}
    conditions = []
    for predicate in predicates:
        capability = allowed.get(predicate.field)
        if not predicate.approved or predicate.criterion_id not in branch.criterion_ids:
            raise ValueError("Every filter needs a reviewed mapping to this branch's thesis criteria")
        if capability is None or predicate.operator not in capability.operators:
            raise ValueError("Unsupported provider field/operator")
        if predicate.mapping == "proxy" and not predicate.lossy_filter_approved:
            raise ValueError("Proxy-based exclusion requires explicit recall-loss approval")
        value = predicate.value
        valid = ((capability.value_kind == "number" and type(value) in {int, float}) or
                 (capability.value_kind == "text" and isinstance(value, str)) or
                 (capability.value_kind == "text_list" and isinstance(value, list) and all(isinstance(v, str) for v in value)))
        if not valid:
            raise ValueError("Filter value has the wrong documented type")
        conditions.append({"field": predicate.field, "type": predicate.operator, "value": value})
    return conditions


def compile_company_search(*, policy: Policy, branch: DiscoveryBranch, catalog: CompanySearchCatalog,
                           predicates: list[ReviewedPredicate], fields: list[str], limit: int) -> dict:
    """Existing filter-only compiler. Its original approval/empty-query guards remain."""
    if not policy.approved:
        raise ValueError("Approved policy is required by the filter-only compiler")
    _validate_branch_request(policy, branch, catalog, fields, limit)
    conditions = _compile_predicates(branch, catalog, predicates)
    if not conditions:
        raise ValueError("Do not issue an unbounded all-company search without an explicit supported search mapping")
    return {"filters": {"op": "and", "conditions": conditions}, "fields": fields, "limit": limit}


class RankedSearch(Model):
    query: StrictStr = Field(min_length=1)
    mode: Literal["hybrid", "lexical", "semantic"] = "hybrid"

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value):
        if not value.strip():
            raise ValueError("Ranked search needs a nonblank natural-language query")
        return value  # preserve the exact reviewed query, not an agent rewrite


class RankedCompanySearchRequest(Model):
    search: RankedSearch
    fields: list[StrictStr] = Field(min_length=1)
    limit: StrictInt = Field(ge=1, le=100)
    filters: dict | None = None
    # No sorts/cursor field: this bounded first-search compiler never emits them.


class ScopedDiscoveryApproval(Model):
    """Trusted operator/backend discovery scope, not final qualification approval."""
    approval_ref: str = Field(min_length=1)
    scope: Literal["discovery_only"] = "discovery_only"
    approved: bool
    mandate_id: str
    thesis_version: int = Field(ge=1)
    policy_version: int = Field(ge=1)
    reference_document_hash: str | None
    branch_id: str
    criterion_ids: list[str] = Field(min_length=1)
    query: StrictStr = Field(min_length=1)
    mode: Literal["hybrid", "lexical", "semantic"]
    max_results: StrictInt = Field(ge=1, le=100)


class CompiledRankedCompanySearch(Model):
    request: RankedCompanySearchRequest
    approval_ref: str
    approval_scope: Literal["discovery_only"] = "discovery_only"
    mandate_id: str
    thesis_version: int
    policy_version: int
    reference_document_hash: str | None
    branch_id: str
    criterion_ids: list[str]
    qualification_policy_approved: bool

    def provider_body(self) -> dict:
        """Only provider fields; persist the enclosing lineage separately."""
        return self.request.model_dump(mode="json", exclude_none=True)


def compile_ranked_company_search(*, policy: Policy, branch: DiscoveryBranch, catalog: CompanySearchCatalog,
                                  search: RankedSearch, approval: ScopedDiscoveryApproval,
                                  fields: list[str], limit: int,
                                  predicates: list[ReviewedPredicate] | None = None) -> CompiledRankedCompanySearch:
    """Pure documented ranked request + lineage, without requiring qualification approval.

    Read-only docs checked 24 Oct 2026: docs.crustdata.com/company-docs/search/
    introduction and reference. Execution/account access is still the backend's job.
    """
    # Revalidate even model_copy() inputs; caller cannot bypass the query enum or
    # whitespace guard with an unvalidated object. No raw request JSON is trusted.
    search = RankedSearch.model_validate(search.model_dump())
    approval = ScopedDiscoveryApproval.model_validate(approval.model_dump())
    if not (policy.approved or policy.reference_direction_reviewed):
        raise ValueError("Reviewed thesis direction or an approved policy is required for discovery")
    _validate_branch_request(policy, branch, catalog, fields, limit)
    if not approval.approved or approval.scope != "discovery_only":
        raise ValueError("Explicit scoped discovery approval is required")
    expected = (policy.mandate_id, policy.thesis_version, policy.policy_version, policy.reference_document_hash, branch.id)
    actual = (approval.mandate_id, approval.thesis_version, approval.policy_version, approval.reference_document_hash, approval.branch_id)
    if actual != expected or len(approval.criterion_ids) != len(set(approval.criterion_ids)) or set(approval.criterion_ids) != set(branch.criterion_ids):
        raise ValueError("Discovery approval does not match mandate/reference/branch/criterion lineage")
    if search.query != approval.query or search.mode != approval.mode or limit > approval.max_results:
        raise ValueError("Ranked query/mode/result limit is outside the reviewed discovery scope")
    if search.mode not in catalog.ranked_modes:
        raise ValueError("Ranked mode is not in the supplied verified provider catalog")
    conditions = _compile_predicates(branch, catalog, predicates or [])
    request = RankedCompanySearchRequest(search=search, fields=fields, limit=limit,
        filters={"op": "and", "conditions": conditions} if conditions else None)
    return CompiledRankedCompanySearch(request=request, approval_ref=approval.approval_ref,
        mandate_id=policy.mandate_id, thesis_version=policy.thesis_version, policy_version=policy.policy_version,
        reference_document_hash=policy.reference_document_hash, branch_id=branch.id, criterion_ids=list(branch.criterion_ids),
        qualification_policy_approved=policy.approved)
