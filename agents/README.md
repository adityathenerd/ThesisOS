# ThesisOS agents

Two real compiled LangGraph graphs with proposal-only outputs. They do not own database commits, provider execution, queues or outreach sending. The backend continues to own those boundaries.

Research graph: agents.research_graph.build_research_graph is a pure typed sourced projection with JSON Schema, optional matcher references and pursue/monitor next-action metadata. Export a captured example without paid calls using agents/.venv/Scripts/python.exe -m agents.research_graph_example. Exact outputs: agents/artifacts/allodirect-research-graph.json, research-graph.schema.json and allodirect-research-graph.mmd. Mapping: planning/agents/research-graph-mapping.md. The example is separate from live saved cases; backend/frontend own actual-case serving and visualization. Current full local suite: 57 passing tests. Human qualification semantics and existing runtime entrypoints are unchanged.

## Run locally (PowerShell, project root)

    agents/.venv/Scripts/python.exe -m unittest discover -s agents/tests -v
    agents/.venv/Scripts/python.exe -m agents.demo

The demo runs initial monitor → targeted investigation intent → new synthetic founder evidence → reassessment/qualification recommendation. It does not supply human approval or accepted qualified state. It uses SCRIPTED findings, no model or provider calls, and an explicitly synthetic software-test policy rather than a real fund mandate.

Fresh isolated environment:

    backend/.venv/Scripts/python.exe -m venv agents/.venv
    agents/.venv/Scripts/python.exe -m pip install -r agents/requirements.lock.txt

Dependencies are isolated from backend/.venv. Tested package versions are frozen in requirements.lock.txt.

## Key/model and explicit live check

OPENAI_API_KEY belongs in ignored agents/.env or the process environment. It must not be printed or supplied as a command-line literal. The optional Set-OpenAIKey.ps1 helper prompts with hidden input; if local script execution is disabled, use the direct PowerShell instructions supplied in the chat instead. Do not weaken execution policy to run a helper.

Default API model: gpt-6.1-sol; reasoning effort: low, per human choice. Override with OPENAI_MODEL and OPENAI_REASONING_EFFORT in agents/.env or environment. The OpenAI Responses adapter uses structured parsing, store=False, a 45-second transport timeout and zero automatic retries. No fallback model/fixture on error.

Only after real testing is authorized:

    agents/.venv/Scripts/python.exe -m agents.live_smoke --execute

This makes at most two OpenAI graph calls: an AlloDirect comparison using captured v0.3 research notes, and thesis-led H/R/D/T discovery hypothesis planning. It makes no Crustdata calls or business-state commits. Reviewed reference direction is preserved with document/version/hash; operational policy.approved remains false. Results cannot silently qualify/activate the reference JSON. Safe output includes actual model, usage, latency and typed failures in ignored agents/work/live-smoke.json.

## Integration surface

    graph = build_matcher(driver)
    result = graph.invoke({"context": case_context, "current_ref": latest_ref})["result"]
    graph = build_orchestrator(driver)
    result = graph.invoke({"context": mandate_context, "current_snapshot_id": snapshot_id})["result"]

Imports: agents.graphs; contracts: agents.models. Driver can be ScriptedDriver for explicit tests or OpenAIResponsesDriver for semantic calls. Graph objects contain no case-specific conversation history. Supply a fresh immutable snapshot each invocation. Optional current references are preflight checks only: backend MUST recheck atomically at acceptance because state can change while inference runs.

agents.projection.to_v01_evaluation creates a pure dictionary compatible with the existing Evaluation model, with null scores and preserved guarded unknowns. It refuses unapproved comparison/failure outcomes and does not commit or establish backend acceptance. Caller supplies evaluation ID/time. Full structured findings, comparison-state/counterevidence and operational version metadata must still be retained separately; the v0.1 projection is not the complete assessment.

