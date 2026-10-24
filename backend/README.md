# ThesisOS backend harness

Run these PowerShell commands from `C:\Users\ASUS\Desktop\ThesisOS`:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The local virtual environment is already installed. On a fresh checkout, use an installed Python 3.12+ (or the bundled Python executable) to create it, then install the tested lock:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
```

Only the app-local virtual environment is modified. `requirements.txt` records direct dependency ranges; `requirements.lock.txt` records the exact versions verified on this Windows machine. HTTPX handles bounded provider requests and verification.

OpenAPI is at `http://127.0.0.1:8000/docs`; the contract is `contracts/v0.1.md`. Run checks with:

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
```

## Configuration and truth boundaries

Copy `config/.env.example` to ignored `config/.env` if needed. Process environment overrides that file. `CRUSTDATA_API_KEY` is server-only. The control-owned `scripts/Set-CrustdataKey.ps1` can save it through hidden input. Never put it in frontend variables. Config status exposes presence only.

| Variable | Default / behavior |
|---|---|
| `PROVIDER_MODE` | `fixture`; only `fixture` or `live` |
| `DATABASE_URL` | `sqlite:///backend/data/thesisos.db`; relative paths resolve against the app root, independent of cwd |
| `CRUSTDATA_API_KEY` | Empty; never returned by API |
| `CRUSTDATA_SEARCH_CONFIG` | Empty; explicit opt-in query JSON path required before a live run |
| `MAX_CASES_PER_RUN` | `10`; integer 1–100 |
| `CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` |

SQLite is the implemented storage adapter. A PostgreSQL URL fails clearly at startup; it is a future adapter seam, not supported connectivity. Startup additively migrates schemas 1/2 to **schema 3**, preserving public projections/history and backfilling assessment pending/gap state. Back up before deployment with SQLite backup APIs, or stop the service before copying the database (preserve sidecars while running). Old schema-1-only source requires its matching database backup for rollback; do not decrement user_version or delete state to recover an interrupted task.

`config/fixtures.json` is an entirely invented development cast, including companies, evidence, people, scores, dispositions and drafts. Changing the thesis does not change fixture scores. The evaluator never claims semantic analysis. A `user_supplied` reference means text was supplied, not that criteria were compiled, reviewed or approved. Mandates retain exact submitted text with version 1; editing/version increments are deferred.

Production live sourcing now requires a **backend-registered discovery-only approval** against the verified catalog. CRUSTDATA_SEARCH_CONFIG selects `{approval_id,attempt_key}`; see config/discovery-selection.example.json. Raw filters and the old headcount access-test example cannot become the health/bio funnel. Qualification-policy approval is separate. No automatic retries, pagination, people or enrichment calls. A successful repeated intent reuses its saved observation; failed/interrupted attempts retain conservative allowance and unknown actual billed usage. A fixture run cannot pollute a mandate containing genuine research.

**Actual first scout is saved and served:** Nurture Bridge Marketing, LLC, case `case_201e1de12eea4da49abc6f8de3317e5a`. One faithful ranked H-track search (limit1) and one genuine gpt-6.1-sol prompt0.2 matcher produced a **monitor** research recommendation, not qualification. Current services explicitly describe consulting rather than a proprietary platform; product/reusable-core proof and YC novelty remain unresolved. Exact graph has24 nodes/28 edges/6 source groups, with source-reported founder/background/project/publication links and explicit unknowns.

Read-only routes (no paid calls): `/api/v1/cases/{id}/research-graph` and `/api/v1/cases/{id}/scout-result`. Graph is the exact agent-owned schema_version0.1 with matcher_summary/research_decision and portable JSON. Case detail has additive agent_assessments and qualification_reviews. `POST /api/v1/cases/{id}/qualification-review` records explicit approve/request_evidence against a current eligible immutable assessment; comparison-only/unknown/stale approval is refused. Qualified never automatically becomes outreach_ready.

