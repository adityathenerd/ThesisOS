# Thesis-led discovery and tooling boundary

24 October 2026. Current user direction: the first company/people search must reflect the investment thesis; deeper tool design is required. This extends the loop upstream. The orchestrator begins before the first paid search; there is no thesis-blind search followed by an agent taking over.

Latest verified unblocker: official docs now establish natural-language ranked Company Search with search.query and hybrid/lexical/semantic mode, optional filters, no sorts and ranked limit1–100. agents/search.py adds compile_ranked_company_search with explicit scoped discovery approval and retained branch/criterion/reference lineage; it permits a nonempty ranked query without predicates while retaining the old filter-only empty-query guard. This removes the need to invent industry/keyword filter mappings for the first H-track scout. Scoped discovery is not qualification approval. Backend owns the actual bounded request and response parsing (ranked total_count may be null). Exact entrypoint/shape is in handoffs/agents-design.md. Earlier filter-only limitations below are historical context for this additive change.

Official references checked read-only on24 October: https://docs.crustdata.com/company-docs/search/introduction and https://docs.crustdata.com/company-docs/search/reference. No provider/model calls were needed for this compiler update.

## Current actual query, not investment policy

Read config/crustdata-search.example.json and backend/app/providers.py. The sample uses headcount.growth_percent.6m > 15, headcount.total > 200 and < 2000, limit 1, with company name/domain/headcount projection. It is explicitly an access-test example, not thesis-derived. Applying this as the primary health/bio funnel would introduce unsupported exclusions and may miss early therapeutic or research teams.

Official public examples confirm the Company Search envelope and these field spellings, and distinguish search from enrich. Public People API examples use separate person/search and person/enrich endpoints; their existence does not prove this account's access or the required company-link filter. References checked 24 October: https://crustdata.com/company-data-api and https://crustdata.com/people-api. No paid provider call was made for this design.

## Upstream agent loop

1. **Reference/mandate interpretation:** exact reviewed reference → criteria, explicit boundaries, stage focus, ambiguities, known-company universe and resource envelope. Human-reviewed direction does not activate unreviewed operational gates.
2. **Orchestrator forms search hypotheses:** problem + user/buyer + artifact/milestone, with criterion references and track coverage. It may propose company-first or people-first routes. These hypotheses are semantic planning outputs, not raw API JSON or proof of fit.
3. **Capability mapping:** map each hypothesis only to documented/tested provider fields/operators/value types and available account capabilities. Record exact versus proxy mappings, missing-data risks and which criteria cannot be filtered faithfully. A query needs no invented 'founder_quality', 'product_proof', 'YC_fit' or 'clinical_validity' field.
4. **Bounded compilation/execution:** reviewed thesis-linked branches compile into allowed provider requests with limits/selected fields. Backend validates/reserves/deduplicates/executes. Existing reviewed mappings can be reused without asking the human to approve every routine query. Material policy changes or new lossy proxies require approval of their meaning, not a silent query tweak.
5. **Normalize and deduplicate:** preserve identity/provenance, search-branch/policy references and retrieval time; compare known-company universe. Known YC backing means reference rather than novel sourcing; absence from a list is not proof of non-backing.
6. **Joint company/team assessment and targeted investigation:** search hits are leads, not qualified companies. Retrieve only the missing company/person/source material that could resolve a consequential criterion. Rebuild the context as accepted observations arrive.
7. **Reconcile coverage and yield:** note duplicate/irrelevant results, missing tracks and exhausted branches. Adjust synonyms/source routes within the thesis, not the thesis to improve yield. Do not automatically rank software above therapeutics because its evidence is easier to access.

## Proposed first search families under reviewed reference v0.3

These are hypothesis terms from the supplied mandate, not verified API filter keys or literal executable payloads. Full exact source/version belongs in each run.

