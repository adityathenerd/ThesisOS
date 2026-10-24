"""Reviewed discovery acceptance; independent of qualification-policy approval.

Pure compilation + backend reservation/execution, never a semantic scheduler.
Agent DTOs cross this boundary as JSON; no agent runtime dependency is required.
"""
import json
from dataclasses import asdict, replace
from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from .assessments import InternalModel, PolicyReference, ReferenceMaterial, content_version
from .errors import ServiceError
from .models import Mandate, Task
from .state import now, uid


class FilterCapability(InternalModel):
    field: str
    operators: dict[str, Literal["text", "text_list"]]
    allowed_values: list[str] | None
    premium_group: str | None


class CompanyCatalog(InternalModel):
    catalog_version: str
    api_version: str
    action: str
    endpoint: str
    checked_at: str
    documentation_status: str
    account_status: str
    account_check: str
    account_check_paid_credits: int
    base_microcredits_per_result: int
    taxonomy_filter_microcredits_per_result: int
    sources: dict[str, str]
    source_sha256: dict[str, str]
    filters: list[FilterCapability]
    projection_fields: list[str]
    required_projection_fields: list[str]
    ranked_modes: list[str]
    max_limit: int
    limitations: list[str]


class DiscoveryHypothesisInput(InternalModel):
    id: str
    criterion_ids: list[str]
    track: str
    route: Literal["company_first", "people_first"]
    hypothesis: str = Field(min_length=1)
    problem_terms: list[str]
    user_or_buyer_terms: list[str]
    artifact_or_milestone_terms: list[str]
    semantic_checks: list[str]
    recall_risks: list[str]


class MappedPredicate(InternalModel):
    criterion_id: str
    field: str
    operator: str
    value: StrictStr | list[StrictStr]
    semantic_mapping: Literal["exact_identity", "proxy"]
    explanation: str = Field(min_length=1)


class RankedMapping(InternalModel):
    criterion_ids: list[str]
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["hybrid", "lexical", "semantic"]
    explanation: str = Field(min_length=1)


class DiscoveryBranchInput(InternalModel):
    id: str
    mandate_id: str
    reference_path: str
    reference_version: str
    reference_sha256: str
    action: Literal["crustdata.company.search"]
    hypothesis: DiscoveryHypothesisInput
    ranked: RankedMapping | None = None
    predicates: list[MappedPredicate] = Field(default_factory=list)
    fields: list[str]
    limit: StrictInt = Field(ge=1, le=100)


class CompiledDiscovery(InternalModel):
    branch: DiscoveryBranchInput
    branch_digest: str
    catalog_version: str
    catalog_digest: str
    request: dict
    request_digest: str
    requires_lossy_filter_approval: bool
    quoted_microcredits_ceiling: int
    semantics: Literal["discovery_lead_only"] = "discovery_lead_only"


class DiscoveryApproval(InternalModel):
    id: str
    mandate_id: str
    branch_digest: str
    request_digest: str
    catalog_digest: str
    scope: Literal["discovery_only"]
    approved: bool
    reviewer: str = Field(min_length=1)
    lossy_filters_reviewed: bool
    max_calls: StrictInt = Field(ge=1)
    max_result_slots: StrictInt = Field(ge=1)
    max_quoted_microcredits: StrictInt = Field(ge=1)