Human qualification authority is settled by contracts/human-qualification-v0.1.md: agents recommend; human approves after v0.3 partner-review evidence conditions pass. Prompt version 0.2 encodes this. MatcherResult.disposition=qualify and requires_human_qualification_review=true are recommendation metadata only. The v0.1 projection conservatively maps that recommendation to monitor with a human-review next action, so legacy recommendation-to-status application cannot auto-qualify a case. Store the full internal proposal separately to retain the positive recommendation.

CaseSummary has optional assessment_id, qualification_approval (HumanQualificationApproval) and qualification_review_pending. Backend supplies the durable record and computes its current flag after checking stored review/assessment/case versions; agent guards check current assessment ID plus thesis/policy/evidence match. A stale, absent or mismatched record cannot authorize qualified/ready use or package work. review_accepted/review_required_to_count refer only to separately configured draft review; they cannot substitute for human qualification. Pending human review can wait without inventing market shortfall.

No model output contains an approval record or reviewer identity. Backend/frontend implement the actual human review action; this module does not store/accept reviews, alter shared HTTP schemas or certify that every C1–C8 item is mandatory. Remaining interpretation questions must concern specific material proof, attribution or contradiction gaps, not who approves qualification.

Snapshot hash covers the factual company/person/relationship/evidence manifest. Thesis/policy/case versions are separate preconditions. Backend is responsible for enforcing immutable versioned policies, building trustworthy packets, accepting transitions and accounting for resources. remaining_output_tokens bounds generated tokens only, NOT total input spend; observed input/output usage must be settled by backend's ledger. remaining_calls is for provider actions and is net of backend reservations. A proposal reserves nothing by itself.

Matcher: validate_snapshot → joint_assessment → guard_decision → END. Orchestrator: reconcile_snapshot → select_work → guard_intents → END. Accepted new evidence causes a new orchestrator/matcher invocation through backend event dispatch. No hidden worker/tool loop.

Before first search, discovery_planning can form semantic hypotheses. Normal executable discover intents require reviewed DiscoveryBranch IDs; agents.search compiles reviewed provider mappings against an explicit capability catalog. No default headcount-growth example is treated as thesis-aware discovery. See planning/agents/discovery-tooling.md.

Ranked first-scout compiler: agents.search.compile_ranked_company_search(...search=RankedSearch(...),approval=ScopedDiscoveryApproval(...)) returns CompiledRankedCompanySearch; .provider_body() contains only search/query/mode, fields, bounded limit and optional reviewed filters. It permits a reviewed nonempty ranked query without filters, with exact discovery-only scope/version/branch/query binding even while qualification policy remains unapproved. Catalog must explicitly supply ranked_modes and verified projections. Sorts are rejected; optional filters/proxy exclusions retain all original approval guards. Existing compile_company_search still rejects empty filter-only requests. Examples/schema: agents/artifacts/first-scout-ranked-request.example.json and compiled-ranked-company-search.schema.json. No network execution is part of either compiler. Current full local suite: 65 passing tests.

## Limits

Schema/reference validation cannot establish factual truth, clinical/scientific validity, source independence or prompt-injection resistance. Scripted and mocked-transport tests verify application boundaries; real model evaluations need representative examples. Current code has no paid Crustdata execution, automatic source investigation, persistent queue, backend registration or outbound sending. It does not replace approved policy normalization or specialist human review.

Full planning/ownership: planning/agents/loop-operating-spec.md and handoffs/agents-design.md. Actual prompts: agents/prompts/constitution.md, matcher.md, orchestrator.md; task modes: agents/prompts.py.

Actual smoke observations: matcher succeeded at 40.951s (7,783 input / 2,208 output tokens), initial orchestrator failed near its 45s bound with no fallback, one deliberate concise orchestrator retry succeeded at 23.570s (6,729 input / 1,208 output tokens; explicit timeout90). Transport-failure billing is unknown. No further automatic retries or provider searches were made. These are two successful model tests, not a demonstration of the complete live research loop or calibrated judgment quality.
