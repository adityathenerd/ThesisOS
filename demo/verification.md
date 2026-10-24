# Frontend and integration verification

Verified 24 October 2026, approximately 11:00–11:10 AM IST. Canonical workspace: `C:\Users\ASUS\Desktop\ThesisOS`. This records observed behavior, not live-provider readiness.

## Build and launch

- TypeScript and production Vite build pass. Dependencies installed only in the app's frontend/node_modules and existing backend/.venv. No managed bundle changed.
- Development server tested on http://127.0.0.1:5173; HTTP backend on http://127.0.0.1:8000. Both returned successful responses and served the integrated browser journey.
- Direct Vite CLI encountered esbuild metadata failure through the Desktop NTFS junction. Normalizing `process.cwd()` before importing Vite in start-dev.mjs resolves it. npm run dev uses that entry. Production preview has matching startup.
- PowerShell launch/setup/stop scripts parse. launch.ps1 reused healthy existing services, started a missing frontend in a hidden process, built/served production, and recorded ownership. stop.ps1 released that owned frontend port while preserving the separately started healthy backend. Relaunch succeeded.
- The stop timestamp check was corrected for PowerShell's ISO date deserialization. Owned process trees are handled for Windows venv redirectors. A fresh backend process through the root launcher was not exercised because a separately owned backend already occupied 8000; its manual launch and HTTP surface are verified by backend handoff. No second backend sharing that database was started for testing.

## Actual browser journey against HTTP backend

The browser used the real local API and SQLite state with fixture provider mode. It did not use the browser fallback during these checks.

1. Created an explicit placeholder mandate with target 2; reviewed saved exact text, reference status, and v1.
2. Ran sourcing and observed Northstar Robotics (fictional), Orbit Materials (fictional), and Atlas Consumer (fictional): 3 cases, 1/2 outreach-ready, shortfall.
3. Reloaded and reopened saved cases. Orbit showed needs_evidence, a missing pilot claim, unknown actual thesis match, evidence ledger, source keys, and unknown observation times.
4. Requested the backend catalog replay helper and submitted its exact synthetic pilot signal. Observed Orbit case v2, History (2), earlier needs_evidence and current outreach_ready, a labeled replay event, and progress 2/2 completed.
5. Inspected the fictional founder Arun Mehta, source reference, rationale, synthetic package, and unsent draft. Copy displayed “Draft copied for review. Nothing was sent.” Download produced a text package with per-record synthetic labels, placeholder reference, evidence, and NOT SENT heading. A copy is retained as sample-review-package.txt.
6. Search with a nonexistent company displayed a useful no-match state. Rejected filter showed Atlas. ArrowRight in the History tab selected Outreach package. Selected mandate/case persisted after reload; its default view returns to evidence.
7. Deliberately set backend base URL to unused port 8009. Observed actionable connection error with launch/CORS guidance, unknown provider state, disabled create actions, and no fixture substitution. Restored HTTP to 8000 afterward.

The separate Node HTTP verification script passed 10 checks, including exact text retention, previous evaluation immutability, catalog replay idempotency, stable case IDs/history on rerun, and 422 rejection of browser-supplied live signals. See integration-report.json. It adds a clearly named synthetic test mandate. Backend-owned tests and isolated socket results are documented in ../handoffs/backend.md.

## Explicit browser fallback and responsiveness

- Switched explicitly to Browser fixtures while the configured backend URL was unavailable. Its independent store started empty; no automatic substitution occurred.
- Created a labeled fallback mandate, sourced 3 invented cases, replayed a synthetic signal for Boreal Works, and observed preserved History (2), monitor status, remaining verification/founder gaps, and honest 1/2 shortfall. Reload retained this history. It did not claim a qualified result from unverified text.
- Restored HTTP backend transport and original mandate/case before handoff.
- Inspected desktop layout at the browser's normal viewport and mobile at 390×844. Mobile stacked the list/detail, retained all tabs and export controls, and had document scroll width 375px against a 390px viewport (no horizontal overflow). Temporary viewport override reset.
- Saved screenshots: screenshots/desktop-workspace.jpg, evaluation-history.jpg, mobile-outreach.jpg, desktop-case.jpg, and connection-error.jpg. All show synthetic fixture material. The connection-error screenshot was taken before the final copy refinement from “not configured” to unknown for an unreachable evaluator.

## Remaining boundaries

No real Crustdata request, credential validity test, genuine capture, actual fund mandate, or semantic evaluator was demonstrated. Synthetic scores/dispositions are predefined harness values independent of thesis text. Nulls stay unknown. There is no sending, meeting booking, public deployment, CRM novelty claim, or production monitoring.

Contract 0.1 has no mandate update route. Review/revise saves a separate immutable mandate; each currently starts at thesis v1. A future additive contract must support in-place version increments and criteria approval before those are claimed.

## Dashboard revision, 24 October 2026

The default landing page now shows the saved pipeline state, observed task/agent activity, company radar, and recent saved events. Cases is a separate view, and each company opens as a single full-width brief. Browser checks verified stage filtering (2 outreach-ready of 3), useful zero-count stage state, company radar navigation, hidden collection in the singular view, actual observed sourcing task activity followed by idle, and last-task restoration after reload. No extra agent telemetry is fabricated; no background monitoring is claimed. Desktop 1440px and mobile 390px inspected; mobile pipeline scroll is contained (870px scroll content inside a 296px panel), document width 375px against viewport 390px. Viewport override reset. Build passed after this revision. New screenshots: dashboard-overview.jpg, dashboard-mobile.jpg, singular-case-mobile.jpg under screenshots/.

## Real runtime readiness checkpoint

Control relayed human authorization for real tests; credential values were not accessed by frontend. Read-only local HTTP inspection is recorded in runtime-integration-status.json: 6 synthetic cases, 8 fixture assessments, zero saved semantic assessments; serving backend still reports semantic matcher not configured. A real connected backend/agent journey is not yet verified. Owner handoffs have not yet confirmed the runtime trigger, test policy/model and accepted HTTP projection.

The UI now separates saved evaluator type from referenced evidence modes and thesis/approval status. Three provenance tests pass with `node --test frontend/tests/provenance.test.mjs` from the app root. Browser history shows 2 synthetic observations in Orbit's first assessment and 3 in its current fixture assessment; neither becomes a semantic result. Production build passes. No extra paid calls or backend/config/agent changes were made by frontend.

## Reference v0.3 alignment

The human-reviewed healthtech/biosciences reference is visible under Thesis & tracks, including therapeutics as an equally core track. Full source snapshot matches the primary byte-for-byte; its 23,728 characters are downloadable, and the unchanged mandate API receives only an explicitly editable 5,824-character abridgment if the user saves a new mandate. Browser review canceled that draft, preserving all existing saved state.

Browser checked all four proof tracks, C1–C8 without weights, three separate readiness/review concepts, unresolved acceptance-gated counting, and research-only examples. T filter shows Graph Therapeutics; primary-R shows MORF-Bio and known-YC Biodock; D shows a transparent research-coverage gap. The four research notes are not added to pipeline cases or readiness counts. Actual download contains the complete final section and therapeutic proof gate. Six source/provenance tests and production build pass. README, three-minute script and fallback notes reflect current reference versus legacy fixture mechanics; no new paid request was made.