def compile_discovery(branch: DiscoveryBranchInput, catalog: CompanyCatalog, reference: ReferenceMaterial) -> CompiledDiscovery:
    """Validates request syntax/linkage. Does not approve a branch or fund policy."""
    if (branch.reference_path, branch.reference_version, branch.reference_sha256) != (reference.document_path, reference.document_version, reference.document_sha256):
        raise ServiceError("stale_version", "Discovery branch does not reference the current pinned thesis direction", 409)
    vocabulary = {c["id"] for c in json.loads(reference.outline_text or "{}").get("shared_criteria", [])}
    criteria = set(branch.hypothesis.criterion_ids)
    if not criteria or not criteria <= vocabulary:
        raise ServiceError("invalid_discovery", "Hypothesis must link to the source comparison vocabulary", 422)
    if branch.hypothesis.route != "company_first" or branch.action != catalog.action:
        raise ServiceError("provider_not_configured", "Only documented Company Search compilation is enabled; people capability is not established", 503)
    if not branch.hypothesis.problem_terms or not branch.hypothesis.user_or_buyer_terms:
        raise ServiceError("invalid_discovery", "Discovery hypothesis needs problem and user/buyer context", 422)
    if branch.limit > catalog.max_limit or not set(branch.fields) <= set(catalog.projection_fields) or not set(catalog.required_projection_fields) <= set(branch.fields):
        raise ServiceError("invalid_discovery", "Unsupported projection or result limit", 422)
    body, conditions, lossy = {"fields": branch.fields, "limit": branch.limit}, [], False
    capabilities = {f.field: f for f in catalog.filters}
    taxonomy = False
    for predicate in branch.predicates:
        capability = capabilities.get(predicate.field)
        if predicate.criterion_id not in criteria or capability is None or predicate.operator not in capability.operators:
            raise ServiceError("invalid_discovery", "Filter needs a verified field/operator and this hypothesis's criterion link", 422)
        value, kind = predicate.value, capability.operators[predicate.operator]
        valid = isinstance(value, str) if kind == "text" else isinstance(value, list) and bool(value)
        values = [value] if isinstance(value, str) else value
        if not valid or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ServiceError("invalid_discovery", "Filter value does not match the documented nonempty type", 422)
        if capability.allowed_values is not None and not set(values) <= set(capability.allowed_values):
            raise ServiceError("invalid_discovery", "Filter value is absent from the verified value snapshot; verify autocomplete before extending it", 422)
        if capability.premium_group == "taxonomy" and predicate.semantic_mapping != "proxy":
            raise ServiceError("invalid_discovery", "Industry/category filters must declare their lossy semantic proxy meaning", 422)
        lossy |= predicate.semantic_mapping == "proxy"
        taxonomy |= capability.premium_group == "taxonomy"
        conditions.append({"field": predicate.field, "type": predicate.operator, "value": value})
    if conditions:
        body["filters"] = {"op": "and", "conditions": conditions}
    if branch.ranked:
        ranked = branch.ranked
        query = " ".join(ranked.query.casefold().split())
        if not ranked.criterion_ids or not set(ranked.criterion_ids) <= criteria or ranked.mode not in catalog.ranked_modes:
            raise ServiceError("invalid_discovery", "Ranked query requires supported mode and criterion linkage", 422)
        # A syntactic link to the reviewed hypothesis, not a semantic fit rule.
        if not any(t.strip() and t.casefold() in query for t in branch.hypothesis.problem_terms) or not any(t.strip() and t.casefold() in query for t in branch.hypothesis.user_or_buyer_terms):
            raise ServiceError("invalid_discovery", "Ranked query must retain hypothesis problem and user/buyer terms; generic all-company queries are refused", 422)
        body["search"] = {"query": ranked.query, "mode": ranked.mode}
    if not conditions and not branch.ranked:
        raise ServiceError("invalid_discovery", "All-company requests are not permitted", 422)
    quote = branch.limit * (catalog.base_microcredits_per_result + (catalog.taxonomy_filter_microcredits_per_result if taxonomy else 0))
    return CompiledDiscovery(branch=branch, branch_digest=content_version(branch), catalog_version=catalog.catalog_version, catalog_digest=content_version(catalog), request=body, request_digest=content_version(body), requires_lossy_filter_approval=lossy, quoted_microcredits_ceiling=quote)


