import unittest

from agents.models import DiscoveryBranch
from agents.reference import reviewed_reference_policy
from agents.search import (
    CompanySearchCatalog, FilterCapability, RankedCompanySearchRequest, RankedSearch,
    ReviewedPredicate, ScopedDiscoveryApproval, compile_company_search, compile_ranked_company_search,
)

QUERY = "Companies building software for referral intake and care coordination workflows for clinics and hospitals"
FIELDS = ["basic_info.name", "basic_info.primary_domain", "basic_info.description"]


class RankedDiscoveryCompiler(unittest.TestCase):
    def setUp(self):
        self.policy = reviewed_reference_policy()  # reviewed direction, NOT approved qualification policy
        self.branch = DiscoveryBranch(id="H-referral-first-scout", action="company_search", criterion_ids=["C1", "C4"],
            hypothesis="Find referral/care-coordination software for clinics and hospitals", semantic_checks=["Product proof", "Founder attribution"],
            recall_limitations=["This H-track branch does not cover the full H/R/D/T portfolio"], approved=True, max_calls=1)
        self.catalog = CompanySearchCatalog(action="company_search", catalog_version="official-docs-2026-10-24",
            filters=[FilterCapability(field="headcount.total", operators=[">"], value_kind="number")], projection_fields=FIELDS,
            required_projection_fields=FIELDS[:2], max_limit=3, ranked_modes=["hybrid", "lexical", "semantic"])
        self.search = RankedSearch(query=QUERY, mode="hybrid")
        self.approval = ScopedDiscoveryApproval(approval_ref="synthetic-test-scope-record-not-real-approval", approved=True,
            mandate_id=self.policy.mandate_id, thesis_version=self.policy.thesis_version, policy_version=self.policy.policy_version,
            reference_document_hash=self.policy.reference_document_hash, branch_id=self.branch.id, criterion_ids=self.branch.criterion_ids,
            query=QUERY, mode="hybrid", max_results=3)

    def compile(self, **overrides):
        values = dict(policy=self.policy, branch=self.branch, catalog=self.catalog, search=self.search, approval=self.approval, fields=FIELDS, limit=3)
        values.update(overrides)
        return compile_ranked_company_search(**values)

    def test_nonempty_ranked_search_without_predicates_has_exact_body_and_lineage(self):
        compiled = self.compile()
        self.assertEqual(compiled.provider_body(), {"search": {"query": QUERY, "mode": "hybrid"}, "fields": FIELDS, "limit": 3})
        self.assertFalse(compiled.qualification_policy_approved)
        self.assertFalse(self.policy.approved)
        self.assertEqual(compiled.approval_scope, "discovery_only")
        self.assertEqual(compiled.branch_id, self.branch.id)
        self.assertEqual(compiled.criterion_ids, ["C1", "C4"])
        self.assertEqual(compiled.reference_document_hash, self.policy.reference_document_hash)
        self.assertNotIn("approval_ref", compiled.provider_body())

    def test_blank_query_unsupported_mode_and_sorts_rejected(self):
        for query in ["", " ", "\n\t"]:
            with self.assertRaises(ValueError):
                RankedSearch(query=query)
        with self.assertRaises(ValueError):
            RankedSearch(query=QUERY, mode="random")
        with self.assertRaises(ValueError):
            RankedCompanySearchRequest(search=self.search, fields=FIELDS, limit=3, sorts=[])
        with self.assertRaises(ValueError):
            self.compile(search=self.search.model_copy(update={"query": "   "}))

    def test_ranked_limit_and_projection_are_bounded(self):
        for limit in [0, 4, 101, True]:
            with self.assertRaises(ValueError):
                self.compile(limit=limit)
        for fields in [[], ["invented.founder_quality"], ["basic_info.name"]]:
            with self.assertRaises(ValueError):
                self.compile(fields=fields)
        with self.assertRaises(ValueError):
            self.compile(approval=self.approval.model_copy(update={"max_results": 2}))
        with self.assertRaises(ValueError):
            RankedCompanySearchRequest(search=self.search, fields=FIELDS, limit=101)

    def test_scope_versions_criteria_and_exact_query_cannot_be_changed(self):
        mutations = [{"approved": False}, {"scope": "qualification"}, {"mandate_id": "other"}, {"thesis_version": 999},
            {"policy_version": 999}, {"reference_document_hash": "stale"}, {"branch_id": "other"}, {"criterion_ids": ["C8"]},
            {"criterion_ids": ["C1", "C4", "C4"]}, {"query": "An unrelated broad query"}, {"mode": "lexical"}]
        for updates in mutations:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.compile(approval=self.approval.model_copy(update=updates))

    def test_ranked_mode_and_branch_require_explicit_catalog_review(self):
        with self.assertRaises(ValueError):
            self.compile(catalog=self.catalog.model_copy(update={"ranked_modes": []}))
        with self.assertRaises(ValueError):
            self.compile(branch=self.branch.model_copy(update={"approved": False}))
        with self.assertRaises(ValueError):
            self.compile(branch=self.branch.model_copy(update={"criterion_ids": ["invented-gate"]}))

    def test_optional_filters_keep_all_original_approval_and_proxy_guards(self):
        predicate = ReviewedPredicate(criterion_id="C1", field="headcount.total", operator=">", value=2,
            mapping="proxy", mapping_explanation="Synthetic mapping solely for software tests, not the real H branch", approved=True)
        with self.assertRaises(ValueError):
            self.compile(predicates=[predicate])
        for changes in [{"approved": False}, {"criterion_id": "C8"}, {"field": "invented.field"}, {"operator": "unsupported"}, {"value": "many"}]:
            with self.assertRaises(ValueError):
                self.compile(predicates=[predicate.model_copy(update={"lossy_filter_approved": True, **changes})])
        compiled = self.compile(predicates=[predicate.model_copy(update={"lossy_filter_approved": True})])
        self.assertEqual(compiled.provider_body()["filters"], {"op": "and", "conditions": [{"field": "headcount.total", "type": ">", "value": 2}]})

    def test_discovery_approval_does_not_globally_relax_old_filter_only_guard(self):
        with self.assertRaises(ValueError):
            compile_company_search(policy=self.policy, branch=self.branch, catalog=self.catalog, predicates=[], fields=FIELDS, limit=3)
        with self.assertRaises(ValueError):
            compile_company_search(policy=self.policy.model_copy(update={"approved": True}), branch=self.branch,
                catalog=self.catalog, predicates=[], fields=FIELDS, limit=3)

    def test_unreviewed_direction_stays_blocked_even_with_scope_record(self):
        with self.assertRaises(ValueError):
            self.compile(policy=self.policy.model_copy(update={"reference_direction_reviewed": False}))


if __name__ == "__main__":
    unittest.main()
