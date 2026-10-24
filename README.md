# ThesisOS

A local pre-outreach scouting workspace with persistent cases, attributable evidence, genuine research assessments, source-linked graphs and a reviewable next step.

**Current foundation:** React/TypeScript + FastAPI/SQLite. The prepared workspace contains nine enriched real company cases at version 3 with genuine prompt 0.3 assessments. Dashboard shows pipeline stages, reported work and company radar; each company opens one focused case. A separate pre-outreach review asks whether an introductory conversation is worthwhile. Conversation merit, person/contact completeness, formal partner-review readiness and human qualification remain distinct. Original assessments, questions, attempts and source limitations remain inspectable. Mandate review preserves canonical thesis v0.3 and the separate pre-outreach overlay.

The bounded worker has explicit start/status/stop controls: up to 30 minutes, 4 new cases, 20 provider requests, 50 credits, 4 model attempts and 1 concurrent operation. Caps, failure or exhaustion of the reviewed plan can stop it earlier. The panel reports actual server state, deadline, confirmed versus reserved credits, stop reason and saved case links. A saved assessment is not completed diligence. No run is active merely because controls or credentials exist. No outreach is sent or qualification accepted. Fixtures remain an explicit fallback.

After intake, pipeline cases enter a separately bounded post-intake stage: existing cases only, up to 8 provider requests, 20 credits, 4 fresh model attempts and 2 public URLs per case, using the original deadline and shared single worker. The panel and case pages distinguish queued research, directed attempts, reassessment and human handoff/monitor outcomes. Accepted material facts trigger one new assessment; no material delta retains the prior assessment and explicit human questions. Cached paid facts can be reused without another provider call. Intake completion is not the end of this stage.

## Fresh checkout on Windows

Install Node.js 20.19+/22.12+ and Python 3.12+. From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./launch.ps1 -NoBrowser
```

These flags apply only to the launched process; do not change persistent user or machine execution policy. If scripts already run normally, use `./setup.ps1` and `./launch.ps1`. Setup creates separate `backend/.venv` and `agents/.venv` environments from their own `requirements.lock.txt` files, then installs frontend dependencies. No global Python dependencies are installed. The agent interpreter is required for genuine model execution. Existing prepared environments are retained; do not reinstall just to rehearse saved results.

Open [ThesisOS](http://127.0.0.1:5173/), [API docs](http://127.0.0.1:8000/docs) and [health](http://127.0.0.1:8000/health). Launch builds and serves the production frontend, starts missing loopback services and reuses healthy ones. `-Dev` enables development mode; `-FixtureOnly` starts only the frontend. Select Browser fixtures explicitly in Connection settings.

On the prepared machine the Desktop ThesisOS folder is an NTFS junction to the shared app directory. A fresh clone uses its own root and does not automatically recreate saved local databases, receipts or secrets.

## Direct terminal alternative

From the repository root, without PowerShell scripts:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
py -3.12 -m venv agents/.venv
agents/.venv/Scripts/python.exe -m pip install -r agents/requirements.lock.txt
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

Run these in two terminals from the root:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm.cmd run preview --prefix frontend
```

Use one backend process/worker per database. Frontend port 5173 is strict; backend CORS permits localhost/127.0.0.1 on that port. Stop manually launched services in their original terminals. `stop.ps1` stops only launcher-recorded processes after PID/start-time checks. Logs are under ignored `demo/logs/`.

## Server credentials and data

Copy `config/.env.example` to ignored `config/.env` when needed. Leave secrets blank until the authorized operator supplies them:

```dotenv
PROVIDER_MODE=fixture
DATABASE_URL=sqlite:///backend/data/thesisos.db
CRUSTDATA_API_KEY=
CRUSTDATA_SEARCH_CONFIG=
```

The model key belongs in ignored `agents/.env` or the server process environment:

```dotenv
OPENAI_API_KEY=
```

Never put credentials in VITE_ variables, browser storage, command-line literals or Git. Restart the backend after configuration changes only when no paid operation is in flight. Key presence does not prove a source/model call. Default fixture sourcing and an explicitly authorized bounded live run are separate paths. Inspecting saved results needs no paid rerun. A fresh database has no historical live cases until imported or explicitly researched; do not reset the prepared demo database.

HTTP defaults to `http://127.0.0.1:8000`, prefix `/api/v1`. Connection settings can select another API or Browser fixtures. Failed requests display errors and never silently substitute fixture data.

## Primary demo journey

1. Open Dashboard and choose the prepared nine-company mandate. Inspect conversation-stage guidance and separate contact-preparation gaps alongside the unchanged formal research dispositions.
2. Open NeoTargets for attributable scientific work and discovery questions. Introductory merit does not prove current company capability, rights, experiments or investment qualification.
3. Open Cadex for its current-operator/status check and separately linked report-search versus leadership/history attempts. Follow a citation into the ledger, inspect direct person graph context, export the full JSON and reload the exact case.
4. Open Mandate review for full canonical v0.3, unchanged run brief, server source/hash binding and the separate pre-outreach policy. Current configuration does not establish every historical input or approve qualification.
5. For an actually started bounded run, inspect deadline/caps/current work and confirmed/reserved credits. View run cases switches explicitly to its separate mandate. Stop is cooperative: an in-flight operation may finish before stopped is reported. Do not start another paid run just to demonstrate saved results.

The earlier Nurture scout remains separate monitor history. AlloDirect, MORF-Bio and Graph Therapeutics are reference investigations; Biodock is a known-YC reference. They are not fabricated live cases. Counts and a conversation category do not establish novelty, scientific validation or outreach readiness.

## Synthetic fallback

Choose an earlier fixture mandate, the legacy placeholder or Browser fixtures explicitly. Orbit and Replay catalog milestone demonstrate synthetic mechanics, not genuine v0.3 judgments; their draft remains unsent. See [fallback instructions](demo/fallback.md), [legacy rehearsal](demo/three-minute-script.md) and [saved first-scout guide](demo/first-scout-guide.md). Mandate revisions save separate records and preserve history. Reference version and a run's thesis version are different identifiers.

## Verification

From the repository root:

```powershell
node --test frontend/tests/*.test.mjs
npm.cmd run build --prefix frontend
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -q
agents/.venv/Scripts/python.exe -m unittest discover -s agents/tests -q
```

Latest owner-reported checkpoint: 45 frontend tests and 62 owner-reported backend tests pass; use current test output for subsequent changes. Tests cover immutable bindings, stale-summary refusal, evidence links, task completion uncertainty, pre-outreach/contact separation, credit reservations and backend execution safety. These verification commands do not authorize provider/model execution.