class DiscoveryStore:
    """Backend authority for reviewed branch registration and atomic reservations."""
    def __init__(self, state):
        self.state = state

    def register(self, compiled: CompiledDiscovery, approval: DiscoveryApproval, catalog: CompanyCatalog):
        reference = self.state.reference_material
        if reference is None or compile_discovery(compiled.branch, catalog, reference) != compiled:
            raise ServiceError("stale_version", "Discovery compilation does not match current reference/catalog", 409)
        if not approval.approved or approval.scope != "discovery_only" or approval.mandate_id != compiled.branch.mandate_id:
            raise ServiceError("discovery_not_approved", "A scoped discovery review is required; qualification policy need not be approved", 409)
        if (approval.branch_digest, approval.request_digest, approval.catalog_digest) != (compiled.branch_digest, compiled.request_digest, compiled.catalog_digest):
            raise ServiceError("stale_version", "Discovery review does not match the exact branch/catalog/request", 409)
        if compiled.requires_lossy_filter_approval and not approval.lossy_filters_reviewed:
            raise ServiceError("discovery_not_approved", "Lossy hard-filter meaning/recall risk needs explicit scoped review", 409)
        if compiled.branch.limit > approval.max_result_slots or compiled.quoted_microcredits_ceiling > approval.max_quoted_microcredits:
            raise ServiceError("resource_limit", "Reviewed request exceeds its explicit result/quoted-credit allowance", 409)
        with self.state.connection(write=True) as db:
            mandate = self.state._read(db, "mandates", Mandate, approval.mandate_id)
            current = self.state.reference_material
            if current is None or current.document_sha256 != compiled.branch.reference_sha256:
                raise ServiceError("stale_version", "Pinned reference changed before discovery approval registration", 409)
            policy_row = db.execute("SELECT payload FROM mandate_policy_refs WHERE mandate_id=?", (mandate.id,)).fetchone()
            policy = PolicyReference.model_validate_json(policy_row[0]) if policy_row else PolicyReference()
            payload = json.dumps({"compiled": compiled.model_dump(mode="json"), "approval": approval.model_dump(mode="json"), "mandate_thesis_version": mandate.thesis_version, "mandate_thesis_digest": content_version({"thesis_text": mandate.thesis_text, "thesis_version": mandate.thesis_version}), "qualification_policy_reference": policy.model_dump()}, sort_keys=True)
            existing = db.execute("SELECT payload FROM discovery_approvals WHERE id=?", (approval.id,)).fetchone()
            if existing and existing[0] != payload:
                raise ServiceError("invalid_transition", "Discovery approval is immutable; issue a new reviewed receipt", 409)
            db.execute("INSERT OR IGNORE INTO discovery_approvals VALUES (?,?,?,?)", (approval.id, mandate.id, payload, now()))

    def reviewed(self, approval_id, mandate_id=None):
        with self.state.connection() as db:
            row = db.execute("SELECT payload FROM discovery_approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ServiceError("discovery_not_approved", "Reviewed discovery approval not found", 409)
        data = json.loads(row[0])
        if mandate_id and data["approval"]["mandate_id"] != mandate_id:
            raise ServiceError("discovery_not_approved", "Discovery approval belongs to another mandate", 409)
        return data

    def reserve(self, approval_id, catalog, *, task_id, attempt_key="initial"):
        data = self.reviewed(approval_id)
        compiled, approval = CompiledDiscovery.model_validate(data["compiled"]), DiscoveryApproval.model_validate(data["approval"])
        reference = self.state.reference_material
        if reference is None or compile_discovery(compiled.branch, catalog, reference) != compiled:
            raise ServiceError("stale_version", "Discovery catalog/reference/request changed; fresh scoped review required", 409)
        with self.state.connection(write=True) as db:
            task = self.state._read(db, "tasks", Task, task_id)
            mandate = self.state._read(db, "mandates", Mandate, approval.mandate_id)
            if task.status != "running" or task.mandate_id != mandate.id:
                raise ServiceError("invalid_transition", "Discovery requires a running accepted task for this mandate", 409)
            if mandate.thesis_version != data["mandate_thesis_version"] or content_version({"thesis_text": mandate.thesis_text, "thesis_version": mandate.thesis_version}) != data["mandate_thesis_digest"]:
                raise ServiceError("stale_version", "Mandate changed after discovery review", 409)
            policy_row = db.execute("SELECT payload FROM mandate_policy_refs WHERE mandate_id=?", (mandate.id,)).fetchone()
            policy = PolicyReference.model_validate_json(policy_row[0]) if policy_row else PolicyReference()
            if policy.model_dump() != data["qualification_policy_reference"]:
                raise ServiceError("stale_version", "Policy reference changed after scoped discovery review", 409)
            old = db.execute("SELECT * FROM discovery_executions WHERE approval_id=? AND attempt_key=?", (approval_id, attempt_key)).fetchone()
            if old:
                return dict(old), False
            usage = db.execute("SELECT COUNT(*),COALESCE(SUM(COALESCE(result_count,result_slots)),0),COALESCE(SUM(quoted_microcredits),0) FROM discovery_executions WHERE approval_id=?", (approval_id,)).fetchone()
            if usage[0] + 1 > approval.max_calls or usage[1] + compiled.branch.limit > approval.max_result_slots or usage[2] + compiled.quoted_microcredits_ceiling > approval.max_quoted_microcredits:
                raise ServiceError("resource_limit", "Discovery allowance exhausted; failed/uncertain attempts retain conservative reservations", 409)
            execution_id = uid("discovery")
            db.execute("INSERT INTO discovery_executions(id,approval_id,attempt_key,task_id,status,result_slots,quoted_microcredits,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (execution_id, approval_id, attempt_key, task_id, "running", compiled.branch.limit, compiled.quoted_microcredits_ceiling, now(), now()))
            return dict(db.execute("SELECT * FROM discovery_executions WHERE id=?", (execution_id,)).fetchone()), True

    def finish(self, execution_id, candidates=None, error=None):
        with self.state.connection(write=True) as db:
            if error:
                changed = db.execute("UPDATE discovery_executions SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'", (error, now(), execution_id))
            else:
                changed = db.execute("UPDATE discovery_executions SET status='succeeded',result_count=?,candidates_json=?,updated_at=? WHERE id=? AND status='running'", (len(candidates), json.dumps([asdict(c) for c in candidates]), now(), execution_id))
                if not changed.rowcount:
                    raise ServiceError("stale_version", "Discovery execution is no longer running", 409)

    def coverage(self, mandate_id):
        with self.state.connection() as db:
            rows = db.execute("SELECT a.payload,e.status,e.result_count,a.id FROM discovery_approvals a LEFT JOIN discovery_executions e ON e.approval_id=a.id WHERE a.mandate_id=?", (mandate_id,)).fetchall()
            encounters = db.execute("SELECT COUNT(*),COUNT(DISTINCT d.company_id) FROM discovery_encounters d JOIN cases c ON c.id=d.case_id WHERE c.mandate_id=?", (mandate_id,)).fetchone()
        reference = self.state.reference_material
        expected = [t["id"] for t in json.loads(reference.outline_text or "{}").get("tracks", [])] if reference else []
        empty = lambda: {"approved_branches": 0, "attempts": 0, "returned_records": 0, "unknown_return_counts": 0, "coverage": "not_executed"}
        tracks = {t: empty() for t in expected}
        seen = set()
        for row in rows:
            track = json.loads(row[0])["compiled"]["branch"]["hypothesis"]["track"]
            group = tracks.setdefault(track, empty())
            if row[3] not in seen:
                group["approved_branches"] += 1
                seen.add(row[3])
            if row[1] is not None:
                group["attempts"] += 1
                if row[2] is None:
                    group["unknown_return_counts"] += 1
                    group["returned_records"] = None
                elif group["returned_records"] is not None:
                    group["returned_records"] += row[2]
                group["coverage"] = "searched_not_exhausted" if row[1] == "succeeded" else "operational_failure"
        # Counts describe executed routes, never sector completeness or novelty.
        return {"tracks": tracks, "encounters": encounters[0], "unique_company_records": encounters[1], "novelty": "unknown; no authoritative known-company/YC universe loaded", "limitations": ["Returned records are not unique qualified leads", "Track label is a search hypothesis, not a verified company classification", "Unapproved/missing tracks remain uncovered", "Product/experimental/people/YC evidence is not established by search"]}


class DiscoverySelection(InternalModel):
    approval_id: str = Field(min_length=1)
    attempt_key: str = Field(default="initial", min_length=1, max_length=200)


class ApprovedCompanySearchProvider:
    """Production live route. Raw access-test JSON cannot bypass scoped review."""
    def __init__(self, settings, state, *, transport=None):
        from .providers import CrustdataSearchProvider
        from .settings import APP_ROOT
        self.settings, self.state = settings, state
        self.store = DiscoveryStore(state)
        self.catalog = CompanyCatalog.model_validate_json((APP_ROOT / "config/provider-catalog/company-search.json").read_text(encoding="utf-8"))
        self.raw = CrustdataSearchProvider(settings, transport)

    def configuration(self):
        from .settings import APP_ROOT
        path = self.settings.crustdata_search_config
        if path is None:
            raise ServiceError("provider_not_configured", "Select a backend-registered discovery-only approval with CRUSTDATA_SEARCH_CONFIG. The access-test example is not a thesis-led funnel.", 503)
        try:
            return DiscoverySelection.model_validate_json((path if path.is_absolute() else APP_ROOT / path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ServiceError("provider_not_configured", "Live discovery accepts an approval_id/attempt_key selector only. Raw filters and the headcount access-test example are not approved sourcing.", 503) from None

    def ensure_available(self, mandate=None):
        if not self.settings.crustdata_api_key.strip():
            raise ServiceError("provider_not_configured", "Live discovery requires server-side CRUSTDATA_API_KEY; no fallback was used.", 503)
        selection = self.configuration()
        data = self.store.reviewed(selection.approval_id, mandate.id if mandate else None)
        compiled = CompiledDiscovery.model_validate(data["compiled"])
        if self.catalog.account_status != "enabled" or self.state.reference_material is None or compile_discovery(compiled.branch, self.catalog, self.state.reference_material) != compiled:
            raise ServiceError("stale_version", "Discovery capability/reference/catalog changed; review the branch again", 409)

    def discover(self, mandate, limit, *, task_id=None):
        from .providers import Candidate
        self.ensure_available(mandate)
        selection = self.configuration()
        data = self.store.reviewed(selection.approval_id, mandate.id)
        compiled = CompiledDiscovery.model_validate(data["compiled"])
        if compiled.branch.limit > limit:
            raise ServiceError("resource_limit", "Reviewed request exceeds the runner case limit; do not silently rewrite an approved query", 409)
        if task_id is None:
            raise ServiceError("invalid_transition", "Reviewed discovery requires an accepted running task", 409)
        execution, created = self.store.reserve(selection.approval_id, self.catalog, task_id=task_id, attempt_key=selection.attempt_key)
        if not created:
            if execution["status"] == "succeeded":
                return [Candidate(**c) for c in json.loads(execution["candidates_json"])]
            raise ServiceError("provider_unavailable", "This discovery intent is running or previously failed/interrupted. No automatic retry was made; inspect its saved execution and allowance.", 503)
        try:
            candidates = self.raw.execute_request(compiled.request)
            normalized = []
            for candidate in candidates:
                refs = {"execution_id": execution["id"], "approval_id": selection.approval_id, "branch_id": compiled.branch.id, "hypothesis_id": compiled.branch.hypothesis.id, "track_hypothesis": compiled.branch.hypothesis.track, "reference_path": compiled.branch.reference_path, "reference_version": compiled.branch.reference_version, "reference_sha256": compiled.branch.reference_sha256, "catalog_version": compiled.catalog_version, "request_digest": compiled.request_digest, "qualification_policy_active": False, "semantic_checks": compiled.branch.hypothesis.semantic_checks, "novelty_status": "unknown"}
                refs["qualification_policy_reference"] = data["qualification_policy_reference"]
                evidence = [{**e, "source_key": e["source_key"] + ":branch:" + compiled.branch.id + ":" + execution["id"]} for e in candidate.evidence]
                normalized.append(replace(candidate, evidence=evidence, discovery_refs=refs))
            self.store.finish(execution["id"], candidates=normalized)
            return normalized
        except Exception as exc:
            message = exc.message if isinstance(exc, ServiceError) else 'Unexpected local discovery failure'
            self.store.finish(execution["id"], error=message)
            raise ServiceError("provider_unavailable", message + " Attempt reservation retained; no automatic retry.", 502, False) from None
