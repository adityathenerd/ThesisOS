# Agent implementation slice

24 October 2026. User now explicitly authorizes building both agents and testing their boundaries. This supersedes planning-only scope for agent-owned implementation, dependency installation and local verification. Backend/frontend/config/shared-contract ownership remains unchanged.

Completed slice: both compiled graphs, internal contracts/prompts, validated search compiler, v0.1 projection, read-only reviewed reference comparison and 35 passing local tests. Three bounded real OpenAI requests were human-authorized: matcher success, initial orchestrator failure, one deliberate orchestrator retest success on gpt-6.1-sol/low. Backend API registration, durable continuation/provider mappings and operational-policy approval remain outstanding. Exact proof/metrics: handoffs/agents-design.md.

Latest authority update: contracts/human-qualification-v0.1.md settles manual qualification. Prompt version0.2 keeps qualify recommendation-only, v0.1 projection stays monitor pending review, orchestrator consumes current backend-supplied approval metadata. 40 tests now pass. No further paid tests or shared/backend/schema edits for this update; backend owns the human review endpoint and accepted versioned records.

## Files and sequencing

Own new agents/ package: typed internal context/result models, versioned constitution/role/task prompts, Matcher and Orchestrator StateGraphs, explicit OpenAI Responses structured-output adapter, fixture/scripted model driver, tests and CLI. Keep its virtual environment and requirements isolated from backend/.venv. Key helper writes only ignored agents/.env; no credential reading/printing in tools or source.

Now: implement typed proposal-only graphs and hard validation gates; mock all external calls and use a labeled synthetic policy/case to test missing evidence, counterevidence, identity attribution, budget, stale snapshots, duplicate work and changed/unchanged reassessment.

Next: document backend integration protocol and provide a pure projection adapter if current wire shapes allow it; do not edit backend-owned modules or shared contracts. Live OpenAI transport is explicit opt-in, model ID configurable, no automatic model calls from fixtures or tests. Existing Crustdata search is the observation source through the backend boundary, not a second independently paid search path in agents.

Later: run a bounded semantic smoke once key/model and actual approved reference policy are available; integrate persistent event/runner continuation in the backend owner chat. Do not fabricate approval or call deterministic fixture findings semantic results.

## Acceptance and limitations

Actual compiled LangGraph nodes run in tests. Backend still accepts authoritative transitions. LLM returns semantic findings; deterministic guards enforce references, required claims, hard failures, allowed actions and limits. Graphs end with proposals; evidence collection and saved version checks happen outside graphs. Unknown or conflicting required claims cannot qualify; pedigree cannot override hard constraints; timing only gates when required. A model output is not investment truth merely because it passes JSON/schema validation.

No infrastructure rewrite, sending, monitoring service, invented thresholds, model fallback, production reliability claim or changed frontend contract. Unresolved fit/attractiveness/readiness policy must remain explicit rather than being silently filled by code.
