# Cached continuous-run recovery: read-only review

24 October2026. Run scout_run_109d8a6bf7e84ea2a5e555fccc23784b. Agent reviewed owner code, retained receipts and production SQLite in read-only mode. No recovery execution, POST, new worker, external source/model/provider call or owner-code change by this chat.

## Actual recovery verified

Initial failure: two paid HTTP200 searches,1.2credits, no model/new case at failure. R response contained20records; original index19/rank20, provider company62168793, had blank name/domain. The old strict parser rejected the response. Raw receipt ebc40da8502d57fb51e1.response.json was retained.

Original R receipt SHA256facbac3b15c40e716cafe040b74c4401debf4cfa4e1cf428d4774eb4b3578e31, received_at2026-10-24T10:53:33.731630Z. Original run deadline2026-10-24T11:23:21.796199Z (16:53:21IST).

Compared current stored run against before-explicit-cached-continuation.json:

- Same run ID, created_at, deadline, mandate and limits.
- Original failed status/reason preserved in the prior snapshot and explicit continuation history.
- First two paid attempt records unchanged; search0/search1 occur exactly twice in aggregate, not fetched again.
- Original R receipt bytes/hash unchanged; actual plan and reference pins remain the same.
- Recovered R discovery execution contains19valid candidates. Every observation retains original received_at10:53:33.731630Z, not recovery time.
- Normalization report explicitly records20original records,19valid and one quarantined identity with original rank/provider ID/reason. Missing identity is a quarantined record, not a negative company judgment.

At the verification snapshot the run was running with8provider attempts,4model attempts and3completed cases; the fourth model could still be in flight. These numbers are a point-in-time observation, not a claim of final completion or thirty minutes of continuous work. Backend/control own final run reporting.

## Code mechanics

PaidTransport cached path requires explicit continuation, exact original route/body, received HTTP200 and retained raw path. It returns a locally normalized response without calling inner transport or reserving another paid attempt. The actual strict record parser is reused through MockTransport to quarantine malformed records. The outer response sink restores raw received_at for final candidate observations. The worker reuses the mandate and original start/deadline; cumulative run attempts remain intact.

## General guard observations sent to backend

1. Check ORIGINAL response record count against request limit before quarantine. Otherwise an oversized response with enough invalid rows could be filtered below the limit and evade the earlier envelope guard. This did not occur in the actual20-record R response.
2. Apply the other-active-run exclusion atomically to resume_cached, matching start's single-run boundary.
3. Verify pinned plan/reference hashes before resuming; do not silently replace them on continuation. Actual current pins were checked and unchanged in this run.
4. Give each prior-failure snapshot a unique filename; the fixed filename could overwrite an earlier failure snapshot on a second manual continuation. The current first snapshot is present and preserves the original failure.

These are concrete code-path followups, not evidence that this actual recovery re-fetched, extended its deadline or reset spend. No readiness, assessment, qualification, calibration or source claims were changed by the review.
