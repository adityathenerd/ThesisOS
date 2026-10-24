# Verified provider documentation for the first scout

Read-only control lookup, 24 October 2026. No API call or credential access.

[Company Search guide](https://docs.crustdata.com/company-docs/search/introduction) documents natural-language ranked requests on the existing POST /company/search endpoint. `search.query` is nonempty text; `search.mode` accepts hybrid, lexical or semantic. Structured filters may be omitted when search is supplied. Requested name/domain/description fields are shown in the guide. Ranked results may have null total_count; that is not a failed response.

[Search reference](https://docs.crustdata.com/company-docs/search/reference) confirms at least filters OR search, ranked limit 1–100, and no sorts with ranked search. Its field/operator catalog is available without signing into the app. This is documentation evidence; account-ranked-search behavior still needs an actual bounded request.

Operator-proposed first H-track branch, grounded in reviewed v0.3 referral/care-coordination scope:

```json
{
  "search": {
    "query": "Companies building software for referral intake and care coordination workflows for clinics and hospitals",
    "mode": "hybrid"
  },
  "fields": ["basic_info.name", "basic_info.primary_domain", "basic_info.description"],
  "limit": 3
}
```

This is a small discovery hypothesis, not an investment filter or relevance guarantee. It avoids unsupported geography/headcount/revenue restrictions. Backend reviews/executes and records branch lineage; agents own compiler changes. Current filters-only compiler must add ranked-request validation rather than treat a valid nonempty ranked query as an unbounded all-company search. Scope discovery approval separately from final qualification approval; the human already reviewed the thesis direction.

The H branch is a first-case test, not coverage of the full H/R/D/T portfolio. No extra universal artifact-keyword requirement is imposed; product/founder/scientific proof is downstream evidence work.