| Track | Problem terms | User/buyer terms | Evidence/milestone terms |
|---|---|---|---|
| H: healthcare operations | Referral intake, prior authorization, tissue ordering, care coordination | Clinic, hospital, provider, payer, administrator | Workflow demo, deployment, pilot, early financing |
| R: research tools | Microscopy analysis, bioinformatics, lab automation, assay tools | Scientist, laboratory, biotech, pharma | Worked example, benchmark, prototype, experimental demonstration |
| D: diagnostics/devices | Intended diagnostic use, point of care, monitoring | Actual population/clinical user and buyer, when known | Functioning prototype, validation report, study context |
| T: therapeutics | Indication, target/modality, disease model, functional assay | Developer, licensor, scientific group, partner | Experimental finding, program, spinout, preclinical milestone |

Artifact terms can prioritize discovery routes, but absence of an indexed word must not reject a company. Do not require revenue, large employee counts, fast hiring, elite education, an AI label or completed clinical trials. Stage labels prompt a current-stage check, not an invented automatic cutoff. A date helps judge freshness but cannot make a company newsworthy by decree.

The term lists are alternative vocabulary and complementary source routes, not instructions to AND every problem, buyer and artifact word into one query. Keep a broader problem/company branch alongside artifact/contributor branches so missing indexed product terms or private work do not erase plausible leads. The current pure compiler supports a conjunction of explicitly reviewed predicates only; richer OR/nested mappings require a verified provider schema, not invented JSON.

The current inspected executable Company Search example does not establish the precise industry/description/keyword field/operator mappings needed for these hypotheses. Surface that mapping gap; do not relabel the headcount example as health/bio search. Account endpoint docs/schema access and verified backend mapping are the next provider integration work.

## Company-first versus people-first

Company-first: discover problem/product candidates → normalize company → find relevant current founders/operators → inspect attributable work. People search should be scoped to a known company when feasible; do not select a generic prestige cohort and assume its companies fit.

People-first: discover contributors to relevant products/experiments → establish whether they are building an in-scope company → verify their actual role → enter the same joint assessment. A paper author, advisor or former employee is not automatically a current founder. For bio, scientific results/university spinouts can be a meaningful source route; GitHub is not a universal proxy for execution.

Both routes need scope, identity, role/tenure evidence, timestamp, source provenance and a reason for the lookup. People capability support remains explicit; Company Search HTTP 200 does not establish People Search/Enrichment access.

## Tool roles and authority

- Search tools discover candidate records using a reviewed hypothesis and bounded provider request. They do not claim investment fit.
- Identity tools resolve company/person/relationship identity. Unresolved matches stay ambiguous.
- Enrichment tools retrieve fields about an identified subject. They do not certify pedigree relevance or founder execution.
- Source/artifact retrieval obtains the particular evidence needed for a criterion and records access/failure. Do not mark private material inspected without authorized access, or a company release equivalent to an inspected demo/experiment.
- The matcher interprets evidence and proposes next questions; the orchestrator selects work. Backend adapters enforce capabilities, schemas, scopes, dedupe, limits and accounting.

## Implemented first slice and honest limits

agents/models.py now separates DiscoveryHypothesis from reviewed DiscoveryBranch and executable Intent. In discovery_planning mode the orchestrator can propose criterion-linked hypotheses before any search, including when operational gate normalization is unapproved. It cannot execute them.

agents/search.py is a pure Company Search compiler for reviewed criterion→field/operator/value mappings against a supplied catalog. It rejects unknown fields/operators/types, missing criterion links, unapproved mappings, unapproved proxy exclusions, unsafe limits and empty all-company requests. It does not discover/document provider fields, execute requests or prove mapping faithfulness. The backend/integration owner supplies the verified catalog and accepts the compiled request.

In normal reconciliation, discover intents must select a supplied reviewed thesis-linked branch and matching discovery capability within allowance. The model cannot generate arbitrary provider JSON. Source/capability/branch gaps are visible; they do not justify a fallback unrelated search.

Next: agree verified field catalog and reviewed mappings for the reference's H/R/D/T families, preserve a broad recall path, compare branch coverage/duplicates and carry semantic criteria forward explicitly. Relevance and recall must be evaluated from actual results before claiming discovery quality. No paid searches are required merely to document or test these guards.
