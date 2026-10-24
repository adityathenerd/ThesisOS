# ThesisOS

A local sourcing workspace that turns an editable mandate into persistent company cases, evidence, assessment history, and a reviewable outreach package.

**Current foundation:** working React/TypeScript frontend + FastAPI/SQLite backend, synthetic discovery and fixture evaluator. The opening Dashboard shows pipeline stages, observed task/agent activity, company radar, and recent saved events. Cases is a separate page; selecting a company opens a singular case brief. Pipeline stages drill into filtered cases. Human-reviewed reference v0.3 is available in Thesis & tracks. A verified real-data app journey, genuine captures, and semantic evaluation remain separate integration work; reference review does not activate runtime policy. The backend search adapter is implemented; default runs remain in explicit fixture mode. A configured key alone does not enable live sourcing. No outreach is sent and no meetings are booked.

## Start on Windows

The Desktop folder is an NTFS junction to the original shared app directory: the same files, not a copy. Edit and launch from the Desktop path.

```powershell
Set-Location 'C:\Users\ASUS\Desktop\ThesisOS'
.\launch.ps1
```

Open [ThesisOS](http://127.0.0.1:5173/). The launcher starts missing services bound to loopback and reuses existing healthy services. Default launch builds the frontend and serves its production preview. `-Dev` enables the development server for editing. `-NoBrowser` suppresses opening a browser. `-FixtureOnly` starts only the frontend; select browser fixtures explicitly in Connection settings.

For a fresh checkout, install Node.js 20.19+/22.12+ and Python 3.12+, then run `.\setup.ps1` once. Dependencies stay in `frontend/node_modules` and `backend/.venv`; managed runtime bundles are not modified. Existing installed dependencies are ready on this machine. Backend installs use the tested lockfile.

```powershell
.\launch.ps1 -Dev -NoBrowser
.\stop.ps1
```

`stop.ps1` stops only processes recorded by this launcher, checking their start times against PID reuse. It leaves services launched separately alone. Logs are in ignored `demo/logs/`. Occupied ports are never stopped automatically. If the current service was already running when launch was called, stop it in its original terminal.

## Manual terminals

Terminal 1, app root:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
Set-Location 'C:\Users\ASUS\Desktop\ThesisOS\frontend'
npm run dev
```

Use one backend process and one worker per SQLite database. [API docs](http://127.0.0.1:8000/docs), [health](http://127.0.0.1:8000/health). Frontend uses strict port 5173; backend CORS permits that localhost/127.0.0.1 origin. The frontend startup normalizes the Desktop junction before loading Vite so esbuild uses consistent paths.

## Saved real scout

The existing Nurture Bridge Marketing, LLC case now has a saved genuine semantic reference comparison and inspectable research graph. Open the dashboard, select the first live scout mandate, then open the company. The decision is monitor for an attributable reusable-workflow artifact, with evidence gates and YC status unresolved. It is not qualified, outreach ready or a novel-YC count. Follow [the read-only saved-case guide](demo/first-scout-guide.md); it requires no additional search/model calls. Full browser-exported graph: [JSON](demo/first-scout-export.json).

## Demo journey

1. Open Thesis & tracks for the human-reviewed v0.3 healthtech/biosciences reference, including therapeutics. New mandates start with an explicit editable abridgment; the full 23,728-character source is preserved and downloadable. Choose a run target; the default 2 is a demo choice, not a thesis allocation.
2. Keep sourced research examples separate from the runnable fixture demonstration. AlloDirect, MORF-Bio and Graph Therapeutics remain investigations with incomplete gates and unknown YC backing. Biodock is a known YC-backed reference, excluded from novel opportunities. They are not inserted as pipeline cases.
3. For the existing mechanics demonstration, use an earlier saved fixture mandate or choose Legacy synthetic harness placeholder when creating a fresh one. Run sourcing and inspect Orbit Materials' evidence gap. Its fixed assessment is not a v0.3 thesis judgment.
4. Replay a signal → **Replay catalog milestone**. The exact backend catalog input saves a second assessment and a labeled replay; earlier history is preserved. The scenario reaches 2/2.
5. Review the fictional founder, rationale, and **unsent** outreach draft; copy or download for review. Reload to verify persistence.

See [three-minute script](demo/three-minute-script.md), [explicit fallback](demo/fallback.md), and [verification](demo/verification.md). Choose the legacy harness starter for a fresh mechanics rehearsal; do not reset the database. Mandates are immutable in contract 0.1. Review & revise saves a **separate mandate**, preserving earlier cases; each currently starts at thesis v1. In-place version increments are a future API addition. Reference version v0.3 is distinct from a saved mandate's thesis version.

## Reference v0.3

Primary: planning/investment-thesis/scouting-mandate.md, routed as human-reviewed on 24 October 2026. The UI snapshots the full primary source and comparison notes verbatim under frontend/src/reference/; demo/thesis-v0.3-source.json records matching SHA-256 hashes. The 6,003-character editable starter fits the unchanged 20,000-character mandate field; the full source does not. No backend field limit or schema was changed and no old mandate/case/evaluation was overwritten.

The reference view keeps H healthcare operations, R research tools, D diagnostics/devices, and T therapeutics distinct; C1–C8 are vocabulary without weights or total ranks. Primary-track filters support within-track comparison. Product/experimental evidence before partner review, human qualification, and outreach readiness remain separate. Agents recommend; a human approves qualification after current evidence gates. That approval is required for semantic qualification and outreach-ready counting. Extra approval of a draft before counting remains a separate choice. Synthetic fixture counts do not establish human acceptance. Live/captured/synthetic provenance is distinct from scientific validation, and saved semantic research comparisons remain visible even when no qualification or operational state transition was accepted.

## Connection and provenance

HTTP transport is the default: `http://127.0.0.1:8000`, prefix `/api/v1`. Connection settings lets you choose HTTP or browser-local fixtures explicitly. Failures display an actionable connection error and never silently substitute data. Switching transport selects an independent data store. Synthetic/live/captured provenance is shown on cases, evidence, people, packages, and events. Null scores and missing observations display as unknown. Scores are assessment indices, never investment probabilities.

Optional frontend defaults: copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_TRANSPORT=http` and `VITE_API_URL=http://127.0.0.1:8000`. Saved browser connection settings take precedence. Never place provider keys in `VITE_` values or browser storage.

To save or replace a server credential:

```powershell
Set-Location 'C:\Users\ASUS\Desktop\ThesisOS'
& .\scripts\Set-CrustdataKey.ps1
```

The control-owned helper prompts with hidden input and saves to ignored `config/.env`. Restart the backend to load it. It neither switches provider mode nor proves key validity. Live search requires explicit provider-mode and reviewed-query configuration in addition to a key. It makes a provider request only after operator opt-in; it never returns synthetic success on a failed real request. See [backend notes](backend/README.md).

## Verification

```powershell
Set-Location 'C:\Users\ASUS\Desktop\ThesisOS\frontend'
npm run build
Set-Location '..'
node .\demo\verify.mjs
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

The verification script requires a running **fixture-mode backend** and adds one clearly named synthetic integration mandate. It checks exact thesis retention, discovery, replay, earlier-history immutability, replay idempotency, rerun identity/history, invalid live-signal errors, and synthetic outreach. Report: `demo/integration-report.json`. It performs no provider requests. Browser checks and their limits are recorded separately.

Frontend boundaries: `src/types.ts` mirrors contract 0.1; `src/api.ts` owns HTTP paths and transport selection; `src/http.ts` owns request deadlines and completion-unknown errors; `src/fixtures.ts` owns browser fallback storage; `src/App.tsx` owns the visible journey. Root launchers and `demo/` belong to frontend integration. Backend owns `backend/`, `config/`; control owns `contracts/` and the credential helper. Shared handoffs track current status.


Task observation continues while the backend reports pending/running; there is no 20-second polling cutoff. Synchronous assessment writes allow 150 seconds. Browser timeout/network interruption never retries a POST: completion may be unknown, so refresh saved state before submitting again. Navigation stops browser observation, not backend work. Cases have individual `#cases/{id}` routes that resolve their mandate after reload.