Full catalog, exact schemas/IDs, dependency boundary, tests, migration/recovery, source/usage evidence and remaining limits: [docs/discovery-review-graph.md](docs/discovery-review-graph.md). Do not repeat paid first-scout scripts merely to inspect the saved result. Actual receipts and portable artifacts are in backend/work/first-scout; root frontend/control owns browser proof.

## Reproducible fixture flow

1. `POST /api/v1/mandates` with `{"title":"Development scenario","thesis_text":"PLACEHOLDER: illustrative example, awaiting actual reference.","target_count":2,"reference_status":"placeholder"}`.
2. `POST /api/v1/mandates/{id}/run`; poll `GET /api/v1/tasks/{id}` until `succeeded` or `failed`.
3. Fetch the mandate's cases. Northstar is illustrative outreach ready, Orbit needs evidence, Atlas is a predefined rejection. The mandate reports shortfall: 1/2.
4. `GET /api/v1/fixtures/signals` returns a synthetic replay payload. Match `canonical_domain` to `orbit-materials.example`, then submit the returned `signal` unchanged to that case's signals endpoint.
5. Orbit has a second immutable evaluation, a replay event and synthetic outreach draft. The mandate reports completed: 2/2. This illustrates state/history mechanics; it is not a real sourcing outcome.
6. Repeat the run or replay, or restart the backend: case IDs and previous history remain intact. An exact catalog replay is idempotent per case. Arbitrary synthetic text creates labeled unverified context and a new fixture evaluation without promoting the case. Captured text without a registered capture and every public live signal are rejected.

## Component boundaries and limitations

- `app/models.py`: typed v0.1 wire shapes, enums and validation.
- `app/main.py`: HTTP transport, safe error responses and CORS.
- `app/settings.py`: server environment and safe status configuration.
- `app/providers.py`: bounded discovery protocol, explicit fixture provider and documented Crustdata search adapter with explicit query opt-in.
- `app/evaluators.py`: typed evaluator protocol and catalog replay evaluator. Genuine semantic evaluation is later work.
- `app/assessments.py`: detached context/proposal models, evaluator adapter protocol and explicit legacy fixture coordinator.
- `app/state.py`: short snapshot reads, conditional version/evidence-checked acceptance, unique identity, immutable history, durable pending assessments, mandate progress and tasks. It never invokes an evaluator.
- `app/discovery.py`: verified compilation, scoped review, atomic reservations/dedupe and coverage limits.
- `app/agent_bridge.py`: pure DTO binding, agent-owned JSON subprocess and explicit human review.
- `app/research_ingest.py` / `research_graph.py`: accepted research packet and agent-owned pure graph projection/export.
- `app/runner.py`: one in-process worker. At most 16 active tasks, one per mandate, bounded candidates per task.

Run **one backend process with one worker for each database**. Do not use Uvicorn `--workers` or multiple app instances sharing it: startup recovery treats running invocations and pending/running tasks as interrupted. Execution is not durable; interrupted work is visibly failed on restart with a retry instruction. Rerunning cannot duplicate companies/cases or reset a signaled case. Candidate batch writes are atomic and committed **before** assessment. Each assessment is accepted independently after evaluation outside all database transactions. Evaluator failure preserves saved candidates/observations and previously accepted assessments; pending cases are safely retryable. A failed replay also retains its observation; repeating the exact catalog replay retries the pending assessment without duplicating the signal. A future durable runner can implement `JobRunner` without changing the task HTTP shape.

The implemented internal snapshot/proposal/acceptance models, schema migration, failure/recovery proof and **proposed-only** next foundation slice (people/role-tenure, typed findings/gaps/intents, resource reservations and lossless reconciliation cursor) are documented in [docs/agent-foundation.md](docs/agent-foundation.md). No LangGraph execution, real semantic policy, independent semantic scheduler or reference-thesis activation is enabled by this boundary.

The local API has no authentication and must stay bound to loopback for this demo. Outreach sending, automatic semantic qualification, continuous monitoring, distributed workers and fund-wide CRM novelty are not implemented. Actual explicit-CLI research comparison is separate from the default fixture evaluator. People/Enrich access and full H/R/D/T discovery coverage remain unproven.
